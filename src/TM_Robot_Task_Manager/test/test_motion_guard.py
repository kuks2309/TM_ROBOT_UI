import pytest

from tm_task_manager.safety import motion_guard as mg
from tm_task_manager.safety.boundary_monitor import (
    STATE_IDLE, STATE_STOPPED, STATE_WATCHING, BoundaryJudge, BoundaryMonitor)
from tm_task_manager.services.motion_gateway import MotionGateway

PILLAR = {'name': 'pillar', 'min': [-300, -300, 0], 'max': [300, 300, 600]}
CELL = {'name': 'cell', 'min': [-900, -900, -200], 'max': [900, 900, 1300]}

HOME_POSE = [800.0, 0.0, 800.0, 0.0, 0.0, 0.0]


def area(**overrides):
    base = {
        'enabled': True,
        'margin_mm': 20.0,
        'allowed_boxes': [],
        'keep_out_boxes': [PILLAR],
        'keep_out_auto_stop': True,
        'tool': {'enabled': True, 'radius_mm': 45.0, 'length_mm': None},
    }
    base.update(overrides)
    return base


def guard(**overrides):
    logs = []
    g = mg.MotionGuard(area(**overrides), log_callback=logs.append)
    g.logs = logs
    return g


class TestRotation:
    def test_회전이_없으면_오프셋이_그대로_더해진다(self):
        target = mg.tool_offset_to_base([100, 200, 300, 0, 0, 0], 10, 20, 30)
        assert target == pytest.approx([110, 220, 330])

    def test_z축_90도면_x_오프셋이_y_로_간다(self):
        target = mg.tool_offset_to_base([0, 0, 0, 0, 0, 90], 100, 0, 0)
        assert target == pytest.approx([0, 100, 0], abs=1e-9)

    def test_y축_90도면_x_오프셋이_아래로_간다(self):
        target = mg.tool_offset_to_base([0, 0, 0, 0, 90, 0], 100, 0, 0)
        assert target == pytest.approx([0, 0, -100], abs=1e-9)


class TestGuardDisabled:
    def test_비활성이면_ptp_도_통과한다(self):
        g = guard(enabled=False)
        d = g.check(mg.MOTION_PTP_TCP, tcp_pose=HOME_POSE, target_mm=[0, 0, 100])
        assert d.allowed is True
        assert d.checked is False

    def test_비활성_통과도_기록에_남는다(self):
        g = guard(enabled=False)
        g.check(mg.MOTION_LINE, tcp_pose=HOME_POSE, target_mm=[0, 0, 100])
        assert len(g.records()) == 1


class TestGuardLine:
    def test_안전한_직선은_통과하고_검사됨으로_남는다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE, tcp_pose=HOME_POSE, target_mm=[800, 0, 1000])
        assert d.allowed is True
        assert d.checked is True

    def test_금지구역을_지나는_직선은_거부한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE, tcp_pose=[-800, 0, 300, 0, 0, 0], target_mm=[800, 0, 300])
        assert d.allowed is False
        assert 'pillar' in d.reason

    def test_현재_위치를_모르면_거부한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE, tcp_pose=None, target_mm=[800, 0, 1000])
        assert d.allowed is False
        assert '현재 로봇 위치를 알 수 없습니다' in d.reason

    def test_목표가_없으면_거부한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE, tcp_pose=HOME_POSE, target_mm=None)
        assert d.allowed is False

    def test_허용구역을_벗어나는_직선은_거부한다(self):
        g = guard(allowed_boxes=[CELL], keep_out_boxes=[])
        d = g.check(mg.MOTION_LINE, tcp_pose=HOME_POSE, target_mm=[1200, 0, 800])
        assert d.allowed is False
        assert '허용 구역' in d.reason


class TestGuardRelative:
    def test_상대_이동을_절대_목표로_바꿔_검사한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE_RELATIVE, tcp_pose=[800, 0, 300, 0, 0, 0],
                    offset_mm=[-1600, 0, 0])
        assert d.allowed is False
        assert d.target_mm == pytest.approx([-800, 0, 300])

    def test_안전한_상대_이동은_통과한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE_RELATIVE, tcp_pose=HOME_POSE, offset_mm=[0, 0, 100])
        assert d.allowed is True
        assert d.checked is True

    def test_오프셋이_없으면_거부한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE_RELATIVE, tcp_pose=HOME_POSE, offset_mm=None)
        assert d.allowed is False


