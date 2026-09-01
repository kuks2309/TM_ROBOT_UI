"""aruco_detector 단일 노드 기동 — config/aruco_params.yaml 로드, image_topic·marker_size 인자 오버라이드."""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    pkg_share = get_package_share_directory('tm_aruco_detect')
    config_file = os.path.join(pkg_share, 'config', 'aruco_params.yaml')

    return LaunchDescription([
        DeclareLaunchArgument(
            'image_topic',
            default_value='/techman_image',
            description='Input image topic from TMvision'
        ),
        DeclareLaunchArgument(
            'marker_size',
            default_value='0.05',
            description='ArUco marker size in meters'
        ),

        Node(
            package='tm_aruco_detect',
            executable='aruco_detector_node',
            name='aruco_detector',
            output='screen',
            parameters=[
                config_file,
                {
                    'image_topic': LaunchConfiguration('image_topic'),
                    'marker_size': LaunchConfiguration('marker_size'),
                }
            ],
        ),
    ])
