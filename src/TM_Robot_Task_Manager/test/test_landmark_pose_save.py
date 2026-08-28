import re

import pytest
import yaml
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, Recipe, RecipeManager


def _pose():
    return {'x': 199.731, 'y': 567.0249, 'z': 248.0812,
            'rx': -179.9876, 'ry': -0.0134, 'rz': 0.0071, 'detected': True}


def _only_yaml(directory):
    files = sorted(p for p in directory.iterdir() if p.suffix == '.yaml')
    assert len(files) == 1, f"YAML 1개를 기대했으나 {files}"
    return files[0]


@pytest.fixture
def executor():
    node = MagicMock()
    node.current_base_name = 'RobotBase'
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    ex.tm_landmark_pose = _pose()
    return ex


def _save_job(caption='드로어마커_저장', **params):
    job = Job(job_id=1, job_type='save_landmark_pose', params=params)
    job.caption = caption
    return job


def _load_recipe(executor, file_path):
    recipe = Recipe(name='pallet0_drawer_cali')
    recipe.file_path = str(file_path)
    executor.current_recipe = recipe
    return recipe


def _logs(executor):
    return "\n".join(executor.logs)


def test_job_type_is_registered():
    spec = RecipeManager.JOB_TYPES['save_landmark_pose']
    assert spec['category'] == 'Landmark'
    assert spec['params']['save_path']['type'] == 'dirpath'
    assert spec['params']['save_path']['default'] == ''
    assert spec['params']['operator']['type'] == 'str'
    assert spec['params']['operator']['default'] == ''


def test_dispatch_reaches_handler(executor, tmp_path):
    """_execute_job 분기가 실제로 이 Job 을 핸들러로 보내는지."""
    _load_recipe(executor, tmp_path / 'recipes' / 'pallet0_drawer_cali.yaml')
    assert executor._execute_job(_save_job(save_path=str(tmp_path / 'out'))) is True
    assert _only_yaml(tmp_path / 'out')


def test_saves_all_six_dof_named_by_recipe_caption_and_timestamp(executor, tmp_path):
    _load_recipe(executor, tmp_path / 'recipes' / 'pallet0_drawer_cali.yaml')
    save_dir = tmp_path / 'landmark_pose'

    assert executor._exec_save_landmark_pose(
        _save_job(operator='jjh', save_path=str(save_dir))) is True

    target = _only_yaml(save_dir)
    assert re.fullmatch(
        r'pallet0_drawer_cali_드로어마커_저장_\d{8}_\d{6}\.yaml', target.name)

    data = yaml.safe_load(target.read_text(encoding='utf-8'))
    assert data['operator'] == 'jjh'
    assert data['recipe'] == 'pallet0_drawer_cali'
    assert data['task_caption'] == '드로어마커_저장'
    assert data['saved_at']
    assert set(data['landmark']) == {'x', 'y', 'z', 'rx', 'ry', 'rz'}
    assert data['landmark']['x'] == pytest.approx(199.731)
    assert data['landmark']['y'] == pytest.approx(567.025)   # 3자리 반올림
    assert data['landmark']['rx'] == pytest.approx(-179.988)
    assert data['landmark']['rz'] == pytest.approx(0.007)
    assert 'detected' not in data['landmark']
    assert str(target) in _logs(executor)


def test_no_scan_fails(executor, tmp_path):
    executor.tm_landmark_pose = None

    assert executor._exec_save_landmark_pose(_save_job(save_path=str(tmp_path))) is False
    assert "scan_tm_landmark 를 먼저 실행" in _logs(executor)
    assert not list(tmp_path.iterdir())


def test_blank_save_path_fails(executor, tmp_path):
    assert executor._exec_save_landmark_pose(_save_job()) is False
    assert "save_path 가 비어 있습니다" in _logs(executor)


def test_incomplete_pose_fails(executor, tmp_path):
    executor.tm_landmark_pose.pop('rz')

    assert executor._exec_save_landmark_pose(_save_job(save_path=str(tmp_path))) is False
    assert "빠진 값이 있습니다" in _logs(executor)
    assert not list(tmp_path.iterdir())


def test_blank_operator_warns_and_saves_null(executor, tmp_path):
    assert executor._exec_save_landmark_pose(_save_job(save_path=str(tmp_path))) is True

    data = yaml.safe_load(_only_yaml(tmp_path).read_text(encoding='utf-8'))
    assert data['operator'] is None
    assert "작업자 이름이 비어 있습니다" in _logs(executor)


def test_no_recipe_loaded_records_null_recipe(executor, tmp_path):
    executor.current_recipe = None

    assert executor._exec_save_landmark_pose(_save_job(save_path=str(tmp_path))) is True

    data = yaml.safe_load(_only_yaml(tmp_path).read_text(encoding='utf-8'))
    assert data['recipe'] is None


def test_plate_pose_save_is_untouched(executor, tmp_path):
    """기존 calculate_plate_pose 저장물에 landmark 키가 섞이지 않는다."""
    executor.vision_manager = MagicMock()
    executor.jig_landmark_results = {
        1: {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        2: {'x': 0.0, 'y': 100.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        3: {'x': 200.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        4: {'x': 200.0, 'y': 100.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
    }
    job = Job(job_id=2, job_type='calculate_plate_pose',
              params={'save_path': str(tmp_path), 'operator': 'jjh'})
    job.caption = 'pallet_plate_pose_calc'

    assert executor._exec_calculate_plate_pose(job) is True

    data = yaml.safe_load(_only_yaml(tmp_path).read_text(encoding='utf-8'))
    assert set(data) == {'operator', 'recipe', 'task_caption', 'saved_at',
                         'plate_pose', 'landmarks'}