class TestGuardPtp:
    def test_ptp_tcp_는_구역_활성_시_거부한다(self):
        g = guard()
        d = g.check(mg.MOTION_PTP_TCP, tcp_pose=HOME_POSE, target_mm=[800, 0, 1000])
        assert d.allowed is False
        assert '직선(Line) 이동을 쓰십시오' in d.reason

    def test_ptp_joint_도_거부한다(self):
        g = guard()
        d = g.check(mg.MOTION_PTP_JOINT, tcp_pose=HOME_POSE)
        assert d.allowed is False

    def test_거부는_로그로_알린다(self):
        g = guard()
        g.check(mg.MOTION_PTP_TCP, tcp_pose=HOME_POSE, target_mm=[800, 0, 1000])
        assert any('거부' in line for line in g.logs)


class TestGuardVisionJob:
    def test_비전_잡은_통과시킨다(self):
        g = guard()
        d = g.check(mg.MOTION_VISION_JOB, tcp_pose=HOME_POSE, label='TM_IMG_Send')
        assert d.allowed is True

    def test_비전_잡은_미검사로_기록한다(self):
        g = guard()
        g.check(mg.MOTION_VISION_JOB, tcp_pose=HOME_POSE, label='TM_IMG_Send')
        unchecked = g.unchecked_records()
        assert len(unchecked) == 1
        assert unchecked[0].label == 'TM_IMG_Send'
        assert '좌표를 알 수 없습니다' in unchecked[0].note

    def test_미검사_통과는_로그로_알린다(self):
        g = guard()
        g.check(mg.MOTION_VISION_JOB, tcp_pose=HOME_POSE, label='TM_IMG_Send')
        assert any('미검사' in line for line in g.logs)

    def test_검사된_이동은_미검사_목록에_없다(self):
        g = guard()
        g.check(mg.MOTION_LINE, tcp_pose=HOME_POSE, target_mm=[800, 0, 1000])
        assert g.unchecked_records() == []


class TestGuardEscape:
    def test_시작점이_위반이면_목표점만_보고_탈출을_허용한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE, tcp_pose=[0, 0, 100, 0, 0, 0], target_mm=[800, 0, 800])
        assert d.allowed is True
        assert '갇히지 않도록' in d.note

    def test_탈출이라도_목표가_더러우면_거부한다(self):
        g = guard()
        d = g.check(mg.MOTION_LINE, tcp_pose=[0, 0, 100, 0, 0, 0], target_mm=[100, 100, 200])
        assert d.allowed is False


class TestGuardUnknownKind:
    def test_모르는_종류는_거부한다(self):
        g = guard()
        d = g.check('teleport', tcp_pose=HOME_POSE, target_mm=[0, 0, 0])
        assert d.allowed is False
        assert '해석할 수 없는' in d.reason


class TestBoundaryJudge:
    def test_첫_표본은_점으로_본다(self):
        j = BoundaryJudge(area())
        assert j.update([800, 0, 800]) is None
        assert j.update([0, 0, 100]) is not None

    def test_표본_사이를_선분으로_이어_관통을_잡는다(self):
        j = BoundaryJudge(area())
        assert j.update([-800, 0, 300]) is None
        reason = j.update([800, 0, 300])
        assert reason is not None
        assert 'pillar' in reason

    def test_비활성이면_침범을_보고하지_않는다(self):
        j = BoundaryJudge(area(enabled=False))
        j.update([-800, 0, 300])
        assert j.update([0, 0, 100]) is None

    def test_reset_하면_직전_표본을_잊는다(self):
        j = BoundaryJudge(area())
        j.update([-800, 0, 300])
        j.reset()
        assert j.previous is None
        assert j.update([800, 0, 300]) is None


class FakeRobot:

    def __init__(self, samples):
        self._samples = list(samples)
        self.stop_calls = 0

    def sample(self):
        if not self._samples:
            return None
        return self._samples.pop(0)

    def stop(self):
        self.stop_calls += 1
        return True, '정지 완료'


