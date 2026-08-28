import cv2
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
import rclpy
import time
from cv_bridge import CvBridge


class ImageProcessingService(QObject):
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
        if self.processed_image is None:
            self.processing_error.emit("저장할 처리된 이미지가 없습니다.")
            return False

        try:
            # imwrite 는 실패해도 예외 없이 False 를 돌려준다 — 반환값을 봐야 한다.
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

        # 이 경로는 자체 실행기가 없어 콜백을 직접 돌려야 한다 → spin=True.
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
