"""Task Manager 풀스택 launch — 미실행인 tm_driver·tm_camera_bridge·camera_calibration_node 만 조건부 기동 후 task_manager_node(GUI)를 띄운다."""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, OpaqueFunction, ExecuteProcess, Shutdown
from launch.substitutions import LaunchConfiguration
import subprocess
import time
import os
from ament_index_python.packages import get_package_share_directory


def check_node_running(node_name):
    """`ros2 node list` 출력에 node_name 이 포함되는지 검사한다(부분문자열 매칭·daemon 캐시 의존)."""
    try:
        result = subprocess.run(
            ['ros2', 'node', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return node_name in result.stdout
    except Exception as e:
        print(f"Failed to check node status: {e}")
        return False


def launch_setup(context):
    """기실행 노드는 건너뛰고 필요한 노드 목록을 구성해 반환한다(OpaqueFunction 본체)."""
    robot_ip = LaunchConfiguration('robot_ip').perform(context)

    nodes_to_launch = []

    if not check_node_running('/tm_driver'):
        print(f"[tm_task_manager] TM Driver가 실행되지 않음. 자동으로 실행합니다...")
        print(f"[tm_task_manager] Robot IP: {robot_ip}")

        tm_driver_node = Node(
            package='tm_driver',
            executable='tm_driver',
            name='tm_driver',
            output='screen',
            arguments=[
                f'robot_ip:={robot_ip}',
                '--ros-args',
                '--log-level', 'tm_driver:=error',
                '--log-level', 'rclcpp:=error',
            ],
        )
        nodes_to_launch.append(tm_driver_node)

        time.sleep(2)
    else:
        print(f"[tm_task_manager] TM Driver가 이미 실행 중입니다.")

    if not check_node_running('/tm_camera_bridge'):
        print(f"[tm_task_manager] TM Camera Bridge가 실행되지 않음. 자동으로 실행합니다...")

        # 카메라 브리지가 쓰는 flask/waitress 등을 워크스페이스 vendor/pylibs 에서 찾을 수 있게 PYTHONPATH 에 선두 주입.
        _ws_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        _vendor = os.path.join(_ws_root, 'vendor', 'pylibs')
        _pypath = os.environ.get('PYTHONPATH', '')
        if os.path.isdir(_vendor):
            _pypath = _vendor + (os.pathsep + _pypath if _pypath else '')
            print('[tm_task_manager] 카메라 브리지 PYTHONPATH 에 vendor 추가: %s' % _vendor)

        tm_camera_bridge_node = Node(
            package='tm_task_manager',
            executable='tm_camera_bridge.py',
            name='tm_camera_bridge',
            output='screen',
            additional_env={
                'PYTHONPATH': _pypath,
                'PYTHONUNBUFFERED': '1',
            },
        )
        nodes_to_launch.append(tm_camera_bridge_node)
    else:
        print(f"[tm_task_manager] TM Camera Bridge가 이미 실행 중입니다.")

    if not check_node_running('/camera_calibration_node'):
        print(f"[tm_task_manager] Camera Calibration Node 실행...")
        calib_params = []
        try:
            from ament_index_python.packages import get_package_share_directory
            _p = os.path.join(
                get_package_share_directory('tm_camera_calibration'),
                'config', 'calibration_params.yaml')
            if os.path.isfile(_p):
                calib_params = [_p]
            else:
                print('[tm_task_manager] calibration_params.yaml 없음 — 기본값 사용')
        except Exception as exc:
            print('[tm_task_manager] 캘리브레이션 설정을 못 찾음(%s) — 기본값 사용' % exc)

        camera_calibration_node = Node(
            package='tm_camera_calibration',
            executable='camera_calibration_node',
            name='camera_calibration_node',
            output='screen',
            parameters=calib_params,
        )
        nodes_to_launch.append(camera_calibration_node)

    # GUI 종료 시 launch 전체를 내리기 위해 on_exit=Shutdown().
    task_manager_node = Node(
        package='tm_task_manager',
        executable='task_manager_node',
        name='tm_task_manager',
        output='screen',
        parameters=[{
            'robot_ip': robot_ip,
        }],
        on_exit=Shutdown(),
    )
    nodes_to_launch.append(task_manager_node)

    return nodes_to_launch


def _profile_robot_ip(fallback):
    """robot_ip 기본값 결정 — 프로브 응답 IP → 프로필 값 → fallback 순."""
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
    """robot_ip launch 인자 선언 + launch_setup 을 OpaqueFunction 으로 등록한다."""
    return LaunchDescription([
        DeclareLaunchArgument(
            'robot_ip',
            default_value=_profile_robot_ip('192.168.192.127'),
            description='TM Robot IP address'
        ),

        OpaqueFunction(function=launch_setup),
    ])
