import argparse
import csv
import ctypes
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path

from offline_sim import Pose, clearance, read_walls


def arrange_windows():
    x = ctypes.cdll.LoadLibrary('libX11.so.6')
    x.XOpenDisplay.restype = ctypes.c_void_p
    display = x.XOpenDisplay(None)
    if not display:
        return
    x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x.XDefaultRootWindow.restype = ctypes.c_ulong
    root = x.XDefaultRootWindow(display)
    root_return = ctypes.c_ulong()
    parent = ctypes.c_ulong()
    children = ctypes.POINTER(ctypes.c_ulong)()
    count = ctypes.c_uint()
    x.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint)]
    x.XQueryTree(display, root, ctypes.byref(root_return), ctypes.byref(parent), ctypes.byref(children), ctypes.byref(count))
    x.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
    x.XMoveResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
    for i in range(count.value):
        title = ctypes.c_char_p()
        if x.XFetchName(display, children[i], ctypes.byref(title)) and title.value:
            name = title.value.decode(errors='replace')
            if name == 'Gazebo' or 'RViz' in name:
                offset = 0 if name == 'Gazebo' else 800
                x.XMoveResizeWindow(display, children[i], offset, 0, 800, 850)
            x.XFree(title)
    x.XFree(children)
    x.XFlush.argtypes = [ctypes.c_void_p]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x.XFlush(display)
    x.XCloseDisplay(display)


def stop(process):
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def read_rows(path):
    if not path.exists():
        return []
    with path.open() as stream:
        return [row for row in csv.DictReader(stream) if row.get('state')]


def run_case(name, mode, extra, output, gui):
    path = output / (name + '.csv')
    if path.exists():
        path.unlink()
    world = 'course' if mode == 'wall_basic' else ('maze' if mode in ('wall', 'avoid') else 'empty')
    yaw = '1.57079632679' if mode == 'wall' else '0'
    command = ['ros2', 'launch', 'maze_control', 'simulation.launch.py', 'mode:=' + mode, 'world:=' + world, 'yaw:=' + yaw, 'gui:=' + str(gui).lower(), 'rviz:=' + str(gui).lower(), 'log_file:=' + str(path), *extra]
    if gui:
        command.append('start_delay:=8.0')
    started = time.monotonic()
    recorder = None
    if gui:
        recorder = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'x11grab', '-framerate', '15', '-video_size', '1600x900', '-i', os.environ['DISPLAY'], '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p', str(output / (name + '_raw.mp4'))], start_new_session=True)
    with (output / (name + '.log')).open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while time.monotonic() - started < 700:
                time.sleep(1)
                if gui:
                    arrange_windows()
                rows = read_rows(path)
                if process.poll() is not None:
                    raise RuntimeError(name + ' launch exited; inspect log')
                if not rows:
                    if time.monotonic() - started > 90:
                        raise RuntimeError(name + ' has no valid sensor samples; inspect log')
                    continue
                if gui and recorder is None:
                    subprocess.run(['wmctrl', '-r', 'Gazebo', '-e', '0,0,0,800,850'], check=False)
                    subprocess.run(['wmctrl', '-r', 'RViz', '-e', '0,800,0,800,850'], check=False)
                    recorder = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'x11grab', '-framerate', '15', '-video_size', '1600x900', '-i', os.environ['DISPLAY'], '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p', str(output / (name + '_raw.mp4'))], start_new_session=True)
                last = rows[-1]
                elapsed = float(last['time_s'])
                if elapsed > 450 or last['state'] == 'FAULT':
                    raise RuntimeError(name + ' failed to finish: ' + str(last))
                if last['state'] == 'DONE' or (mode == 'avoid' and elapsed >= 14):
                    if gui:
                        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'x11grab', '-video_size', '1600x900', '-i', os.environ['DISPLAY'], '-frames:v', '1', str(output / (name + '_screen.png'))], check=True)
                    break
            else:
                raise RuntimeError(name + ' wall-clock timeout')
        finally:
            stop(recorder)
            stop(process)
    rows = read_rows(path)
    final = rows[-1]
    distance = sum(math.hypot(float(b['x_m']) - float(a['x_m']), float(b['y_m']) - float(a['y_m'])) for a, b in zip(rows, rows[1:]))
    result = {'name': name, 'model': 'official TurtleBot3 Burger in Gazebo Classic 11', 'samples': len(rows), 'duration_s': float(final['time_s']), 'path_length_m': round(distance, 4), 'minimum_front_range_m': min(float(row['front_m']) for row in rows), 'final_pose': [float(final[k]) for k in ('x_m', 'y_m', 'yaw_rad')], 'final_state': final['state'], 'states': sorted({row['state'] for row in rows}), 'success': final['state'] == 'DONE' if mode != 'avoid' else any(row['state'] == 'AVOID' for row in rows)}
    if world == 'maze':
        result['minimum_body_clearance_m'] = round(min(clearance(Pose(float(row['x_m']), float(row['y_m']), float(row['yaw_rad'])), read_walls()) - 0.13 for row in rows), 4)
        result['body_envelope_radius_m'] = 0.13
        result['success'] = result['success'] and result['minimum_body_clearance_m'] > 0
    if mode == 'point':
        result['goal_error_m'] = math.hypot(result['final_pose'][0] - 1.0, result['final_pose'][1])
    if mode == 'waypoints':
        result['goal_error_m'] = math.hypot(result['final_pose'][0], result['final_pose'][1])
    (output / (name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    if not result['success']:
        raise RuntimeError(name + ' did not pass')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/results/gazebo')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--cases', nargs='+', default=['open_loop', 'point', 'waypoints', 'avoid', 'basic', 'fixed', 'adaptive'])
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    cases = {'open_loop': ('open_loop', []), 'point': ('point', []), 'waypoints': ('waypoints', []), 'avoid': ('avoid', []), 'basic': ('wall_basic', []), 'fixed': ('wall', ['adaptive:=false']), 'adaptive': ('wall', ['adaptive:=true'])}
    for name in args.cases:
        run_case(name, *cases[name], output, args.gui)


if __name__ == '__main__':
    main()