def wait_until(predicate, timeout=2.0):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class TestBoundaryMonitor:
    def test_침범하면_정지를_한_번_부른다(self):
        robot = FakeRobot([[800, 0, 800], [-800, 0, 300], [800, 0, 300]])
        m = BoundaryMonitor(area(), robot.sample, robot.stop, poll_sec=0.01)
        m.start()
        assert wait_until(lambda: m.state == STATE_STOPPED)
        m.stop()
        assert robot.stop_calls == 1
        assert '자동 정지' in m.message

    def test_안전하면_정지하지_않는다(self):
        robot = FakeRobot([[800, 0, 800], [800, 0, 900], [800, 0, 1000]])
        m = BoundaryMonitor(area(), robot.sample, robot.stop, poll_sec=0.01)
        m.start()
        assert wait_until(lambda: robot.sample() is None)
        m.stop()
        assert robot.stop_calls == 0
        assert m.state == STATE_IDLE

    def test_구역이_꺼져_있으면_감시를_시작하지_않는다(self):
        robot = FakeRobot([[0, 0, 100]])
        m = BoundaryMonitor(area(enabled=False), robot.sample, robot.stop, poll_sec=0.01)
        assert m.start() is False
        assert m.state == STATE_IDLE

    def test_침범_콜백을_부른다(self):
        seen = []
        robot = FakeRobot([[0, 0, 100]])
        m = BoundaryMonitor(area(), robot.sample, robot.stop, poll_sec=0.01,
                            on_violation=seen.append)
        m.start()
        assert wait_until(lambda: bool(seen))
        m.stop()
        assert '자동 정지' in seen[0]

    def test_정지_명령_실패도_기록한다(self):
        def failing_stop():
            return False, '서비스 없음'

        robot = FakeRobot([[0, 0, 100]])
        m = BoundaryMonitor(area(), robot.sample, failing_stop, poll_sec=0.01)
        m.start()
        assert wait_until(lambda: '실패' in m.message)
        m.stop()

    def test_reset_하면_다시_감시할_수_있다(self):
        robot = FakeRobot([[0, 0, 100]])
        m = BoundaryMonitor(area(), robot.sample, robot.stop, poll_sec=0.01)
        m.start()
        assert wait_until(lambda: m.state == STATE_STOPPED)
        m.stop()
        m.reset()
        assert m.state == STATE_IDLE


class RecordingSender:
    def __init__(self, result=(True, '이동 완료')):
        self.calls = 0
        self._result = result

    def __call__(self):
        self.calls += 1
        return self._result


