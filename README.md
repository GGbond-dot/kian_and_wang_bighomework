# 地老鼠走迷宫系统

课程：机器人感知与控制综合实践，S0610350。工程已按[课程教学文档](https://www.yuque.com/shellcore/rpide7)的综合实验入口和参数修订。详细依据、示例中的不一致及保留的拓展见 [课程对照说明](docs/course_alignment.md)。

所有控制节点位于一个 `ament_python` 包 `maze_control` 中。当前目录就是工作空间根目录，对应教材里的 `~/ros2maze_ws`；不必移动文件或另建工作空间。自编代码按使用者要求不加注释，原理和来源写在文档里。

## Ubuntu 24 上启动

宿主机使用 Ubuntu 24.04，Docker 内为 Ubuntu 22.04、ROS2 Humble、Gazebo Classic 11 和官方 TurtleBot3 Burger。先在本项目根目录构建更新后的镜像，再启动：

```bash
cd /home/kian/kian_and_wang_bighomework
bash tools/docker.sh build
bash tools/docker.sh wall
```

`wall` 是原先的优化迷宫模式，启动 Gazebo、RViz、机器人、测距节点和控制器。每次运行自动把挂载的当前源码编译到容器 `/tmp`，避免混用宿主 Jazzy 的 build/install。按 Ctrl+C 退出；重新启动会复位场景。不要同时运行两套速度控制节点。

## 按课程顺序运行

每条命令是一套独立实验，先 Ctrl+C 关闭上一套，再运行下一条。

| 命令 | 内容 | 课程对应 |
|---|---|---|
| `bash tools/docker.sh open_loop` | 开环直行，再原地转向 | Ch6.1 |
| `bash tools/docker.sh point` | 从原点驶向 `(1,0)`，5 cm 内停车 | Ch6.2 |
| `bash tools/docker.sh waypoints` | `(1,0)→(1,1)→(0,1)→(0,0)` 矩形闭环 | Ch6.3 |
| `bash tools/docker.sh scan fixed_frame:=base_link` | 原地测距，终端打印前、左、右距离 | Ch7.2 |
| `bash tools/docker.sh avoid world:=maze` | 有障碍场景下反应式避障 | Ch7.3 |
| `bash tools/docker.sh wall_basic` | 课程基础规则，在宽走廊保持左墙距离并到达出口 | Ch7.4 |
| `bash tools/docker.sh wall` | 原自定义蛇形迷宫，里程计转角闭环与速度自适应 | 综合考核与拓展 |

`scan` 模式只加载仿真和测距节点，不发布 `/cmd_vel`，方便手动放置方块、圆柱或连接键盘控制。`avoid` 不指定 world 时使用空场，可以按课程方法手动添加障碍物；它只展示局部避障，不承担迷宫求解。

自定义目标与航点：

```bash
bash tools/docker.sh point goal:='[0.0,1.0]'
bash tools/docker.sh waypoints waypoints:='[[1,0],[0.5,1],[0,0]]'
bash tools/docker.sh wall adaptive:=false
```

基础墙跟随不是完整路径规划器，不保证走通任意迷宫。`wall_basic` 与 `wall` 使用各自的默认场景，比较两种速度策略时用同一个 `wall` 场景切换 adaptive。

## 课程中的 ROS 启动名

一键入口：[simulation.launch.py](src/maze_control/launch/simulation.launch.py)。在已安装依赖的干净 Ubuntu 22.04/Humble 工作空间中：

```bash
source /opt/ros/humble/setup.bash
colcon build --base-paths src --packages-select maze_control
source install/setup.bash
ros2 launch maze_control simulation.launch.py mode:=point
```

在已有仿真中单独启动课程节点时，只选一个控制节点：

```bash
ros2 run maze_control tb3_point2point
ros2 run maze_control tb3_waypoints
ros2 run maze_control scan_region
ros2 run maze_control tb3_avoid
ros2 run maze_control tb3_wall_follower
```

`tb3_wall_follower` 为基础规则；`tb3_wall_follower_optimized` 为拓展状态机。默认话题是 `/scan`、`/odom`、`/cmd_vel`；单独运行控制节点时应确保这套仿真没有其他控制器发布速度。

Ubuntu 24 宿主机无需安装 Humble。上面原生 ROS 命令在 Docker 内执行即可，容器终端用 `bash tools/docker.sh shell`。宿主 VSCode 的 Jazzy 提示环境不代表本项目实际运行版本。

## 参数与分区

课程参数文件：[course.yaml](src/maze_control/config/course.yaml)。

| 项目 | 参数 |
|---|---|
| 点控制 | 距离增益 0.3，角度增益 0.8，最大线速度 0.2 m/s，最大角速度 1.0 rad/s，容差 0.05 m |
| 航点 | 复用同一 P 控制器，依次完成四点并回原点 |
| 雷达测距 | 前方 `[-15,15]°` 最小值；左侧 `[60,90]°` 中值；右侧 `[-90,-60]°` 中值 |
| 基础墙跟随 | 左侧 `[60,90]°` 最小值，目标 0.4 m，前方危险距离 0.35 m，速度 0.15 m/s，右转角速度 −0.6 rad/s |
| 独立避障 | 前方安全距离 0.8 m，速度 0.15 m/s，遇障原地右转 −0.3 rad/s |
| 优化墙跟随 | 保留已调试的正侧方分区、0.38 m 墙距与离散转角状态机，作为独立拓展 |

点控制保留大角差先转向、转角归一化及余弦降速，减少绕圈。雷达通过实际 `angle_min + i*angle_increment` 计算并归一化角度，兼容 0～2π 和 −π～π 扫描。有限测量优先；正无穷仅在没有有限回波时表示量程内无障碍，NaN/负无穷/越界值不参与统计。整个分区均无效时控制器停车。

## 场景与可视化

- `empty.world`：原点出生，点控制、矩形航点、测距和开环实验。
- `course.world`：约 7.5 m 的矩形墙体与 1.5 m 宽底部走廊，出生 `(-3.4,-3.0)` 朝东，右侧开放出口；按课程场景原理独立整理。
- `maze.world`：原来的 4 m × 4 m 蛇形迷宫，出生 `(0.5,0.5)` 朝北。

world 只保存环境，不包含机器人实体；机器人由 launch 单独生成一次。URDF 提供给 robot_state_publisher/RViz，官方 SDF 提供给 Gazebo。简化自编模型可用 `robot:=simplified` 切换。

每个场景有对应 RViz 配置，默认固定坐标系 `odom`，显示 RobotModel、LaserScan、TF、轨迹；`fixed_frame:=base_link` 便于课程的机器人中心观测。墙体均有碰撞，SDF pose 使用完整六项值，墙高保证激光可命中。

## 检查与数据

```bash
bash tools/docker.sh test
bash tools/docker.sh headless
```

`test` 运行纯算法、资源和脚本检查。`headless` 跑优化迷宫，不显示 GUI。需要按课程批量验收时可运行 `bash tools/docker.sh verify`，会依次运行各模式并保存 CSV；默认不制作讲解视频。

运行日志写入宿主 `results/gazebo_模式_时间.csv`，包含位姿、命令速度、墙距和状态。辅助话题 `/wall_distances` 中 x/y/z 依次是课程测距分区的前/左/右距离；`/trajectory` 为里程计轨迹，`/controller_state` 为状态。

当前课程修订的验证记录保存到 `results/course_alignment`。原 `results/gazebo`、原图形录像和 `deliverables/archive` 是历史材料，不能当作新参数、新闭环航点的验证结果。最新报告已按教师 Word 模板重写，真人演示由使用者自己录制。

## 阅读源码

- [control.py](src/maze_control/maze_control/control.py)：P 控制、课程分区、基础与优化墙跟随。
- [node.py](src/maze_control/maze_control/node.py)：话题、目标切换、超时保护、日志和退出停车。
- [perception.py](src/maze_control/maze_control/perception.py)：分区测距发布与打印。
- [课程对照说明](docs/course_alignment.md)：逐项来源、采用方式和必要修正。

任务书允许 AI 辅助，但要求说明使用范围并由实际组员理解、调试和完善。本工程如实保留来源和工具验证记录。成员为 kian 和 wang，分工按各 50% 提供安排建议，提交前按实际参与确认；学号等个人信息待填。正式报告填写真实信息、模块分工与至少两篇参考文献，录制不超过三分钟的真人讲解演示，按学习通 L6 综合设计要求提交。

## 报告与答辩准备

- [最新课程报告](deliverables/课程报告_kian_wang.docx)：教师模板十章，包含当前实测数据、分工与 AI 使用说明；封面组号、学号和提交日期待填。
- [答辩阅读指南](docs/答辩阅读指南.md)：源码阅读顺序、数据流、常见问答及分工建议。
- [报告正文](docs/report.md)：方便检索和后续修改；重新生成使用 `tools/build_template_report.py`，须安装 python-docx 与 Pillow。
- [教师原模板](docs/reference/课程报告模板.docx)：保留原件副本。

旧文件名 `deliverables/综合设计报告.docx` 同步为最新版本；对齐前报告保存在 archive。当前 `micromouse_project.zip` 包含源码、报告、答辩指南和本轮实验记录，不含历史讲解录像。
