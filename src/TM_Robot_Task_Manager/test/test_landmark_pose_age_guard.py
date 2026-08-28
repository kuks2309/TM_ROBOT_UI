"""move_to_landmark_pose 의 저장본 유효시간 가드 (max_age_min).

드로어 마커는 여닫힘에 따라 움직인다. 스캔 레시피와 파지 레시피를 분리하면
파지 쪽이 «언제 잰 것인지 모르는» 저장본을 조용히 쓸 수 있어, 스캔을 건너뛰어도
경고 없이 엉뚱한 곳에 손이 간다. 이 가드가 그 침묵을 깬다.
"""
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
    """minutes_ago 분 전에 저장된 landmark_pose 파일을 만든다."""
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


# --- 등록 -------------------------------------------------------------

def test_param_is_registered():
    spec = RecipeManager.JOB_TYPES['move_to_landmark_pose']['params']['max_age_min']
    assert spec['type'] == 'float'
    assert spec['default'] == 0.0, "기본값은 무제한이어야 기존 레시피 동작이 안 바뀐다"


# --- 기본 동작 (가드 꺼짐) --------------------------------------------

def test_no_guard_accepts_ancient_file(executor, tmp_path):
    """기본값 0 이면 아무리 낡아도 통과 — 기존 레시피 동작 보존."""
    _write(tmp_path, 'a_20200101_000000.yaml', minutes_ago=60 * 24 * 365)
    pose, msg = executor._load_landmark_pose_from_files(_params(tmp_path))
    assert pose is not None, msg
    assert pose['x'] == pytest.approx(POSE['x'])


def test_guard_absent_key_behaves_as_unlimited(executor, tmp_path):
    _write(tmp_path, 'a_20200101_000000.yaml', minutes_ago=99999)
    params = _params(tmp_path)
    params.pop('max_age_min', None)
    assert executor._load_landmark_pose_from_files(params)[0] is not None


# --- 가드 동작 --------------------------------------------------------

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
    """경계 직전은 통과 — 초과(>)만 거부한다.

    saved_at 은 1초 단위라 «정확히 경계» 는 잴 수 없다. 한쪽씩 물린 값으로 본다.
    """
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
    """낡은 최신본을 건너뛰고 더 낡은 것을 쓰면 더 위험하다 — 통째 거부."""
    _write(tmp_path, 'a_20260823_090000.yaml', minutes_ago=200)
    _write(tmp_path, 'a_20260823_120000.yaml', minutes_ago=90)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30, average_count=2))
    assert pose is None, msg


def test_partly_stale_average_is_rejected(executor, tmp_path):
    """평균 대상 중 하나만 낡아도 평균이 오염된다."""
    _write(tmp_path, 'a_20260823_120000.yaml', minutes_ago=1)
    _write(tmp_path, 'a_20260823_090000.yaml', minutes_ago=500)
    pose, msg = executor._load_landmark_pose_from_files(
        _params(tmp_path, max_age_min=30, average_count=2))
    assert pose is None, msg
    assert 'a_20260823_090000.yaml' in msg


# --- 시각 판정 --------------------------------------------------------

def test_saved_at_wins_over_mtime(executor, tmp_path):
    """rsync·복사로 mtime 이 새것이 돼도 saved_at 이 낡았으면 거부한다."""
    target = _write(tmp_path, 'a.yaml', minutes_ago=600)
    import os
    os.utime(target, None)          # mtime 을 '지금' 으로 — 복사 흉내
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


# --- 입력 방어 --------------------------------------------------------

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


# --- 상위 경로 배선 ---------------------------------------------------

def test_guard_reaches_move_job(executor, tmp_path):
    """_landmark_frame_inputs 를 통해 실제 이동 Job 이 거부되는가."""
    _write(tmp_path, 'a.yaml', minutes_ago=90)
    parsed, reason = executor._landmark_frame_inputs(
        _params(tmp_path, landmark_source='file', max_age_min=30))
    assert parsed is None
    assert '유효시간' in reason


def test_latest_scan_ignores_guard(executor, tmp_path):
    """메모리 경로는 방금 잰 값이라 유효시간 개념이 없다."""
    executor.tm_landmark_pose = dict(POSE)
    parsed, reason = executor._landmark_frame_inputs(
        {'landmark_source': 'latest_scan', 'max_age_min': 1})
    assert parsed is not None, reason
