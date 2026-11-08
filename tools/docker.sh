set -euo pipefail
cd "$(dirname "$0")/.."
export LOCAL_UID="$(id -u)"
export LOCAL_GID="$(id -g)"
command=${1:-wall}
if [ "$#" -gt 0 ]; then shift; fi
docker compose version >/dev/null
case "$command" in
    verify)
        exec docker run --rm --init --shm-size 1g --user "$LOCAL_UID:$LOCAL_GID" --network host --env HOME=/tmp/micromouse-home --env LIBGL_ALWAYS_SOFTWARE=1 --env QT_X11_NO_MITSHM=1 --env GAZEBO_MODEL_DATABASE_URI= --volume "$PWD/results:/results:rw" micromouse:humble verify "$@"
        ;;
    build)
        exec docker compose build "$@"
        ;;
    test)
        exec docker run --rm --user "$LOCAL_UID:$LOCAL_GID" --env HOME=/tmp/micromouse-home micromouse:humble test
        ;;
    headless)
        exec docker run --rm --init --user "$LOCAL_UID:$LOCAL_GID" --network host --env HOME=/tmp/micromouse-home --env ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-35}" --volume "$PWD:/workspace:ro" --volume "$PWD/results:/results:rw" micromouse:humble wall gui:=false rviz:=false "$@"
        ;;
    wall|wall_basic|point|waypoints|open_loop|avoid|scan|shell) ;;
    *) printf '%s\n' 'Choose build, test, headless, wall, point, waypoints, open_loop, avoid or shell.' >&2; exit 1 ;;
esac
: "${DISPLAY:?No DISPLAY found. Use headless or run from an X11 or XWayland desktop.}"
command -v xauth >/dev/null
export XAUTH_FILE="$(mktemp /tmp/micromouse-xauth.XXXXXX)"
trap 'rm -f "$XAUTH_FILE"' EXIT
cookies="$(xauth nlist "$DISPLAY")"
if [ -z "$cookies" ]; then
    printf '%s\n' 'No X11 cookie found. Run in the desktop terminal and check DISPLAY and XAUTHORITY.' >&2
    exit 1
fi
printf '%s\n' "$cookies" | sed 's/^..../ffff/' | xauth -f "$XAUTH_FILE" nmerge -
docker compose run --rm micromouse "$command" "$@"
