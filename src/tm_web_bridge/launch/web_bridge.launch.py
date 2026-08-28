import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    no_user_site = SetEnvironmentVariable('PYTHONNOUSERSITE', '1')
    rosbridge_launch = os.path.join(
        get_package_share_directory('rosbridge_server'),
        'launch',
        'rosbridge_websocket_launch.xml',
    )

    rosbridge = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(rosbridge_launch)
    )

    # PYTHONNOUSERSITE=1 이 ~/.local 을 가리므로 `pip install --user fastapi` 가
    # 이 프로세스에서는 안 보인다. 워크스페이스 안 vendor/pylibs 를 직접 얹는다
    # (카메라 브리지가 같은 이유로 죽었다 — 2026-08-27 팹).
    _ws_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    _vendor = os.path.join(_ws_root, 'vendor', 'pylibs')
    _pypath = os.environ.get('PYTHONPATH', '')
    if os.path.isdir(_vendor):
        _pypath = _vendor + (os.pathsep + _pypath if _pypath else '')

    web_bridge = Node(
        package='tm_web_bridge',
        executable='tm_web_bridge',
        name='tm_web_bridge',
        output='screen',
        additional_env={'PYTHONPATH': _pypath, 'PYTHONUNBUFFERED': '1'},
    )

    return LaunchDescription([no_user_site, rosbridge, web_bridge])
