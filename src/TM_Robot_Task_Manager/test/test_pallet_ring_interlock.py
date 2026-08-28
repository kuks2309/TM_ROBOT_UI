#!/usr/bin/env python3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.recipe_manager import RecipeManager

RECIPE_DIR = Path(__file__).resolve().parents[1] / 'config' / 'recipes'

RINGS = {
    'pallet_ring_even_pick_place.yaml': [0, 2, 2, 4, 4, 0],
    'pallet_ring_odd_pick_place.yaml': [1, 3, 3, 5, 5, 1],
}


@pytest.fixture(params=sorted(RINGS), ids=lambda n: n.split('_')[2])
def ring(request):
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
    return index + int(job.params['skip_count']) + 1


def test_인터록이_여섯개다(checks):
    assert len(checks) == 6, '사이클 3개 × (집기·놓기) 여야 한다'


def test_집기놓기가_번갈아_나온다(checks):
    expects = [j.params['expect'] for _, j in checks]
    assert expects == ['present', 'empty'] * 3


def test_슬롯이_링_순서다(ring):
    name, _, checks = ring
    slots = [j.params['slot'] for _, j in checks]
    assert slots == RINGS[name]


def test_짝수홀수가_서로_섞이지_않는다(ring):
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
    places = [(i, j) for i, j in checks if j.params['expect'] == 'empty']
    for (index, job), (next_index, _) in zip(places, places[1:]):
        skipped = [jobs[k].type for k in range(index + 1, next_index)]
        assert 'smc_release' in skipped, f'idx{index} skip 구간에 그리퍼 열기가 안 들어있다'
        assert 'smc_grip' in skipped, f'idx{index} skip 구간에 파지가 안 들어있다'


def test_마지막_놓기는_stop이다(checks):
    last_index, last = [c for c in checks if c[1].params['expect'] == 'empty'][-1]
    assert last.params['on_mismatch'] == 'stop', (
        f'마지막 놓기 인터록(idx{last_index})이 stop 이 아니다')


def test_마지막_집기_skip은_레시피_끝을_넘는다(jobs, checks):
    last_index, last = [c for c in checks if c[1].params['expect'] == 'present'][-1]
    assert _landing(last_index, last) >= len(jobs)


def test_슬롯이_전부_범위안(checks):
    assert all(0 <= j.params['slot'] <= 5 for _, j in checks)