class TestMotionGateway:
    def test_거부되면_전송하지_않는다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: [-800, 0, 300, 0, 0, 0])
        sender = RecordingSender()
        ok, reason = gw.send_line(sender, target_mm=[800, 0, 300])
        assert ok is False
        assert sender.calls == 0
        assert 'pillar' in reason

    def test_통과하면_전송한다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE)
        sender = RecordingSender()
        ok, message = gw.send_line(sender, target_mm=[800, 0, 1000])
        assert ok is True
        assert sender.calls == 1
        assert message == '이동 완료'

    def test_ptp_는_전송되지_않는다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE)
        sender = RecordingSender()
        ok, _ = gw.send_ptp_tcp(sender, target_mm=[800, 0, 1000])
        assert ok is False
        assert sender.calls == 0

    def test_비전_잡은_전송되고_미검사로_남는다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE)
        sender = RecordingSender()
        ok, _ = gw.send_vision_job(sender, label='TM_IMG_Send')
        assert ok is True
        assert sender.calls == 1
        assert len(g.unchecked_records()) == 1

    def test_전송_중_감시가_돌고_끝나면_멈춘다(self):
        g = guard()
        robot = FakeRobot([HOME_POSE, [800, 0, 900]])
        monitor = BoundaryMonitor(g.area, robot.sample, robot.stop, poll_sec=0.01)
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE, monitor=monitor)

        states = []

        def sender():
            states.append(monitor.state)
            return True, '이동 완료'

        ok, _ = gw.send_line(sender, target_mm=[800, 0, 1000])
        assert ok is True
        assert states == [STATE_WATCHING]
        assert monitor.state == STATE_IDLE

    def test_감시가_정지시키면_실패로_보고한다(self):
        g = guard()
        robot = FakeRobot([[0, 0, 100]])
        monitor = BoundaryMonitor(g.area, robot.sample, robot.stop, poll_sec=0.01)
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE, monitor=monitor)

        def sender():
            wait_until(lambda: monitor.state == STATE_STOPPED)
            return True, '이동 완료'

        ok, message = gw.send_line(sender, target_mm=[800, 0, 1000])
        assert ok is False
        assert '자동 정지' in message

    def test_정지_상태에서_다음_이동은_탈출로_허용된다(self):
        g = guard()
        robot = FakeRobot([[0, 0, 100]])
        monitor = BoundaryMonitor(g.area, robot.sample, robot.stop, poll_sec=0.01)
        monitor.start()
        assert wait_until(lambda: monitor.state == STATE_STOPPED)
        monitor.stop()

        gw = MotionGateway(g, tcp_pose_fn=lambda: [0, 0, 100, 0, 0, 0], monitor=monitor)
        sender = RecordingSender()
        ok, _ = gw.send_line(sender, target_mm=[800, 0, 800], watch=False)
        assert ok is True
        assert sender.calls == 1

    def test_watch_가_꺼지면_감시를_걸지_않는다(self):
        g = guard()
        robot = FakeRobot([HOME_POSE])
        monitor = BoundaryMonitor(g.area, robot.sample, robot.stop, poll_sec=0.01)
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE, monitor=monitor)

        states = []
        ok, _ = gw.send_line(lambda: (states.append(monitor.state), (True, 'ok'))[1],
                             target_mm=[800, 0, 1000], watch=False)
        assert ok is True
        assert states == [STATE_IDLE]

    def test_검사만_하고_전송하지_않을_수_있다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: [-800, 0, 300, 0, 0, 0])
        decision = gw.check(mg.MOTION_LINE, target_mm=[800, 0, 300])
        assert decision.allowed is False


class TestScriptMotionGuard:
    def _script_motion(self, gateway):
        from tm_task_manager.services.tm_robot_script_motion import TmRobotScriptMotion

        class FakeGv:
            def __init__(self):
                self.scripts = []

            def send_script(self, script):
                self.scripts.append(script)
                return True, 'OK'

        gv = FakeGv()
        return TmRobotScriptMotion(gv, gateway=gateway), gv

    def test_금지구역을_지나는_line_은_스크립트를_보내지_않는다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: [-800, 0, 300, 0, 0, 0])
        motion, gv = self._script_motion(gw)
        ok, _ = motion.line_cpp(800, 0, 300, 0, 0, 0)
        assert ok is False
        assert gv.scripts == []

    def test_안전한_line_은_스크립트를_보낸다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE)
        motion, gv = self._script_motion(gw)
        ok, _ = motion.line_cpp(800, 0, 1000, 0, 0, 0)
        assert ok is True
        assert len(gv.scripts) == 1

    def test_ptp_는_구역_활성_시_보내지_않는다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE)
        motion, gv = self._script_motion(gw)
        ok, _ = motion.ptp_cpp(800, 0, 1000, 0, 0, 0)
        assert ok is False
        assert gv.scripts == []

    def test_raw_스크립트의_모션_명령을_막는다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE)
        motion, gv = self._script_motion(gw)
        ok, reason = motion.send_raw_script('Line("CPP", 0, 0, 100, 0, 0, 0, 50, 200, 0, true)')
        assert ok is False
        assert gv.scripts == []
        assert '모션 명령' in reason

    def test_모션이_아닌_raw_스크립트는_통과시킨다(self):
        g = guard()
        gw = MotionGateway(g, tcp_pose_fn=lambda: HOME_POSE)
        motion, gv = self._script_motion(gw)
        ok, _ = motion.send_raw_script('ChangeBase("RobotBase")')
        assert ok is True
        assert len(gv.scripts) == 1

    def test_관문이_없으면_그대로_보낸다(self):
        motion, gv = self._script_motion(None)
        ok, _ = motion.line_cpp(0, 0, 100, 0, 0, 0)
        assert ok is True
        assert len(gv.scripts) == 1
