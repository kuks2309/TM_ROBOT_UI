import os
import re

import pytest
import yaml
from unittest.mock import MagicMock

from tm_task_manager import paths
from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, Recipe, RecipeManager


def _rectangle_landmarks():
    marks = {
        1: {'x': 0.0,   'y': 0.0,   'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        2: {'x': 0.0,   'y': 100.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        3: {'x': 200.0, 'y': 0.0,   'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        4: {'x': 200.0, 'y': 100.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
    }
    for i, mark in marks.items():
        mark['measured_at'] = f'2026-08-14 09:0{i}:00'
    return marks


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
    ex.vision_manager = MagicMock()
    ex.jig_landmark_results = _rectangle_landmarks()
    return ex


def _calc_job(caption='pallet_plate_pose_calc', **params):
    job = Job(job_id=1, job_type='calculate_plate_pose', params=params)
    job.caption = caption
    return job


def _load_recipe(executor, file_path):
    recipe = Recipe(name='pallet3_cali')
    recipe.file_path = str(file_path)
    executor.current_recipe = recipe
    return recipe


def _logs(executor):
    return "\n".join(executor.logs)


def test_save_path_param_is_registered():
    params = RecipeManager.JOB_TYPES['calculate_plate_pose']['params']
    assert params['save_path']['type'] == 'dirpath'
    assert params['save_path']['default'] == ''
    assert params['operator']['type'] == 'str'
    assert params['operator']['default'] == ''


def test_no_save_path_keeps_memory_only(executor):
    assert executor._exec_calculate_plate_pose(_calc_job()) is True
    assert executor.detected_plate_pose is not None
    assert "저장 완료" not in _logs(executor)


def test_saves_yaml_named_by_recipe_caption_and_timestamp(executor, tmp_path):
    _load_recipe(executor, tmp_path / 'recipes' / 'pallet3_cali.yaml')
    save_dir = tmp_path / 'out'

    assert executor._exec_calculate_plate_pose(
        _calc_job(operator='홍길동', save_path=str(save_dir))) is True

    target = _only_yaml(save_dir)
    assert re.fullmatch(r'pallet3_cali_pallet_plate_pose_calc_\d{8}_\d{6}\.yaml', target.name)

    data = yaml.safe_load(target.read_text(encoding='utf-8'))
    assert data['operator'] == '홍길동'
    assert data['recipe'] == 'pallet3_cali'
    assert data['task_caption'] == 'pallet_plate_pose_calc'
    assert set(data['plate_pose']) == {'x', 'y', 'z', 'rx', 'ry', 'rz'}
    assert data['plate_pose']['x'] == pytest.approx(executor.detected_plate_pose['x'], abs=1e-3)
    assert set(data['landmarks']) == {'jig1', 'jig2', 'jig3', 'jig4'}
    assert data['landmarks']['jig3']['x'] == pytest.approx(200.0)
    assert data['landmarks']['jig3']['measured_at'] == '2026-08-14 09:03:00'
    assert data['saved_at']
    assert str(target) in _logs(executor)


def test_blank_operator_warns_and_saves_null(executor, tmp_path):
    assert executor._exec_calculate_plate_pose(_calc_job(save_path=str(tmp_path))) is True

    data = yaml.safe_load(_only_yaml(tmp_path).read_text(encoding='utf-8'))
    assert data['operator'] is None
    assert "작업자 이름이 비어 있습니다" in _logs(executor)


def test_missing_measured_at_is_recorded_as_null(executor, tmp_path):
    for mark in executor.jig_landmark_results.values():
        mark.pop('measured_at')

    assert executor._exec_calculate_plate_pose(_calc_job(save_path=str(tmp_path))) is True

    data = yaml.safe_load(_only_yaml(tmp_path).read_text(encoding='utf-8'))
    assert data['landmarks']['jig1']['measured_at'] is None


def test_scan_job_records_measurement_timestamp(executor):
    executor.jig_landmark_results = {}
    executor.scan_landmark_averaged = lambda *a, **kw: (
        {'x': 1.0, 'y': 2.0, 'z': 3.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0, 'detected': True},
        {'count_after_outlier': 1},
    )

    job = Job(job_id=9, job_type='scan_tm_landmark_jig', params={'jig_number': 2})
    assert executor._exec_scan_tm_landmark_jig(job) is True

    measured_at = executor.jig_landmark_results[2]['measured_at']
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', measured_at)


def test_file_name_falls_back_without_recipe_and_caption(executor, tmp_path):
    executor.current_recipe = None
    assert executor._exec_calculate_plate_pose(
        _calc_job(caption='', save_path=str(tmp_path))) is True
    assert re.fullmatch(r'calculate_plate_pose_1_\d{8}_\d{6}\.yaml', _only_yaml(tmp_path).name)


def test_file_name_sanitizes_path_separators(executor, tmp_path):
    _load_recipe(executor, tmp_path / 'pallet3_cali.yaml')
    assert executor._exec_calculate_plate_pose(
        _calc_job(caption='a/b c', save_path=str(tmp_path / 'out'))) is True
    assert re.fullmatch(r'pallet3_cali_a_b_c_\d{8}_\d{6}\.yaml',
                        _only_yaml(tmp_path / 'out').name)


def test_relative_path_resolves_under_package_root(executor, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PACKAGE_ROOT', tmp_path)
    executor.current_recipe = None
    assert executor._exec_calculate_plate_pose(
        _calc_job(caption='plate', save_path='data/plate')) is True
    assert re.fullmatch(r'plate_\d{8}_\d{6}\.yaml',
                        _only_yaml(tmp_path / 'data' / 'plate').name)


def test_save_failure_fails_the_job(executor, tmp_path):
    blocker = tmp_path / 'blocker'
    blocker.write_text('not a directory', encoding='utf-8')

    assert executor._exec_calculate_plate_pose(_calc_job(save_path=str(blocker))) is False
    assert "저장 실패" in _logs(executor)
    assert executor.detected_plate_pose is not None


def test_blank_save_path_is_ignored(executor, tmp_path):
    assert executor._exec_calculate_plate_pose(_calc_job(save_path='   ')) is True
    assert os.listdir(tmp_path) == []
