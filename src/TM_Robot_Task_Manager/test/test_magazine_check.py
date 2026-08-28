#!/usr/bin/env python3
"""매거진 재고 서비스·check_magazine 잡 단위 테스트.

판정 로직(비트 매핑·극성·디바운스)은 magazine_detect C++ 코어 소유이고 거기서 시험된다.
여기서 지키는 것은 **파이썬 쪽 계약** 두 가지다:
  · 판정 불가(미수신·stale)를 «비어 있음» 과 섞지 않는다 — 섞으면 없는 박스를 집으러 간다
  · 기대와 다르면 잡이 실패해 레시피가 선다
"""
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
    """구독만 받아 두는 최소 노드. 실제 ROS 없이 서비스 계약을 시험한다."""

    def __init__(self):
        self.subscription = None

    def get_logger(self):
        return _FakeLogger()

    def create_subscription(self, msg_type, topic, cb, qos):
        self.subscription = (msg_type, topic, cb, qos)
        return object()


class _FakeState:
    """MagazineState 대역 — present/raw/valid 만 있으면 서비스 계약은 성립한다."""

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


# ── 서비스 계약 ──────────────────────────────────────────────
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
    # 마지막 확정값은 남아 있지만 조회는 판정 불가여야 한다
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
    """QoS 는 발행자와 맞아야 한다 — BEST_EFFORT 구독자는 RELIABLE 발행자와 호환이지만
    재고는 놓치면 안 되는 값이라 RELIABLE 로 고정한다. VOLATILE 은 발행자와 동일해야 한다
    (VOLATILE 발행 ↔ TRANSIENT_LOCAL 구독은 비호환 — CLAUDE.md §5).

    conftest 가 rclpy 를 대역으로 갈아끼우므로 실제 enum 을 못 쓴다.
    대신 rclpy.qos 대역을 심어 «무엇을 골랐는지» 를 직접 확인한다.
    """
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


# ── 잡 계약 ─────────────────────────────────────────────────
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
    # 모르는 것을 «비었다» 로 읽으면 없는 박스를 집으러 간다.
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


# ── 불일치 처리: stop / skip / ignore ────────────────────────
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
    """on_mismatch 를 안 적으면 기존 동작(정지)이어야 한다 — 기존 레시피 무영향."""
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
    # 실행 루프가 +1 을 더 하므로 다음 실행은 index 14 가 된다
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
    """역순으로 돌면서 앞으로 건너뛰면 의도와 반대로 간다 — 조용히 틀리느니 선다."""
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
    """모름은 «기대와 다름» 이 아니다. ignore 를 걸어도 진행하면 안 된다."""
    svc = _service()  # 아무것도 안 먹임 → 판정 불가
    ex = _executor_in_recipe(svc, index=5)
    for mode in ('stop', 'skip', 'ignore'):
        assert ex._exec_check_magazine(
            _Job(slot=1, expect='present', on_mismatch=mode,
                 skip_count=11, timeout=0.1)) is False, f'{mode} 에서 진행했다'
        assert ex.current_job_index == 5
