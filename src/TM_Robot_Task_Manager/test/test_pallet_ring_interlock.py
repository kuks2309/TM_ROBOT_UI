#!/usr/bin/env python3
"""팔레트 순환 레시피(짝수·홀수)의 매거진 인터록 배선 계약 테스트.

skip_count 는 «잡 몇 개를 건너뛴다» 는 절대 숫자다. 사이클에 잡을 하나 넣거나 빼면
착지점이 조용히 어긋나 엉뚱한 데서 이어진다 — 그 순간을 여기서 잡는다.

지키는 계약 두 가지:
  · 집기 인터록의 skip 은 «다음 사이클의 집기 인터록» 에 정확히 착지한다
  · 놓기 인터록의 skip 은 «다음 사이클의 놓기 인터록» 에 정확히 착지한다
    (그 사이의 smc_release·smc_grip 을 건너뛰므로 쥔 박스를 놓치지 않는다)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.recipe_manager import RecipeManager

RECIPE_DIR = Path(__file__).resolve().parents[1] / 'config' / 'recipes'

# 링마다 도는 팔레트가 다르다 — 짝수는 로봇 앞쪽, 홀수는 뒤쪽.
RINGS = {
    'pallet_ring_even_pick_place.yaml': [0, 2, 2, 4, 4, 0],
    'pallet_ring_odd_pick_place.yaml': [1, 3, 3, 5, 5, 1],
}


@pytest.fixture(params=sorted(RINGS), ids=lambda n: n.split('_')[2])
def ring(request):
    """(레시피명, 잡 목록, 인터록 목록)."""
    name = request.param
    path = RECIPE_DIR / name
    if not path.exists():
        pytest.skip(f'레시피 없음: {path}')
    jobs = RecipeManager().load_recipe(str(path)).jobs
    checks = [(i, j) for i, j in enumerate(jobs) if j.type == 'check_magazine']
    return name, jobs, checks


@pytest.fixture
def jobs(ring):
    return ring[1]


@pytest.fixture
def checks(ring):
    return ring[2]


def _landing(index, job):
    """skip 발동 시 다음에 실행될 잡의 인덱스.

    핸들러가 current_job_index 에 skip_count 를 더하고, 실행 루프가 성공 후 1 을 더한다.
    """
    return index + int(job.params['skip_count']) + 1


def test_인터록이_여섯개다(checks):
    assert len(checks) == 6, '사이클 3개 × (집기·놓기) 여야 한다'


def test_집기놓기가_번갈아_나온다(checks):
    expects = [j.params['expect'] for _, j in checks]
    assert expects == ['present', 'empty'] * 3


def test_슬롯이_링_순서다(ring):
    """짝수는 P0→P2→P4→P0, 홀수는 P1→P3→P5→P1."""
    name, _, checks = ring
    slots = [j.params['slot'] for _, j in checks]
    assert slots == RINGS[name]


def test_짝수홀수가_서로_섞이지_않는다(ring):
    """짝수 레시피에 홀수 팔레트가 들어가면 로봇이 뒤쪽으로 횡단한다 — 링 분리의 이유."""
    name, _, checks = ring
    parity = 0 if 'even' in name else 1
    assert all(j.params['slot'] % 2 == parity for _, j in checks)


def test_집기_인터록_skip은_다음_집기_인터록에_착지(checks):
    picks = [(i, j) for i, j in checks if j.params['expect'] == 'present']
    for (index, job), (next_index, _) in zip(picks, picks[1:]):
        assert job.params['on_mismatch'] == 'skip'
        assert _landing(index, job) == next_index, (
            f'집기 인터록 idx{index} 의 skip 이 idx{_landing(index, job)} 에 떨어진다 '
            f'— 다음 집기 인터록은 idx{next_index}')


def test_놓기_인터록_skip은_다음_놓기_인터록에_착지(checks):
    places = [(i, j) for i, j in checks if j.params['expect'] == 'empty']
    for (index, job), (next_index, _) in zip(places, places[1:]):
        assert job.params['on_mismatch'] == 'skip'
        assert _landing(index, job) == next_index, (
            f'놓기 인터록 idx{index} 의 skip 이 idx{_landing(index, job)} 에 떨어진다 '
            f'— 다음 놓기 인터록은 idx{next_index}')


def test_놓기_skip이_건너뛰는_구간에_파지와_해제가_들어있다(jobs, checks):
    """쥔 박스를 놓치지 않으려면 건너뛰는 구간이 smc_release·smc_grip 을 삼켜야 한다."""
    places = [(i, j) for i, j in checks if j.params['expect'] == 'empty']
    for (index, job), (next_index, _) in zip(places, places[1:]):
        skipped = [jobs[k].type for k in range(index + 1, next_index)]
        assert 'smc_release' in skipped, f'idx{index} skip 구간에 그리퍼 열기가 안 들어있다'
        assert 'smc_grip' in skipped, f'idx{index} skip 구간에 파지가 안 들어있다'


def test_마지막_놓기는_stop이다(checks):
    """뒤에 갈 팔레트가 없다. skip 하면 박스를 쥔 채 레시피가 조용히 끝난다."""
    last_index, last = [c for c in checks if c[1].params['expect'] == 'empty'][-1]
    assert last.params['on_mismatch'] == 'stop', (
        f'마지막 놓기 인터록(idx{last_index})이 stop 이 아니다')


def test_마지막_집기_skip은_레시피_끝을_넘는다(jobs, checks):
    """마지막 사이클은 건너뛸 다음 사이클이 없으므로 끝으로 나가야 한다(정상 종료)."""
    last_index, last = [c for c in checks if c[1].params['expect'] == 'present'][-1]
    assert _landing(last_index, last) >= len(jobs)


def test_슬롯이_전부_범위안(checks):
    assert all(0 <= j.params['slot'] <= 5 for _, j in checks)
