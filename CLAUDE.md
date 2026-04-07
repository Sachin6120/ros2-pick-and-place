# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ROS 2 Humble pick-and-place simulation with a custom 3-DOF robotic arm in Gazebo Classic 11, using MoveIt 2 for motion planning and ros2_control for hardware abstraction. Pure simulation — no real hardware.

Active workspace: `pick_and_place_ws/`. The `ros2_ws/` directory contains inactive skeleton packages.

## Build & Run Commands

```bash
# Build
cd ~/pick_and_place_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash

# Launch (three separate terminals, in order)
ros2 launch pick_and_place gazebo.launch.py      # Gazebo + controllers
ros2 launch pick_and_place moveit.launch.py      # MoveIt 2 move_group
ros2 run pick_and_place pick_and_place_node.py   # Demo orchestrator

# Or all-in-one (includes 20s/35s startup delays via TimerAction)
ros2 launch pick_and_place demo.launch.py

# Run with multiple trials for metrics collection
ros2 run pick_and_place pick_and_place_node.py --ros-args -p num_trials:=10

# Analyze collected metrics (CSV at ~/.ros/pick_place_metrics.csv)
python3 src/pick_and_place/scripts/metrics_logger.py analyze [--plot]
```

## Architecture

### Node Graph

```
Gazebo (physics) ──► gazebo_ros2_control plugin ──► ros2_control controllers
                                                     ├─ arm_controller (JointTrajectoryController)
                                                     └─ gripper_controller (GripperActionController)
                                                              ▲
                                                              │
pick_and_place_node.py ──► MoveIt 2 (move_group) ────────────┘
        │                  - OMPL RRTConnect planner
        │                  - KDL IK solver
        │
        └──► Gazebo SetEntityState service  (cube attach/detach hack)
```

### Package Structure (`src/pick_and_place/`)

- `urdf/` — Robot description: `arm.urdf.xacro` (kinematics), `arm.gazebo.xacro` (Gazebo plugins), `arm.ros2_control.xacro` (hardware interfaces)
- `config/` — `controllers.yaml` (PID gains), `moveit_config.yaml` (OMPL + inline SRDF), `kinematics.yaml` (KDL), `joint_limits.yaml`, `moveit_controllers.yaml`
- `launch/` — `gazebo.launch.py`, `moveit.launch.py`, `demo.launch.py`
- `scripts/` — `pick_and_place_node.py` (main orchestrator), `metrics_logger.py`
- `worlds/table_cube.world` — SDF world with table and dynamic cube

## Critical Non-Obvious Details

**Gazebo ros2_control plugin bug workaround**: `gazebo.launch.py` preprocesses the URDF via xacro and writes it to a temp file rather than passing it as a parameter string. This avoids a crash in `gazebo_ros2_control` when `robot_description` is passed directly as a parameter.

**Inline SRDF**: MoveIt's SRDF (planning groups, end-effector, collision disabling) is embedded as a YAML string inside `moveit_config.yaml` — there is no separate `.srdf` file.

**Custom analytical IK**: `pick_and_place_node.py` (lines 59–81) contains a hand-written 2-link law-of-cosines IK solver for the arm's lower two joints. This bypasses MoveIt's numerical KDL solver for speed.

**Cube grasp simulation**: The pick-and-place "grasp" is implemented by calling Gazebo's `SetEntityState` service to teleport the cube to the gripper pose each timestep — there is no real contact/friction simulation.

**Pick-and-place phase sequence**: Home → Pre-grasp → Grasp approach → Lift (cube attached) → Transport → Place (cube detached) → Retreat. Each phase logs planning/execution times and pose error to `~/.ros/pick_place_metrics.csv`.

**Controller PID tuning**: Gains are conservative (p=20, i=0.5, d=2) and tolerances are relaxed (0.15 rad goal tolerance) to accommodate Gazebo's physics instability.

**demo.launch.py timing**: Uses `TimerAction` delays — 20s before starting MoveIt, 35s before starting the pick-and-place node — to allow Gazebo and controllers to fully initialize.

**Optional Python deps**: `pandas` and `matplotlib` are only required for `metrics_logger.py analyze --plot`. The main demo node has no extra Python dependencies beyond standard ROS 2 packages.
