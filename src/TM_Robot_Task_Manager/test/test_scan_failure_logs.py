import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor


def _pose(detected, **over):
    p = {'x': 199.731, 'y': 567.025, 'z': 248.081,
         'rx': -179.988, 'ry': -0.013, 'rz': 0.007, 'detected': detected}
    p.update(over)
    return p


@pytest.fixture
def executor():
    ex = JobExecutor(ros_node=MagicMock())
    ex.logs = []
    ex.on_log = ex.logs.append
    ex.vision_manager = MagicMock()
    ex.vision_manager.execute_tm_landmark_scan.return_value = (True, 'Landmark 인식 완료')
    ex.vision_manager.execute_tm_landmark_jig_scan.return_value = (True, 'Jig 인식 완료')
    return ex


def _logs(executor):
    return "\n".join(executor.logs)


def test_detect_false_is_distinguished_and_shows_coords(executor):
    executor.vision_manager.execute_tm_landmark_read.return_value = (True, _pose(False))

    pose, analysis = executor.scan_landmark_averaged(2, 'none', 0.0)

    assert pose is None
    log = _logs(executor)
    assert 'g_tm_landmark_detect 가 true/=1 아님' in log
    assert '199.731' in log and '567.025' in log
    assert '결과 읽기 실패' not in log


def test_jig_path_names_its_own_detect_variable(executor):
    executor.vision_manager.execute_tm_landmark_jig_read.return_value = (True, _pose(False))

    executor.scan_landmark_averaged(1, 'none', 0.0, jig_number=3)

    assert 'g_jig_landmark3_detect 가 true/=1 아님' in _logs(executor)


def test_read_failure_reports_the_reason(executor):
    executor.vision_manager.execute_tm_landmark_read.return_value = (False, '결과 읽기 실패')

    executor.scan_landmark_averaged(1, 'none', 0.0)

    log = _logs(executor)
    assert '변수 읽기 실패 — 결과 읽기 실패' in log
    assert '미검출' not in log


def test_non_dict_result_reports_format_error(executor):
    executor.vision_manager.execute_tm_landmark_read.return_value = (True, 'garbage')

    executor.scan_landmark_averaged(1, 'none', 0.0)

    assert '결과 형식 오류 — garbage' in _logs(executor)


def test_scan_command_failure_still_reported_separately(executor):
    executor.vision_manager.execute_tm_landmark_scan.return_value = (False, '타임아웃')

    executor.scan_landmark_averaged(1, 'none', 0.0)

    log = _logs(executor)
    assert '스캔 실패 (1회차)' in log
    assert '변수 읽기 실패' not in log and '미검출' not in log


def test_success_path_unchanged(executor):
    executor.vision_manager.execute_tm_landmark_read.return_value = (True, _pose(True))

    pose, analysis = executor.scan_landmark_averaged(3, 'none', 0.0)

    assert pose is not None
    assert pose['x'] == pytest.approx(199.731)
    assert analysis['count_after_outlier'] == 3
    log = _logs(executor)
    assert '측정 1: X=199.731' in log
    assert '미검출' not in log and '읽기 실패' not in log


def test_mixed_results_keep_only_detected_ones(executor):
    executor.vision_manager.execute_tm_landmark_read.side_effect = [
        (True, _pose(True)),
        (True, _pose(False, x=0.0, y=0.0, z=0.0)),
        (True, _pose(True)),
    ]

    pose, analysis = executor.scan_landmark_averaged(3, 'none', 0.0)

    assert analysis['count_original'] == 2
    assert pose['x'] == pytest.approx(199.731)
    assert '측정 2: 미검출' in _logs(executor)
