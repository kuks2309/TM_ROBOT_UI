from typing import Callable, Optional, Tuple

SERVICE_NAME = 'set_event'


class RobotStopService:

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
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.STOP, '정지(STOP)')

    def pause(self) -> Tuple[bool, str]:
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.PAUSE, '일시정지(PAUSE)')

    def resume(self) -> Tuple[bool, str]:
        from tm_msgs.srv import SetEvent
        return self._send(SetEvent.Request.RESUME, '재개(RESUME)')

    def stop_sync(self, timeout_sec: float = 3.0) -> Tuple[bool, str]:
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
