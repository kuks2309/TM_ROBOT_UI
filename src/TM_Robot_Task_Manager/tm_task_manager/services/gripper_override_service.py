"""그리퍼 강제 열기(인터록 우회) — 수동 탈출 경로. SMC·SCHUNK 양쪽을 지원한다.

왜 필요한가
    SMC 그리퍼(MK4)는 `homing_required_` 가 서 있으면 어떤 명령이든 원점복귀를 먼저 한다.
    원점복귀는 스트로크 끝까지 여는 최대 행정이라 매거진 감지 시 `forbid_any` 로 거부된다
    (DL-GR02, 낙하 방지). 그 결과 **박스를 문 채로는 release 가 시작조차 못 하고,
    박스를 빼려면 열어야 하는 순환**이 생긴다. 이 서비스가 그 순환의 유일한 탈출구다.

    우회는 goal 의 `bypass_interlock` 로 전달되며 **그 명령 한 번에만** 유효하다
    (FSM `bypass_interlock_` 는 per-goal). 레시피 실행 경로는 영향받지 않는다.

왜 백엔드가 둘인가
    강제 열기는 기계를 가리지 않는 «공통 탈출구» 다 — 어느 로봇이든 사람이 박스를 빼야
    하는 순간이 온다. 그래서 SMC(MK4) 를 먼저 시도하고, **그 백엔드가 아예 없는 기계면**
    SCHUNK(MK2) 서비스로 넘어간다. 기계마다 다른 버튼을 두지 않기 위함이다.

    넘어가는 조건은 «없음» 뿐이다. 백엔드가 있는데 명령이 실패한 경우에는 넘어가지
    않는다 — 열기는 물리 동작이라, 실패했다고 다른 그리퍼에 같은 명령을 자동으로
    또 보내면 사람이 예상하지 못한 곳이 움직인다.

없을 때
    지원 백엔드가 하나도 없으면 **아무것도 보내지 않고** 사유만 돌려준다. 조용히
    성공한 척하거나 엉뚱한 곳에 명령을 흘리지 않는다.

안전
    이 경로는 «박스를 문 채 스트로크 끝까지 열 수 있다» 는 뜻이다. 낙하 위험을 사람이
    지는 선택이므로 호출부(UI)가 반드시 확인을 받아야 한다. 이 서비스는 확인을 대행하지 않는다.
"""
import rclpy

GRIPPER_ACTION_TIMEOUT_SEC = 30.0
_SERVER_WAIT_SEC = 3.0
_GOAL_ACCEPT_WAIT_SEC = 5.0

# 백엔드 시도 결과. UNAVAILABLE 만 다음 백엔드로 넘어간다.
_OK, _UNAVAILABLE, _FAILED = 'ok', 'unavailable', 'failed'

SCHUNK_RELEASE_COMMAND = 2      # tc_msgs/srv/GripperCommand: 1=grip, 2=release, 3=home


