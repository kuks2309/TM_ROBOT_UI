"""로봇 정지 — tm_msgs/SetEvent 의 STOP·PAUSE·RESUME 배선.

이 워크스페이스는 SetEvent 를 import 만 해 두고 실제로 부른 적이 없었다. 안전 구역
감시가 침범을 찾아도 멈출 수단이 없으면 의미가 없으므로 여기서 배선한다.

## 왜 응답을 기다리지 않는가

이 앱의 ROS 스핀은 GUI 스레드의 QTimer 가 `rclpy.spin_once` 로 돌린다
(main_window `_spin_ros`). 감시 스레드에서 `spin_until_future_complete` 를 부르면
같은 노드를 두 스레드가 동시에 스핀해 경합이 난다. `call_async` 는 요청 전송까지는
스핀 없이 끝나므로, 정지 요청은 즉시 나가고 응답은 GUI 스핀이 받는다.

응답을 봐야 하는 GUI 경로에서는 `stop_sync()` 를 쓴다.
"""
from typing import Callable, Optional, Tuple

SERVICE_NAME = 'set_event'


class RobotStopService:
    """SetEvent 로 로봇을 정지·일시정지·재개시킨다."""

    def __init__(self, node, log_callback: Optional[Callable[[str], None]] = None):
        self._node = node
        self._log_callback = log_callback
        self._client = None

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _get_client(self):
        if self._client is None:
            if self._node is None:
                return None
            from tm_msgs.srv import SetEvent
            self._client = self._node.create_client(SetEvent, SERVICE_NAME)
        return self._client

    def _request(self, func_value: int) -> 'object':
        from tm_msgs.srv import SetEvent
        request = SetEvent.Request()
        request.func = func_value
        request.arg0 = 0
        request.arg1 = 0
        return request

    def _send(self, func_value: int, what: str, timeout_sec: float = 0.5) -> Tuple[bool, str]:
        client = self._get_client()
        if client is None:
            return False, 'ROS2 노드가 없습니다'
        if not client.wait_for_service(timeout_sec=timeout_sec):
            return False, f'{SERVICE_NAME} 서비스를 찾을 수 없습니다 (TM Driver 확인)'
        try:
            client.call_async(self._request(func_value))
        except Exception as exc:
            return False, f'{what} 요청 실패: {exc}'
        self._log(f'[로봇] {what} 요청 전송')
        return True, f'{what} 요청 전송'

    def stop(self) -> Tuple[bool, str]:
        """즉시 정지. 감시 스레드에서 부르므로 응답을 기다리지 않는다."""
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.STOP, '정지(STOP)')

    def pause(self) -> Tuple[bool, str]:
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.PAUSE, '일시정지(PAUSE)')

    def resume(self) -> Tuple[bool, str]:
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.RESUME, '재개(RESUME)')

    def stop_sync(self, timeout_sec: float = 3.0) -> Tuple[bool, str]:
        """응답까지 확인하는 정지. **GUI 스레드에서만** 부른다 (노드를 스핀한다)."""
        import rclpy
        from tm_msgs.srv import SetEvent

        client = self._get_client()
        if client is None:
            return False, 'ROS2 노드가 없습니다'
        if not client.wait_for_service(timeout_sec=1.0):
            return False, f'{SERVICE_NAME} 서비스를 찾을 수 없습니다 (TM Driver 확인)'

        future = client.call_async(self._request(SetEvent.Request.STOP))
        rclpy.spin_until_future_complete(self._node, future, timeout_sec=timeout_sec)

        result = future.result()
        if result is None:
            return False, '정지 요청 타임아웃'
        if not result.ok:
            return False, '정지 요청이 거부되었습니다'
        return True, '정지 완료'
