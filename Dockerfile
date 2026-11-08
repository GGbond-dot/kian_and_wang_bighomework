FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ros-humble-gazebo-ros-pkgs ros-humble-turtlebot3-description ros-humble-turtlebot3-gazebo ros-humble-xacro python3-colcon-common-extensions python3-yaml libgl1-mesa-dri mesa-utils && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends xvfb xauth ffmpeg wmctrl python3-pil && rm -rf /var/lib/apt/lists/*
RUN apt-get update -o Dir::Etc::sourcelist="sources.list" -o Dir::Etc::sourceparts="-" -o Acquire::http::Timeout="30" && apt-get install -y --no-install-recommends liburdfdom-tools && rm -rf /var/lib/apt/lists/*
ARG COURSE_UID=1000
ARG COURSE_GID=1000
RUN if ! getent group "$COURSE_GID" >/dev/null; then groupadd --gid "$COURSE_GID" course; fi; if ! getent passwd "$COURSE_UID" >/dev/null; then useradd --uid "$COURSE_UID" --gid "$COURSE_GID" --home-dir /tmp/micromouse-home --no-create-home course; fi
WORKDIR /opt/micromouse
COPY src ./src
COPY tests ./tests
COPY tools ./tools
COPY docker ./docker
COPY compose.yaml ./compose.yaml
RUN source /opt/ros/humble/setup.bash && colcon build --base-paths src --packages-select maze_control && python3 -m unittest discover -s tests -v
ENV TURTLEBOT3_MODEL=burger
ENV ROS_DOMAIN_ID=35
ENV ROS_LOCALHOST_ONLY=1
ENTRYPOINT ["bash", "/opt/micromouse/docker/entrypoint.sh"]
CMD ["wall"]
