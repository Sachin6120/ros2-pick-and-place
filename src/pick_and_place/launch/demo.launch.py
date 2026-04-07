"""All-in-one launcher: Gazebo + MoveIt 2 + pick-and-place node."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("pick_and_place")

    num_trials = DeclareLaunchArgument(
        "num_trials", default_value="1", description="Number of pick-place trials"
    )

    # 1. Gazebo + controllers
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_dir, "launch", "gazebo.launch.py")
        )
    )

    # 2. MoveIt 2 (delay to let Gazebo + controllers come up)
    moveit_launch = TimerAction(
        period=20.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_dir, "launch", "moveit.launch.py")
                )
            )
        ],
    )

    # 3. Pick-and-place node (delay further)
    pick_place_node = TimerAction(
        period=35.0,
        actions=[
            Node(
                package="pick_and_place",
                executable="pick_and_place_node.py",
                parameters=[{"num_trials": LaunchConfiguration("num_trials")}],
                output="screen",
            )
        ],
    )

    return LaunchDescription([
        num_trials,
        gazebo_launch,
        moveit_launch,
        pick_place_node,
    ])
