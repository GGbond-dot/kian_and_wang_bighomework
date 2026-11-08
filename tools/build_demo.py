import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/gazebo_gui'
WORK = ROOT / 'results/video_edit'
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], text=True))


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    output = ROOT / 'deliverables'
    output.mkdir(exist_ok=True)
    chapters = [
        ('open_loop', 8, '开环直行与原地转向｜Gazebo 实录｜AI 合成旁白', '这是容器内官方机器人实际运行录像。先展示开环直行和原地转向。'),
        ('point', 8, '里程计点到点 P 控制｜到达目标后停车', '点控制根据里程计计算位置和朝向误差，接近目标时减速，到点后停车。'),
        ('waypoints', 16, '四航点依次跟踪｜Gazebo 与 RViz 同屏', '航点模式依次经过四个坐标点。右侧是可视化工具，显示机器人和实际里程计轨迹。四元数转换为偏航角，角度误差统一归一化。'),
        ('avoid', 10, '激光雷达反应式避障｜前方障碍触发原地右转', '激光扫描按实际角度分区，提取前、左、右距离。前方障碍接近时停止前进并转向。'),
        ('adaptive', 128, '迷宫完整连续过程', '现在展示完整迷宫运行。机器人只依靠激光雷达与里程计，使用左墙跟随策略。左侧开口出现时先越过墙角，再闭环转向。前方堵塞时右转。控制器根据前方空间和转向幅度自适应减速，使用里程计保持直角走廊方向。录像连续保留从起点到出口的过程，倍速在字幕中标明。到达出口后进入完成状态，并持续发送零速度。实验数据保存在原始日志中。'),
    ]
    manifest = []
    for name, target, label, speech in chapters:
        source = SOURCE / (name + '_raw.mp4')
        final = ROOT / 'results/gazebo_gui_final' / (name + '_raw.mp4')
        if name == 'adaptive' and final.with_name(name + '.json').exists():
            source = final
        available = duration(source) - 6
        if available <= 0:
            raise ValueError('video too short: ' + name)
        speed = available / target
        label += f'｜{speed:.2f} 倍速'
        if name == 'adaptive':
            label += '｜左 Gazebo 右 RViz｜原片与 CSV 随包附带'
        caption = WORK / (name + '.txt')
        caption.write_text(label)
        wav = WORK / (name + '.wav')
        subprocess.run(['espeak-ng', '-v', 'cmn', '-s', '190', '-w', str(wav), speech], check=True)
        voice_speed = max(1.0, duration(wav) / (target - 0.5))
        audio_filter = []
        while voice_speed > 2:
            audio_filter.append('atempo=2.0')
            voice_speed /= 2
        audio_filter.extend([f'atempo={voice_speed:.6f}', 'apad'])
        vf = f'trim=start=6,setpts=(PTS-STARTPTS)*{target / available:.8f},fps=25,drawbox=x=0:y=850:w=1600:h=50:color=black:t=fill,drawtext=fontfile={FONT}:textfile={caption}:expansion=none:x=20:y=860:fontsize=22:fontcolor=white,tpad=stop_mode=clone:stop_duration=1'
        clip = WORK / (name + '.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(source), '-i', str(wav), '-filter_complex', f'[0:v]{vf}[v];[1:a]{",".join(audio_filter)}[a]', '-map', '[v]', '-map', '[a]', '-t', str(target), '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2', str(clip)], check=True)
        manifest.append({'chapter': name, 'source': str(source.relative_to(ROOT)), 'trim_initial_idle_s': 6, 'playback_speed': round(speed, 4), 'duration_s': target, 'narration': 'AI synthesized Mandarin with espeak-ng'})
    listing = WORK / 'concat.txt'
    listing.write_text('\n'.join("file '" + str(WORK / (name + '.mp4')) + "'" for name, _, _, _ in chapters) + '\n')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(output / '演示视频.mp4')], check=True)
    (SOURCE / 'video_provenance.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
