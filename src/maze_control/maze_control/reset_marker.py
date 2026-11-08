import rclpy
from interactive_markers.interactive_marker_server import InteractiveMarkerServer
from rclpy.node import Node
from std_srvs.srv import Trigger
from visualization_msgs.msg import InteractiveMarker, InteractiveMarkerControl, InteractiveMarkerFeedback, Marker


def make_reset_marker(start_x, start_y):
    marker = InteractiveMarker()
    marker.header.frame_id = 'odom'
    marker.name = 'restart_maze'
    marker.description = 'RESET MAZE'
    marker.pose.position.x = start_x
    marker.pose.position.y = start_y
    marker.pose.position.z = 0.45
    marker.pose.orientation.w = 1.0
    marker.scale = 0.55
    control = InteractiveMarkerControl()
    control.name = 'reset_button'
    control.orientation.w = 1.0
    control.interaction_mode = InteractiveMarkerControl.BUTTON
    control.always_visible = True
    button = Marker()
    button.type = Marker.CYLINDER
    button.pose.orientation.w = 1.0
    button.scale.x = 0.28
    button.scale.y = 0.28
    button.scale.z = 0.10
    button.color.r = 0.90
    button.color.g = 0.12
    button.color.b = 0.08
    button.color.a = 1.0
    label = Marker()
    label.type = Marker.TEXT_VIEW_FACING
    label.pose.position.z = 0.18
    label.pose.orientation.w = 1.0
    label.scale.z = 0.13
    label.color.r = 1.0
    label.color.g = 1.0
    label.color.b = 1.0
    label.color.a = 1.0
    label.text = 'RESET'
    control.markers.extend((button, label))
    marker.controls.append(control)
    return marker


class ResetMarker(Node):
    def __init__(self):
        super().__init__('maze_reset_marker')
        self.declare_parameter('start_x', 0.5)
        self.declare_parameter('start_y', 0.5)
        self.client = self.create_client(Trigger, 'restart_maze')
        self.server = InteractiveMarkerServer(self, 'maze_reset')
        marker = make_reset_marker(
            self.get_parameter('start_x').value,
            self.get_parameter('start_y').value,
        )
        self.server.insert(marker, feedback_callback=self.receive_click)
        self.server.applyChanges()

    def receive_click(self, feedback):
        if feedback.event_type != InteractiveMarkerFeedback.BUTTON_CLICK:
            return
        if not self.client.service_is_ready():
            self.get_logger().error('迷宫复位服务尚未就绪')
            return
        future = self.client.call_async(Trigger.Request())
        future.add_done_callback(self.receive_result)

    def receive_result(self, future):
        try:
            result = future.result()
            log = self.get_logger().info if result.success else self.get_logger().error
            log(result.message)
        except Exception as error:
            self.get_logger().error(str(error))


def main(args=None):
    rclpy.init(args=args)
    node = ResetMarker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
