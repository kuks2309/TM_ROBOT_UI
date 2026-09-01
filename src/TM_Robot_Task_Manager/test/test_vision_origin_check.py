"""job_executor vision_origin_check job 과 배치 정책을 검증한다."""
import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor
from tm_task_manager.recipe_manager import Job
from tm_task_manager.services.config_manager import ConfigManager
from tm_task_manager.services.vision_origin_check_service import VisionOriginCheckService


REFERENCE_LANDMARK = {'x': 12.11, 'y': 708.6, 'z': -35.31, 'rx': 179.24, 'ry': 0.44, 'rz': 178.86}
REFERENCE_TCP = {'x': 10.0, 'y': 700.0, 'z': -30.0, 'rx': 180.0, 'ry': 0.0, 'rz': 180.0}


def measurement(x=12.11, y=708.6, z=-35.31, rx=179.24, ry=0.44, rz=178.86, detected=True):
    return {'x': x, 'y': y, 'z': z, 'rx': rx, 'ry': ry, 'rz': rz, 'detected': detected}


@pytest.fixture
def vision_manager():
    vm = MagicMock()
    vm.execute_tm_landmark_scan.return_value = (True, "Landmark 인식 완료")
    vm.execute_tm_landmark_jig_scan.return_value = (True, "Jig 인식 완료")
    vm.execute_tm_landmark_read.return_value = (True, measurement())
    vm.execute_tm_landmark_jig_read.return_value = (True, measurement())
    return vm


@pytest.fixture
def node():
    n = MagicMock()
    n.current_base_name = 'RobotBase'
    n.current_tcp_pose = [10.0, 700.0, -30.0, 180.0, 0.0, 180.0]
    return n


@pytest.fixture
def executor(node, vision_manager, tmp_path):
    ex = JobExecutor(ros_node=node, vision_manager=vision_manager)
    ex.logs = []
    ex.on_log = ex.logs.append

    ex.move_calls = []

    def _fake_move(motion_type, x, y, z, rx, ry, rz, velocity, decomposed_tcp=False):
        ex.move_calls.append((motion_type, x, y, z, rx, ry, rz, velocity))
        return True, f"이동 완료 ({x:.2f}, {y:.2f}, {z:.2f})"

    ex._move_to_position = _fake_move

    ex.vision_origin_check_service = VisionOriginCheckService(
        config_manager=ConfigManager(config_path=str(tmp_path / 'positions.yaml')),
        log_callback=ex.logs.append,
    )

    ex.alarms = []
    ex.on_origin_check_alarm = ex.alarms.append
    return ex


@pytest.fixture
def learned_executor(executor):
    executor.vision_origin_check_service.save_reference(
        tcp_pose=REFERENCE_TCP, landmark=REFERENCE_LANDMARK
    )
    executor.vision_origin_check_service.set_tolerance(1.0, 0.5)
    return executor


def verify_job(**params):
    return Job(job_id=1, job_type='vision_origin_check', params=params)


def logs_of(executor):
    return "\n".join(executor.logs)


