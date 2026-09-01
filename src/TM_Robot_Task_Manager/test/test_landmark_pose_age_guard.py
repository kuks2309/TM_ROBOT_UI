"""job_executor 랜드마크 pose 파일 신선도 가드(max_age·saved_at/mtime 우선순위)를 검증한다."""
import time

import pytest
import yaml
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import RecipeManager


POSE = {'x': 109.77, 'y': 567.01, 'z': -231.95,
        'rx': -179.99, 'ry': -0.01, 'rz': -89.99}


@pytest.fixture
def executor():
    node = MagicMock()
    node.current_base_name = 'RobotBase'
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    return ex


def _write(directory, name, minutes_ago, *, pose=None, saved_at='auto'):
    stamp = time.time() - minutes_ago * 60.0
    data = {'operator': 'jjh', 'recipe': 'drawer_marker_scan_low',
            'landmark': dict(pose or POSE)}
    if saved_at == 'auto':
        data['saved_at'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp))
    elif saved_at is not None:
        data['saved_at'] = saved_at
    target = directory / name
    with open(target, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    import os
    os.utime(target, (stamp, stamp))
    return target


def _params(directory, **extra):
    p = {'source_path': str(directory), 'file_prefix': '', 'average_count': 1}
    p.update(extra)
    return p


def _logs(executor):
    return "\n".join(executor.logs)


def test_param_is_registered():
    spec = RecipeManager.JOB_TYPES['move_to_landmark_pose']['params']['max_age_min']
    assert spec['type'] == 'float'
    assert spec['default'] == 0.0, "기본값은 무제한이어야 기존 레시피 동작이 안 바뀐다"


def test_no_guard_accepts_ancient_file(executor, tmp_path):
    _write(tmp_path, 'a_20200101_000000.yaml', minutes_ago=60 * 24 * 365)
    pose, msg = executor._load_landmark_pose_from_files(_params(tmp_path))
    assert pose is not None, msg
    assert pose['x'] == pytest.approx(POSE['x'])


def test_guard_absent_key_behaves_as_unlimited(executor, tmp_path):
    _write(tmp_path, 'a_20200101_000000.yaml', minutes_ago=99999)
    params = _params(tmp_path)
    params.pop('max_age_min', None)
    assert executor._load_landmark_pose_from_files(params)[0] is not None


def test_fresh_file_passes_guard(executor, tmp_path):
    _write(tmp_path, 'a_20260823_120000.yaml', minutes_ago=5)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is not None, msg


def test_stale_file_is_rejected(executor, tmp_path):
    _write(tmp_path, 'a_20260823_120000.yaml', minutes_ago=90)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is None, "낡은 저장본이 통과했다"
    assert '유효시간' in msg and '30분' in msg
    assert '다시 스캔' in msg, "해법을 안내해야 한다"
    assert 'a_20260823_120000.yaml' in msg, "어느 파일인지 지목해야 한다"


def test_just_under_limit_passes(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=29.5)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is not None, msg


def test_just_over_limit_is_rejected(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=30.5)
    pose, _ = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is None


def test_stale_does_not_silently_fall_back_to_older(executor, tmp_path):
    _write(tmp_path, 'a_20260823_090000.yaml', minutes_ago=200)
    _write(tmp_path, 'a_20260823_120000.yaml', minutes_ago=90)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30, average_count=2))
    assert pose is None, msg


def test_partly_stale_average_is_rejected(executor, tmp_path):
    _write(tmp_path, 'a_20260823_120000.yaml', minutes_ago=1)
    _write(tmp_path, 'a_20260823_090000.yaml', minutes_ago=500)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30, average_count=2))
    assert pose is None, msg
    assert 'a_20260823_090000.yaml' in msg


def test_saved_at_wins_over_mtime(executor, tmp_path):
    target = _write(tmp_path, 'a.yaml', minutes_ago=600)
    import os
    os.utime(target, None)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is None, "mtime 에 속았다"


def test_missing_saved_at_falls_back_to_mtime(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=600, saved_at=None)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is None, msg


def test_missing_saved_at_fresh_mtime_passes(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=1, saved_at=None)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is not None, msg


def test_broken_saved_at_warns_and_uses_mtime(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=1, saved_at='어제쯤')
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30))
    assert pose is not None, msg
    assert 'saved_at 형식' in _logs(executor)


def test_non_numeric_max_age_is_refused(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=1)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min='삼십분'))
    assert pose is None
    assert 'max_age_min' in msg


def test_negative_max_age_means_unlimited(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=99999)
    pose, _ = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=-1))
    assert pose is not None


def test_guard_reaches_move_job(executor, tmp_path):
    _write(tmp_path, 'a.yaml', minutes_ago=90)
    parsed, reason = executor._landmark_frame_inputs(
        _params(tmp_path, landmark_source='file', max_age_min=30))
    assert parsed is None
    assert '유효시간' in reason


def test_latest_scan_ignores_guard(executor, tmp_path):
    executor.tm_landmark_pose = dict(POSE)
    parsed, reason = executor._landmark_frame_inputs(
        {'landmark_source': 'latest_scan', 'max_age_min': 1})
    assert parsed is not None, reason
