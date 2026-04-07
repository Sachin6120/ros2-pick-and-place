"""Launch Gazebo with the 3-DOF arm, table, and cube.

Fixed version:
- Correct robot spawn alignment with table
- Stable controller startup sequence
- Uses temp URDF workaround for gazebo_ros2_control
"""

import os
import subprocess
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    RegisterEventHandler,
    TimerAction,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def launch_setup(context):
    pkg_dir = get_package_share_directory("pick_and_place")

    xacro_file = os.path.join(pkg_dir, "urdf", "arm.urdf.xacro")
    world_file = os.path.join(pkg_dir, "worlds", "table_cube.world")
    controllers_file = os.path.join(pkg_dir, "config", "controllers.yaml")

    # ================= URDF PROCESS =================
    urdf_string = subprocess.check_output([
        "xacro",
        xacro_file,
        "controllers_file:=" + controllers_file,
    ]).decode("utf-8")

    urdf_tmp = os.path.join(tempfile.gettempdir(), "pick_place_arm.urdf")
    with open(urdf_tmp, "w") as f:
        f.write(urdf_string)

    # ================= GAZEBO =================
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("gazebo_ros"),
                "launch",
                "gazebo.launch.py",
            )
        ),
        launch_arguments={
            "world": world_file,
            "verbose": "true",
        }.items(),
    )

    # ================= ROBOT STATE PUBLISHER =================
    robot_state_pub = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        arguments=[urdf_tmp],
        parameters=[{"use_sim_time": True}],
        output="screen",
    )

    # ================= SPAWN ROBOT (FIXED) =================
    spawn_entity = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        arguments=[
            "-file", urdf_tmp,
            "-entity", "pick_place_arm",

            # 🔥 FINAL CORRECT POSITION
            "-x", "-0.05",   # slightly behind cube
            "-y", "0.0",
            "-z", "0.0",   # EXACT table surface height
        ],
        output="screen",
    )

    # ================= CONTROLLERS =================

    joint_state_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager", "/controller_manager",
        ],
        output="screen",
    )

    arm_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "arm_controller",
            "--controller-manager", "/controller_manager",
        ],
        output="screen",
    )

    gripper_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "gripper_controller",
            "--controller-manager", "/controller_manager",
        ],
        output="screen",
    )

    # ================= SEQUENCING =================

    # Wait for Gazebo to fully load
    delayed_jsb = TimerAction(
        period=12.0,
        actions=[joint_state_spawner],
    )

    # Start arm controller after JSB
    arm_after_jsb = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_spawner,
            on_exit=[arm_controller_spawner],
        )
    )

    # Start gripper after arm
    gripper_after_arm = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=arm_controller_spawner,
            on_exit=[gripper_controller_spawner],
        )
    )

    return [
        gazebo,
        robot_state_pub,
        spawn_entity,
        delayed_jsb,
        arm_after_jsb,
        gripper_after_arm,
    ]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup),
    ])