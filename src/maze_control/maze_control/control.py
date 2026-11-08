import math
from statistics import median
from dataclasses import dataclass


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Pose:
    x: float
    y: float
    yaw: float


@dataclass
class Scan:
    ranges: list
    angle_min: float
    angle_increment: float
    range_min: float
    range_max: float


def sector_distance(scan, center, half_width=math.radians(15), statistic='min'):
    values = []
    clear_return = False
    for i, value in enumerate(scan.ranges):
        if abs(wrap(scan.angle_min + i * scan.angle_increment - center)) > half_width + 1e-9:
            continue
        if value == math.inf:
            clear_return = True
        elif math.isfinite(value) and scan.range_min <= value <= scan.range_max:
            values.append(value)
    if values:
        return median(values) if statistic == 'median' else min(values)
    return scan.range_max if clear_return else None


def sectors(scan):
    return tuple(sector_distance(scan, angle) for angle in (0, math.pi / 2, -math.pi / 2))


def course_regions(scan, wall_following=False):
    statistic = 'min' if wall_following else 'median'
    return (
        sector_distance(scan, 0),
        sector_distance(scan, math.radians(75), statistic=statistic),
        sector_distance(scan, math.radians(-75), statistic=statistic),
    )


def point_control(pose, goal, max_speed=0.2, tolerance=0.05, kp_distance=0.3, kp_angle=0.8, max_angular=1.0):
    dx, dy = goal[0] - pose.x, goal[1] - pose.y
    distance = math.hypot(dx, dy)
    if distance <= tolerance:
        return 0.0, 0.0, True
    error = wrap(math.atan2(dy, dx) - pose.yaw)
    angular = clamp(kp_angle * error, -max_angular, max_angular)
    linear = min(max_speed, kp_distance * distance) * max(0.0, math.cos(error))
    if abs(error) > 0.6:
        linear = 0.0
    return linear, angular, False


def pose_goal_control(pose, goal, max_speed=0.2, position_tolerance=0.05, yaw_tolerance=0.05, kp_distance=0.3, kp_angle=0.8, max_angular=1.0):
    linear, angular, reached = point_control(pose, (goal.x, goal.y), max_speed, position_tolerance, kp_distance, kp_angle, max_angular)
    if not reached:
        return linear, angular, False, 'RVIZ_GOAL'
    error = wrap(goal.yaw - pose.yaw)
    if abs(error) > yaw_tolerance:
        return 0.0, clamp(kp_angle * error, -max_angular, max_angular), False, 'RVIZ_ALIGN'
    return 0.0, 0.0, True, 'RVIZ_REACHED'


class BasicWallFollower:
    def __init__(self, target=0.4, front_danger=0.35, speed=0.15, turn_speed=0.6):
        self.target = target
        self.front_danger = front_danger
        self.speed = speed
        self.turn_speed = turn_speed
        self.state = 'FOLLOW'

    def step(self, distances):
        front, left, _ = distances
        if front is None or left is None:
            self.state = 'INVALID_SCAN'
            return 0.0, 0.0
        if front < self.front_danger:
            self.state = 'TURN_RIGHT'
            return 0.0, -self.turn_speed
        if left > self.target + 0.1:
            self.state = 'ADJUST_LEFT'
            return self.speed, 0.4
        if left < self.target - 0.1:
            self.state = 'ADJUST_RIGHT'
            return self.speed, -0.3
        self.state = 'FOLLOW'
        return self.speed, 0.0


class WallFollower:
    def __init__(self, target=0.38, max_speed=0.18, adaptive=True):
        self.target = target
        self.max_speed = max_speed
        self.adaptive = adaptive
        self.state = 'FOLLOW'
        self.anchor = None
        self.turn_goal = 0.0
        self.state_since = 0.0
        self.open_since = None
        self.corridor_heading = None

    def enter(self, state, pose, now):
        self.state = state
        self.anchor = Pose(pose.x, pose.y, pose.yaw)
        self.state_since = now
        self.open_since = None

    def turn(self, angle, pose, now):
        self.enter('TURN', pose, now)
        heading = pose.yaw if self.corridor_heading is None else self.corridor_heading
        self.turn_goal = wrap(heading + angle)

    def step(self, pose, scan, now):
        if scan is None:
            return 0.0, 0.0
        front, left, right = sectors(scan)
        if any(value is None for value in (front, left, right)):
            return 0.0, 0.0
        if self.corridor_heading is None:
            self.corridor_heading = pose.yaw
        if self.state == 'FAULT':
            return 0.0, 0.0
        if self.state in ('TURN', 'ADVANCE', 'CLEAR') and now - self.state_since > 15.0:
            self.enter('FAULT', pose, now)
            return 0.0, 0.0
        if self.state == 'TURN':
            error = wrap(self.turn_goal - pose.yaw)
            if abs(error) < 0.045:
                self.corridor_heading = self.turn_goal
                self.enter('CLEAR', pose, now)
                return 0.0, 0.0
            return 0.0, clamp(2.2 * error, -0.9, 0.9)
        if self.state in ('ADVANCE', 'CLEAR'):
            distance = math.hypot(pose.x - self.anchor.x, pose.y - self.anchor.y)
            limit = 0.22 if self.state == 'ADVANCE' else 0.32
            if distance >= limit or front < 0.27:
                if self.state == 'ADVANCE':
                    self.turn(math.pi / 2, pose, now)
                else:
                    self.enter('FOLLOW', pose, now)
                return 0.0, 0.0
            return 0.12, clamp(2.0 * wrap(self.anchor.yaw - pose.yaw), -0.5, 0.5)
        if left > 0.72:
            if self.open_since is None:
                self.open_since = now
            if now - self.open_since >= 0.15:
                self.enter('ADVANCE', pose, now)
                return 0.0, 0.0
        else:
            self.open_since = None
        if front < 0.30:
            self.turn(math.pi / 2 if left > 0.72 else (-math.pi / 2 if right > 0.40 else math.pi), pose, now)
            return 0.0, clamp(2.2 * wrap(self.turn_goal - pose.yaw), -0.9, 0.9)
        correction = clamp(1.6 * (min(left, 0.8) - self.target), -0.35, 0.35)
        angular = clamp(2.2 * wrap(self.corridor_heading + correction - pose.yaw), -0.75, 0.75)
        speed = self.max_speed
        if self.adaptive:
            speed *= clamp((front - 0.22) / 0.65, 0.25, 1.0) / (1 + 1.5 * abs(angular))
        return speed, angular
