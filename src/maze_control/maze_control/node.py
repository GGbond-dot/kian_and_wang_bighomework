import csv
import json
import math
import signal
import time
from pathlib import Path

import rclpy
from rclpy.executors import ExternalShutdownException
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry, Path as RosPath
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from std_srvs.srv import Empty, Trigger

from .control import BasicWallFollower, Pose, Scan, WallFollower, course_regions, point_control, pose_goal_control, sectors


class Controller(Node):
    def __init__(self, default_mode='wall'):
        names = {'point': 'tb3_point2point', 'waypoints': 'tb3_waypoints', 'avoid': 'tb3_avoid', 'wall_basic': 'tb3_wall_follower', 'open_loop': 'tb3_open_loop', 'wall': 'tb3_wall_follower_optimized'}
        super().__init__(names[default_mode])
        defaults = {
            'mode': default_mode, 'max_speed': 0.2 if default_mode in ('point', 'waypoints') else 0.18,
            'target_distance': 0.4 if default_mode == 'wall_basic' else 0.38,
            'adaptive': True, 'sensor_timeout': 0.8,
            'start_delay': 0.0,
            'goal': '[1.0, 0.0]',
            'waypoints': '[[1.0,0.0],[1.0,1.0],[0.0,1.0],[0.0,0.0]]',
            'kp_distance': 0.3, 'kp_angle': 0.8, 'goal_tolerance': 0.05,
            'goal_yaw_tolerance': 0.05, 'max_angular': 1.0, 'safe_distance': 0.8,
            'forward_speed': 0.15, 'turn_speed': 0.3,
            'front_danger': 0.35, 'wall_speed': 0.15, 'wall_turn_speed': 0.6,
            'exit_x': 4.35, 'exit_y_min': 0.15, 'exit_y_max': 0.85,
            'log_file': '/tmp/micromouse_run.csv',
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        self.param = lambda name: self.get_parameter(name).value
        self.mode = self.param('mode')
        if self.mode not in names:
            raise ValueError('unsupported controller mode: ' + self.mode)
        self.goals = [json.loads(self.param('goal'))] if self.mode == 'point' else json.loads(self.param('waypoints'))
        if not self.goals or any(len(g) != 2 or not all(math.isfinite(float(v)) for v in g) for g in self.goals):
            raise ValueError('goals must contain finite [x, y] coordinates')
        self.follower = WallFollower(self.param('target_distance'), self.param('max_speed'), self.param('adaptive'))
        self.basic_follower = BasicWallFollower(self.param('target_distance'), self.param('front_danger'), self.param('wall_speed'), self.param('wall_turn_speed'))
        self.pose = None
        self.scan = None
        self.pose_time = self.scan_time = -math.inf
        self.started = None
        self.ready_since = None
        self.index = 0
        self.done = False
        self.manual_goal = None
        self.path = RosPath()
        self.path.header.frame_id = 'odom'
        self.publisher = self.create_publisher(Twist, 'cmd_vel', 10)
        self.state_pub = self.create_publisher(String, 'controller_state', 10)
        self.path_pub = self.create_publisher(RosPath, 'trajectory', 10)
        self.create_subscription(Odometry, 'odom', self.receive_odom, qos_profile_sensor_data)
        self.create_subscription(LaserScan, 'scan', self.receive_scan, qos_profile_sensor_data)
        if self.mode == 'wall':
            self.create_subscription(PoseStamped, 'goal_pose', self.receive_goal, 10)
            self.reset_client = self.create_client(Empty, 'reset_world')
            self.create_service(Trigger, 'restart_maze', self.restart_maze)
        logfile = Path(self.param('log_file')).expanduser()
        logfile.parent.mkdir(parents=True, exist_ok=True)
        self.stream = logfile.open('w', newline='')
        self.writer = csv.writer(self.stream)
        self.writer.writerow(['time_s', 'x_m', 'y_m', 'yaw_rad', 'v_m_s', 'w_rad_s', 'front_m', 'left_m', 'right_m', 'state'])
        self.timer = self.create_timer(0.1 if self.mode == 'wall_basic' else 0.05, self.tick)
        self.get_logger().info('控制模式: ' + self.mode + '，等待 /odom 与 /scan')

    def receive_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        if not all(math.isfinite(v) for v in (p.x, p.y, yaw)):
            return
        self.pose = Pose(p.x, p.y, yaw)
        self.pose_time = time.monotonic()
        stamped = PoseStamped()
        stamped.header = msg.header
        stamped.pose = msg.pose.pose
        if not self.path.poses or math.hypot(p.x - self.path.poses[-1].pose.position.x, p.y - self.path.poses[-1].pose.position.y) > 0.025:
            self.path.poses.append(stamped)
            self.path.poses = self.path.poses[-5000:]
        self.path.header.stamp = msg.header.stamp

    def receive_scan(self, msg):
        self.scan = Scan(msg.ranges, msg.angle_min, msg.angle_increment, msg.range_min, msg.range_max)
        self.scan_time = time.monotonic()

    def receive_goal(self, msg):
        p, q = msg.pose.position, msg.pose.orientation
        values = (p.x, p.y, q.x, q.y, q.z, q.w)
        if msg.header.frame_id not in ('', 'odom') or not all(math.isfinite(v) for v in values) or sum(v * v for v in (q.x, q.y, q.z, q.w)) < 1e-12:
            self.get_logger().error('RViz 目标必须是 odom 坐标系中的有限位姿')
            return
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        self.manual_goal = Pose(p.x, p.y, yaw)
        self.done = False
        self.reset_follower()
        self.get_logger().info(f'收到 RViz 目标: x={p.x:.3f}, y={p.y:.3f}, yaw={yaw:.3f}')

    def reset_follower(self):
        self.follower = WallFollower(self.param('target_distance'), self.param('max_speed'), self.param('adaptive'))

    def restart_maze(self, request, response):
        if not self.reset_client.service_is_ready():
            response.success = False
            response.message = 'Gazebo reset_world service is not ready'
            return response
        self.publish(0, 0, 'RESETTING')
        self.reset_client.call_async(Empty.Request())
        self.manual_goal = None
        self.index = 0
        self.done = False
        self.started = None
        self.ready_since = None
        self.pose = None
        self.scan = None
        self.pose_time = self.scan_time = -math.inf
        self.reset_follower()
        self.path = RosPath()
        self.path.header.frame_id = 'odom'
        self.path_pub.publish(self.path)
        response.success = True
        response.message = 'Maze reset requested; wall following will resume from the start'
        return response

    def publish(self, v, w, state):
        msg = Twist()
        msg.linear.x, msg.angular.z = float(v), float(w)
        self.publisher.publish(msg)
        self.state_pub.publish(String(data=state))

    def tick(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        receipt = time.monotonic()
        if self.pose is None or self.scan is None or max(receipt - self.pose_time, receipt - self.scan_time) > self.param('sensor_timeout'):
            self.publish(0, 0, 'WAIT_SENSORS')
            return
        distances = sectors(self.scan) if self.mode == 'wall' else course_regions(self.scan, wall_following=self.mode == 'wall_basic')
        if any(v is None for v in distances):
            self.publish(0, 0, 'INVALID_SCAN')
            return
        if self.started is None:
            if self.ready_since is None:
                self.ready_since = now
            if now - self.ready_since < self.param('start_delay'):
                self.publish(0, 0, 'PREPARE')
                return
            self.started = now
        elapsed = now - self.started
        v = w = 0.0
        state = 'DONE'
        if not self.done:
            if self.mode in ('wall', 'wall_basic'):
                if self.mode == 'wall' and self.manual_goal is not None:
                    v, w, reached, state = pose_goal_control(self.pose, self.manual_goal, self.param('max_speed'), self.param('goal_tolerance'), self.param('goal_yaw_tolerance'), self.param('kp_distance'), self.param('kp_angle'), self.param('max_angular'))
                    if reached:
                        self.manual_goal = None
                        self.reset_follower()
                elif self.pose.x >= self.param('exit_x') and self.param('exit_y_min') <= self.pose.y <= self.param('exit_y_max'):
                    self.done = True
                else:
                    if self.mode == 'wall_basic':
                        v, w = self.basic_follower.step(distances)
                        state = self.basic_follower.state
                    else:
                        v, w = self.follower.step(self.pose, self.scan, now)
                        state = self.follower.state
            elif self.mode in ('point', 'waypoints'):
                v, w, reached = point_control(self.pose, self.goals[self.index], self.param('max_speed'), self.param('goal_tolerance'), self.param('kp_distance'), self.param('kp_angle'), self.param('max_angular'))
                state = 'GOAL_' + str(self.index + 1)
                if reached:
                    self.get_logger().info('已到达目标点 ' + str(self.goals[self.index]))
                    self.index += 1
                    self.done = self.index == len(self.goals)
            elif self.mode == 'open_loop':
                if elapsed < 3.0:
                    v, state = 0.12, 'OPEN_STRAIGHT'
                elif elapsed < 3.0 + math.pi / 1.2:
                    w, state = 0.6, 'OPEN_TURN'
                else:
                    self.done = True
            elif self.mode == 'avoid':
                v, w = (0.0, -self.param('turn_speed')) if distances[0] <= self.param('safe_distance') else (self.param('forward_speed'), 0.0)
                state = 'AVOID' if w else 'FORWARD'
        if v > 0 and distances[0] < 0.20:
            v = w = 0.0
            state = 'SAFETY_STOP'
        if self.done:
            v = w = 0.0
            state = 'DONE'
        self.publish(v, w, state)
        self.path_pub.publish(self.path)
        self.writer.writerow([f'{elapsed:.3f}', self.pose.x, self.pose.y, self.pose.yaw, v, w, *distances, state])
        self.stream.flush()

    def stop_robot(self):
        self.timer.cancel()
        for _ in range(3):
            self.publish(0, 0, 'STOPPED')
            time.sleep(0.03)

    def destroy_node(self):
        self.stream.close()
        return super().destroy_node()


def main(args=None, default_mode='wall'):
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    node = Controller(default_mode)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.stop_robot()
            node.destroy_node()
            rclpy.shutdown()
        else:
            node.stream.close()
