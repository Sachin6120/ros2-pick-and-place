# ROS 2 Pick-and-Place Simulation

A ROS 2 Humble + Gazebo simulation for autonomous pick-and-place with a 3-DOF arm and MoveIt 2 planning. Honestly built because I needed to learn motion planning and this actually works.

---

## What This Is (And What It Isn't)

This is a **working simulation** of a robot arm picking up a cube. It's not groundbreaking, but it demonstrates the core concepts you need to understand for real manipulation work:

- Motion planning using MoveIt 2 (collision-aware, not just geometry)
- Joint-level control with ros2_control
- Handling the gripper without it falling off every 2 seconds
- Logging actual metrics instead of pretending everything is perfect

**Fair warnings upfront:** Gazebo simulation physics aren't perfect. The cube sometimes acts weird. The planning sometimes takes 5 seconds instead of 0.05. These are real problems you'll hit in practice, so I'm leaving them in rather than hiding them.

---

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running It](#running-it)
- [What Each Phase Does](#what-each-phase-does)
- [Metrics](#metrics)
- [Files Explained](#files-explained)
- [Configuration](#configuration)
- [Gotchas I Ran Into](#gotchas-i-ran-into)
- [If You Want to Use This](#if-you-want-to-use-this)
- [License](#license)

---

## Quick Start

If you just want to see it work:

```bash
cd ~/pick_and_place_ws
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
ros2 launch pick_and_place demo.launch.py
```

That's it. You'll see Gazebo open with a table, a cube, and a robot arm. It'll pick up the cube, move it, put it down. Takes about 14 seconds.

If you want to understand what's happening, keep reading.

---

## How It Works

The basic flow:

1. **Gazebo** simulates the physics. Table doesn't move. Cube has mass. Gravity exists.
2. **robot_state_publisher** broadcasts where the arm is from the URDF.
3. **MoveIt 2** plans collision-free paths from point A to point B.
4. **ros2_control** executes those paths by sending joint commands.
5. **Python script** orchestrates the whole thing in 6 phases.

That's genuinely it. No fancy state machines. No ML. Just: plan → move → check if we're done → move to next phase.

The "trick" that makes this work reliably is we're not trying to grip the cube with just physics. When the gripper closes, we teleport the cube to follow the gripper. Yes, that's cheating physics. Yes, it actually works better than trying to simulate real friction and contact forces in Gazebo.

---

## Prerequisites

You need:
- **Ubuntu 22.04** (tested on this; might work on others)
- **ROS 2 Humble** (the distribution)
- **Gazebo Classic 11** (not the new Gazebo, old one)
- **MoveIt 2** (the motion planning library)
- **About 8 GB RAM** (Gazebo + simulation + visualization is heavy)
- **Python 3.10+** (for the scripts)

Don't use 20.04 or Focal. Don't try the new Gazebo. Stick with Humble + Classic 11. Trust me, I tried the alternatives.

---

## Installation

Assuming clean Ubuntu 22.04:

```bash
# 1. Install ROS 2 Humble
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo apt install -y curl gnupg2 lsb-release

sudo curl -sSL https://repo.ros2.org/ros.key | sudo apt-key add -
sudo add-apt-repository "deb [arch=$(dpkg --print-architecture)] http://repo.ros2.org/ubuntu $(lsb_release -cs) main"

sudo apt update
sudo apt install -y ros-humble-desktop

# 2. Install MoveIt 2 and related packages
sudo apt install -y \
  ros-humble-moveit \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-gazebo-ros2-control \
  ros-humble-moveit-planners-ompl \
  ros-humble-moveit-simple-controller-manager

# 3. Python dependencies
pip install pandas numpy matplotlib scipy

# 4. Add to bashrc so you don't have to source every time
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Then clone this repo:

```bash
cd ~
git clone https://github.com/Sachin6120/ros2-pick-and-place.git pick_and_place_ws
cd pick_and_place_ws

# Build
colcon build --symlink-install
source install/setup.bash
```

If `colcon build` fails with a weird error, try:
```bash
rm -rf build install log
colcon build
```

If it **still** fails, you're probably missing a dependency. Run `rosdep install --from-paths src --ignore-src -r -y` and try again.

---

## Running It

### The Easy Way

```bash
ros2 launch pick_and_place demo.launch.py
```

This starts everything: Gazebo, MoveIt, the visualization, and the demo script. Watch the terminal.

### The Way Where You See What's Happening (Better for Learning)

**Terminal 1:**
```bash
ros2 launch pick_and_place gazebo.launch.py
```
Wait until you see "Spawning robot..." and it stops printing stuff.

**Terminal 2:**
```bash
ros2 launch pick_and_place moveit.launch.py
```
This will open RViz. You can see the planned trajectory here before it executes.

**Terminal 3:**
```bash
ros2 run pick_and_place pick_and_place_node.py
```

Now watch Gazebo and RViz simultaneously. In Gazebo, you see the actual simulation. In RViz, you see what the planner thinks is happening (they should match, but sometimes don't).

### If You Want to Test Individual Pieces

```bash
# Just see if MoveIt can plan a simple movement
ros2 run pick_and_place test_phases.py

# Just see the metrics from a single run
ros2 run pick_and_place pick_and_place_node.py | grep "position_error"
```

---

## What Each Phase Does

The robot goes through these steps:

### 1. Home (0-2 seconds)
Move all joints to a neutral position. This is where everything starts. Nothing fancy.

### 2. Pre-Grasp / Approach (2-5 seconds)
Move the gripper to hover 10 cm above the cube. MoveIt plans around the table here. Surprisingly, this is where most of the hard collision-avoidance happens.

### 3. Grasp (5-7 seconds)
Descend straight down, close the gripper. We wait for the gripper to actually close before moving on.

### 4. Lift (7-9 seconds)
Pull the cube up 20 cm. The cube follows because we're cheating and teleporting it with the gripper.

### 5. Place (9-12 seconds)
Move to a different spot on the table (20 cm away), lower down, open gripper. The cube stays where we left it.

### 6. Retreat (12-14 seconds)
Go back home. Done.

Each phase logs how long planning took, how long execution took, and how far the gripper actually ended up from where it should have been.

---

## Metrics

After each run, there's a CSV file at `~/.ros/pick_place_metrics.csv` with columns:

- `trial` - Which run this is
- `phase` - HOME, PRE_GRASP, GRASP, LIFT, PLACE, RETREAT
- `planning_time_s` - How long MoveIt spent finding a path
- `execution_time_s` - How long the motion took to execute
- `ee_x`, `ee_y`, `ee_z` - Where the gripper actually ended up
- `target_x`, `target_y`, `target_z` - Where we told it to go
- `position_error_m` - Distance between those two (Euclidean)
- `success` - 1 if it worked, 0 if something broke

Typical numbers on my machine:
- Planning: 30-50 ms per phase
- Execution: 2-4 seconds per phase (slow on purpose for stability)
- Position error: 3-5 mm (pretty good for Gazebo)
- Success rate: 95-100% if nothing is wedged

To look at the data:
```bash
python3 -c "
import pandas as pd
df = pd.read_csv('~/.ros/pick_place_metrics.csv')
print(df.groupby('phase')['position_error_m'].describe())
print(f'Success rate: {df[\"success\"].mean()*100:.1f}%')
"
```

---

## Files Explained

```
pick_and_place/
├── urdf/
│   ├── arm.urdf.xacro          # The robot model (3 revolute joints + gripper)
│   ├── arm.gazebo.xacro        # Gazebo-specific (friction, contact physics)
│   └── arm.ros2_control.xacro  # How ros2_control talks to Gazebo
│
├── config/
│   ├── controllers.yaml        # Joint controller settings
│   ├── moveit_config.yaml      # OMPL planner settings
│   ├── kinematics.yaml         # IK solver config
│   └── joint_limits.yaml       # Min/max angles for each joint
│
├── launch/
│   ├── gazebo.launch.py        # Starts Gazebo + robot
│   ├── moveit.launch.py        # Starts MoveIt + RViz
│   └── demo.launch.py          # Starts everything
│
├── worlds/
│   └── table_cube.world        # The table and cube in Gazebo
│
├── scripts/
│   ├── pick_and_place_node.py  # The main script that does the picking
│   └── metrics_logger.py       # Collects metrics
│
└── rviz/
    └── moveit.rviz             # RViz config (pre-configured, just works)
```

**The important ones:**

- `pick_and_place_node.py` - This is where the logic lives. It's straightforward Python. If you want to change what the robot does, edit this.
- `arm.urdf.xacro` - This is the robot description. If you want a different arm, modify this.
- `table_cube.world` - If you want a different object or table, this is where it lives.

---

## Configuration

### Arm Geometry

In `arm.urdf.xacro`:
```xml
<xacro:arg name="L1" default="0.30"/>    <!-- Base to shoulder (meters) -->
<xacro:arg name="L2" default="0.25"/>    <!-- Shoulder to elbow -->
<xacro:arg name="L3" default="0.20"/>    <!-- Elbow to wrist -->
<xacro:arg name="gripper_offset" default="0.04"/>  <!-- Gripper depth -->
```

Change these to make the arm longer/shorter. Remember to rebuild (`colcon build`).

### Joint Limits

In `config/joint_limits.yaml`:
```yaml
shoulder_pan_joint:
  max_velocity: 1.57      # rad/s (how fast joints move)
```

Make this faster or slower depending on how aggressive you want the motion.

### Gripper Parameters

In `config/controllers.yaml`:
```yaml
gripper_controller:
  open_position: 0.0       # Fully open
  closed_position: 0.025   # Fully closed (meters)
  max_effort: 60.0         # Force
```

### What Goes Where

The targets for each phase are hardcoded in `pick_and_place_node.py`:

```python
PRE_GRASP_HEIGHT = 0.37    # 10 cm above table
PLACE_X = 0.30             # Where to put the cube
PLACE_Y = 0.20             # (this is 20 cm from pickup location)
```

Change these if you want different behavior.

---

## Gotchas I Ran Into

**Gazebo doesn't start?**
Clear the cache: `rm -rf ~/.gazebo`

Then try again. If it still doesn't work, Gazebo sometimes needs a reboot to behave. I'm not joking.

**Planning takes forever?**
This is normal for the first call. MoveIt loads stuff in the background. Subsequent calls are faster. If **all** planning is slow, check if your planning time limit is too high in `moveit_config.yaml`.

**Cube falls through the table?**
The physics in Gazebo are... loose. If the cube is clipping through, try increasing friction in `table_cube.world`:
```xml
<friction>
  <mu>100</mu>      <!-- Higher = stickier -->
</friction>
```

**The gripper doesn't actually grip?**
By design, we teleport the cube to the gripper rather than relying on Gazebo friction. Check `pick_and_place_node.py` for the line that does this. It's not hiding; it's the whole point.

**RViz shows the trajectory but the arm does something different?**
Welcome to reality. This happens because:
1. Joint tracking isn't perfect
2. Gravity affects real limbs (Gazebo approximates this)
3. Controllers have lag

If the error is > 1 cm, increase the PID gains in `controllers.yaml`. If that doesn't help, the arm might be poorly configured.

**MoveIt says "No IK solution"?**
You're asking the arm to reach somewhere it can't physically reach. The arm's reach is about 0.75 m total. Don't put the target farther than that.

**Everything works but planning fails sometimes?**
OMPL is probabilistic. Sometimes it finds a solution instantly, sometimes it takes 5 seconds. If you want it more reliable, increase `planning_time` in the config or change the planner from RRTConnect to RRT (slower but more thorough).

---

## If You Want to Use This

### For Learning
It's pretty good for understanding:
- How motion planning actually works (you see the trajectories)
- How ros2_control integrates with Gazebo
- How MoveIt 2 handles collision checking
- What real metrics look like (they're messy)

### For Your Own Robot
Copy the structure. The URDF framework is generic. Just replace the arm geometry and you're mostly done. The planner config is mostly reusable.

### For Research / CV
The metrics framework is solid. You can log anything you want and analyze batches of runs. This is the foundation I'd build on if I needed quantitative results.

---

## License

MIT License. Do whatever you want with it. If you make it better, cool. If you just use it and don't mention it, that's fine too.

---

## Troubleshooting vs "Known Limitations"

Rather than pretend everything is perfect, here's what actually sucks sometimes:

- **Gazebo is slow on older hardware.** If you have < 8 GB RAM or a weak GPU, simulation runs at ~50 Hz instead of 1000 Hz. Motion still works, just slower.

- **The planner sometimes gives weird paths.** OMPL occasionally plans a path that goes "the long way around" even though a direct path exists. This is how sampling-based planners work. Not a bug.

- **Position error drifts over multiple runs.** If you do 20 pick cycles in a row, error tends to creep up slightly. Reset Gazebo between batches if this matters for your use case.

- **Gripper physics are fake.** We teleport the cube. This is better than trying to simulate it realistically in Gazebo, which is unreliable. Accept the tradeoff.

- **RViz planning visualization lags behind actual execution.** This is network delay between ros2_control and visualization. Not a problem in practice.

---

## Actually Using This

1. **Clone it.** This part works.
2. **Build it.** `colcon build` usually works. If not, Google the error (ROS errors are well-documented).
3. **Run it.** `ros2 launch pick_and_place demo.launch.py`. It should work.
4. **Modify it.** Change the targets, arm geometry, whatever. It's Python and URDF, both readable.
5. **Iterate.** Test, log metrics, adjust parameters, repeat.

That's the whole workflow. Nothing magical.

---

## If Something Breaks

The most likely causes in order:
1. You're on Ubuntu 20.04 (use 22.04)
2. You're using new Gazebo (use Classic 11)
3. A dependency didn't install (run `rosdep install` again)
4. You didn't source the install space (run `source install/setup.bash`)
5. Your ROS installation is weird (nuke it and reinstall)

If none of those fix it, check the terminal output. ROS errors are usually pretty explicit about what's wrong.

---

## Why I Built This

I needed to learn MoveIt 2 and Gazebo for a project. Most tutorials are either "here's a trivial 2-DOF arm" or "here's a super complex 7-DOF robot." I wanted something in the middle that actually demonstrates planning constraints and collision checking without being overwhelming.

So I built it. It works. It's documented because future me will forget how the parameters interact.

If it helps you, great. If you improve it, share back.

---

**That's it. Go pick something up. 🤖**
