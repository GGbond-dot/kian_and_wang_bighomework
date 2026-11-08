set -e
mkdir -p "$HOME"
source /opt/ros/humble/setup.bash
mode=${1:-wall}
if [ "$#" -gt 0 ]; then shift; fi
case "$mode" in
    verify)
        source /opt/micromouse/install/setup.bash
        exec python3 /opt/micromouse/tools/gazebo_trials.py --output /results/course_alignment "$@"
        ;;
    test)
        cd /opt/micromouse
        exec python3 -m unittest discover -s tests -v
        ;;
    shell)
        source /opt/micromouse/install/setup.bash
        exec bash
        ;;
    wall|wall_basic|point|waypoints|open_loop|avoid|scan) ;;
    *) printf '%s\n' 'Choose wall, point, waypoints, open_loop, avoid, test or shell.' >&2; exit 1 ;;
esac
if [ -d /workspace/src/maze_control ]; then
    cd /tmp
    colcon --log-base /tmp/micromouse-log build --base-paths /workspace/src --packages-select maze_control --build-base /tmp/micromouse-build --install-base /tmp/micromouse-install
    source /tmp/micromouse-install/setup.bash
else
    source /opt/micromouse/install/setup.bash
fi
log_file=/tmp/micromouse_run.csv
if [ -d /results ] && [ -w /results ]; then
    log_file="/results/gazebo_${mode}_$(date +%Y%m%d_%H%M%S).csv"
fi
exec ros2 launch maze_control simulation.launch.py mode:="$mode" log_file:="$log_file" "$@"
