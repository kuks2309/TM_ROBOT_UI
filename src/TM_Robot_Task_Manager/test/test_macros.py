"""macros 패키지(레지스트리·실행 계약·블랙보드·시퀀스 검증)를 검증한다."""
import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job, RecipeManager
from tm_task_manager.macros import (
    MACROS,
    MacroContext,
    MacroResult,
    get_macro,
    run_macro,
    validate_sequence,
)
from tm_task_manager.macros.base import MacroSpec


@pytest.fixture
def executor():
    node = MagicMock()
    node.current_base_name = 'RobotBase'
    ex = JobExecutor(ros_node=node, vision_manager=MagicMock())
    ex.logs = []
    ex.on_log = ex.logs.append
    return ex


@pytest.fixture
def ctx(executor):
    return executor._macro_context()


class TestMacroResult:
    def test_success_carries_data(self):
        r = MacroResult.success('done', value=3)
        assert r.ok is True and r.message == 'done' and r.data == {'value': 3}

    def test_failure_is_not_ok(self):
        r = MacroResult.failure('nope')
        assert r.ok is False and r.data == {}


class TestRegistry:
    def test_builtin_macros_registered(self):
        assert 'wait' in MACROS
        assert 'vision_origin_check' in MACROS

    def test_spec_declares_contract(self):
        spec = get_macro('vision_origin_check')
        assert spec.produces == ['origin_check_result']
        assert spec.external_requires() == ['taught_origin']
        assert spec.blackboard_requires() == []

    def test_unknown_macro_is_none(self):
        assert get_macro('does_not_exist') is None


class TestRunMacro:
    def test_unknown_macro_fails_gracefully(self, ctx):
        result = run_macro('does_not_exist', ctx)
        assert result.ok is False
        assert 'does_not_exist' in result.message

    def test_applies_declared_defaults(self, ctx):
        result = run_macro('wait', ctx, {'duration': 0})
        assert result.ok is True

    def test_ignores_params_the_macro_does_not_declare(self, ctx):
        result = run_macro('wait', ctx, {'duration': 0, 'unrelated_job_param': 'x'})
        assert result.ok is True

    def test_stop_request_aborts_wait(self, executor, ctx):
        executor._stop_requested = True
        result = run_macro('wait', ctx, {'duration': 1000})
        assert result.ok is False
        assert '취소' in result.message

    def test_blackboard_requires_blocks_execution(self, ctx):
        MACROS['_probe_needs'] = MacroSpec(
            name='_probe_needs', summary='t', category='Test', params={},
            fn=lambda c: MacroResult.success(), requires=['never_produced'],
        )
        try:
            result = run_macro('_probe_needs', ctx)
            assert result.ok is False
            assert 'never_produced' in result.message
        finally:
            del MACROS['_probe_needs']

    def test_bool_return_is_wrapped(self, ctx):
        MACROS['_probe_bool'] = MacroSpec(
            name='_probe_bool', summary='t', category='Test', params={},
            fn=lambda c: True,
        )
        try:
            assert run_macro('_probe_bool', ctx).ok is True
        finally:
            del MACROS['_probe_bool']


class TestValidateSequence:
    def test_accepts_satisfied_order(self):
        ok, problems = validate_sequence(['wait', 'vision_origin_check'])
        assert ok is True and problems == []

    def test_rejects_unknown_macro(self):
        ok, problems = validate_sequence(['nope'])
        assert ok is False and 'nope' in problems[0]

    def test_detects_out_of_order_dependency(self):
        MACROS['_probe_producer'] = MacroSpec(
            name='_probe_producer', summary='t', category='Test', params={},
            fn=lambda c: MacroResult.success(), produces=['thing'])
        MACROS['_probe_consumer'] = MacroSpec(
            name='_probe_consumer', summary='t', category='Test', params={},
            fn=lambda c: MacroResult.success(), requires=['thing'])
        try:
            assert validate_sequence(['_probe_producer', '_probe_consumer'])[0] is True

            ok, problems = validate_sequence(['_probe_consumer', '_probe_producer'])
            assert ok is False and 'thing' in problems[0]
        finally:
            del MACROS['_probe_producer']
            del MACROS['_probe_consumer']


