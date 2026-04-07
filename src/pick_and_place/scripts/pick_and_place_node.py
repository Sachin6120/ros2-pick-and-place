#!/usr/bin/env python3

import math
import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from control_msgs.action import FollowJointTrajectory
from control_msgs.action import GripperCommand as GripperCommandAction
from control_msgs.msg import GripperCommand
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from sensor_msgs.msg import JointState
from builtin_interfaces.msg import Duration

from gazebo_msgs.srv import SetEntityState
from gazebo_msgs.msg import EntityState
from geometry_msgs.msg import Pose, Twist

# ================== GEOMETRY ==================
BASE_HEIGHT = 0.05
L1 = 0.30
L2 = 0.25
L3 = 0.20
GRIPPER_OFFSET = 0.04
SHOULDER_Z = BASE_HEIGHT + L1

ARM_JOINTS = ["shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint"]

# ================== SCENE ==================
CUBE_X = 0.30
CUBE_Y = 0.0
TABLE_Z = 0.27
PLACE_X = 0.30
PLACE_Y = 0.20
CUBE_NAME = "cube"

# This is the distance from the end of L3 to the center of the fingers
# Adjusted to ensure the cube sits INSIDE the gripper
TCP_CENTER_OFFSET = 0.035 

GRIPPER_PHYSICALLY_OPEN = 0.0
GRIPPER_PHYSICALLY_CLOSED = 0.025
MOVE_TIME = 2.5 

# ================== IK & FK ==================
def solve_ik(x, y, z):
    q1 = math.atan2(y, x)
    r = math.sqrt(x*x + y*y)
    z_rel = z - SHOULDER_Z
    # We target the actual point where the cube should be
    a1, a2 = L2, L3 + GRIPPER_OFFSET
    d = math.sqrt(r*r + z_rel*z_rel)
    if d > a1 + a2 or d < abs(a1 - a2): return None
    cos_q3 = (d*d - a1*a1 - a2*a2) / (2*a1*a2)
    cos_q3 = max(-1.0, min(1.0, cos_q3))
    q3 = math.acos(cos_q3)
    angle = math.atan2(z_rel, r) + math.atan2(a2 * math.sin(q3), a1 + a2 * math.cos(q3))
    q2 = math.pi/2 - angle
    return (q1, q2, q3)

def solve_fk(q1, q2, q3):
    """Calculates actual wrist position (end of L3) from joint angles."""
    r = L2 * math.sin(q2) + (L3 + GRIPPER_OFFSET) * math.sin(q2 + q3)
    x = r * math.cos(q1)
    y = r * math.sin(q1)
    z = SHOULDER_Z + L2 * math.cos(q2) + (L3 + GRIPPER_OFFSET) * math.cos(q2 + q3)
    return (x, y, z)

