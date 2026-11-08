import os
import signal
import subprocess
import time

import rclpy
from ament_index_python.packages import get_package_prefix
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


def main():
    rclpy.init()
    node = rclpy.create_node('course_stop_verification')
    commands = []
    states = []
    node.create_subscription(Twist, 'cmd_vel', commands.append, 10)
    node.create_subscription(String, 'controller_state', lambda msg: states.append(msg.data), 10)
    scan_pub = node.create_publisher(LaserScan, 'scan', 10)
    odom_pub = node.create_publisher(Odometry, 'odom', 10)
    executable = os.path.join(get_package_prefix('maze_control'), 'lib', 'maze_control', 'tb3_avoid')
    process = subprocess.Popen([executable], start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not any(cmd.linear.x > 0 for cmd in commands):
            scan = LaserScan()
            scan.angle_increment = 0.01745329252
            scan.range_min, scan.range_max = 0.12, 3.5
            scan.ranges = [3.5] * 360
            odom = Odometry()
            odom.pose.pose.orientation.w = 1.0
            scan_pub.publish(scan)
            odom_pub.publish(odom)
            rclpy.spin_once(node, timeout_sec=0.1)
        if not any(cmd.linear.x > 0 for cmd in commands):
            raise RuntimeError('The controller did not drive forward with valid synthetic sensor data')
        process.send_signal(signal.SIGINT)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and 'STOPPED' not in states:
            rclpy.spin_once(node, timeout_sec=0.1)
        code = process.wait(timeout=5)
        for _ in range(5):
            rclpy.spin_once(node, timeout_sec=0.05)
        if code != 0 or 'STOPPED' not in states or commands[-1].linear.x != 0 or commands[-1].angular.z != 0:
            raise RuntimeError('SIGINT did not terminate cleanly with a final zero Twist')
        print('PASS: synthetic sensor data triggered movement; SIGINT produced a final zero Twist and clean exit')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