class TestScanLandmarkAveraged:
    def test_uses_plain_landmark_path_by_default(self, executor, vision_manager):
        pose, analysis = executor.scan_landmark_averaged(1, 'none', 0.1)

        assert pose is not None
        vision_manager.execute_tm_landmark_scan.assert_called_once()
        vision_manager.execute_tm_landmark_read.assert_called_once()
        vision_manager.execute_tm_landmark_jig_scan.assert_not_called()
        vision_manager.execute_tm_landmark_jig_read.assert_not_called()

    def test_uses_jig_path_when_jig_number_given(self, executor, vision_manager):
        pose, analysis = executor.scan_landmark_averaged(1, 'none', 0.1, jig_number=3)

        assert pose is not None
        vision_manager.execute_tm_landmark_jig_scan.assert_called_once_with(3, 0.1, pause_ethernet=False)
        vision_manager.execute_tm_landmark_jig_read.assert_called_once_with(3)
        vision_manager.execute_tm_landmark_scan.assert_not_called()

    def test_averages_repeated_measurements(self, executor, vision_manager):
        vision_manager.execute_tm_landmark_read.side_effect = [
            (True, measurement(x=10.0)),
            (True, measurement(x=12.0)),
            (True, measurement(x=14.0)),
        ]

        pose, analysis = executor.scan_landmark_averaged(3, 'none', 0.1)

        assert pose['x'] == pytest.approx(12.0)
        assert analysis['count_original'] == 3

    def test_skips_undetected_measurements(self, executor, vision_manager):
        vision_manager.execute_tm_landmark_read.side_effect = [
            (True, measurement(x=10.0)),
            (True, measurement(x=999.0, detected=False)),
        ]

        pose, analysis = executor.scan_landmark_averaged(2, 'none', 0.1)

        assert pose['x'] == pytest.approx(10.0)
        assert analysis['count_original'] == 1

    def test_continues_after_failed_scan_attempt(self, executor, vision_manager):
        vision_manager.execute_tm_landmark_scan.side_effect = [
            (False, "스캔 타임아웃"),
            (True, "Landmark 인식 완료"),
        ]
        vision_manager.execute_tm_landmark_read.return_value = (True, measurement(x=11.0))

        pose, _ = executor.scan_landmark_averaged(2, 'none', 0.1)

        assert pose['x'] == pytest.approx(11.0)
        assert vision_manager.execute_tm_landmark_read.call_count == 1

    def test_returns_none_when_no_valid_measurement(self, executor, vision_manager):
        vision_manager.execute_tm_landmark_read.return_value = (False, "결과 읽기 실패")

        pose, analysis = executor.scan_landmark_averaged(2, 'none', 0.1)

        assert pose is None and analysis is None
        assert "유효한 측정값 없음" in logs_of(executor)


class TestVisionOriginCheckGuards:
    def test_fails_without_service(self, executor):
        executor.vision_origin_check_service = None
        assert executor._execute_job(verify_job()) is False

    def test_fails_when_reference_not_learned(self, executor, vision_manager):
        assert executor._execute_job(verify_job()) is False
        assert "학습" in logs_of(executor)
        vision_manager.execute_tm_landmark_scan.assert_not_called()

    def test_fails_when_base_is_not_robot_base(self, learned_executor, node, vision_manager):
        node.current_base_name = 'vision_TM_Landmark_detection'

        assert learned_executor._execute_job(verify_job()) is False
        assert "RobotBase" in logs_of(learned_executor)
        vision_manager.execute_tm_landmark_scan.assert_not_called()

    def test_does_not_measure_when_move_fails(self, learned_executor, vision_manager):
        def _failing_move(*args, **kwargs):
            return False, "이동 실패"

        learned_executor._move_to_position = _failing_move

        assert learned_executor._execute_job(verify_job()) is False
        vision_manager.execute_tm_landmark_scan.assert_not_called()

    def test_fails_when_measurement_unavailable(self, learned_executor, vision_manager):
        vision_manager.execute_tm_landmark_read.return_value = (False, "결과 읽기 실패")

        assert learned_executor._execute_job(verify_job(repeat_count=1)) is False
        assert learned_executor.alarms == []


class TestVisionOriginCheckMotion:
    def test_moves_to_learned_tcp_pose(self, learned_executor):
        learned_executor._execute_job(verify_job(repeat_count=1, velocity=30.0))

        assert learned_executor.move_calls == [
            ('tcp', 10.0, 700.0, -30.0, 180.0, 0.0, 180.0, 30.0)
        ]

    def test_skips_move_when_disabled(self, learned_executor):
        learned_executor._execute_job(
            verify_job(repeat_count=1, move_to_reference=False)
        )

        assert learned_executor.move_calls == []


class TestVisionOriginCheckJudgement:
    def test_passes_within_tolerance(self, learned_executor):
        assert learned_executor._execute_job(verify_job(repeat_count=1)) is True
        assert learned_executor.alarms == []
        assert "통과" in logs_of(learned_executor)

    def test_fails_and_alarms_beyond_tolerance(self, learned_executor, vision_manager):
        vision_manager.execute_tm_landmark_read.return_value = (True, measurement(x=20.0))

        assert learned_executor._execute_job(verify_job(repeat_count=1)) is False
        assert len(learned_executor.alarms) == 1

        alarm = learned_executor.alarms[0]
        assert alarm.passed is False
        assert alarm.failed_axes == ['x']
        assert "교정" in logs_of(learned_executor)

    def test_alarm_is_optional(self, learned_executor, vision_manager):
        learned_executor.on_origin_check_alarm = None
        vision_manager.execute_tm_landmark_read.return_value = (True, measurement(x=20.0))

        assert learned_executor._execute_job(verify_job(repeat_count=1)) is False

    def test_does_not_clobber_scan_state_of_other_jobs(self, learned_executor):
        learned_executor.detected_landmark_pose = {'sentinel': True}

        learned_executor._execute_job(verify_job(repeat_count=1))

        assert learned_executor.detected_landmark_pose == {'sentinel': True}


