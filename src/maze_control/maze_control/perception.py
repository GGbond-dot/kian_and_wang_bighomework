import rclpy
from rclpy.executors import ExternalShutdownException
from geometry_msgs.msg import Vector3
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

from .control import Scan, course_regions


class ScanFeatures(Node):
    def __init__(self):
        super().__init__('scan_region_filter_node')
        self.declare_parameter('log_period', 1.0)
        self.last_log = -float('inf')
        self.publisher = self.create_publisher(Vector3, 'wall_distances', 10)
        self.create_subscription(LaserScan, 'scan', self.receive, qos_profile_sensor_data)

    def receive(self, msg):
        scan = Scan(msg.ranges, msg.angle_min, msg.angle_increment, msg.range_min, msg.range_max)
        values = course_regions(scan)
        self.publisher.publish(Vector3(**dict(zip(('x', 'y', 'z'), [float('nan') if v is None else float(v) for v in values]))))
        now = self.get_clock().now().nanoseconds * 1e-9
        if now - self.last_log >= self.get_parameter('log_period').value:
            labels = ['无效' if value is None else f'{value:.2f} m' for value in values]
            self.get_logger().info(f'front_dist={labels[0]} left_dist={labels[1]} right_dist={labels[2]}')
            self.last_log = now


def main(args=None):
    rclpy.init(args=args)
    node = ScanFeatures()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