# ================== NODE ==================
class PickAndPlaceNode(Node):
    def __init__(self):
        super().__init__("pick_and_place_node")
        self.arm_client = ActionClient(self, FollowJointTrajectory, "/arm_controller/follow_joint_trajectory")
        self.gripper_client = ActionClient(self, GripperCommandAction, "/gripper_controller/gripper_cmd")
        self.set_state_client = self.create_client(SetEntityState, "/set_entity_state")
        
        self.joint_sub = self.create_subscription(JointState, "/joint_states", self.joint_callback, 10)
        
        self.current_joints = [0.0, 0.0, 0.0]
        self.is_grasping = False
        
        # 50Hz is plenty for Gazebo and prevents service call bottlenecks
        self.timer = self.create_timer(0.02, self.on_timer_update) 

    def joint_callback(self, msg):
        try:
            mapping = {name: pos for name, pos in zip(msg.name, msg.position)}
            self.current_joints = [mapping[j] for j in ARM_JOINTS]
        except KeyError:
            pass

    def on_timer_update(self):
        """Moves the cube with the gripper in real-time if grasping."""
        if self.is_grasping:
            q1, q2, q3 = self.current_joints
            x, y, z = solve_fk(q1, q2, q3)
            
            # --- THE FIX: PROJECT OFFSET BASED ON ROTATION ---
            # Instead of a static X correction, we move the cube along the 
            # vector the arm is currently pointing (q1).
            # We subtract because the gripper extends 'out' from the wrist.
            target_x = x + (TCP_CENTER_OFFSET * math.cos(q1))
            target_y = y + (TCP_CENTER_OFFSET * math.sin(q1))
            
            # Vertical centering: cube is 0.05m tall, so -0.025 centers its origin
            self.set_cube_pose(target_x, target_y, z - 0.02)

    def move_to_xyz(self, x, y, z, name="move"):
        ik = solve_ik(x, y, z)
        if ik is None: 
            self.get_logger().error(f"IK failed for {name} at {x}, {y}, {z}")
            return False
        traj = JointTrajectory()
        traj.joint_names = ARM_JOINTS
        pt = JointTrajectoryPoint(positions=list(ik), time_from_start=Duration(sec=int(MOVE_TIME)))
        traj.points = [pt]
        goal = FollowJointTrajectory.Goal(trajectory=traj)
        self.arm_client.wait_for_server()
        future = self.arm_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        gh = future.result()
        if gh and gh.accepted:
            result_future = gh.get_result_async()
            rclpy.spin_until_future_complete(self, result_future)
        return True

    def move_gripper(self, pos):
        self.gripper_client.wait_for_server()
        goal = GripperCommandAction.Goal()
        goal.command = GripperCommand(position=pos, max_effort=100.0)
        future = self.gripper_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        time.sleep(0.8) # Reduced wait time for snappier feel

    def set_cube_pose(self, x, y, z):
        if not self.set_state_client.wait_for_service(timeout_sec=0.1): return False
        req = SetEntityState.Request()
        req.state = EntityState(name=CUBE_NAME)
        req.state.pose.position.x = float(x)
        req.state.pose.position.y = float(y)
        req.state.pose.position.z = float(z)
        req.state.pose.orientation.w = 1.0 
        req.state.reference_frame = "world"
        req.state.twist = Twist() 
        self.set_state_client.call_async(req)
        return True

    def run(self):
        self.get_logger().info("🚀 STARTING CENTERED PICK-AND-PLACE")
        self.move_gripper(GRIPPER_PHYSICALLY_OPEN)

        # 1. Approach (Hover above cube)
        self.move_to_xyz(CUBE_X, CUBE_Y, TABLE_Z + 0.12, "HOVER")
        
        # 2. Descent (Move to grasp height)
        # Note: We target the CUBE center, IK handles reaching it.
        self.move_to_xyz(CUBE_X, CUBE_Y, TABLE_Z + 0.04, "DESCENT")

        # 3. Grasp
        self.get_logger().info("🧲 Activating Grasp")
        self.move_gripper(GRIPPER_PHYSICALLY_CLOSED)
        self.is_grasping = True 
        time.sleep(0.2)

        # 4. Lift & Transit
        self.move_to_xyz(CUBE_X, CUBE_Y, TABLE_Z + 0.15, "LIFT")
        self.move_to_xyz(PLACE_X, PLACE_Y, TABLE_Z + 0.15, "TRANSIT")

        # 5. Place
        # Lower slightly more to ensure it touches the table before release
        self.move_to_xyz(PLACE_X, PLACE_Y, TABLE_Z + 0.025, "PLACE")
        time.sleep(0.5) 

        # 6. Release Sequence
        self.get_logger().info("🔓 Releasing...")
        self.is_grasping = False # Release virtual glue FIRST so it drops naturally
        time.sleep(0.1)
        self.move_gripper(GRIPPER_PHYSICALLY_OPEN)
        
        # 7. Vertical Retreat
        self.move_to_xyz(PLACE_X, PLACE_Y, TABLE_Z + 0.15, "RETREAT")
        self.get_logger().info("✅ TASK COMPLETE.")

def main():
    rclpy.init()
    node = PickAndPlaceNode()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()