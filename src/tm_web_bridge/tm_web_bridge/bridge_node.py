import re
import threading
import time

from rclpy.node import Node

from sensor_msgs.msg import JointState, CompressedImage
from geometry_msgs.msg import PoseStamped
from tm_msgs.msg import FeedbackState
from tm_msgs.srv import SetPositions, SendScript, SetIO

from tm_task_manager.services.robot_motion_service import RobotMotionService, is_tm_joint_state
from tm_task_manager.services.teaching_service import TeachingService
from tm_task_manager.services.coordinate_transformer import CoordinateTransformer
from tm_task_manager.services.vision_manager import VisionManager
from tm_task_manager.services.image_capture_service import (
    VISION_CAPTURE_COMMAND,
    VISION_CAPTURE_COMMAND_VAR,
)
from tm_task_manager.global_variable_script import GlobalVariableScript
from tm_task_manager.recipe_manager import Recipe
from tm_task_manager.job_executor import ExecutionState
from .bridge_executor import BridgeJobExecutor

SEQUENCE_WHITELIST = {
    "go_home",
    "move_to_point",
    "move_linear",
    "line_move_to_point",
    "pose_keep_move_to_point",
    "wait",
    "scan_tm_landmark_jig",
    "calculate_plate_pose",
    "align_to_plane_normal",
    "measure_plane_distance",
}
MAX_SEQ_VELOCITY = 30.0

LIVE_VIEWER_TTL = 5.0
LIVE_FRAME_TIMEOUT = 3.0
LIVE_JOG_YIELD = 0.35


