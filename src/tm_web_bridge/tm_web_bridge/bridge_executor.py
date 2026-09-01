"""JobExecutor 확장 — move_linear 잡을 tm_driver send_script(Move_Line) 로 수행한다."""
import threading
import time

from tm_task_manager.job_executor import JobExecutor


class BridgeJobExecutor(JobExecutor):
    """웹 시퀀스용 실행기 — move_linear 잡 하나만 오버라이드한다."""

    def _exec_move_linear(self, job) -> bool:
        """Move_Line("TPP", …) 상대 오프셋 직선 이동 (offset mm, velocity mm/s).

        완료는 로봇측 완료 신호가 아니라 motion_service.is_moving 폴링으로 판정한다:
        이동 시작 감지 최대 2s, 이후 최대 30s 안에 비이동 연속 5회면 완료로 본다.
        """
        params = job.params if hasattr(job, "params") else job
        offset_x = params.get("offset X", 0.0)
        offset_y = params.get("offset Y", 0.0)
        offset_z = params.get("offset Z", 0.0)
        velocity_mm_s = params.get("velocity", 50.0)

        node = self.ros_node
        if not node:
            self._log("ROS2 노드가 없습니다")
            return False

        from tm_msgs.srv import SendScript

        client = getattr(node, "send_script_client", None)
        if not client:
            self._log("send_script 클라이언트가 없습니다")
            return False
        if not client.wait_for_service(timeout_sec=1.0):
            self._log("send_script 서비스를 사용할 수 없습니다")
            return False

        vel = int(velocity_mm_s)
        script = f'Move_Line("TPP", {offset_x}, {offset_y}, {offset_z}, 0, 0, 0, {vel}, 200, 0, true)'
        request = SendScript.Request()
        request.id = "gv"
        request.script = script
        self._log(
            f"직선 이동(Move_Line): 오프셋({offset_x:.1f}, {offset_y:.1f}, {offset_z:.1f})mm, "
            f"속도 {vel} mm/s"
        )

        future = client.call_async(request)
        done = threading.Event()
        future.add_done_callback(lambda _f: done.set())
        if not done.wait(timeout=10.0):
            self._log("직선 이동 실패: send_script 타임아웃")
            return False
        result = future.result()
        if result is None or not result.ok:
            self._log("직선 이동 실패: 스크립트 전송 실패")
            return False

        motion_service = node.motion_service
        start_time = time.time()

        while time.time() - start_time < 2.0:
            if self._stop_requested:
                self._log("직선 이동 취소됨")
                return False
            if motion_service.is_moving:
                break
            time.sleep(0.05)

        stable_count = 0
        while time.time() - start_time < 30.0:
            if self._stop_requested:
                self._log("직선 이동 취소됨")
                return False
            if not motion_service.is_moving:
                stable_count += 1
                if stable_count >= 5:
                    self._log("직선 이동 완료")
                    return True
            else:
                stable_count = 0
            time.sleep(0.05)

        self._log("직선 이동 실패: 이동 완료 확인 타임아웃")
        return False
