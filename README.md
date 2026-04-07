# ROS 2 Pick-and-Place Demonstration in Gazebo with MoveIt 2

> **Simulation-only** · ROS 2 Humble · Gazebo Classic 11 · MoveIt 2

A reproducible, end-to-end pick-and-place pipeline for a custom 3-DOF robotic arm.
The robot identifies a cube on a table, plans a collision-free trajectory with MoveIt 2,
grasps the object, transports it, and places it at the target pose—all inside Gazebo.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Repository Layout](#repository-layout)
3. [Prerequisites](#prerequisites)
4. [Build & Launch](#build--launch)
5. [Running the Pick-and-Place Demo](#running-the-pick-and-place-demo)
6. [Metrics & Validation](#metrics--validation)
7. [Recording a Demo Video](#recording-a-demo-video)
8. [Design Decisions](#design-decisions)
9. [Troubleshooting](#troubleshooting)
10. [CV-Ready Results Write-Up](#cv-ready-results-write-up)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Gazebo Classic 11                                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │  Table   │  │  Cube    │  │  3-DOF Arm + Grip  │    │
│  └──────────┘  └──────────┘  └────────────────────┘    │
│        ▲              ▲               ▲                 │
│        │              │               │                 │
│   gazebo_ros2_control + joint_state_broadcaster         │
└────────┬──────────────┬───────────────┬─────────────────┘
         │              │               │
   ┌─────▼──────────────▼───────────────▼──────┐
   │           ROS 2 Humble (DDS)              │
   │  ┌────────────────────────────────────┐   │
   │  │   MoveIt 2 (move_group node)       │   │
   │  │   • OMPL planner (RRTConnect)      │   │
   │  │   • Planning scene (table+cube)    │   │
   │  │   • Trajectory execution           │   │
   │  └────────────────────────────────────┘   │
   │  ┌────────────────────────────────────┐   │
   │  │  pick_and_place_node (Python)      │   │
   │  │  • Pre-grasp → Grasp → Lift        │   │
   │  │  • Transport → Place → Retreat     │   │
   │  │  • Metrics logger (CSV)            │   │
   │  └────────────────────────────────────┘   │
   └───────────────────────────────────────────┘
```

### Node Graph

| Node | Purpose |
|---|---|
| `gazebo` | Physics simulation, renders world |
| `robot_state_publisher` | Publishes `/tf` from URDF + joint states |
| `joint_state_broadcaster` | Reads Gazebo joint states → `/joint_states` |
| `joint_trajectory_controller` | Accepts trajectory goals from MoveIt 2 |
| `gripper_controller` | Controls gripper open/close |
| `move_group` | MoveIt 2 planning + execution pipeline |
| `pick_and_place_node` | Orchestrates the demo sequence |

---

## Repository Layout

```
pick_and_place_ws/
└── src/
    └── pick_and_place/
        ├── CMakeLists.txt
        ├── package.xml
        ├── urdf/
        │   ├── arm.urdf.xacro          # 3-DOF arm + gripper macro
        │   ├── arm.gazebo.xacro         # Gazebo-specific tags
        │   └── arm.ros2_control.xacro   # ros2_control hardware interface
        ├── config/
        │   ├── controllers.yaml         # ros2_control controller config
        │   ├── moveit_config.yaml        # MoveIt 2 planner settings
        │   ├── kinematics.yaml          # KDL kinematics solver
        │   ├── joint_limits.yaml        # Joint limits override
        │   └── moveit_controllers.yaml  # MoveIt→controller mapping
        ├── launch/
        │   ├── gazebo.launch.py         # Gazebo + robot spawn
        │   ├── moveit.launch.py         # MoveIt 2 move_group
        │   └── demo.launch.py          # Full demo (gazebo + moveit + script)
        ├── worlds/
        │   └── table_cube.world         # Gazebo world with table + cube
        ├── scripts/
        │   ├── pick_and_place_node.py   # Main demo orchestrator
        │   └── metrics_logger.py        # CSV metrics collection
        ├── rviz/
        │   └── moveit.rviz             # RViz2 config for visualization
        └── test/
            └── test_metrics.py          # Validation / multi-trial runner
```

---

## Prerequisites

| Dependency | Version | Install |
|---|---|---|
| Ubuntu | 22.04 LTS | — |
| ROS 2 | Humble Hawksbill | `sudo apt install ros-humble-desktop` |
| Gazebo Classic | 11.x | `sudo apt install ros-humble-gazebo-ros-pkgs` |
| MoveIt 2 | Humble branch | `sudo apt install ros-humble-moveit` |
| ros2_control | Humble | `sudo apt install ros-humble-ros2-control ros-humble-ros2-controllers` |
| gazebo_ros2_control | Humble | `sudo apt install ros-humble-gazebo-ros2-control` |
| Python deps | — | `pip install pandas matplotlib` (for metrics) |

```bash
# One-liner for all ROS 2 deps:
sudo apt install -y \
  ros-humble-desktop \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-moveit \
  ros-humble-ros2-control \
  ros-humble-ros2-controllers \
  ros-humble-gazebo-ros2-control \
  ros-humble-moveit-planners-ompl \
  ros-humble-moveit-ros-move-group \
  ros-humble-moveit-simple-controller-manager
```

---

## Build & Launch

```bash
# 1. Clone / copy the workspace
cd ~/pick_and_place_ws

# 2. Build
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash

# 3. Launch Gazebo + controllers
ros2 launch pick_and_place gazebo.launch.py

# 4. In a new terminal — launch MoveIt 2
source install/setup.bash
ros2 launch pick_and_place moveit.launch.py

# 5. In a new terminal — run the demo
source install/setup.bash
ros2 run pick_and_place pick_and_place_node.py
```

Or use the combined launcher:

```bash
ros2 launch pick_and_place demo.launch.py
```

---

## Running the Pick-and-Place Demo

The `pick_and_place_node` executes six phases:

1. **Home** — move to a known joint configuration.
2. **Pre-grasp** — position end-effector above the cube.
3. **Grasp** — descend, close gripper.
4. **Lift** — raise with cube.
5. **Place** — move to target location, lower, open gripper.
6. **Retreat** — withdraw and return to home.

Each phase logs planning time, execution time, and end-effector pose to CSV.

---

## Metrics & Validation

Run a batch of N trials:

```bash
ros2 run pick_and_place pick_and_place_node.py --ros-args -p num_trials:=10
```

Metrics are saved to `~/.ros/pick_place_metrics.csv`. Columns:

| Field | Description |
|---|---|
| `trial` | Trial number |
| `phase` | Phase name (pre_grasp, grasp, …) |
| `planning_time_s` | OMPL planning time (seconds) |
| `execution_time_s` | Trajectory execution wall time |
| `ee_x, ee_y, ee_z` | Actual end-effector position |
| `target_x, target_y, target_z` | Desired end-effector position |
| `position_error_m` | Euclidean distance |
| `success` | Boolean — phase completed without error |

Aggregate results with:

```bash
python3 src/pick_and_place/scripts/metrics_logger.py analyze
```

---

## Recording a Demo Video

```bash
# Option A: Gazebo built-in recorder
gz log -d 1    # start recording
gz log -d 0    # stop

# Option B: Screen capture (recommended for CV submission)
# Use OBS Studio or SimpleScreenRecorder:
sudo apt install simplescreenrecorder
simplescreenrecorder   # select Gazebo + RViz windows
```

Suggested demo video outline (60–90 s):

1. Show Gazebo world (table, cube, robot) — 5 s
2. Show RViz with MoveIt planning scene — 5 s
3. Run demo, narrate each phase — 40 s
4. Show terminal metrics summary — 10 s

---

## Design Decisions

| Decision | Rationale |
|---|---|
| 3-DOF arm (shoulder_pan, shoulder_lift, elbow) | Minimal complexity that still demonstrates planning in 3D workspace. Easy to extend to 6-DOF. |
| Prismatic gripper (1-DOF) | Simple actuation; avoids complex finger kinematics while demonstrating grasp/release. |
| Gazebo Classic over Ignition | Better ROS 2 Humble integration, more community examples, fewer version quirks at time of writing. |
| OMPL RRTConnect planner | Fast, reliable for low-DOF arms; works out of the box with MoveIt 2. |
| Python orchestrator (not C++) | Faster iteration, easier to read/modify for portfolio demos. MoveIt Python bindings are sufficient for this scope. |
| CSV metrics (not rosbag) | Lightweight, easy to analyze with pandas, no extra tooling required. |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Controller not found` | Ensure `gazebo.launch.py` fully loads before starting MoveIt. Use `demo.launch.py` with built-in delays. |
| Cube falls through table | Check `<collision>` tags in world file and increase `<mu>` friction. |
| MoveIt cannot find IK solution | Verify `kinematics.yaml` solver is `kdl_kinematics_plugin/KDLKinematicsPlugin` and joint limits match URDF. |
| Gripper doesn't close | Confirm `gripper_controller` is loaded: `ros2 control list_controllers`. |
| Planning fails (timeout) | Increase `planning_time` in `moveit_config.yaml` or reduce planning scene complexity. |

---

## CV-Ready Results Write-Up

### Project: Simulated Robotic Pick-and-Place with ROS 2 & MoveIt 2

**Summary.**
Designed and implemented a complete pick-and-place pipeline for a custom
3-DOF robotic arm in Gazebo simulation. The system uses MoveIt 2 for
collision-aware motion planning (OMPL/RRTConnect) and ros2_control for
joint-level trajectory tracking. A Python orchestration node drives a
six-phase manipulation sequence (home → pre-grasp → grasp → lift → place
→ retreat) and logs quantitative metrics per trial.

**Technical Contributions.**

- Authored a parametric URDF/Xacro model of a 3-DOF revolute arm with a
  1-DOF prismatic gripper, including inertial properties, collision
  geometry, Gazebo plugins, and ros2_control hardware interfaces.
- Configured MoveIt 2 with OMPL planning, KDL kinematics, and a custom
  planning scene (table as collision object) to ensure safe trajectories.
- Built a ROS 2 Python node that sequences Cartesian and joint-space goals
  through the MoveIt action interface, with error handling and retry logic.
- Implemented an automated metrics pipeline that records planning time,
  execution time, and end-effector pose error across N configurable trials
  and exports results to CSV for statistical analysis.

**Representative Results (10-trial batch).**

| Metric | Mean | Std Dev |
|---|---|---|
| Planning time | ~0.05 s | ~0.02 s |
| Execution time (full cycle) | ~12 s | ~1.5 s |
| End-effector position error | < 5 mm | < 2 mm |
| Success rate | 100 % | — |

*(Values are representative targets for a well-tuned setup; actual numbers
should be replaced after running your own trials.)*

**Tools & Technologies.**
ROS 2 Humble, MoveIt 2, Gazebo Classic 11, OMPL, ros2_control, URDF/Xacro,
Python, pandas.

---

## License

MIT — see [LICENSE](LICENSE).
