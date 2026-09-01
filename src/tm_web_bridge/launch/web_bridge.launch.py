"""rosbridge websocket 과 tm_web_bridge 노드(FastAPI 포함)를 함께 띄우는 launch 구성."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    """env 설정 + rosbridge include + tm_web_bridge 노드 1개 기동."""
    # ~/.local site-packages 가 ROS 파이썬 환경을 가리는 것을 차단
    no_user_site = SetEnvironmentVariable('PYTHONNOUSERSITE', '1')
    rosbridge_launch = os.path.join(
        get_package_share_directory('rosbridge_server'),
        'launch',
        'rosbridge_websocket_launch.xml',
    )

    rosbridge = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(rosbridge_launch)
    )

    # PYTHONNOUSERSITE=1 로 사용자 설치 패키지가 안 보이므로, 워크스페이스
    # vendor/pylibs(fastapi 등 동봉 라이브러리)가 있으면 PYTHONPATH 앞에 얹는다
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
