#!/usr/bin/env python3
"""tools/jig_plate_validator 의 사각형 가드 판정을 검증한다."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.tools.jig_plate_validator import JigPlateValidator


def _marks(jig1_y, jig2_y, jig3_y, jig4_y, x_left=450.5, x_right=646.9, z=-325.0):
    return [
        {'x': x_right, 'y': jig1_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
        {'x': x_left, 'y': jig2_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
        {'x': x_right, 'y': jig3_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
        {'x': x_left, 'y': jig4_y, 'z': z, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
    ]


PALLET3 = _marks(-70.795, -68.767, 66.251, 65.044)
GOOD = _marks(-68.5, -68.5, 68.5, 68.5)


def _validator(marks, side=1.0, diag=1.5, angle=1.0):
    v = JigPlateValidator()
    assert v.load_from_dicts(marks)
    v.TOLERANCE_SIDE_DIFF = side
    v.TOLERANCE_DIAGONAL_DIFF = diag
    v.TOLERANCE_ANGLE = angle
    return v


def test_load_from_dicts_requires_exactly_four():
    v = JigPlateValidator()
    assert v.load_from_dicts(PALLET3[:3]) is False
    assert v.load_from_dicts(PALLET3 + PALLET3[:1]) is False
    assert v.load_from_dicts(PALLET3) is True
    assert len(v.marks) == 4


def test_load_from_dicts_tolerates_missing_rotation():
    v = JigPlateValidator()
    assert v.load_from_dicts([{'x': 0.0, 'y': 0.0, 'z': 0.0} for _ in range(4)])
    assert v.marks[0].rx == 0.0


def test_rectangle_passes_for_true_rectangle():
    results = _validator(GOOD).check_rectangle()
    assert results, "검증 결과가 비어 있으면 안 된다"
    assert all(r.passed for r in results), [str(r) for r in results]


def test_pallet3_short_side_triggers_guard():
    results = _validator(PALLET3).check_rectangle()
    failed = [r for r in results if not r.passed]
    assert failed, "pallet3 사다리꼴이 통과하면 가드가 무의미하다"

    side = next(r for r in results if r.name == "대향변(수평) 차이")
    assert side.passed is False
    assert side.value == pytest.approx(3.243, abs=0.01)


def test_pallet3_diagonal_alone_would_not_catch_it():
    results = _validator(PALLET3, diag=10.0).check_rectangle()
    diag = next(r for r in results if r.name == "대각선 차이")
    assert diag.passed is True
    assert diag.value < 1.0


def test_threshold_override_changes_verdict():
    loose = _validator(PALLET3, side=5.0).check_rectangle()
    assert all(r.passed for r in loose)

    strict = _validator(PALLET3, side=1.0).check_rectangle()
    assert any(not r.passed for r in strict)


def test_get_side_lengths_matches_measurement():
    d = _validator(PALLET3).get_side_lengths()
    assert d['jig1-jig3'] == pytest.approx(137.046, abs=0.01)
    assert d['jig2-jig4'] == pytest.approx(133.811, abs=0.01)
    assert set(d) == {'jig1-jig3', 'jig2-jig4', 'jig1-jig2',
                      'jig3-jig4', 'jig1-jig4', 'jig2-jig3'}


def test_get_side_lengths_empty_without_marks():
    assert JigPlateValidator().get_side_lengths() == {}


class _FakeExecutor:

    def __init__(self, alarm=None):
        self.on_plate_rect_alarm = alarm
        self.logs = []
        self.payload = None

    def _log(self, msg):
        self.logs.append(msg)

    _confirm_plate_rectangle = None


@pytest.fixture
def confirm():
    from tm_task_manager.job_executor import JobExecutor
    return JobExecutor._confirm_plate_rectangle


B_STD = {'max_side_diff_mm': 1.0, 'max_diagonal_diff_mm': 1.5,
         'max_angle_error_deg': 1.0}


def test_guard_passes_good_plate_without_asking(confirm):
    def _never(_):
        pytest.fail("정상 배치인데 작업자에게 물었다")

    ex = _FakeExecutor(alarm=_never)
    assert confirm(ex, GOOD, B_STD) is True


def test_guard_aborts_when_operator_declines(confirm):
    ex = _FakeExecutor(alarm=lambda payload: False)
    assert confirm(ex, PALLET3, B_STD) is False


def test_guard_continues_when_operator_approves(confirm):
    ex = _FakeExecutor(alarm=lambda payload: True)
    assert confirm(ex, PALLET3, B_STD) is True


def test_guard_payload_carries_results_and_distances(confirm):
    captured = {}

    def _alarm(payload):
        captured.update(payload)
        return True

    ex = _FakeExecutor(alarm=_alarm)
    confirm(ex, PALLET3, B_STD)

    assert captured['failed'], "실패 항목이 전달되어야 한다"
    assert all(not r.passed for r in captured['failed'])
    assert captured['distances']['jig1-jig3'] == pytest.approx(137.046, abs=0.01)


def test_guard_aborts_when_no_callback_registered(confirm):
    ex = _FakeExecutor(alarm=None)
    assert confirm(ex, PALLET3, B_STD) is False


def test_guard_can_be_disabled_by_param(confirm):
    def _never(_):
        pytest.fail("가드를 껐는데 물었다")

    ex = _FakeExecutor(alarm=_never)
    assert confirm(ex, PALLET3, {**B_STD, 'rect_guard_enabled': False}) is True


def test_guard_skips_when_landmarks_unloadable(confirm):
    ex = _FakeExecutor(alarm=lambda p: False)
    assert confirm(ex, PALLET3[:3], B_STD) is True


def test_guard_uses_defaults_when_params_absent(confirm):
    ex = _FakeExecutor(alarm=lambda payload: False)
    assert confirm(ex, PALLET3, {}) is False
    assert confirm(ex, GOOD, {}) is True
