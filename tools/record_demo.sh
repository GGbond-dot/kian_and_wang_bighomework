set -eu
output=${1:-demo.mp4}
display=${DISPLAY:?Please run from an X11 desktop session}
resolution=${RESOLUTION:-1920x1080}
audio=${RECORD_AUDIO:-1}
if [ "$audio" = "1" ]; then
    ffmpeg -y -f x11grab -framerate 25 -video_size "$resolution" -i "$display" -f pulse -i default -t "${DURATION:-175}" -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart "$output"
else
    ffmpeg -y -f x11grab -framerate 25 -video_size "$resolution" -i "$display" -t "${DURATION:-175}" -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p -movflags +faststart "$output"
fi
