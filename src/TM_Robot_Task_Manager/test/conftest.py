import sys
from unittest.mock import MagicMock

sys.modules['rclpy'] = MagicMock()
sys.modules['rclpy.node'] = MagicMock()
sys.modules['rclpy.qos'] = MagicMock()
sys.modules['rclpy.executors'] = MagicMock()
sys.modules['rclpy.time'] = MagicMock()
sys.modules['tf2_ros'] = MagicMock()
sys.modules['tf2_py'] = MagicMock()
sys.modules['tf2_py._tf2_py'] = MagicMock()
sys.modules['geometry_msgs'] = MagicMock()
sys.modules['geometry_msgs.msg'] = MagicMock()
sys.modules['tm_msgs'] = MagicMock()
sys.modules['tm_msgs.srv'] = MagicMock()
sys.modules['tm_msgs.msg'] = MagicMock()
sys.modules['cv_bridge'] = MagicMock()

import pytest
import os
import tempfile
from unittest.mock import MagicMock, PropertyMock


@pytest.fixture
def temp_recipe_dir(tmp_path):
    recipe_dir = tmp_path / "recipes"
    recipe_dir.mkdir()
    return recipe_dir


@pytest.fixture
def sample_job_dict():
    return {
        'id': 1,
        'type': 'move_to_point',
        'name': 'Test Move',
        'target': [100.0, 200.0, 300.0, 0.0, 90.0, 0.0],
        'speed': 50,
        'params': {'use_joint': False}
    }


@pytest.fixture
def sample_recipe_dict():
    return {
        'name': 'Test Recipe',
        'description': 'A test recipe',
        'jobs': [
            {'id': 1, 'type': 'go_home', 'name': 'Go Home'},
            {'id': 2, 'type': 'wait', 'name': 'Wait', 'params': {'duration': 1.0}}
        ]
    }


@pytest.fixture
def mock_ros_node():
    node = MagicMock()
    node.is_sct_connected = True
    node.current_tcp_pose = [100.0, 200.0, 300.0, 0.0, 90.0, 0.0]
    node.current_joint_positions = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
    node.current_base_name = 'RobotBase'
    node._call_set_positions = MagicMock(return_value=(True, "Success"))
    node.ask_item_client = MagicMock()
    node.send_script_client = MagicMock()
    node.get_logger = MagicMock(return_value=MagicMock())
    return node


@pytest.fixture
def mock_vision_manager():
    vm = MagicMock()
    vm.write_variable = MagicMock(return_value=True)
    vm.send_script_exit = MagicMock(return_value=True)
    vm.execute_tm_landmark_scan = MagicMock(return_value=(True, "OK"))
    vm.execute_tm_landmark_jig_scan = MagicMock(return_value=(True, "OK"))
    vm.execute_tm_landmark_jig_read = MagicMock(return_value=(True, {'detected': True, 'x': 0, 'y': 0, 'z': 0}))
    vm.get_tag = MagicMock(return_value=None)
    vm.gv_manager = MagicMock()
    vm.gv_manager.write_variable = MagicMock(return_value=(True, "OK"))
    vm.gv_manager.send_script_exit = MagicMock(return_value=True)
    return vm


@pytest.fixture
def mock_gv_manager():
    gv = MagicMock()
    gv.write_variable = MagicMock(return_value=(True, "OK"))
    gv.read_variable = MagicMock(return_value=(True, "0"))
    gv.send_script_exit = MagicMock(return_value=True)
    return gv
