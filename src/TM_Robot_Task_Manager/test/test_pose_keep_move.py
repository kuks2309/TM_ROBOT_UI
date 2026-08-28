import math
import pytest
from unittest.mock import MagicMock

from tm_task_manager.job_executor import JobExecutor, POSE_KEEP_MIN_SEGMENT_MM
from tm_task_manager.recipe_manager import Job


def _angle_difference_deg(target, current):
    diff = (target - current + 180.0) % 360.0 - 180.0
    return abs(diff)


@pytest.fixture
def node():
    n = MagicMock()
    n.current_base_name = 'RobotBase'
    n.current_tcp_pose = [100.0, 200.0, 300.0, 0.0, 90.0, 0.0]
    n._call_set_positions = MagicMock(return_value=(True, "이동 완료"))
    n.motion_service._angle_difference_deg = _angle_difference_deg
    return n


@pytest.fixture
def executor(node):
    ex = JobExecutor(ros_node=node)
    ex.logs = []
    ex.on_log = ex.logs.append
    return ex


def make_job(coordinate_mode=None, **params):
    return Job(job_id=1, job_type='pose_keep_move_to_point',
               params=params, coordinate_mode=coordinate_mode)


def sent_positions(node):
    return [call.args[1] for call in node._call_set_positions.call_args_list]



class TestBuildPoseKeepSegments:
    TCP = [100.0, 200.0, 300.0, 0.0, 90.0, 0.0]
    VEL = 10.0

    def build(self, executor, x, y, z, **kw):
        return executor._build_pose_keep_segments(self.TCP, x, y, z, self.VEL, **kw)

    def test_ascend_z_first(self, executor):
        segs = self.build(executor, 150.0, 200.0, 400.0)

        assert segs == [
            ('Z 상승', 100.0, 200.0, 400.0, self.VEL),
            ('XY 이동', 150.0, 200.0, 400.0, self.VEL),
        ]

    def test_descend_xy_first(self, executor):
        segs = self.build(executor, 150.0, 200.0, 250.0)

        assert segs == [
            ('XY 이동', 150.0, 200.0, 300.0, self.VEL),
            ('Z 하강', 150.0, 200.0, 250.0, self.VEL),
        ]

    def test_same_height_single_xy_segment(self, executor):
        segs = self.build(executor, 150.0, 260.0, 300.0)

        assert segs == [('XY 이동', 150.0, 260.0, 300.0, self.VEL)]

    def test_pure_z_ascend_only(self, executor):
        segs = self.build(executor, 100.0, 200.0, 400.0)

        assert segs == [('Z 상승', 100.0, 200.0, 400.0, self.VEL)]

    def test_pure_z_descend_only(self, executor):
        segs = self.build(executor, 100.0, 200.0, 250.0)

        assert segs == [('Z 하강', 100.0, 200.0, 250.0, self.VEL)]

    def test_below_threshold_no_segment(self, executor):
        tiny = POSE_KEEP_MIN_SEGMENT_MM / 10.0
        segs = self.build(executor, 100.0 + tiny, 200.0, 300.0 + tiny)

        assert segs == []

    def test_just_above_threshold_included(self, executor):
        segs = self.build(executor, 100.0 + POSE_KEEP_MIN_SEGMENT_MM * 1.5, 200.0, 300.0)

        assert len(segs) == 1
        assert segs[0][0] == 'XY 이동'



class TestDescentDamping:
    TCP = [100.0, 200.0, 300.0, 0.0, 90.0, 0.0]

    def test_long_descent_splits_into_approach_and_decel(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 100.0, 200.0, 200.0, 25.0,
            decel_zone_mm=40.0, decel_velocity=10.0
        )

        assert segs == [
            ('Z 하강', 100.0, 200.0, 240.0, 25.0),
            ('Z 하강(감속 진입)', 100.0, 200.0, 200.0, 10.0),
        ]

    def test_short_descent_uses_decel_velocity_whole(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 100.0, 200.0, 280.0, 25.0,
            decel_zone_mm=40.0, decel_velocity=10.0
        )

        assert segs == [('Z 하강(저속)', 100.0, 200.0, 280.0, 10.0)]

    def test_no_split_when_already_slow(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 100.0, 200.0, 200.0, 10.0,
            decel_zone_mm=40.0, decel_velocity=10.0
        )

        assert segs == [('Z 하강', 100.0, 200.0, 200.0, 10.0)]

    def test_zone_zero_disables_damping(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 100.0, 200.0, 200.0, 25.0,
            decel_zone_mm=0.0, decel_velocity=10.0
        )

        assert segs == [('Z 하강', 100.0, 200.0, 200.0, 25.0)]

    def test_ascend_is_not_damped(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 100.0, 200.0, 400.0, 25.0,
            decel_zone_mm=40.0, decel_velocity=10.0
        )

        assert segs == [('Z 상승', 100.0, 200.0, 400.0, 25.0)]

    def test_exec_applies_damping_by_default(self, executor, node):
        job = make_job(X=100.0, Y=200.0, Z=100.0, velocity=25.0)

        assert executor._exec_pose_keep_move_to_point(job) is True

        calls = node._call_set_positions.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs['velocity'] == 25.0
        assert calls[1].kwargs['velocity'] == 10.0
        assert calls[1].args[1][2] == pytest.approx(0.100)
        assert calls[0].args[1][2] == pytest.approx(0.140)



