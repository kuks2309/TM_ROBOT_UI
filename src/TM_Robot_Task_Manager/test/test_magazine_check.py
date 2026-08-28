#!/usr/bin/env python3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.services.magazine_state_service import MagazineStateService


class _FakeLogger:
    def info(self, *a, **k):
        pass

    def warn(self, *a, **k):
        pass


class _FakeNode:

    def __init__(self):
        self.subscription = None

    def get_logger(self):
        return _FakeLogger()

    def create_subscription(self, msg_type, topic, cb, qos):
        self.subscription = (msg_type, topic, cb, qos)
        return object()


class _FakeState:

    def __init__(self, present, valid=True, raw=None):
        self.present = list(present)
        self.raw = list(raw if raw is not None else present)
        self.valid = valid


EMPTY = [False] * 6
SLOT1_ONLY = [False, True, False, False, False, False]


def _service():
    svc = MagazineStateService(ros_node=_FakeNode())
    if not svc.available:
        pytest.skip('magazine_detect 미소싱 — 워크스페이스 빌드 후 실행할 것')
    return svc


def _feed(svc, state):
    svc._on_state(state)


def test_미수신은_판정불가():
    svc = _service()
    assert svc.is_valid() is False
    assert svc.slot_present(1) is None, '한 번도 못 받았는데 판정을 내놨다'


def test_슬롯1만_있음():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    assert svc.slot_present(1) is True
    assert svc.slot_present(0) is False
    assert svc.present_list() == SLOT1_ONLY


def test_stale는_비었다와_다르다():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    _feed(svc, _FakeState(SLOT1_ONLY, valid=False))
    assert svc.present_list() == SLOT1_ONLY
    assert svc.slot_present(1) is None, 'stale 인데 재고를 확정해서 답했다'


def test_범위밖_슬롯():
    svc = _service()
    _feed(svc, _FakeState(EMPTY))
    assert svc.slot_present(6) is None
    assert svc.slot_present(-1) is None


def test_미소싱이면_비활성():
    svc = MagazineStateService(ros_node=None)
    assert svc.available is False
    assert svc.slot_present(0) is None


def test_구독_토픽():
    node = _FakeNode()
    svc = MagazineStateService(ros_node=node)
    if not svc.available:
        pytest.skip('magazine_detect 미소싱')
    assert node.subscription[1] == '/magazine_detect_node/state'


def test_구독_QoS가_RELIABLE_VOLATILE(monkeypatch):
    import sys
    import types

    captured = {}

    stub = types.ModuleType('rclpy.qos')

    class _Reliability:
        RELIABLE = 'RELIABLE'
        BEST_EFFORT = 'BEST_EFFORT'

    class _Durability:
        VOLATILE = 'VOLATILE'
        TRANSIENT_LOCAL = 'TRANSIENT_LOCAL'

    class _History:
        KEEP_LAST = 'KEEP_LAST'
        KEEP_ALL = 'KEEP_ALL'

    def _profile(**kwargs):
        captured.update(kwargs)
        return 'qos'

    stub.QoSProfile = _profile
    stub.ReliabilityPolicy = _Reliability
    stub.DurabilityPolicy = _Durability
    stub.HistoryPolicy = _History
    monkeypatch.setitem(sys.modules, 'rclpy.qos', stub)

    assert MagazineStateService._make_qos() == 'qos'
    assert captured['reliability'] == 'RELIABLE'
    assert captured['durability'] == 'VOLATILE'
    assert captured['history'] == 'KEEP_LAST'
    assert captured['depth'] == 10


class _Job:
    def __init__(self, **params):
        self.params = params


def _executor(svc):
    from tm_task_manager.job_executor import JobExecutor
    node = _FakeNode()
    node.magazine_state_service = svc
    ex = JobExecutor(ros_node=node)
    ex.log_callback = None
    return ex


