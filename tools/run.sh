set -eu
if [ ! -f /opt/ros/humble/setup.bash ]; then
    printf '%s\n' 'ROS2 Humble is required. Run this project on Ubuntu 22.04 with Gazebo Classic 11.' >&2
    exit 1
fi
set +u
source /opt/ros/humble/setup.bash
set -u
cd "$(dirname "$0")/.."
mode=${1:-wall}
if [ "$#" -gt 0 ]; then shift; fi
case "$mode" in
    wall|wall_basic|point|waypoints|open_loop|avoid|scan) ;;
    *) printf '%s\n' 'Choose wall, wall_basic, point, waypoints, open_loop, avoid or scan.' >&2; exit 1 ;;
esac
colcon build --base-paths src --packages-select maze_control
set +u
source install/setup.bash
set -u
ros2 launch maze_control simulation.launch.py mode:="$mode" "$@"
