import math
import os
import signal
import subprocess
import time

import rclpy
from ament_index_python.packages import get_package_prefix
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from std_srvs.srv import Empty, Trigger
from visualization_msgs.msg import InteractiveMarkerFeedback

from maze_control.reset_marker import make_reset_marker


def main():
    marker = make_reset_marker(0.5, 0.5)
    quaternions = [
        marker.pose.orientation,
        *(control.orientation for control in marker.controls),
        *(item.pose.orientation for control in marker.controls for item in control.markers),
    ]
    if any(abs(value.w - 1.0) > 1e-12 for value in quaternions):
        raise RuntimeError('Reset marker contains an invalid zero quaternion')
    rclpy.init()
    node = rclpy.create_node('interactive_maze_verification')
    commands = []
    states = []
    resets = []
    node.create_subscription(Twist, 'cmd_vel', commands.append, 10)
    node.create_subscription(String, 'controller_state', lambda msg: states.append(msg.data), 10)
    scan_pub = node.create_publisher(LaserScan, 'scan', 10)
    odom_pub = node.create_publisher(Odometry, 'odom', 10)
    goal_pub = node.create_publisher(PoseStamped, 'goal_pose', 10)
    feedback_pub = node.create_publisher(InteractiveMarkerFeedback, 'maze_reset/feedback', 10)
    node.create_service(Empty, 'reset_world', lambda request, response: resets.append(True) or response)
    reset_client = node.create_client(Trigger, 'restart_maze')
    executable = os.path.join(get_package_prefix('maze_control'), 'lib', 'maze_control', 'tb3_wall_follower_optimized')
    marker_executable = os.path.join(get_package_prefix('maze_control'), 'lib', 'maze_control', 'maze_reset_marker')
    process = subprocess.Popen([executable, '--ros-args', '-p', 'exit_x:=99.0', '-p', 'log_file:=/tmp/interactive_check.csv'], start_new_session=True)
    marker_process = subprocess.Popen([marker_executable], start_new_session=True)

    def sensors(x, y, yaw):
        scan = LaserScan()
        scan.angle_increment = math.pi / 180
        scan.range_min, scan.range_max = 0.12, 3.5
        scan.ranges = [3.5] * 360
        for degree in range(65, 116):
            scan.ranges[degree] = 0.38
        odom = Odometry()
        odom.header.frame_id = 'odom'
        odom.pose.pose.position.x = x
        odom.pose.pose.position.y = y
        odom.pose.pose.orientation.z = math.sin(yaw / 2)
        odom.pose.pose.orientation.w = math.cos(yaw / 2)
        scan_pub.publish(scan)
        odom_pub.publish(odom)

    def wait_for(expected, x, y, yaw, goal=None, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and expected not in states:
            sensors(x, y, yaw)
            if goal is not None:
                goal_pub.publish(goal)
            rclpy.spin_once(node, timeout_sec=0.05)
        if expected not in states:
            raise RuntimeError('Controller did not publish ' + expected)

    try:
        wait_for('FOLLOW', 0.5, 0.5, math.pi / 2)
        goal = PoseStamped()
        goal.header.frame_id = 'odom'
        goal.pose.position.x = 0.5
        goal.pose.position.y = 0.8
        goal.pose.orientation.w = 1.0
        wait_for('RVIZ_GOAL', 0.5, 0.5, math.pi / 2, goal)
        if not any(command.linear.x > 0 for command in commands):
            raise RuntimeError('RViz goal did not produce forward motion')
        wait_for('RVIZ_ALIGN', 0.5, 0.8, math.pi / 2)
        if not any(command.angular.z < 0 for command in commands):
            raise RuntimeError('Final heading did not produce clockwise alignment')
        wait_for('RVIZ_REACHED', 0.5, 0.8, 0.0)
        if not reset_client.wait_for_service(timeout_sec=3):
            raise RuntimeError('restart_maze service was not available')
        feedback = InteractiveMarkerFeedback()
        feedback.header.frame_id = 'odom'
        feedback.client_id = 'verification'
        feedback.marker_name = 'restart_maze'
        feedback.control_name = 'reset_button'
        feedback.event_type = InteractiveMarkerFeedback.BUTTON_CLICK
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not resets:
            feedback_pub.publish(feedback)
            rclpy.spin_once(node, timeout_sec=0.05)
        if not resets or 'RESETTING' not in states:
            raise RuntimeError('RViz reset marker did not call Gazebo reset_world')
        wait_for('FOLLOW', 0.5, 0.5, math.pi / 2)
        process.send_signal(signal.SIGINT)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and 'STOPPED' not in states:
            rclpy.spin_once(node, timeout_sec=0.05)
        if process.wait(timeout=5) != 0 or 'STOPPED' not in states:
            raise RuntimeError('Controller did not stop cleanly')
        print('PASS: RViz pose goal, final yaw, maze reset and wall-follow resume all worked')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if marker_process.poll() is None:
            marker_process.kill()
            marker_process.wait()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
