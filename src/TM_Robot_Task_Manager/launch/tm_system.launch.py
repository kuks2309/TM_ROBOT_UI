from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os



def _profile_robot_ip(fallback):
    """MK2·MK4 의 robot_ip 를 **둘 다 두드려** 응답하는 쪽을 쓴다.

    둘 중 하나에는 붙는다는 전제(사용자 확인 2026-08-27)라, 어느 기계 앞이든
    같은 명령으로 뜨게 한다. 5890(SCT, 명령 채널)에 TCP 가 열리는지로 판정한다.

    순서: 확정된 프로필의 IP 를 먼저 두드린다 — 두 로봇이 같은 망에 있을 때
    순서가 뒤바뀌면 엉뚱한 기계에 명령이 간다.

    아무 응답이 없으면 프로필 값 → fallback 순으로 떨어진다. launch 는 설치 순서에
    따라 패키지 import 가 실패할 수 있어 전체를 방어적으로 감싼다.
    """
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