class TestJobDispatch:
    def test_dispatches_vision_origin_check(self, learned_executor):
        assert learned_executor._execute_job(verify_job(repeat_count=1)) is True

    def test_unknown_job_type_still_fails(self, executor):
        assert executor._execute_job(Job(job_id=9, job_type='nonexistent_job')) is False


class TestPublicVerifyEntryPoint:
    def test_matches_job_path_on_pass(self, learned_executor):
        assert learned_executor.vision_origin_check(repeat_count=1) is True
        assert learned_executor.last_origin_check_result.passed is True

    def test_records_result_on_failure(self, learned_executor, vision_manager):
        vision_manager.execute_tm_landmark_read.return_value = (True, measurement(x=20.0))

        assert learned_executor.vision_origin_check(repeat_count=1) is False
        assert learned_executor.last_origin_check_result.failed_axes == ['x']

    def test_clears_stale_result_when_guard_rejects(self, learned_executor, node):
        learned_executor.vision_origin_check(repeat_count=1)
        assert learned_executor.last_origin_check_result is not None

        node.current_base_name = 'vision_TM_Landmark_detection'
        assert learned_executor.vision_origin_check(repeat_count=1) is False
        assert learned_executor.last_origin_check_result is None


def placement_recipe(*jobs):
    recipe = MagicMock()
    recipe.jobs = list(jobs)
    return recipe


def info_job(policy):
    return Job(job_id=0, job_type='recipe_info', params={'vision_origin_check': policy})


def move_job():
    return Job(job_id=5, job_type='move_to_point', params={})


@pytest.fixture
def monitor_tab():
    from tm_task_manager.tabs.run_monitor_tab import RunMonitorTab
    return RunMonitorTab(MagicMock())


class TestVisionOriginCheckPlacement:
    def test_passes_when_policy_is_none(self, monitor_tab):
        recipe = placement_recipe(info_job('none'), move_job())
        assert monitor_tab._validate_vision_origin_check_placement(recipe) == (True, '')

    def test_passes_when_recipe_info_absent(self, monitor_tab):
        recipe = placement_recipe(move_job())
        assert monitor_tab._validate_vision_origin_check_placement(recipe)[0] is True

    def test_first_policy_ignores_recipe_info_position(self, monitor_tab):
        recipe = placement_recipe(info_job('first'), verify_job(), move_job())
        assert monitor_tab._validate_vision_origin_check_placement(recipe)[0] is True

    def test_first_policy_rejects_when_not_leading(self, monitor_tab):
        recipe = placement_recipe(info_job('first'), move_job(), verify_job())
        is_valid, reason = monitor_tab._validate_vision_origin_check_placement(recipe)
        assert is_valid is False
        assert '첫 번째' in reason

    def test_last_policy_accepts_trailing_check(self, monitor_tab):
        recipe = placement_recipe(info_job('last'), move_job(), verify_job())
        assert monitor_tab._validate_vision_origin_check_placement(recipe)[0] is True

    def test_last_policy_rejects_when_not_trailing(self, monitor_tab):
        recipe = placement_recipe(info_job('last'), verify_job(), move_job())
        is_valid, reason = monitor_tab._validate_vision_origin_check_placement(recipe)
        assert is_valid is False
        assert '마지막' in reason

    def test_both_policy_requires_both_ends(self, monitor_tab):
        ok = placement_recipe(info_job('both'), verify_job(), move_job(), verify_job())
        assert monitor_tab._validate_vision_origin_check_placement(ok)[0] is True

        half = placement_recipe(info_job('both'), verify_job(), move_job())
        is_valid, reason = monitor_tab._validate_vision_origin_check_placement(half)
        assert is_valid is False
        assert '마지막' in reason and '첫 번째' not in reason

    def test_rejects_recipe_with_only_metadata(self, monitor_tab):
        recipe = placement_recipe(info_job('first'))
        is_valid, reason = monitor_tab._validate_vision_origin_check_placement(recipe)
        assert is_valid is False
        assert '실행할 Job이 없습니다' in reason
