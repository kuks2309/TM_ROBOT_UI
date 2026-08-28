import time
from typing import Optional, Tuple
from PyQt5.QtCore import QObject, QThread, pyqtSignal
import numpy as np


# 현재 로봇 프로젝트의 이미지 캡처 트리거 — 전역변수 명령 방식.
# job_executor.py 의 AI 캡처 경로(`g_robot_command=3` + `ScriptExit()`)와 동일한 규약.
VISION_CAPTURE_COMMAND_VAR = "g_robot_command"
VISION_CAPTURE_COMMAND = 3


class ImageCaptureWorker(QThread):
    image_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, ros_node, gv_manager, timeout_sec: float = 3.0):
        super().__init__()
        self._ros_node = ros_node
        self._gv_manager = gv_manager
        self._timeout_sec = timeout_sec
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            if not self._ros_node:
                self.error_occurred.emit("ROS2 노드가 없습니다")
                return

            baseline = self._ros_node.start_techman_image_subscription()
            self.status_changed.emit("카메라 이미지 구독 시작")

            self.status_changed.emit(f"캡처 명령 전송 요청 (g_robot_command={VISION_CAPTURE_COMMAND})...")

            def _send() -> Tuple[bool, str]:
                ok, msg = self._gv_manager.write_variable(
                    VISION_CAPTURE_COMMAND_VAR, VISION_CAPTURE_COMMAND)
                if not ok:
                    return False, msg
                if not self._gv_manager.send_script_exit():
                    return False, "ScriptExit() 발행 실패"
                return True, "캡처 명령 전송 완료"

            label = f'{VISION_CAPTURE_COMMAND_VAR}={VISION_CAPTURE_COMMAND}'
            gateway = getattr(self._ros_node, 'motion_gateway', None)
            if gateway is not None:
                success, result = gateway.send_vision_job(_send, label=label)
            else:
                success, result = _send()

            if not success:
                self.error_occurred.emit(f"캡처 명령 전송 실패: {result}")
                return

            self.status_changed.emit("캡처 명령 전송 완료 — 촬영 대기")

            if self._should_stop:
                return

            # 이번 요청(baseline) **뒤에** 도착한 프레임만 받는다.
            # 예전에는 공용 플래그 하나만 보고 빠져나와, 다른 소비자가 받은
            # 이미지나 이전 캡처의 늦은 프레임을 이번 것으로 쓰는 일이 있었다.
            msg, err = self._ros_node.wait_techman_image(
                baseline, self._timeout_sec,
                should_stop=lambda: self._should_stop)
            if msg is None:
                if err != '중단 요청':
                    self.error_occurred.emit(err)
                return

            try:
                from cv_bridge import CvBridge
                bridge = CvBridge()
                cv_image = bridge.imgmsg_to_cv2(msg, "bgr8")
                self.status_changed.emit("이미지 캡처 완료")
                self.image_ready.emit(cv_image)
            except Exception as e:
                self.error_occurred.emit(f"이미지 변환 오류: {e}")

        except Exception as e:
            self.error_occurred.emit(f"이미지 캡처 오류: {e}")


class ImageCaptureService(QObject):
    image_captured = pyqtSignal(object)
    capture_status = pyqtSignal(str)
    capture_error = pyqtSignal(str)
    capture_started = pyqtSignal()
    capture_finished = pyqtSignal()

    def __init__(self, ros_node=None, gv_manager=None):
        super().__init__()
        self._ros_node = ros_node
        self._gv_manager = gv_manager
        self._worker: Optional[ImageCaptureWorker] = None
        self._last_captured_image: Optional[np.ndarray] = None

    def set_ros_node(self, ros_node):
        self._ros_node = ros_node

    def set_gv_manager(self, gv_manager):
        self._gv_manager = gv_manager

    @property
    def last_captured_image(self) -> Optional[np.ndarray]:
        return self._last_captured_image

    @property
    def is_capturing(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def capture_image(self, timeout_sec: float = 3.0) -> None:
        if self.is_capturing:
            self.capture_error.emit("이미 캡처가 진행 중입니다")
            return

        if not self._gv_manager:
            self.capture_error.emit("GlobalVariableScript 관리자가 초기화되지 않았습니다")
            return

        if not self._ros_node:
            self.capture_error.emit("ROS2 노드가 초기화되지 않았습니다")
            return

        self.capture_started.emit()
        self.capture_status.emit("이미지 캡처 시작...")

        self._worker = ImageCaptureWorker(
            self._ros_node, self._gv_manager, timeout_sec
        )
        self._worker.image_ready.connect(self._on_image_ready)
        self._worker.status_changed.connect(self.capture_status)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def cancel_capture(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
            self.capture_status.emit("캡처 취소됨")
            self.capture_finished.emit()

    def _on_image_ready(self, cv_image):
        self._last_captured_image = cv_image
        self.image_captured.emit(cv_image)

    def _on_error(self, error_msg: str):
        self.capture_error.emit(error_msg)

    def _on_worker_finished(self):
        self._worker = None
        self.capture_finished.emit()
