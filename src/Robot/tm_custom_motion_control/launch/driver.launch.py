"""tm_robot_driver 의 config_file 인자만 선언하는 launch 구성 — 기동하는 노드는 없다."""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    """config_file 인자 선언만 반환한다 (Node 액션 없음)."""
    pkg_dir = get_package_share_directory('tm_robot_driver')

    config_file = os.path.join(pkg_dir, 'config', 'robot_config.yaml')

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value=config_file,
            description='Path to robot config file'
        ),

    ])