class TestJobIncludesMacros:
    def test_declared_job_types_reference_registered_macros(self):
        for job_type, spec in RecipeManager.JOB_TYPES.items():
            for macro_def in spec.get('macros', []):
                assert get_macro(macro_def['use']) is not None, \
                    f"{job_type} 이 등록되지 않은 매크로 '{macro_def['use']}' 를 참조합니다"

    def test_declared_job_sequences_are_valid(self):
        for job_type, spec in RecipeManager.JOB_TYPES.items():
            uses = [m['use'] for m in spec.get('macros', [])]
            if uses:
                ok, problems = validate_sequence(uses)
                assert ok, f"{job_type}: {problems}"

    def test_wait_job_runs_through_macro_path(self, executor):
        job = Job(job_id=1, job_type='wait', params={'duration': 0})
        assert executor._execute_job(job) is True
        assert any('WAIT' in line for line in executor.logs)

    def test_composite_job_runs_both_macros_in_order(self, executor):
        calls = []
        MACROS['_probe_a'] = MacroSpec(
            name='_probe_a', summary='t', category='Test', params={},
            fn=lambda c: (calls.append('a'), MacroResult.success())[1])
        MACROS['_probe_b'] = MacroSpec(
            name='_probe_b', summary='t', category='Test', params={},
            fn=lambda c: (calls.append('b'), MacroResult.success())[1])
        try:
            job = Job(job_id=1, job_type='_probe_job', params={})
            assert executor._run_macro_sequence(
                job, [{'use': '_probe_a'}, {'use': '_probe_b'}]) is True
            assert calls == ['a', 'b']
        finally:
            del MACROS['_probe_a']
            del MACROS['_probe_b']

    def test_sequence_stops_at_first_failure(self, executor):
        calls = []
        MACROS['_probe_fail'] = MacroSpec(
            name='_probe_fail', summary='t', category='Test', params={},
            fn=lambda c: MacroResult.failure('boom'))
        MACROS['_probe_after'] = MacroSpec(
            name='_probe_after', summary='t', category='Test', params={},
            fn=lambda c: (calls.append('after'), MacroResult.success())[1])
        try:
            job = Job(job_id=1, job_type='_probe_job', params={})
            assert executor._run_macro_sequence(
                job, [{'use': '_probe_fail'}, {'use': '_probe_after'}]) is False
            assert calls == []
        finally:
            del MACROS['_probe_fail']
            del MACROS['_probe_after']

    def test_bind_maps_job_param_to_macro_param(self, executor):
        seen = {}
        MACROS['_probe_bind'] = MacroSpec(
            name='_probe_bind', summary='t', category='Test',
            params={'duration': {'type': 'int', 'default': 1}},
            fn=lambda c, duration=1: (seen.update(duration=duration), MacroResult.success())[1])
        try:
            job = Job(job_id=1, job_type='_probe_job', params={'settle_ms': 777})
            executor._run_macro_sequence(
                job, [{'use': '_probe_bind', 'bind': {'duration': 'settle_ms'}}])
            assert seen['duration'] == 777
        finally:
            del MACROS['_probe_bind']


class TestBlackboard:
    def test_shared_between_macros_in_one_run(self, executor):
        MACROS['_probe_put'] = MacroSpec(
            name='_probe_put', summary='t', category='Test', params={},
            fn=lambda c: (c.put('shared', 42), MacroResult.success())[1],
            produces=['shared'])
        MACROS['_probe_read'] = MacroSpec(
            name='_probe_read', summary='t', category='Test', params={},
            fn=lambda c: MacroResult.success(seen=c.get('shared')),
            requires=['shared'])
        try:
            job = Job(job_id=1, job_type='_probe_job', params={})
            assert executor._run_macro_sequence(
                job, [{'use': '_probe_put'}, {'use': '_probe_read'}]) is True
            assert executor.macro_blackboard['shared'] == 42
        finally:
            del MACROS['_probe_put']
            del MACROS['_probe_read']

    def test_cleared_when_recipe_run_starts(self, executor):
        executor.macro_blackboard['stale'] = 1
        recipe = MagicMock()
        recipe.jobs = [Job(job_id=1, job_type='wait', params={'duration': 0})]
        executor.load_recipe(recipe)
        executor.run_from(0)
        assert 'stale' not in executor.macro_blackboard

    def test_last_origin_check_result_reads_blackboard(self, executor):
        assert executor.last_origin_check_result is None
        executor.macro_blackboard['origin_check_result'] = 'sentinel'
        assert executor.last_origin_check_result == 'sentinel'


class TestMacroContext:
    def test_emit_is_safe_without_callback(self, ctx, executor):
        executor.on_origin_check_alarm = None
        ctx.emit('on_origin_check_alarm', 'payload')

    def test_emit_forwards_to_callback(self, ctx, executor):
        received = []
        executor.on_origin_check_alarm = received.append
        ctx.emit('on_origin_check_alarm', 'payload')
        assert received == ['payload']

    def test_exposes_executor_handles(self, ctx, executor):
        assert ctx.ros_node is executor.ros_node
        assert ctx.vision_manager is executor.vision_manager
