from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os


def _profile_robot_ip(fallback):
    try:
        from tm_task_manager import robot_profile

        print('[tm_task_manager] 로봇 IP 탐색: %s' % robot_profile.probe_report())
        robot_id, ip = robot_profile.probe_robot_ip()
        if ip:
            print('[tm_task_manager] 응답한 로봇으로 붙습니다: %s (%s:%d)'
                  % (robot_id, ip, robot_profile.ROBOT_PORT))
            return ip

        found = robot_profile.robot_ip(None)
        if found:
            print('[tm_task_manager] 응답 없음 — 프로필 값을 그대로 씁니다: %s' % found)
            return found
        print('[tm_task_manager] 응답 없음 · 프로필 미확정 — 기본값 %s' % fallback)
    except Exception as exc:
        print('[tm_task_manager] 로봇 프로필을 읽지 못했습니다(%s) — 기본값 %s' % (exc, fallback))
    return fallback

def generate_launch_description():
    robot_ip = LaunchConfiguration('robot_ip')

    return LaunchDescription([
        DeclareLaunchArgument(
            'robot_ip',
            default_value=_profile_robot_ip('192.168.192.127'),
            description='TM Robot IP address'
        ),

        Node(
            package='tm_driver',
            executable='tm_driver',
            name='tm_driver',
            output='screen',
            arguments=[robot_ip],
        ),

        Node(
            package='tm_task_manager',
            executable='task_manager_node',
            name='tm_task_manager',
            output='screen',
            parameters=[{
                'robot_ip': robot_ip,
            }],
        ),
    ])
