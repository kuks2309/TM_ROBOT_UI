import rclpy

GRIPPER_ACTION_TIMEOUT_SEC = 30.0
_SERVER_WAIT_SEC = 3.0
_GOAL_ACCEPT_WAIT_SEC = 5.0

_OK, _UNAVAILABLE, _FAILED = 'ok', 'unavailable', 'failed'

SCHUNK_RELEASE_COMMAND = 2


class GripperOverrideService:

    def __init__(self, ros_node, log_callback=None):
        self._node = ros_node
        self._log = log_callback or (lambda msg: None)


    def _smc_client(self):
        return getattr(self._node, 'gripper_action_client', None)

    def _schunk_client(self):
        return getattr(self._node, 'schunk_gripper_client', None)

    def backends(self):
        found = []
        if self._smc_client() is not None:
            found.append('SMC')
        if self._schunk_client() is not None:
            found.append('SCHUNK')
        return found

    def available(self) -> bool:
        return bool(self.backends())

    def unavailable_reason(self) -> str:
        if self.available():
            return ''
        return ("이 기계에는 강제 열기를 지원하는 그리퍼가 없습니다 "
                "(gripper_ros·tc_msgs 둘 다 미소싱)")


    def force_release(self, timeout_sec: float = GRIPPER_ACTION_TIMEOUT_SEC):
        if self._node is None:
            reason = "ROS2 노드가 없습니다 — 실행하지 않았습니다"
            self._log(f"[그리퍼 강제 열기] {reason}")
            return False, reason

        notes = []
        for name, attempt in (('SMC', self._force_release_smc),
                              ('SCHUNK', self._force_release_schunk)):
            state, reason = attempt(timeout_sec)
            if state == _OK:
                return True, reason
            if state == _FAILED:
                self._log(f"[그리퍼 강제 열기] {name} 실패 — {reason}")
                return False, f"{name}: {reason}"
            notes.append(f"{name}: {reason}")

        joined = ' / '.join(notes)
        self._log(f"[그리퍼 강제 열기] 지원 백엔드 없음 — 실행하지 않았습니다 ({joined})")
        return False, f"강제 열기를 지원하는 그리퍼가 없습니다 — 실행하지 않았습니다 ({joined})"


    def _force_release_smc(self, timeout_sec: float):
        client = self._smc_client()
        if client is None:
            return _UNAVAILABLE, "gripper_ros 미소싱"

        try:
            from gripper_ros.action import GripperCommand
        except ImportError:
            return _UNAVAILABLE, "gripper_ros.action.GripperCommand import 실패"

        if not client.wait_for_server(timeout_sec=_SERVER_WAIT_SEC):
            return _UNAVAILABLE, "gripper_node 액션 서버 없음 (미기동/미활성)"

        goal = GripperCommand.Goal()
        goal.command = GripperCommand.Goal.COMMAND_PROFILE
        goal.profile = 'release'
        goal.step = 0
        goal.bypass_interlock = True

        self._log("[그리퍼 강제 열기] SMC — 인터록 우회 release 전송")
        send_future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self._node, send_future, timeout_sec=_GOAL_ACCEPT_WAIT_SEC)
        if not send_future.done():
            return _FAILED, "goal 전송 응답 없음"

        handle = send_future.result()
        if handle is None or not handle.accepted:
            return _FAILED, "goal 거절됨 (다른 명령 수행 중이거나 상태 불가)"

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self._node, result_future, timeout_sec=timeout_sec)
        if not result_future.done():
            return _FAILED, f"결과 대기 타임아웃 ({timeout_sec:.0f}초)"

        wrapped = result_future.result()
        result = getattr(wrapped, 'result', None)
        if result is None:
            return _FAILED, "결과 없음"

        code = getattr(result, 'result_code', None)
        message = getattr(result, 'message', '') or ''
        if code == 0:
            self._log("[그리퍼 강제 열기] SMC 성공 (result_code=0)")
            return _OK, "열림 (SMC)"
        return _FAILED, f"result_code={code} {message}".strip()


    def _force_release_schunk(self, timeout_sec: float):
        client = self._schunk_client()
        if client is None:
            return _UNAVAILABLE, "tc_msgs 미소싱"

        try:
            from tc_msgs.srv import GripperCommand
        except ImportError:
            return _UNAVAILABLE, "tc_msgs.srv.GripperCommand import 실패"

        if not client.wait_for_service(timeout_sec=_SERVER_WAIT_SEC):
            return _UNAVAILABLE, "/gripper_command 서비스 없음 (tc_end_effector 미기동)"

        req = GripperCommand.Request()
        req.command = SCHUNK_RELEASE_COMMAND

        self._log("[그리퍼 강제 열기] SCHUNK — release(command=2) 전송")
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self._node, future, timeout_sec=timeout_sec)
        if not future.done():
            return _FAILED, f"응답 타임아웃 ({timeout_sec:.0f}초)"

        res = future.result()
        if res is not None and getattr(res, 'received', False):
            self._log("[그리퍼 강제 열기] SCHUNK 수신 확인(received=True)")
            return _OK, "열기 명령 수신됨 (SCHUNK — 수신 확인까지만 보증)"
        return _FAILED, "received=False/None"
