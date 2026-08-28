###############################################################################################
#  tm20_move_group_only.launch.py
#
#  웹 스택(scripts/web_gui.sh)과 **공존**하는 MoveIt 기동 launch.
#
#  벤더 tm20_run_move_group.launch.py 는 tm_driver 와 RViz 를 자체 기동한다. 웹 스택이 이미
#  tm_driver 를 띄운 상태에서 그것을 돌리면 tm_driver 가 **중복 기동**된다(과거 사고 재현).
#  본 launch 는 tm_driver·RViz 를 제외하고, 이미 떠 있는 tm_driver 의 /joint_states 와
#  /tmr_arm_controller/follow_joint_trajectory 를 그대로 사용한다.
#
#  robot_description 은 실물 보정 모델(tm20-calib)을 로드한다 — tm20_run_move_group.launch.py 와 동일.
#  use_sim_time 은 False (실물은 wall clock. 벤더 기본값 True 는 /clock 퍼블리셔가 없는 실물 환경에 부적절).
###############################################################################################

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

import xacro
import yaml


def load_file(package_name, file_path):
    absolute_file_path = os.path.join(get_package_share_directory(package_name), file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return file.read()
    except OSError:
        return None


def load_yaml(package_name, file_path):
    absolute_file_path = os.path.join(get_package_share_directory(package_name), file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return yaml.safe_load(file)
    except OSError:
        return None


def generate_launch_description():
    description_path = 'tm_description'
    xacro_path = 'tm20-calib.urdf.xacro'
    moveit_config_path = 'tm20_moveit_config'
    srdf_path = 'config/tm20.srdf'

    # Robot description (실물 보정 모델)
    robot_description_config = xacro.process_file(
        os.path.join(get_package_share_directory(description_path), 'xacro', xacro_path)
    )
    robot_description = {'robot_description': robot_description_config.toxml()}

    robot_description_semantic = {
        'robot_description_semantic': load_file(moveit_config_path, srdf_path)
    }

    robot_description_kinematics = {
        'robot_description_kinematics': load_yaml(moveit_config_path, 'config/kinematics.yaml')
    }

    # Planning (OMPL)
    ompl_planning_pipeline_config = {
        'planning_pipelines': ['ompl'],
        'ompl': {
            'planning_plugin': 'ompl_interface/OMPLPlanner',
            'request_adapters': """default_planner_request_adapters/AddTimeOptimalParameterization default_planner_request_adapters/FixWorkspaceBounds default_planner_request_adapters/FixStartStateBounds default_planner_request_adapters/FixStartStateCollision default_planner_request_adapters/FixStartStatePathConstraints""",
            'start_state_max_bounds_error': 0.1,
        },
    }
    ompl_planning_pipeline_config['ompl'].update(
        load_yaml(moveit_config_path, 'config/ompl_planning.yaml')
    )

    # 실행 컨트롤러 — 이미 떠 있는 tm_driver 의 tmr_arm_controller 액션을 사용
    moveit_controllers = {
        'moveit_simple_controller_manager': load_yaml(moveit_config_path, 'config/controllers.yaml'),
        'moveit_controller_manager': 'moveit_simple_controller_manager/MoveItSimpleControllerManager',
    }

    trajectory_execution = {
        'moveit_manage_controllers': True,
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.1,
    }

    planning_scene_monitor_parameters = {
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
    }

    joint_limits_yaml = {
        'robot_description_planning': load_yaml(moveit_config_path, 'config/joint_limits.yaml')
    }

    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        emulate_tty=True,
        parameters=[
            robot_description,
            robot_description_semantic,
            robot_description_kinematics,
            ompl_planning_pipeline_config,
            trajectory_execution,
            moveit_controllers,
            planning_scene_monitor_parameters,
            joint_limits_yaml,
            {'use_sim_time': False},
        ],
    )

    static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_transform_publisher',
        output='log',
        arguments=['0.0', '0.0', '0.0', '0.0', '0.0', '0.0', 'world', 'base'],
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[robot_description, {'use_sim_time': False}],
    )

    # tm_driver·RViz 는 의도적으로 제외 — 웹 스택이 이미 기동한다.
    return LaunchDescription([static_tf, robot_state_publisher, move_group_node])
