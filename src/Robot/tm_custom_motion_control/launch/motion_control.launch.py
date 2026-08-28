from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'default_velocity_ptp',
            default_value='25.0',
            description='Default PTP velocity (%)'
        ),
        DeclareLaunchArgument(
            'default_velocity_linear',
            default_value='100.0',
            description='Default linear velocity (mm/s)'
        ),
        DeclareLaunchArgument(
            'default_acc_time',
            default_value='0.2',
            description='Default acceleration time (s)'
        ),
        DeclareLaunchArgument(
            'default_blend',
            default_value='0',
            description='Default blend percentage (%)'
        ),
        DeclareLaunchArgument(
            'gripper_open_pin',
            default_value='0',
            description='Gripper open DO pin'
        ),
        DeclareLaunchArgument(
            'gripper_close_pin',
            default_value='1',
            description='Gripper close DO pin'
        ),
        DeclareLaunchArgument(
            'gripper_module',
            default_value='0',
            description='Gripper IO module (0=Control Box, 1=End Module)'
        ),

        Node(
            package='tm_custom_motion_control',
            executable='motion_control_node',
            name='motion_control_node',
            parameters=[{
                'default_velocity_ptp': LaunchConfiguration('default_velocity_ptp'),
                'default_velocity_linear': LaunchConfiguration('default_velocity_linear'),
                'default_acc_time': LaunchConfiguration('default_acc_time'),
                'default_blend': LaunchConfiguration('default_blend'),
                'gripper_open_pin': LaunchConfiguration('gripper_open_pin'),
                'gripper_close_pin': LaunchConfiguration('gripper_close_pin'),
                'gripper_module': LaunchConfiguration('gripper_module'),
            }],
            output='screen'
        ),
    ])