class TestPoseKeepMoveExecution:
    def test_orientation_locked_on_every_segment(self, executor, node):
        job = make_job(X=150.0, Y=200.0, Z=400.0, velocity=10.0)

        assert executor._exec_pose_keep_move_to_point(job) is True

        positions = sent_positions(node)
        assert len(positions) == 2
        lock_rad = [0.0, math.pi / 2.0, 0.0]
        for pos in positions:
            assert pos[3:6] == pytest.approx(lock_rad)

    def test_ascend_moves_z_before_xy(self, executor, node):
        job = make_job(X=150.0, Y=200.0, Z=400.0)

        assert executor._exec_pose_keep_move_to_point(job) is True

        first, second = sent_positions(node)
        assert first[:3] == pytest.approx([0.100, 0.200, 0.400])
        assert second[:3] == pytest.approx([0.150, 0.200, 0.400])

    def test_descend_moves_xy_before_z(self, executor, node):
        job = make_job(X=150.0, Y=200.0, Z=250.0)

        assert executor._exec_pose_keep_move_to_point(job) is True

        first, second = sent_positions(node)
        assert first[:3] == pytest.approx([0.150, 0.200, 0.300])
        assert second[:3] == pytest.approx([0.150, 0.200, 0.250])

    def test_default_velocity_is_10_percent(self, executor, node):
        job = make_job(X=150.0, Y=200.0, Z=400.0)

        executor._exec_pose_keep_move_to_point(job)

        assert node._call_set_positions.call_args_list[0].kwargs['velocity'] == 10.0

    def test_offset_applied_to_target(self, executor, node):
        job = make_job(X=150.0, Y=200.0, Z=400.0,
                       **{'offset X': 10.0, 'offset Y': -5.0, 'offset Z': 20.0})

        assert executor._exec_pose_keep_move_to_point(job) is True

        last = sent_positions(node)[-1]
        assert last[:3] == pytest.approx([0.160, 0.195, 0.420])

    def test_abort_remaining_segments_on_failure(self, executor, node):
        node._call_set_positions = MagicMock(return_value=(False, "LINE_T 거절"))
        job = make_job(X=150.0, Y=200.0, Z=400.0)

        assert executor._exec_pose_keep_move_to_point(job) is False
        assert node._call_set_positions.call_count == 1
        assert any('중단' in log for log in executor.logs)

    def test_skip_when_below_threshold(self, executor, node):
        job = make_job(X=100.0, Y=200.0, Z=300.0)

        assert executor._exec_pose_keep_move_to_point(job) is True
        assert node._call_set_positions.call_count == 0

    def test_dispatch_via_execute_job(self, executor, node):
        job = make_job(X=150.0, Y=200.0, Z=400.0)

        assert executor._execute_job(job) is True
        assert node._call_set_positions.call_count == 2

    def test_orientation_deviation_logged(self, executor):
        job = make_job(X=150.0, Y=200.0, Z=400.0)

        executor._exec_pose_keep_move_to_point(job)

        assert sum('[자세검증]' in log for log in executor.logs) == 2



class TestPoseKeepMoveRejection:
    def test_reject_non_robotbase_frame(self, executor, node):
        node.current_base_name = 'UserBase1'
        job = make_job(X=150.0, Y=200.0, Z=400.0)

        assert executor._exec_pose_keep_move_to_point(job) is False
        assert node._call_set_positions.call_count == 0

    def test_reject_all_zero_target(self, executor, node):
        job = make_job(X=0.0, Y=0.0, Z=0.0)

        assert executor._exec_pose_keep_move_to_point(job) is False
        assert node._call_set_positions.call_count == 0

    def test_reject_when_tcp_pose_unavailable(self, executor, node):
        node.current_tcp_pose = None
        job = make_job(X=150.0, Y=200.0, Z=400.0)

        assert executor._exec_pose_keep_move_to_point(job) is False
        assert node._call_set_positions.call_count == 0

    def test_reject_relative_without_landmark(self, executor, node):
        job = make_job(coordinate_mode='relative', X=10.0, Y=0.0, Z=5.0)
        executor.tm_transform_matrix = None

        assert executor._exec_pose_keep_move_to_point(job) is False
        assert node._call_set_positions.call_count == 0


