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
