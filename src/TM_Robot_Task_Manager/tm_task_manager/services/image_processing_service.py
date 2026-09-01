"""이미지 이진화·저장과 동기식 techman 캡처 (호출 스레드 블로킹판)."""
import cv2
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
import rclpy
import time
from cv_bridge import CvBridge


class ImageProcessingService(QObject):
    """threshold 처리 결과 보관 + TMflow 캡처 동기 실행.

    capture_techman_image 는 캡처 시퀀스 전체(대기 포함 최대 약 timeout_sec
    + 0.2s)를 호출 스레드에서 블로킹한다 — 스레드판은 ImageCaptureService.
    """

    processing_completed = pyqtSignal(object)
    processing_error = pyqtSignal(str)
    image_captured = pyqtSignal(object, str)
    capture_error = pyqtSignal(str)
    capture_started = pyqtSignal()

    def __init__(self, gv_manager=None, ros_node=None):
        super().__init__()
        self.processed_image = None
        self.gv_manager = gv_manager
        self.ros_node = ros_node

    def apply_threshold(self, image, threshold_value):
        """BGR 이미지를 GRAY→이진화→BGR 로 처리해 반환·시그널 이중 통지한다."""
        if image is None:
            self.processing_error.emit("이미지가 없습니다.")
            return None

        try:
            img = image.copy()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)
            processed = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

            self.processed_image = processed
            self.processing_completed.emit(processed)
            return processed

        except Exception as e:
            self.processing_error.emit(f"Threshold 적용 오류: {e}")
            return None

    def save_image(self, file_path):
        """처리 결과를 imwrite 로 저장한다 (실패는 processing_error 시그널)."""
        if self.processed_image is None:
            self.processing_error.emit("저장할 처리된 이미지가 없습니다.")
            return False

        try:
            if not cv2.imwrite(file_path, self.processed_image):
                self.processing_error.emit(
                    f"이미지 저장 실패 (경로·권한·형식 확인): {file_path}")
                return False
            return True
        except Exception as e:
            self.processing_error.emit(f"이미지 저장 오류: {e}")
            return False

    def get_processed_image(self):
        return self.processed_image

    def has_processed_image(self):
        return self.processed_image is not None

    def capture_techman_image(self, timeout_sec: float = 3.0) -> bool:
        """동기 캡처: g_robot_command=3 + ScriptExit 후 새 프레임을 기다린다.

        sleep(0.2s)은 TMflow 잡 기동 여유. wait_techman_image(spin=True)로
        호출 스레드에서 노드를 spin 하며 대기한다 — GUI 스레드에서 부르면
        그 시간만큼 화면이 멎는다.
        """
        if self.gv_manager is None:
            self.capture_error.emit("GlobalVariableScript 관리자가 초기화되지 않았습니다")
            return False
        if self.ros_node is None:
            self.capture_error.emit("ROS2 노드가 없습니다")
            return False

        self.capture_started.emit()

        success, result = self.gv_manager.write_variable('g_robot_command', 3)
        if not success:
            self.capture_error.emit(f"g_robot_command = 3 전송 실패: {result}")
            return False

        success = self.gv_manager.send_script_exit(script_id='imgcap')
        if not success:
            self.capture_error.emit("ScriptExit() 전송 실패")
            return False

        time.sleep(0.2)

        baseline = self.ros_node.start_techman_image_subscription()

        msg, err = self.ros_node.wait_techman_image(
            baseline, timeout_sec, spin=True)
        if msg is None:
            self.capture_error.emit(err)
            return False

        try:
            bridge = CvBridge()
            cv_image = bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.capture_error.emit(f"이미지 변환 오류: {e}")
            return False

        self.image_captured.emit(cv_image, "Image Capture 완료")
        return True