class GripperOverrideService:
    """인터록을 우회해 그리퍼를 여는 단일 목적 서비스.

    ros_node 에서 두 백엔드를 찾는다.
      - `gripper_action_client` — SMC(MK4), gripper_ros GripperCommand 액션
      - `schunk_gripper_client` — SCHUNK(MK2), tc_msgs GripperCommand 서비스
    둘 다 없으면 비활성으로 동작하고 사유를 돌려준다.
    """

    def __init__(self, ros_node, log_callback=None):
        self._node = ros_node
        self._log = log_callback or (lambda msg: None)

    # --- 가용성 -------------------------------------------------------

    def _smc_client(self):
        return getattr(self._node, 'gripper_action_client', None)

    def _schunk_client(self):
        return getattr(self._node, 'schunk_gripper_client', None)

    def backends(self):
        """이 기계에서 쓸 수 있는 백엔드 이름 목록 (시도 순서대로)."""
        found = []
        if self._smc_client() is not None:
            found.append('SMC')
        if self._schunk_client() is not None:
            found.append('SCHUNK')
        return found

    def available(self) -> bool:
        """강제 열기를 쓸 수 있는지 — 백엔드가 하나라도 있으면 참."""
        return bool(self.backends())

    def unavailable_reason(self) -> str:
        """왜 못 쓰는지 (UI 툴팁용). 쓸 수 있으면 빈 문자열."""
        if self.available():
            return ''
        return ("이 기계에는 강제 열기를 지원하는 그리퍼가 없습니다 "
                "(gripper_ros·tc_msgs 둘 다 미소싱)")

    # --- 실행 ---------------------------------------------------------

    def force_release(self, timeout_sec: float = GRIPPER_ACTION_TIMEOUT_SEC):
        """인터록을 우회해 release(열기)를 1회 전송한다. SMC → SCHUNK 순.

        Returns: (성공 여부, 사람이 읽을 사유)
        """
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
                # 백엔드는 있는데 실패했다 — 다른 그리퍼로 넘기지 않는다.
                self._log(f"[그리퍼 강제 열기] {name} 실패 — {reason}")
                return False, f"{name}: {reason}"
            notes.append(f"{name}: {reason}")

        joined = ' / '.join(notes)
        self._log(f"[그리퍼 강제 열기] 지원 백엔드 없음 — 실행하지 않았습니다 ({joined})")
        return False, f"강제 열기를 지원하는 그리퍼가 없습니다 — 실행하지 않았습니다 ({joined})"

    # --- 백엔드: SMC (MK4) --------------------------------------------

    def _force_release_smc(self, timeout_sec: float):
        client = self._smc_client()
        if client is None:
            return _UNAVAILABLE, "gripper_ros 미소싱"

        try:
            from gripper_ros.action import GripperCommand
        except ImportError:
            return _UNAVAILABLE, "gripper_ros.action.GripperCommand import 실패"

        if not client.wait_for_server(timeout_sec=_SERVER_WAIT_SEC):
            # 노드가 안 떴거나 lifecycle 이 active 가 아니다 — «이 기계에 없는» 것과 구분되지
            # 않으므로 다음 백엔드에 기회를 준다. 둘 다 없으면 어차피 아무것도 안 보낸다.
            return _UNAVAILABLE, "gripper_node 액션 서버 없음 (미기동/미활성)"

        goal = GripperCommand.Goal()
        goal.command = GripperCommand.Goal.COMMAND_PROFILE
        goal.profile = 'release'
        goal.step = 0
        goal.bypass_interlock = True  # ← 이 명령 한 번만 우회

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

        # 액션 계약에 success 필드는 없다 — RESULT_OK(0) 만이 성공이다(GripperCommand.action).
        code = getattr(result, 'result_code', None)
        message = getattr(result, 'message', '') or ''
        if code == 0:
            self._log("[그리퍼 강제 열기] SMC 성공 (result_code=0)")
            return _OK, "열림 (SMC)"
        return _FAILED, f"result_code={code} {message}".strip()

    # --- 백엔드: SCHUNK (MK2) -----------------------------------------

    def _force_release_schunk(self, timeout_sec: float):
        """SCHUNK 서보 그리퍼 — tc_msgs/srv/GripperCommand(/gripper_command) release.

        이쪽에는 인터록 우회 개념이 없다(서비스가 그런 필드를 받지 않는다). 매거진
        인터록은 SMC FSM 안에 있는 것이므로, SCHUNK 에서는 평범한 release 가 곧
        «막히지 않는 열기» 다. 같은 버튼이 두 기계에서 같은 결과를 내는 이유다.
        """
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
        # 서비스는 수신 확인(bool received)만 돌려준다 — 실제 개폐 완료 보증이 아니다.
        if res is not None and getattr(res, 'received', False):
            self._log("[그리퍼 강제 열기] SCHUNK 수신 확인(received=True)")
            return _OK, "열기 명령 수신됨 (SCHUNK — 수신 확인까지만 보증)"
        return _FAILED, "received=False/None"
