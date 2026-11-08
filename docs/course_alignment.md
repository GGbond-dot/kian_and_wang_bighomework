# 课程文档对照与修订

核对日期：2026-11-07。课程知识库为 [机器人感知与控制综合实践 2026](https://www.yuque.com/shellcore/rpide7)。本次读取课程目录和公开正文，重点核对考核、Ch3 工作空间与节点、Ch4 Launch/TF、Ch5 URDF、Ch6 运动控制、Ch7 感知与墙跟随。课程正文仅用于核对，没有将整套讲义复制到工程。

## 采用的约定

| 课程章节 | 工程调整 |
|---|---|
| [课程考核](https://www.yuque.com/shellcore/rpide7/ogornlkgxk4eqrx2) | 保持 Humble、官方 Burger、Gazebo/RViz、自定义碰撞迷宫、一键 launch；不新增 SLAM 或全局导航依赖 |
| [Ch6.2 点到点](https://www.yuque.com/shellcore/rpide7/uf21ur1nh3b17swm) | 所有控制节点统一到 maze_control；默认 `(1,0)`，距离/角度增益 0.3/0.8，容差 0.05 m；注册 tb3_point2point |
| [Ch6.3 航点](https://www.yuque.com/shellcore/rpide7/czkn1yendbfp2fxc) | 默认四点 `(1,0),(1,1),(0,1),(0,0)`，回原点停车；注册 tb3_waypoints，可传自定义折线 |
| [Ch7.2 雷达](https://www.yuque.com/shellcore/rpide7/kpx2gfger7atm1cg) | scan_region 按角度划分前、左、右；前方最小值，左右中值；持续打印距离 |
| [Ch7.3 避障](https://www.yuque.com/shellcore/rpide7/zkg7vifg3g2fbo3u) | tb3_avoid 使用 sensor_data QoS，0.8 m 阈值、0.15 m/s 直行、遇障原地转向；Ctrl+C 主动发零速度 |
| [Ch7.4 左墙跟随](https://www.yuque.com/shellcore/rpide7/yyll3ya9h21p0mgo) | 增加基础 tb3_wall_follower、0.4 m 左墙距、0.35 m 前向阈值、10 Hz 规则控制；提供对应宽走廊 world |
| [Ch4.1 Launch](https://www.yuque.com/shellcore/rpide7/cpyscwriox2vnc88) | 安装 Python launch 及 YAML；按模式自动选择场景、出生坐标、课程节点和 RViz 配置 |
| [Ch5.3 URDF](https://www.yuque.com/shellcore/rpide7/gn5onn2crxz7l2o4) | 保留完整 link/joint/visual/collision/inertial 简化模型；增加 check_urdf 工具供检查；默认仍为课程要求的官方 Burger |

当前目录承担教材 `~/ros2maze_ws` 工作空间的角色，不强制修改使用者的目录名。`src/maze_control` 承担教材同名功能包的角色。原来的 `micromouse` ROS 包名已迁移，Docker 镜像和 Compose 服务名仍为 micromouse，以便继续使用原来的主机启动命令。

## 示例中的不一致如何处理

1. 雷达示例同时出现从 0 开始的 360° 数组和“数组中间是前方”的写法。工程始终依据消息角度并归一化，正确处理 −15° 在 0～2π 扫描中的尾部索引，不照搬中间索引或边缘截断。
2. 独立避障示例的右转文字与正角速度不一致。ROS 中正角速度为逆时针左转，工程约定遇障右转，因此使用负角速度；课堂验证时可按实际要求自行切换方向。
3. Ch7.2 测距教学采用侧方中值，Ch7.4 基础墙跟随采用侧方最小值。工程分别实现两种统计，共用测量过滤与角度计算，不把不同统计的输出混写为同一种结果。
4. 部分示例将 SDF 内容传给 robot_state_publisher，或假设所有官方 URDF 都含 Gazebo 插件。工程保持 URDF/Xacro 给 robot_state_publisher、官方带插件 SDF 给 Gazebo 的有效组合，同时兼容安装包中的 .urdf 和 .urdf.xacro 路径。
5. 课程 world 示例存在省略 pose 项的写法；本工程使用完整 x/y/z/roll/pitch/yaw，并保证碰撞墙高覆盖激光高度。course.world 按约 7.5 m 场景和底部走廊原理重新编写，不声称逐字复现讲义 world。
6. 基础讲义通常示范多个终端依次启动，综合考核明确要求一键启动。最终入口负责启动整套系统，单节点 ros2 run 只作为学习与单模块实验方法。
7. 示范范围内缺测可按最大量程处理。本工程额外区分正无穷无回波与整区 NaN 等无效数据；整区无效时停车，保留传感器超时停车和大角差先转向保护。

## 保留的拓展

原来已验证的优化墙跟随作为 tb3_wall_follower_optimized 保留，默认 `wall` 命令继续运行原蛇形迷宫。它使用里程计转角状态机、走廊方向约束、自适应速度及原先调试的正侧方分区。基础模式使用 `wall_basic` 命令和单独的宽走廊，两种模式的参数及算法区别明确记录，避免把拓展策略说成课堂基础代码。

课程允许自行修改参数与环境，不要求所有组使用相同 world。选择自定义矩形墙迷宫符合综合考核要求。讲义提供的多种迷宫及其失败案例属于可进一步测试的资源，本次不宣称全部已经通过。

## 验证与材料范围

新增回归检查覆盖课程 P 增益与 5 cm 阈值、矩形闭环目标、0～2π/−π～π 分区及侧方中值、基础墙跟随转向符号。另在 Humble 中通过真实 ROS 发布订阅检查退出停车：注入合成传感器使控制器前进，再发 SIGINT，确认最后速度为零且进程正常退出。这个通信测试与 Gazebo 动力学实验明确区分。

Gazebo 验证采用官方 Burger、真实传感器插件和保存的 CSV，当前修订结果放在 results/course_alignment。旧 results/gazebo 和旧文档/录像保留为历史资料。本次不生成新的讲解视频或伪造人工操作记录；最终演示由组员自己录制并讲解。

所有自编代码继续按使用者要求不添加注释，因此与任务书“注释清晰”的文字要求存在差异。设计和出处集中记录在本文及 README，组员需要自行理解、检查并据实完善。没有编造组员姓名或人工贡献。

## 本轮验证结果

课程对齐后的 21 项自动化测试通过，另通过退出停车 ROS 通信检查。Docker 中官方 Burger 的实际 Gazebo 记录如下，数据文件均位于 results/course_alignment：

| 模式 | 用时 s | 结果 |
|---|---:|---|
| 开环运动 | 6.3 | DONE |
| 课程目标点 (1,0) | 10.3 | DONE，终点误差 0.0384 m |
| 矩形闭环回原点 | 46.5 | DONE，终点误差 0.0406 m |
| 反应式避障 | 14.4 | 出现 AVOID/FORWARD 状态 |
| 课程基础墙跟随 | 57.4 | DONE |
| 优化蛇形迷宫 | 141.1 | DONE |

本轮未重新录制演示视频。原先优化模式的历史固定速度对照保留，但没有把该旧数据伪称为本轮所有模式的新参数实验。course_sources.json，其中记录所用课程章节、更新日期和读取内容校验值。

## 教师报告模板更新

已依据本地《课程报告-机器人感知与控制综合实践》模板完成十章报告，输出 deliverables/课程报告_kian_wang.docx，并新增 docs/答辩阅读指南.md。成员 kian 与 wang 按各 50% 提供分工建议，个人信息与实际贡献由本人确认。报告采用本轮六项 Gazebo 数据，旧报告归档；没有生成新的讲解视频。
