"""Launch MoveIt 2 move_group for the pick-and-place arm."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import yaml


def load_yaml(package_name: str, file_name: str) -> dict:
    """Load a YAML file from a ROS 2 package share directory."""
    path = os.path.join(get_package_share_directory(package_name), file_name)
    with open(path, "r") as f:
        return yaml.safe_load(f)


def generate_launch_description():
    pkg_dir = get_package_share_directory("pick_and_place")
    xacro_file = os.path.join(pkg_dir, "urdf", "arm.urdf.xacro")

    robot_description = ParameterValue(
        Command(["xacro ", xacro_file]), value_type=str
    )

    # Load SRDF from the moveit_config.yaml (embedded)
    moveit_config = load_yaml("pick_and_place", "config/moveit_config.yaml")
    srdf_value = (
        moveit_config.get("move_group", {})
        .get("ros__parameters", {})
        .get("robot_description_semantic", {})
        .get("value", "")
    )

    kinematics = load_yaml("pick_and_place", "config/kinematics.yaml")
    joint_limits = load_yaml("pick_and_place", "config/joint_limits.yaml")
    moveit_controllers = load_yaml("pick_and_place", "config/moveit_controllers.yaml")

    # Compose parameters for move_group
    move_group_params = {
        "use_sim_time": True,
        "robot_description": robot_description,
        "robot_description_semantic": srdf_value,
        "robot_description_kinematics": kinematics,
        "robot_description_planning": joint_limits,
        "planning_plugin": "ompl_interface/OMPLPlanner",
        "default_planning_pipeline": "ompl",
        "request_adapters": (
            "default_planner_request_adapters/AddTimeOptimalParameterization "
            "default_planner_request_adapters/ResolveConstraintFrames "
            "default_planner_request_adapters/FixWorkspaceBounds "
            "default_planner_request_adapters/FixStartStateBounds "
            "default_planner_request_adapters/FixStartStateCollision "
            "default_planner_request_adapters/FixStartStatePathConstraints"
        ),
        "default_planning_pipeline": "ompl",
        "capabilities": "",
        "disable_capabilities": "",
        "moveit_manage_controllers": True,
        "trajectory_execution.allowed_execution_duration_scaling": 1.2,
        "trajectory_execution.allowed_goal_duration_margin": 0.5,
        "trajectory_execution.allowed_start_tolerance": 0.01,
        "publish_robot_description_semantic": True,
    }

    # Merge controller manager params
    if moveit_controllers:
        for key, val in moveit_controllers.get(
            "moveit_simple_controller_manager", {}
        ).get("ros__parameters", {}).items():
            move_group_params[f"moveit_simple_controller_manager.{key}"] = val
        move_group_params[
            "moveit_controller_manager"
        ] = "moveit_simple_controller_manager/MoveItSimpleControllerManager"

    # OMPL planner configs
    ompl_params = {
        "arm.default_planner_config": "RRTConnect",
        "arm.planner_configs": ["RRTConnect", "RRTstar"],
    }
    move_group_params.update(ompl_params)

    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[move_group_params],
    )

    # RViz2 with MoveIt panel
    rviz_config = os.path.join(pkg_dir, "rviz", "moveit.rviz")
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config],
        parameters=[
            {"robot_description": robot_description},
            {"robot_description_semantic": srdf_value},
            {"robot_description_kinematics": kinematics},
        ],
        output="screen",
    )

    return LaunchDescription([
        move_group_node,
        rviz_node,
    ])
