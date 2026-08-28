"""tm_driver 의 connect_tmsvr 서비스로 로봇 이더넷(TMSVR) 연결을 요청하고 상태를 관리하는 모듈."""
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
from tm_msgs.srv import ConnectTM, SetEvent
from tm_msgs.msg import FeedbackState
from enum import Enum
from typing import Optional, Callable


class ConnectionState(Enum):
    """로봇 연결 상태."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class RobotConnectionManager:
    """TMSVR 연결 요청과 로봇 준비 상태(FeedbackState error_code 기반) 추적을 담당한다."""

    def __init__(self, node: Node):
        self.node = node
        self.state = ConnectionState.DISCONNECTED
        self.robot_ip = ""
        self.is_robot_ready = False
        self.error_message = ""

        self.on_state_changed: Optional[Callable[[ConnectionState], None]] = None
        self.on_robot_status_changed: Optional[Callable[[bool], None]] = None

        self.connect_client = self.node.create_client(
            ConnectTM,
            'connect_tmsvr'
        )

        self.feedback_sub = self.node.create_subscription(
            FeedbackState,
            'tm_driver/feedback_states',
            self._on_feedback_state,
            10
        )

        self.node.get_logger().info('Robot Connection Manager initialized')

    def _set_state(self, state: ConnectionState):
        if self.state != state:
            self.state = state
            if self.on_state_changed:
                self.on_state_changed(state)

    def _on_feedback_state(self, msg: FeedbackState):
        """error_code==0 을 로봇 정상(ready)으로 판정하고, 변화가 있을 때만 콜백을 부른다."""
        was_ready = self.is_robot_ready

        try:
            error_code = getattr(msg, 'error_code', 0)
            self.is_robot_ready = (error_code == 0)

            if was_ready != self.is_robot_ready and self.on_robot_status_changed:
                self.on_robot_status_changed(self.is_robot_ready)

        except AttributeError as e:
            self.node.get_logger().debug(f'FeedbackState parsing: {e}')

    def connect(self, robot_ip: str, timeout_sec: float = 5.0) -> tuple[bool, str]:
        """connect_tmsvr 서비스로 로봇 이더넷 연결을 요청한다.

        Args:
            robot_ip: 로봇 IP 주소.
            timeout_sec: 서비스 대기·응답 타임아웃 (s).

        Returns:
            (성공 여부, 사용자 표시용 메시지).
        """
        if self.state == ConnectionState.CONNECTED:
            return True, "이미 연결되어 있습니다"

        self.robot_ip = robot_ip
        self._set_state(ConnectionState.CONNECTING)

        if not self.connect_client.wait_for_service(timeout_sec=timeout_sec):
            self._set_state(ConnectionState.ERROR)
            self.error_message = "TM Driver 서비스를 찾을 수 없습니다"
            return False, self.error_message

        request = ConnectTM.Request()
        request.server = 0
        request.reconnect = True
        request.timeout = 0.0
        request.timeval = 0.0

        try:
            future = self.connect_client.call_async(request)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout_sec)

            if future.result() is not None:
                response = future.result()
                if response.ok:
                    self._set_state(ConnectionState.CONNECTED)
                    self.node.get_logger().info(f'로봇 연결 성공: {robot_ip}')
                    return True, f"로봇 연결 성공: {robot_ip}"
                else:
                    self._set_state(ConnectionState.ERROR)
                    self.error_message = f"연결 실패: {response.msg}"
                    return False, self.error_message
            else:
                self._set_state(ConnectionState.ERROR)
                self.error_message = "서비스 호출 타임아웃"
                return False, self.error_message

        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            self.error_message = f"연결 오류: {str(e)}"
            self.node.get_logger().error(self.error_message)
            return False, self.error_message

    def disconnect(self) -> tuple[bool, str]:
        """로컬 연결 상태만 해제한다 — 드라이버에 실제 해제 명령은 보내지 않는다(soft disconnect).

        Returns:
            (True, 메시지).
        """
        if self.state == ConnectionState.DISCONNECTED:
            return True, "이미 연결 해제되어 있습니다"

        self._set_state(ConnectionState.DISCONNECTED)
        self.is_robot_ready = False
        self.node.get_logger().info('로봇 연결 해제')

        if self.on_robot_status_changed:
            self.on_robot_status_changed(False)

        return True, "연결 해제됨"

    def get_connection_info(self) -> dict:
        """현재 상태·IP·ready·오류 메시지를 요약한 dict 를 반환한다."""
        return {
            'state': self.state.value,
            'robot_ip': self.robot_ip,
            'is_ready': self.is_robot_ready,
            'error': self.error_message
        }

    def is_connected(self) -> bool:
        """연결 상태(CONNECTED) 여부."""
        return self.state == ConnectionState.CONNECTED

    def is_ready(self) -> bool:
        """연결되어 있고 로봇에 오류가 없는(error_code==0) 상태 여부."""
        return self.is_connected() and self.is_robot_ready
