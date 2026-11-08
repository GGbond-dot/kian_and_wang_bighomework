import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def configure(context):
    share = Path(get_package_share_directory('maze_control'))
    gazebo = Path(get_package_share_directory('gazebo_ros'))
    robot = LaunchConfiguration('robot').perform(context)
    mode = LaunchConfiguration('mode').perform(context)
    executables = {'wall': 'tb3_wall_follower_optimized', 'wall_basic': 'tb3_wall_follower', 'point': 'tb3_point2point', 'waypoints': 'tb3_waypoints', 'open_loop': 'tb3_open_loop', 'avoid': 'tb3_avoid', 'scan': None}
    if mode not in executables:
        raise ValueError('unsupported mode: ' + mode)
    world_name = LaunchConfiguration('world').perform(context)
    if world_name == 'auto':
        world_name = 'maze' if mode == 'wall' else ('course' if mode == 'wall_basic' else 'empty')
    layout = {'maze': (0.5, 0.5, 1.57079632679, 4.35, 0.15, 0.85), 'course': (-3.4, -3.0, 0.0, 3.95, -3.65, -2.4), 'empty': (0.0, 0.0, 0.0, 4.35, 0.15, 0.85)}
    if world_name not in layout:
        raise ValueError('world must be maze, course or empty')
    defaults = dict(zip(('x', 'y', 'yaw', 'exit_x', 'exit_y_min', 'exit_y_max'), layout[world_name]))
    def number(name):
        value = LaunchConfiguration(name).perform(context)
        return defaults[name] if value == 'auto' else float(value)
    actions = []
    if robot == 'official':
        import xacro
        description_share = Path(get_package_share_directory('turtlebot3_description'))
        simulation_share = Path(get_package_share_directory('turtlebot3_gazebo'))
        candidates = [description_share / 'urdf' / name for name in ('turtlebot3_burger.urdf', 'turtlebot3_burger.urdf.xacro')]
        urdf_path = next((path for path in candidates if path.is_file()), None)
        if urdf_path is None:
            raise FileNotFoundError('TurtleBot3 Burger URDF/Xacro was not found')
        description = xacro.process_file(str(urdf_path)).toxml()
        model = ET.parse(simulation_share / 'models' / 'turtlebot3_burger' / 'model.sdf')
        for element in model.findall('.//sensor/visualize'):
            element.text = 'false'
        model_file = tempfile.NamedTemporaryFile(mode='w', suffix='.sdf', delete=False)
        with model_file:
            model_file.write(ET.tostring(model.getroot(), encoding='unicode'))
        spawn_args = ['-file', model_file.name]
        model_path = os.pathsep.join(filter(None, [str(simulation_share / 'models'), os.environ.get('GAZEBO_MODEL_PATH', '')]))
        actions.append(SetEnvironmentVariable('GAZEBO_MODEL_PATH', model_path))
    elif robot == 'simplified':
        description = (share / 'urdf' / 'burger.urdf').read_text()
        spawn_args = ['-topic', 'robot_description']
    else:
        raise ValueError('robot must be official or simplified')
    world = str(share / 'worlds' / (world_name + '.world'))
    actions.extend([
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(gazebo / 'launch' / 'gazebo.launch.py')), launch_arguments={'world': world, 'gui': LaunchConfiguration('gui')}.items()),
        Node(package='robot_state_publisher', executable='robot_state_publisher', parameters=[{'robot_description': description, 'use_sim_time': True}], output='screen'),
        Node(package='gazebo_ros', executable='spawn_entity.py', arguments=['-entity', 'burger', *spawn_args, '-x', str(number('x')), '-y', str(number('y')), '-z', '0.01', '-Y', str(number('yaw')), '-timeout', '60'], output='screen'),
        Node(package='maze_control', executable='scan_region', parameters=[{'use_sim_time': True}], output='screen'),
        Node(package='rviz2', executable='rviz2', arguments=['-d', str(share / 'config' / (world_name + '.rviz')), '-f', LaunchConfiguration('fixed_frame')], parameters=[{'use_sim_time': True}], condition=IfCondition(LaunchConfiguration('rviz')), output='screen'),
    ])
    if executables[mode] is not None:
        actions.append(Node(package='maze_control', executable=executables[mode], parameters=[str(share / 'config' / 'course.yaml'), {
            'use_sim_time': True,
            'start_delay': ParameterValue(LaunchConfiguration('start_delay'), value_type=float),
            'adaptive': ParameterValue(LaunchConfiguration('adaptive'), value_type=bool),
            **{name: number(name) for name in ('exit_x', 'exit_y_min', 'exit_y_max')},
            'goal': ParameterValue(LaunchConfiguration('goal'), value_type=str),
            'waypoints': ParameterValue(LaunchConfiguration('waypoints'), value_type=str),
            'log_file': ParameterValue(LaunchConfiguration('log_file'), value_type=str),
        }], output='screen'))
    return actions


def generate_launch_description():
    defaults = {
        'world': 'auto', 'robot': 'official', 'mode': 'wall', 'rviz': 'true',
        'gui': 'true', 'adaptive': 'true', 'x': 'auto', 'y': 'auto',
        'yaw': 'auto', 'goal': '[1.0,0.0]',
        'waypoints': '[[1.0,0.0],[1.0,1.0],[0.0,1.0],[0.0,0.0]]',
        'exit_x': 'auto', 'exit_y_min': 'auto', 'exit_y_max': 'auto',
        'fixed_frame': 'odom',
        'log_file': '/tmp/micromouse_run.csv',
        'start_delay': '0.0',
    }
    return LaunchDescription([DeclareLaunchArgument(key, default_value=value) for key, value in defaults.items()] + [OpaqueFunction(function=configure)])
