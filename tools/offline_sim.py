import csv
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'maze_control'))
from maze_control.control import Pose, Scan, WallFollower, point_control, wrap


def read_walls():
    root = ET.parse(ROOT / 'src/maze_control/worlds/maze.world').getroot()
    walls = []
    for model in root.findall('world/model'):
        box = model.find('link/collision/geometry/box/size')
        if box is None:
            continue
        x, y = map(float, model.findtext('pose').split()[:2])
        sx, sy = map(float, box.text.split()[:2])
        walls.append((x - sx / 2, y - sy / 2, x + sx / 2, y + sy / 2))
    return walls


def clearance(pose, walls):
    return min(math.hypot(max(x0 - pose.x, 0, pose.x - x1), max(y0 - pose.y, 0, pose.y - y1)) for x0, y0, x1, y1 in walls)


def ray_distance(x, y, dx, dy, walls):
    nearest = 3.5
    for x0, y0, x1, y1 in walls:
        if abs(dx) < 1e-12:
            if not x0 <= x <= x1:
                continue
            tx0, tx1 = -math.inf, math.inf
        else:
            tx0, tx1 = sorted(((x0 - x) / dx, (x1 - x) / dx))
        if abs(dy) < 1e-12:
            if not y0 <= y <= y1:
                continue
            ty0, ty1 = -math.inf, math.inf
        else:
            ty0, ty1 = sorted(((y0 - y) / dy, (y1 - y) / dy))
        near, far = max(tx0, ty0), min(tx1, ty1)
        if far >= max(near, 0):
            nearest = min(nearest, max(near, 0))
    return nearest


def laser(pose, walls):
    return Scan([ray_distance(pose.x, pose.y, math.cos(pose.yaw + math.radians(i)), math.sin(pose.yaw + math.radians(i)), walls) for i in range(360)], 0, math.pi / 180, 0.12, 3.5)


def integrate(pose, v, w, dt):
    if abs(w) > 1e-9:
        pose.x += v / w * (math.sin(pose.yaw + w * dt) - math.sin(pose.yaw))
        pose.y += v / w * (math.cos(pose.yaw) - math.cos(pose.yaw + w * dt))
    else:
        pose.x += v * math.cos(pose.yaw) * dt
        pose.y += v * math.sin(pose.yaw) * dt
    pose.yaw = wrap(pose.yaw + w * dt)


def simulate(adaptive=True, output=None):
    walls = read_walls()
    pose = Pose(0.5, 0.5, math.pi / 2)
    follower = WallFollower(adaptive=adaptive)
    rows = []
    distance = 0.0
    minimum = math.inf
    reached = False
    for step in range(4001):
        now = step * 0.1
        scan = laser(pose, walls)
        v, w = follower.step(pose, scan, now)
        gap = clearance(pose, walls) - 0.105
        minimum = min(minimum, gap)
        rows.append((now, pose.x, pose.y, pose.yaw, v, w, gap, follower.state))
        if pose.x >= 4.35 and 0.15 <= pose.y <= 0.85:
            reached = True
            break
        if gap < 0 or follower.state == 'FAULT':
            break
        integrate(pose, v, w, 0.1)
        distance += abs(v) * 0.1
    result = {
        'model': 'ideal differential-drive kinematics, geometric laser, not Gazebo',
        'adaptive': adaptive, 'reached_exit': reached,
        'duration_s': round(now, 2), 'path_length_m': round(distance, 4),
        'minimum_body_clearance_m': round(minimum, 4),
        'final_pose': [round(pose.x, 4), round(pose.y, 4), round(pose.yaw, 4)],
        'final_state': follower.state,
    }
    if output:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        name = 'adaptive' if adaptive else 'fixed'
        with (output / (name + '.csv')).open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['time_s', 'x_m', 'y_m', 'yaw_rad', 'v_m_s', 'w_rad_s', 'body_clearance_m', 'state'])
            writer.writerows(rows)
        (output / (name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="760" viewBox="-0.4 -0.4 5.2 5.2">', '<rect x="-0.4" y="-0.4" width="5.2" height="5.2" fill="white"/>', '<g transform="translate(0 4) scale(1 -1)">']
        for x0, y0, x1, y1 in walls:
            parts.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="#475569"/>')
        points = ' '.join(f'{row[1]:.4f},{row[2]:.4f}' for row in rows[::3])
        parts.extend([f'<polyline points="{points}" fill="none" stroke="#ea580c" stroke-width="0.025"/>', '<circle cx="0.5" cy="0.5" r="0.07" fill="#16a34a"/>', '</g>', '<text x="0" y="4.55" font-size="0.11">Computed kinematic trajectory - not a Gazebo experiment</text>', '</svg>'])
        (output / (name + '.svg')).write_text('\n'.join(parts))
    return result


def point_experiment():
    pose = Pose(0, 0, 2.8)
    goals = [(1, 0), (1, 1), (0, 1)]
    for goal in goals:
        for step in range(4000):
            v, w, done = point_control(pose, goal)
            if done:
                break
            integrate(pose, v, w, 0.05)
        else:
            raise RuntimeError('waypoint did not converge')
    return math.hypot(pose.x - goals[-1][0], pose.y - goals[-1][1])


if __name__ == '__main__':
    for adaptive in (False, True):
        print(json.dumps(simulate(adaptive, ROOT / 'results'), indent=2))
    print('Final waypoint error:', point_experiment())