class TestStraightPath:
    """straight=True — 현재점→목표점 한 직선 (법선따라 하강/상승).

    평면 좌표계에서 접근점과 파지점은 X/Y 오프셋이 같으므로 그 사이 직선이 곧 법선이다.
    기본값(False)은 L 자를 유지해야 한다 — 장거리 이동이 대각선이 되면 장애물에 부딪힌다.
    """

    TCP = [100.0, 200.0, 300.0, 0.0, 90.0, 0.0]

    def test_descend_is_one_line_no_xy_first(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 102.8, 200.0, 200.0, 10.0,
            decel_zone_mm=0.0, straight=True
        )

        assert segs == [('직선 하강', 102.8, 200.0, 200.0, 10.0)]

    def test_ascend_is_one_line_no_z_first(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 102.8, 200.0, 400.0, 20.0,
            decel_zone_mm=40.0, decel_velocity=10.0, straight=True
        )

        assert segs == [('직선 상승', 102.8, 200.0, 400.0, 20.0)]

    def test_decel_split_stays_on_the_same_line(self, executor):
        """감속 분할이 경로를 꺾으면 안 된다 — 내분점이 직선 위에 있어야 한다."""
        segs = executor._build_pose_keep_segments(
            self.TCP, 110.0, 200.0, 200.0, 25.0,
            decel_zone_mm=40.0, decel_velocity=10.0, straight=True
        )

        assert len(segs) == 2
        assert segs[0][0] == '직선 하강'
        assert segs[1] == ('직선 하강(감속 진입)', 110.0, 200.0, 200.0, 10.0)

        # 100mm 중 60mm 지점 → x 는 10mm 중 6mm 진행
        assert segs[0][1] == pytest.approx(106.0)
        assert segs[0][3] == pytest.approx(240.0)

        # 두 구간의 방향이 같은가(= 꺾이지 않았는가)
        def unit(ax, ay, az, bx, by, bz):
            d = (bx - ax, by - ay, bz - az)
            n = math.sqrt(sum(c * c for c in d))
            return tuple(c / n for c in d)

        first = unit(self.TCP[0], self.TCP[1], self.TCP[2],
                     segs[0][1], segs[0][2], segs[0][3])
        second = unit(segs[0][1], segs[0][2], segs[0][3],
                      segs[1][1], segs[1][2], segs[1][3])
        assert first == pytest.approx(second)

    def test_short_descent_uses_decel_velocity_whole(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 101.0, 200.0, 280.0, 25.0,
            decel_zone_mm=40.0, decel_velocity=10.0, straight=True
        )

        assert segs == [('직선 하강(저속)', 101.0, 200.0, 280.0, 10.0)]

    def test_below_threshold_no_segment(self, executor):
        segs = executor._build_pose_keep_segments(
            self.TCP, 100.0, 200.0, 300.0, 10.0, straight=True
        )

        assert segs == []

    def test_diagonal_distance_counts_not_just_z(self, executor):
        """Z 차이는 문턱 미만이어도 수평으로 움직이면 이동해야 한다."""
        segs = executor._build_pose_keep_segments(
            self.TCP, 105.0, 200.0, 300.0, 10.0, straight=True
        )

        assert segs == [('직선 상승', 105.0, 200.0, 300.0, 10.0)]

    def test_default_is_still_L_shaped(self, executor):
        """기본값은 절대 바뀌면 안 된다 — 장거리 이동이 대각선이 되면 장애물에 박는다."""
        segs = executor._build_pose_keep_segments(
            self.TCP, 500.0, 700.0, 200.0, 25.0,
            decel_zone_mm=40.0, decel_velocity=10.0
        )

        assert segs[0] == ('XY 이동', 500.0, 700.0, 300.0, 25.0)
        assert segs[1][0] == 'Z 하강'


class TestPlanePoseStraightParam:
    """잡 파라미터 straight_path 가 엔진까지 배선됐는가."""

    PLATE = {'x': 817.652, 'y': 215.032, 'z': -325.950,
             'rx': 0.261, 'ry': -0.074, 'rz': 89.574}

    def _plane_job(self, **extra):
        params = {
            'offset_x': 0.0, 'offset_y': 0.0, 'offset_z': 100.0,
            'offset_rx': 180.0, 'offset_ry': 0.0, 'offset_rz': 0.0,
            'velocity': 10.0,
        }
        params.update(extra)
        return Job(job_id=1, job_type='move_to_plane_pose', params=params)

    def _capture(self, executor, monkeypatch):
        executor.detected_plate_pose = dict(self.PLATE)
        seen = {}

        def fake(label, target, velocity, decel_zone_mm, decel_velocity,
                 straight=False):
            seen['straight'] = straight
            return True

        monkeypatch.setattr(executor, '_move_pose_keep', fake)
        return seen

    def test_param_declared_in_schema(self):
        from tm_task_manager.recipe_manager import RecipeManager

        spec = RecipeManager.JOB_TYPES['move_to_plane_pose']['params']['straight_path']
        assert spec['type'] == 'bool'
        assert spec['default'] is False

    def test_straight_path_reaches_move_pose_keep(self, executor, monkeypatch):
        seen = self._capture(executor, monkeypatch)

        assert executor._exec_move_to_plane_pose(self._plane_job(straight_path=True))
        assert seen['straight'] is True

    def test_default_is_false(self, executor, monkeypatch):
        seen = self._capture(executor, monkeypatch)

        assert executor._exec_move_to_plane_pose(self._plane_job())
        assert seen['straight'] is False
