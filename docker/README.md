# Ubuntu 24 上运行 Ubuntu 22 的课程环境

基础镜像为 osrf/ros:humble-desktop。容器内安装 Humble、Gazebo Classic 11、官方 TurtleBot3 Burger、RViz。宿主机继续使用 Ubuntu 24.04 和原来的 Jazzy。

镜像已经在本机实际构建成功，容器内 colcon 编译和 21 项测试通过。官方 Burger 在 Gazebo 中通过全部基础实验，两种墙跟随策略均抵达出口。宿主 Jazzy 的安装没有被修改。

## 构建与运行

在项目根目录：

```bash
bash tools/docker.sh build
bash tools/docker.sh test
bash tools/docker.sh wall
```

第一次构建需要下载大型基础镜像及安装依赖，时间取决于网络。Dockerfile 会执行 colcon build 和自动化测试；这些步骤失败会直接使构建失败。

工具脚本要求 Docker Engine 和 Compose 插件可用。先用 docker version 与 docker compose version 检查。若提示 Docker socket 权限错误，按本机 Docker 安装方式授予当前账户访问权限；项目脚本不会替你修改用户组。

## 批量验证

```bash
bash tools/docker.sh verify
```

默认在无界面 Gazebo 中依次运行课程基础实验、基础墙跟随和两种优化策略，保存 CSV 与日志。不会默认录制视频。新改源码后先重新 build；verify 使用镜像中的已编译工程。

## 各项实验

```bash
bash tools/docker.sh open_loop
bash tools/docker.sh point goal:='[1.0,0.0]'
bash tools/docker.sh waypoints
bash tools/docker.sh scan fixed_frame:=base_link
bash tools/docker.sh wall_basic
bash tools/docker.sh avoid world:=maze
bash tools/docker.sh wall adaptive:=false
bash tools/docker.sh wall robot:=simplified
```

每次先 Ctrl+C 结束上一套系统。默认 world、朝向由脚本按模式选择，可继续传 launch 参数覆盖。

无图形界面的完整迷宫运行：

```bash
bash tools/docker.sh headless
```

此时 Gazebo 只运行服务器，不启动 Gazebo 客户端与 RViz。入口仍会使用官方模型和真实 Gazebo 物理插件。无界面运行成功也不能替代要求的图形演示。

## 图形界面

Ubuntu 24 的 Wayland 桌面通常同时提供 XWayland。请从本人桌面终端运行脚本，确保 DISPLAY 和 XAUTHORITY 正确，宿主机已安装 xauth。

脚本提取当前会话 X11 cookie，生成临时授权文件，只读传入容器，退出后删除；不会执行 xhost + 全局放开访问。容器以宿主 UID/GID 运行，results 不应产生 root 所有的文件。

默认使用 Mesa 软件渲染，无需 GPU 透传或 NVIDIA 容器运行时。若画面较慢，可先使用 headless 验证物理与控制，再在宿主机空闲时运行 GUI。不要把缺少图形设备误判成 ROS 通信错误。

## 构建和数据隔离

源码目录以只读形式挂载到 /workspace。每次运行会编译到容器 /tmp/micromouse-build、/tmp/micromouse-install 和 /tmp/micromouse-log，容器删除后清理；不会加载宿主 Jazzy 的 install。image 内也保存一份编译和测试过的工程。

Gazebo CSV 写入 /results，对应宿主机 results，文件名包含模式和时间戳。镜像标签为 micromouse:humble。

## 常见检查

- 镜像拉取超时：检查 Docker Hub 网络和本机已配置的镜像服务；不要下载来源不明的替代镜像。
- 找不到 Compose：安装 Docker Compose 插件，确保 docker compose version 可运行。
- 无 DISPLAY 或无 cookie：使用桌面终端，确认 XWayland 与当前 XAUTHORITY；也可先运行 headless。
- GUI 启动但无雷达或里程计：查看容器输出中的插件加载信息，确认当前 world、机器人生成与 /clock。
- 模型加载失败：默认使用容器安装的 turtlebot3_gazebo 和 turtlebot3_description，模型搜索路径由 launch 设置。
- DDS 不通：容器使用 host 网络，ROS_DOMAIN_ID 默认为 35 且 ROS_LOCALHOST_ONLY=1；宿主调试终端也需匹配，避免与其他项目混用。
- shell 模式只加载镜像内预编译工程。通过挂载源码运行实验时，wall 等模式会重新编译当前源码。

## 课程入口

ROS 功能包已统一为 maze_control。启动文件为 src/maze_control/launch/simulation.launch.py，默认参数依课程章节整理，详见 ../docs/course_alignment.md。宿主启动方式与镜像标签不变。

## 依据

[OSRF ROS 镜像](https://hub.docker.com/r/osrf/ros/tags?name=humble-desktop-full)

[Docker Compose 服务规范](https://docs.docker.com/reference/compose-file/services/)
