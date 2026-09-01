"""camera_calibration_node 의 Trigger 서비스 4종을 비동기 호출하는 Qt 어댑터."""
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal
from std_srvs.srv import Trigger


class CameraCalibrationService(QObject):
    """calibration/* Trigger 4종을 call_async 로 부르고 결과를 Qt 시그널로 바꾼다.

    add_done_callback 콜백은 rclpy executor 스레드에서 돈다 — 시그널 emit 은
    queued connection 이라 스레드 경계를 안전하게 넘지만, _captured_count 증가는
    executor 스레드에서 일어나므로 GUI 쪽 읽기와는 비동기다.
    서비스 이름이 상대 이름이라 노드 네임스페이스에 종속된다.
    """

    status_changed = pyqtSignal(str)
    chessboard_detected = pyqtSignal(bool, str)
    image_captured = pyqtSignal(bool, str, int)
    calibration_completed = pyqtSignal(bool, str)
    calibration_saved = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, ros_node=None):
        super().__init__()
        self._ros_node = ros_node
        self._captured_count = 0

        self._detect_client = None
        self._capture_client = None
        self._run_client = None
        self._save_client = None

        if ros_node:
            self._init_service_clients()

    @property
    def captured_count(self) -> int:
        return self._captured_count

    def reset_captured_count(self):
        self._captured_count = 0

    def _init_service_clients(self):
        if not self._ros_node:
            return

        self._detect_client = self._ros_node.create_client(
            Trigger, 'calibration/detect_chessboard')
        self._capture_client = self._ros_node.create_client(
            Trigger, 'calibration/capture_image')
        self._run_client = self._ros_node.create_client(
            Trigger, 'calibration/run_calibration')
        self._save_client = self._ros_node.create_client(
            Trigger, 'calibration/save_calibration')

    def _check_service_available(self, client, service_name: str) -> bool:
        """서버 생존 확인 — wait_for_service(1s)로 호출 스레드가 최대 1초 블로킹."""
        if not client:
            self.error_occurred.emit("Calibration 서비스가 초기화되지 않았습니다")
            self.status_changed.emit("서비스 연결 실패")
            return False

        if not client.wait_for_service(timeout_sec=1.0):
            self.error_occurred.emit(
                f"Calibration 서비스를 찾을 수 없습니다. "
                "camera_calibration_node가 실행 중인지 확인하세요."
            )
            self.status_changed.emit("서비스 연결 실패")
            return False

        return True


    def detect_chessboard(self):
        """체스보드 인식을 요청한다 — 결과는 chessboard_detected 시그널."""
        if not self._check_service_available(self._detect_client, "detect"):
            return

        self.status_changed.emit("Chessboard 인식 중...")
        request = Trigger.Request()
        future = self._detect_client.call_async(request)
        future.add_done_callback(self._on_detect_done)

    def capture_image(self):
        """캘리브레이션용 이미지 1장 캡처를 요청한다 — 결과는 image_captured 시그널."""
        if not self._check_service_available(self._capture_client, "capture"):
            return

        self.status_changed.emit("이미지 캡처 중...")
        request = Trigger.Request()
        future = self._capture_client.call_async(request)
        future.add_done_callback(self._on_capture_done)

    def run_calibration(self):
        """캘리브레이션 계산 실행을 요청한다 — 결과는 calibration_completed 시그널."""
        if not self._check_service_available(self._run_client, "calibration"):
            return

        self.status_changed.emit("캘리브레이션 실행 중...")
        request = Trigger.Request()
        future = self._run_client.call_async(request)
        future.add_done_callback(self._on_run_done)

    def save_calibration(self):
        """캘리브레이션 결과 저장을 요청한다 — 결과는 calibration_saved 시그널."""
        if not self._check_service_available(self._save_client, "save"):
            return

        self.status_changed.emit("결과 저장 중...")
        request = Trigger.Request()
        future = self._save_client.call_async(request)
        future.add_done_callback(self._on_save_done)


    def _on_detect_done(self, future):
        try:
            response = future.result()
            self.chessboard_detected.emit(response.success, response.message)
            if response.success:
                self.status_changed.emit("Chessboard 인식 성공")
            else:
                self.status_changed.emit("Chessboard 인식 실패")
        except Exception as e:
            self.error_occurred.emit(f"Chessboard 인식 오류: {e}")
            self.status_changed.emit("오류 발생")

    def _on_capture_done(self, future):
        """(executor 스레드) 캡처 성공 시 카운트를 올리고 시그널로 통지."""
        try:
            response = future.result()
            if response.success:
                self._captured_count += 1
            self.image_captured.emit(
                response.success, response.message, self._captured_count
            )
            if response.success:
                self.status_changed.emit("이미지 캡처 완료")
            else:
                self.status_changed.emit("캡처 실패")
        except Exception as e:
            self.error_occurred.emit(f"이미지 캡처 오류: {e}")
            self.status_changed.emit("오류 발생")

    def _on_run_done(self, future):
        try:
            response = future.result()
            self.calibration_completed.emit(response.success, response.message)
            if response.success:
                self.status_changed.emit("캘리브레이션 완료")
            else:
                self.status_changed.emit("캘리브레이션 실패")
        except Exception as e:
            self.error_occurred.emit(f"캘리브레이션 오류: {e}")
            self.status_changed.emit("오류 발생")

    def _on_save_done(self, future):
        try:
            response = future.result()
            self.calibration_saved.emit(response.success, response.message)
            if response.success:
                self.status_changed.emit("저장 완료")
            else:
                self.status_changed.emit("저장 실패")
        except Exception as e:
            self.error_occurred.emit(f"저장 오류: {e}")
            self.status_changed.emit("오류 발생")