def test_잡_기대일치면_성공():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor(svc)
    assert ex._exec_check_magazine(_Job(slot=1, expect='present')) is True
    assert ex._exec_check_magazine(_Job(slot=0, expect='empty')) is True


def test_잡_기대불일치면_실패():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor(svc)
    assert ex._exec_check_magazine(_Job(slot=0, expect='present')) is False
    assert ex._exec_check_magazine(_Job(slot=1, expect='empty')) is False


def test_잡_판정불가는_실패다():
    svc = _service()
    ex = _executor(svc)
    assert ex._exec_check_magazine(_Job(slot=1, expect='empty', timeout=0.1)) is False
    assert ex._exec_check_magazine(_Job(slot=1, expect='present', timeout=0.1)) is False


def test_잡_슬롯범위밖은_실패():
    svc = _service()
    _feed(svc, _FakeState(EMPTY))
    ex = _executor(svc)
    assert ex._exec_check_magazine(_Job(slot=6, expect='empty')) is False


def test_잡_slot이_숫자가_아니면_실패():
    svc = _service()
    _feed(svc, _FakeState(EMPTY))
    ex = _executor(svc)
    assert ex._exec_check_magazine(_Job(slot='뒤왼', expect='empty')) is False


class _FakeRecipe:
    def __init__(self, count):
        self.jobs = [object()] * count


def _executor_in_recipe(svc, job_count=40, index=0):
    ex = _executor(svc)
    ex.current_recipe = _FakeRecipe(job_count)
    ex.current_job_index = index
    ex._direction = 1
    return ex


def test_기본은_stop이다():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=5)
    assert ex._exec_check_magazine(_Job(slot=0, expect='present')) is False
    assert ex.current_job_index == 5, '정지인데 인덱스를 움직였다'


def test_stop_명시():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=5)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='stop')) is False
    assert ex.current_job_index == 5


def test_ignore는_통과하고_인덱스를_안_움직인다():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=5)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='ignore')) is True
    assert ex.current_job_index == 5, 'ignore 인데 건너뛰었다'


def test_skip은_skip_count만큼_전진한다():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=2)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='skip', skip_count=11)) is True
    assert ex.current_job_index == 13


def test_일치하면_skip_설정이어도_안_건너뛴다():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=2)
    assert ex._exec_check_magazine(
        _Job(slot=1, expect='present', on_mismatch='skip', skip_count=11)) is True
    assert ex.current_job_index == 2, '기대와 일치했는데 건너뛰었다'


def test_skip_count_0은_그대로_진행():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=2)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='skip', skip_count=0)) is True
    assert ex.current_job_index == 2


def test_skip이_레시피_끝을_넘으면_끝으로_간다():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, job_count=10, index=5)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='skip', skip_count=99)) is True
    assert ex.current_job_index == 9, '레시피 밖으로 인덱스가 나갔다'


def test_skip_count_음수는_정지():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=5)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='skip', skip_count=-3)) is False
    assert ex.current_job_index == 5


def test_skip_count가_숫자가_아니면_정지():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=5)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='skip', skip_count='열하나')) is False


def test_역순실행중_skip은_정지():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=5)
    ex._direction = -1
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='skip', skip_count=11)) is False
    assert ex.current_job_index == 5


def test_알수없는_on_mismatch는_stop():
    svc = _service()
    _feed(svc, _FakeState(SLOT1_ONLY))
    ex = _executor_in_recipe(svc, index=5)
    assert ex._exec_check_magazine(
        _Job(slot=0, expect='present', on_mismatch='그만')) is False


def test_판정불가는_on_mismatch와_무관하게_정지():
    svc = _service()
    ex = _executor_in_recipe(svc, index=5)
    for mode in ('stop', 'skip', 'ignore'):
        assert ex._exec_check_magazine(
            _Job(slot=1, expect='present', on_mismatch=mode,
                 skip_count=11, timeout=0.1)) is False, f'{mode} 에서 진행했다'
        assert ex.current_job_index == 5