class BridgeNode(Node):
    def __init__(self):
        super().__init__('tm_web_bridge')

        self.motion_service = RobotMotionService()
        self.teaching_service = TeachingService(ros_node=self)

        self._sct_connected = False
        self._svr_connected = False

        self.create_subscription(JointState, 'joint_states', self._on_joint_state, 10)
        self.create_subscription(PoseStamped, 'tool_pose', self._on_tool_pose, 10)
        self.create_subscription(FeedbackState, '/feedback_states', self._on_feedback_state, 10)

        self.set_positions_client = self.create_client(SetPositions, 'set_positions')
        self.send_script_client = self.create_client(SendScript, 'send_script')
        self.set_io_client = self.create_client(SetIO, 'set_io')

        self._jog_lock = threading.Lock()

        self.motion_enabled = False

        self.gv_manager = GlobalVariableScript(self)
        self.vision_manager = VisionManager(gv_manager=self.gv_manager, ros_node=self)

        self.job_executor = BridgeJobExecutor(
            ros_node=self, vision_manager=self.vision_manager
        )
        self.job_executor.on_log = self._on_seq_log
        self._seq_logs = []
        self._seq_total = 0
        self._seq_lock = threading.Lock()
        self._seq_thread = None
        self._seq_stop_flag = False

        self._live_viewers = {}
        self._live_lock = threading.Lock()
        self._live_thread = None
        self._live_running = False

        self._frame_evt = threading.Event()
        self.create_subscription(
            CompressedImage, '/techman_image/compressed', self._on_frame, 1)

        self.get_logger().info('tm_web_bridge 노드 시작 (joint_states/tool_pose/feedback 구독, set_positions 클라이언트)')


    def _on_joint_state(self, msg):
        if is_tm_joint_state(msg.name, msg.position):
            self.motion_service.update_joint_state(list(msg.position[:6]))

    def _on_tool_pose(self, msg):
        p = msg.pose
        self.motion_service.update_tcp_pose(
            p.position.x, p.position.y, p.position.z,
            p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w,
        )

    def _on_feedback_state(self, msg):
        tcp_speed = list(msg.tcp_speed) if msg.tcp_speed else []
        joint_vel = list(msg.joint_vel) if msg.joint_vel else []
        self.motion_service.update_feedback_state(tcp_speed, joint_vel)
        self._sct_connected = bool(msg.is_sct_connected)
        self._svr_connected = bool(msg.is_svr_connected)


    def _call_set_positions(self, motion_type, positions, velocity, acc_time,
                            blend_percentage=0, fine_goal=False):
        if not self.set_positions_client.wait_for_service(timeout_sec=1.0):
            return False, "set_positions 서비스를 사용할 수 없습니다 (tm_driver 미기동?)"

        request = SetPositions.Request()
        request.motion_type = motion_type
        request.positions = positions
        request.velocity = CoordinateTransformer.velocity_percent_to_service(motion_type, velocity)
        request.acc_time = acc_time
        request.blend_percentage = blend_percentage
        request.fine_goal = fine_goal

        future = self.set_positions_client.call_async(request)

        done = threading.Event()
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(timeout=10.0):
            return False, "set_positions 서비스 타임아웃"

        result = future.result()
        if result is None or not result.ok:
            return False, "set_positions 실패"

        self.motion_service.target_position = list(positions)
        start_time = time.time()
        stable_count = 0
        stable_threshold = 3
        while time.time() - start_time < 30.0:
            if self.motion_service.check_motion_complete():
                stable_count += 1
                if stable_count >= stable_threshold:
                    msg = self.motion_service.get_motion_complete_message()
                    self.motion_service.clear_motion_state()
                    return True, msg
            else:
                stable_count = 0
            time.sleep(0.1)

        self.motion_service.clear_motion_state()
        return True, "이동 명령 전송됨 (완료 확인 타임아웃)"


    def set_motion_enabled(self, enabled: bool) -> bool:
        self.motion_enabled = bool(enabled)
        self.get_logger().warning(f'motion_enabled = {self.motion_enabled}')
        return self.motion_enabled

    def jog(self, axis, direction, step_mm, velocity_percent):
        if not self.motion_enabled:
            return False, "모션이 비활성 상태입니다. /motion/enable 로 활성화 후 시도하세요."
        if not self._jog_lock.acquire(blocking=False):
            return False, "이전 조그 명령이 진행 중입니다"
        try:
            tcp = self.motion_service.current_tcp_pose
            if not tcp or len(tcp) < 6:
                return False, "현재 로봇 위치를 알 수 없습니다 (tool_pose 없음 · tm_driver 미기동?)"
            orientation = [tcp[3], tcp[4], tcp[5]]
            return self.teaching_service.jog_tcp(
                axis, direction, step_mm, velocity_percent,
                list(tcp), orientation, self._call_set_positions,
            )
        finally:
            self._jog_lock.release()


    @property
    def current_tcp_pose(self):
        return self.motion_service.current_tcp_pose


    def _on_seq_log(self, message):
        self._seq_logs.append(str(message))
        if len(self._seq_logs) > 200:
            self._seq_logs = self._seq_logs[-200:]

    def run_sequence(self, jobs):
        if not self.motion_enabled:
            return False, "모션이 비활성 상태입니다. /motion/enable 로 활성화 후 시도하세요."

        if not self._sct_connected:
            return False, (
                "로봇 명령 채널(Listen 노드, TCP 5890)이 연결되지 않았습니다. "
                "로봇 펜던트에서 Listen 노드가 포함된 프로젝트를 실행(Play)하세요. "
                f"(상태 채널: {'정상' if self._svr_connected else '끊김'})"
            )

        with self._seq_lock:
            if self.job_executor.state == ExecutionState.RUNNING:
                return False, "이미 시퀀스가 실행 중입니다."
            if not jobs:
                return False, "실행할 시퀀스가 비어 있습니다."

            bad = sorted(
                {j.get("type") for j in jobs if j.get("type") not in SEQUENCE_WHITELIST}
            )
            if bad:
                return False, (
                    f"v1 미지원 잡: {', '.join(bad)} "
                    f"(지원: {', '.join(sorted(SEQUENCE_WHITELIST))})"
                )

            jobs_data = []
            for i, j in enumerate(jobs):
                params = dict(j.get("params", {}) or {})
                if "velocity" in params:
                    try:
                        params["velocity"] = min(float(params["velocity"]), MAX_SEQ_VELOCITY)
                    except (TypeError, ValueError):
                        params["velocity"] = MAX_SEQ_VELOCITY
                jobs_data.append({"id": i + 1, "type": j.get("type"), "params": params})

            recipe = Recipe.from_dict({"name": "web_sequence", "jobs": jobs_data})
            self.job_executor.load_recipe(recipe)
            self._seq_logs = []
            self._seq_total = len(jobs_data)
            self._seq_stop_flag = False

            self._seq_thread = threading.Thread(
                target=self.job_executor.run, daemon=True
            )
            self._seq_thread.start()
            return True, (
                f"시퀀스 실행 시작 ({self._seq_total}개 잡, 속도 상한 {MAX_SEQ_VELOCITY}%)"
            )

    def stop_sequence(self):
        self._seq_stop_flag = True
        self.job_executor.stop()
        return True, "시퀀스 정지 요청됨"

    def sequence_status(self):
        state = self.job_executor.state.value
        if self._seq_stop_flag and state in ("error", "stopped"):
            state = "stopped"
        return {
            "state": state,
            "current_index": self.job_executor.current_job_index,
            "total": self._seq_total,
            "logs": self._seq_logs[-40:],
        }


    def set_digital_output(self, module, pin, state):
        if not self.motion_enabled:
            return False, "모션이 비활성 상태입니다. 상단 '모션 활성' 스위치를 켜세요."
        if module not in (0, 1):
            return False, "module 은 0(ControlBox) 또는 1(EndEffector) 여야 합니다"
        max_pin = 16 if module == 0 else 4
        if not isinstance(pin, int) or pin < 0 or pin >= max_pin:
            return False, f"pin 범위 오류 (module {module}: 0~{max_pin - 1})"
        if not self.set_io_client.wait_for_service(timeout_sec=1.0):
            return False, "set_io 서비스를 사용할 수 없습니다 (tm_driver 미기동?)"

        request = SetIO.Request()
        request.module = module
        request.type = SetIO.Request.TYPE_DIGITAL_OUT
        request.pin = pin
        request.state = 1.0 if state else 0.0

        future = self.set_io_client.call_async(request)
        done = threading.Event()
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(timeout=5.0):
            return False, "set_io 서비스 타임아웃"
        result = future.result()
        if result is None or not result.ok:
            return False, "set_io 실패"

        label = "CB" if module == 0 else "EE"
        return True, f"DO {label}{pin} = {'ON' if state else 'OFF'}"


    def _trigger_capture_command(self):
        """이미지 캡처 트리거 — 전역변수 명령 방식.

        PyQt 쪽 image_capture_service.py 및 job_executor.py 의 AI 캡처 경로와
        동일한 규약(`g_robot_command=3` + `ScriptExit()`)을 쓴다.
        """
        if not self.send_script_client.wait_for_service(timeout_sec=1.0):
            return False, "send_script 서비스를 사용할 수 없습니다 (tm_driver 미기동?)"

        ok, msg = self.gv_manager.write_variable(
            VISION_CAPTURE_COMMAND_VAR, VISION_CAPTURE_COMMAND)
        if not ok:
            return False, msg
        if not self.gv_manager.send_script_exit():
            return False, "ScriptExit() 발행 실패"
        return True, f"캡처 명령 전송됨 ({VISION_CAPTURE_COMMAND_VAR}={VISION_CAPTURE_COMMAND})"

    def capture_vision(self, job_name=None):
        if not self.motion_enabled:
            return False, "모션이 비활성 상태입니다. 상단 '모션 활성' 스위치를 켜세요."
        return self._trigger_capture_command()

    def capture_still(self, job_name=None):
        return self._trigger_capture_command()


    def _on_frame(self, _msg):
        self._frame_evt.set()

    def _prune_live_viewers(self):
        now = time.monotonic()
        for vid in [v for v, t in self._live_viewers.items()
                    if now - t > LIVE_VIEWER_TTL]:
            self._live_viewers.pop(vid, None)

    def live_join(self, viewer_id):
        if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", str(viewer_id)):
            return 0, False
        with self._live_lock:
            self._live_viewers[str(viewer_id)] = time.monotonic()
            self._prune_live_viewers()
            n = len(self._live_viewers)
            if not self._live_running:
                self._live_running = True
                self._live_thread = threading.Thread(
                    target=self._live_loop, daemon=True)
                self._live_thread.start()
                self.get_logger().info(f'라이브 촬영 루프 시작 (시청자 {n}명)')
        return n, True

    def live_leave(self, viewer_id):
        with self._live_lock:
            self._live_viewers.pop(str(viewer_id), None)
            self._prune_live_viewers()
            n = len(self._live_viewers)
        return n, n > 0

    def live_status(self):
        with self._live_lock:
            self._prune_live_viewers()
            n = len(self._live_viewers)
            running = self._live_running
        return {"live": bool(n) and running, "viewers": n}

    def _live_loop(self):
        try:
            while True:
                with self._live_lock:
                    self._prune_live_viewers()
                    if not self._live_viewers:
                        self._live_running = False
                        break

                if self._jog_lock.locked():
                    time.sleep(LIVE_JOG_YIELD)
                    continue

                self._frame_evt.clear()
                ok, msg = self.capture_still()
                if not ok:
                    self.get_logger().warning(f'라이브 촬영 실패: {msg}')
                    time.sleep(1.0)
                    continue

                if not self._frame_evt.wait(timeout=LIVE_FRAME_TIMEOUT):
                    self.get_logger().warning(
                        '라이브: 프레임 미도착 — /techman_image/compressed 발행자 확인 '
                        '(jpeg_republish 노드가 떠 있는가?). 루프가 타임아웃 페이스로 느려진다.')
        finally:
            with self._live_lock:
                self._live_running = False
            self.get_logger().info('라이브 촬영 루프 종료')


    def get_status(self):
        tcp = self.motion_service.current_tcp_pose
        joints = self.motion_service.current_joint_position
        return {
            "connected": tcp is not None,
            "sct_connected": self._sct_connected,
            "svr_connected": self._svr_connected,
            "current_tcp_pose": list(tcp) if tcp else None,
            "current_joint_position": list(joints) if joints else None,
            "moving": bool(self.motion_service.is_moving),
            "motion_enabled": self.motion_enabled,
        }
