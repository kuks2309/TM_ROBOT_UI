#!/usr/bin/env python3
"""tabs/task_edit_tab 버튼 라벨 규칙을 검증한다."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tm_task_manager.recipe_manager import RecipeManager
from tm_task_manager.tabs.task_edit_tab import TaskEditTab

MOVE_LABEL = "이 위치로 이동"


class _Job:
    def __init__(self, t):
        self.type = t


class _FakeTab:
    def __init__(self, param_widgets=None):
        self.param_widgets = param_widgets or {}
        self.recipe_manager = RecipeManager()


def label(job_type, param_widgets=None):
    return TaskEditTab._exec_button_label(_FakeTab(param_widgets), _Job(job_type))


GRIPPER = ['smc_grip', 'smc_release', 'smc_home',
           'schunk_grip', 'schunk_release', 'schunk_home']


@pytest.mark.parametrize("jt", GRIPPER)
def test_그리퍼_잡은_이동이라고_말하지_않는다(jt):
    got = label(jt)
    assert got != MOVE_LABEL, f"{jt} 가 «이동» 으로 표시된다"
    assert got == RecipeManager.JOB_TYPES[jt]['name']


def test_check_magazine_라벨():
    assert label('check_magazine') == '매거진 재고 확인'


def test_이동_파라미터가_있으면_이동_라벨():
    assert label('move_to_point', {'motion_type': object()}) == MOVE_LABEL


def test_등록된_모든_잡이_이름을_가진다():
    bad = []
    for jt, spec in RecipeManager.JOB_TYPES.items():
        if jt == 'recipe_info':
            continue
        if 'motion_type' in (spec.get('params') or {}):
            continue
        if label(jt) == MOVE_LABEL:
            bad.append(jt)
    assert not bad, f"«이동» 으로 잘못 표시되는 Task: {bad}"


def test_미등록_타입은_이동_라벨로_폴백():
    assert label('존재하지_않는_잡') == MOVE_LABEL
