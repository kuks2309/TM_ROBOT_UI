"""TM Driver set_event 서비스로 정지/일시정지/재개 명령을 보낸다."""
from typing import Callable, Optional, Tuple

SERVICE_NAME = 'set_event'


class RobotStopService:
    """set_event(SetEvent) 클라이언트 래퍼.

    stop/pause/resume 은 fire-and-forget(call_async 후 결과 미확인) — 반환의
    '요청 전송'은 수락 보증이 아니다. 결과 확인이 필요하면 stop_sync 를 쓰되,
    stop_sync 는 호출 스레드에서 노드를 spin 하므로 루트 executor 가 같은
    노드를 spin 중인 컨텍스트·감시 스레드(BoundaryMonitor stop_fn)에서는
    부르면 안 된다.
    """

    def __init__(self, node, log_callback: Optional[Callable[[str], None]] = None):
        self._node = node
        self._log_callback = log_callback
        self._client = None

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _get_client(self):
        """SetEvent 클라이언트 지연 생성 (노드 없으면 None)."""
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
        """wait_for_service(timeout_sec) 후 call_async 전송 — future 는 버린다."""
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
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.STOP, '정지(STOP)')

    def pause(self) -> Tuple[bool, str]:
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.PAUSE, '일시정지(PAUSE)')

    def resume(self) -> Tuple[bool, str]:
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.RESUME, '재개(RESUME)')

    def stop_sync(self, timeout_sec: float = 3.0) -> Tuple[bool, str]:
        """STOP 을 보내고 응답 ok 까지 확인한다 — 호출 스레드에서 spin (클래스 주석 참조)."""
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
