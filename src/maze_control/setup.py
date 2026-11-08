from glob import glob
from setuptools import setup

setup(
    name='maze_control',
    version='1.0.0',
    packages=['maze_control'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/maze_control']),
        ('share/maze_control', ['package.xml']),
        *[('share/maze_control/' + folder, glob(folder + '/*')) for folder in ['launch', 'worlds', 'urdf', 'config']],
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Course project team',
    maintainer_email='student@example.com',
    description='Reactive micromouse course project',
    license='MIT',
    entry_points={'console_scripts': [
        'controller = maze_control.node:main',
        'scan_region = maze_control.perception:main',
        'scan_features = maze_control.perception:main',
        'maze_reset_marker = maze_control.reset_marker:main',
        'tb3_point2point = maze_control.tb3_point2point:main',
        'tb3_waypoints = maze_control.tb3_waypoints:main',
        'tb3_avoid = maze_control.tb3_avoid:main',
        'tb3_open_loop = maze_control.tb3_open_loop:main',
        'tb3_wall_follower = maze_control.tb3_wall_follower:main',
        'tb3_wall_follower_optimized = maze_control.node:main',
    ]},
)
