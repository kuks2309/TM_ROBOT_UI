from typing import List
from PyQt5 import uic
from PyQt5.QtWidgets import QVBoxLayout, QFileDialog, QTableWidgetItem
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap
from ament_index_python.packages import get_package_share_directory
import os
import cv2
import numpy as np

from .base_tab import BaseTab


class AIDetectionTab(BaseTab):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

        self.ui_widget = None

        self._detection_timer = None

        self._pending_single_detection = False

    def init_ui(self):
        if self.ros_node:
            self.ros_node.get_logger().info('[AIDetectionTab] init_ui() 시작')

        try:
            package_share_dir = get_package_share_directory('tm_task_manager')
            ui_path = f"{package_share_dir}/ui/ai_detection_tab.ui"
            self.ui_widget = uic.loadUi(ui_path)
            if self.ros_node:
                self.ros_node.get_logger().info(f'[AIDetectionTab] UI 로드 완료: {ui_path}')
        except Exception as e:
            if self.ros_node:
                self.ros_node.get_logger().error(f'[AIDetectionTab] UI 로드 실패: {e}')
            return

        if not hasattr(self.mw, 'tab_aiDetection'):
            print("[AIDetectionTab] ERROR: tab_aiDetection이 main_window에 없음!")
            return

        layout = self.mw.tab_aiDetection.layout()
        if layout is None:
            layout = QVBoxLayout(self.mw.tab_aiDetection)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_widget)
        print("[AIDetectionTab] 레이아웃 설정 완료")

        self._init_detection_setup()

        self._init_confidence_controls()

        self._detection_timer = QTimer()
        self._detection_timer.setInterval(100)
        self._detection_timer.timeout.connect(self._run_detection)

        print("[AIDetectionTab] init_ui() 완료")

    def _init_detection_setup(self):
        if not self.ui_widget or not hasattr(self.mw, 'ai_detection_service'):
            return

        service = self.mw.ai_detection_service

        combo_detection = self.ui_widget.comboBox_detection
        combo_detection.clear()
        for task_id, display_name in service.get_available_tasks():
            combo_detection.addItem(display_name, task_id)

        combo_runtime = self.ui_widget.comboBox_runtime
        combo_runtime.clear()
        for runtime_id, display_name in service.get_available_runtimes():
            combo_runtime.addItem(display_name, runtime_id)

        self._refresh_model_combobox()

        if self.ros_node:
            self.ros_node.get_logger().info('[AIDetectionTab] Detection Setup 초기화 완료')

    def _refresh_model_combobox(self):
        if not self.ui_widget or not hasattr(self.mw, 'ai_detection_service'):
            return

        task = self.ui_widget.comboBox_detection.currentData()
        runtime = self.ui_widget.comboBox_runtime.currentData()

        combo_model = self.ui_widget.comboBox_model
        combo_model.clear()

        if task and runtime:
            models = self.mw.ai_detection_service.get_available_models(task, runtime)
            for name, path in models:
                combo_model.addItem(name, path)

        if self.ros_node:
            count = combo_model.count()
            self.ros_node.get_logger().info(
                f'[AIDetectionTab] 모델 목록 갱신: task={task}, runtime={runtime}, {count}개'
            )

    def _init_confidence_controls(self):
        if not self.ui_widget:
            return

        initial_confidence = 0.5
        self.ui_widget.doubleSpinBox_confidence.setValue(initial_confidence)
        self.ui_widget.horizontalSlider_confidence.setValue(int(initial_confidence * 100))

        self.ui_widget.doubleSpinBox_confidence.valueChanged.connect(
            lambda value: self.ui_widget.horizontalSlider_confidence.setValue(int(value * 100))
        )
        self.ui_widget.horizontalSlider_confidence.valueChanged.connect(
            lambda value: self.ui_widget.doubleSpinBox_confidence.setValue(value / 100.0)
        )

    def connect_signals(self):
        if self.ros_node:
            self.ros_node.get_logger().info('[AIDetectionTab] connect_signals() 시작')

        if not hasattr(self.mw, 'ai_detection_service') or not self.mw.ai_detection_service:
            if self.ros_node:
                self.ros_node.get_logger().error('[AIDetectionTab] ERROR: ai_detection_service가 없음!')
            return

        service = self.mw.ai_detection_service

        service.model_loaded.connect(self._on_model_loaded)
        service.detection_completed.connect(self._on_detection_completed)
        service.detection_error.connect(self._on_detection_error)
        service.status_changed.connect(self._on_status_changed)

        if self.ui_widget:
            self.ui_widget.comboBox_detection.currentIndexChanged.connect(self._on_detection_changed)
            self.ui_widget.comboBox_runtime.currentIndexChanged.connect(self._on_runtime_changed)

            self.ui_widget.comboBox_model.currentIndexChanged.connect(self._on_model_changed)
            self.ui_widget.pushButton_loadModel.clicked.connect(self._on_load_custom_model)

            self.ui_widget.doubleSpinBox_confidence.valueChanged.connect(self._on_confidence_changed)

            self.ui_widget.pushButton_startDetection.toggled.connect(self._on_toggle_detection)
            self.ui_widget.pushButton_singleDetection.clicked.connect(self._on_single_detection)

        if hasattr(self.mw, 'image_capture_service') and self.mw.image_capture_service:
            self.mw.image_capture_service.image_captured.connect(self._on_capture_then_detect)

        if self.ros_node:
            self.ros_node.get_logger().info('[AIDetectionTab] 시그널 연결 완료')


    def _on_model_loaded(self, success: bool, message: str):
        if success:
            self._log(f"모델 로드 성공: {message}")
        else:
            self._log(f"모델 로드 실패: {message}")

    def _on_detection_completed(self, detections: List, annotated_image: np.ndarray, fps: float):
        if self.ui_widget:
            self.ui_widget.label_fps.setText(f"FPS: {fps:.1f}")

        self._display_image(annotated_image)

        self._update_results_table(detections)

    def _on_detection_error(self, error_msg: str):
        self._log(f"Detection Error: {error_msg}")

    def _on_status_changed(self, status: str):
        if self.ui_widget:
            self.ui_widget.label_detectionStatus.setText(f"Status: {status}")


    def _on_detection_changed(self, index: int):
        if index < 0:
            return
        self._refresh_model_combobox()

    def _on_runtime_changed(self, index: int):
        if index < 0:
            return
        self._refresh_model_combobox()

    def _on_model_changed(self, index: int):
        if not self.ui_widget or index < 0:
            return

        model_path = self.ui_widget.comboBox_model.itemData(index)

        if model_path and self.mw.ai_detection_service:
            self.mw.ai_detection_service.load_model(model_path)

    def _on_load_custom_model(self):
        runtime = self.ui_widget.comboBox_runtime.currentData() if self.ui_widget else "pc"
        if runtime == "hailo":
            file_filter = "Hailo Model (*.hef)"
        else:
            file_filter = "PyTorch Model (*.pt)"

        from ..services.ai_detection_service import AIDetectionService
        initial_dir = AIDetectionService.TASKS_ROOT if os.path.isdir(AIDetectionService.TASKS_ROOT) else ""

        file_path, _ = QFileDialog.getOpenFileName(
            self.ui_widget,
            "Select Model",
            initial_dir,
            file_filter
        )

        if file_path and self.mw.ai_detection_service:
            self.mw.ai_detection_service.load_model(file_path)

    def _on_confidence_changed(self, threshold: float):
        if self.mw.ai_detection_service:
            self.mw.ai_detection_service.set_confidence_threshold(threshold)

    def _on_toggle_detection(self, checked: bool):
        if not self._detection_timer:
            return

        if checked:
            if self.ui_widget:
                self.ui_widget.pushButton_startDetection.setText("Stop Detection")
            self._detection_timer.start()
            self._log("Detection started")
        else:
            if self.ui_widget:
                self.ui_widget.pushButton_startDetection.setText("Start Detection")
            self._detection_timer.stop()
            self._log("Detection stopped")

    def _on_single_detection(self):
        if not self.mw.ai_detection_service or not self.mw.ai_detection_service.is_model_loaded:
            self._log("모델을 먼저 로드하세요")
            return

        if not hasattr(self.mw, 'image_capture_service') or not self.mw.image_capture_service:
            self._log("ImageCaptureService가 없습니다")
            return

        if self.mw.image_capture_service.is_capturing:
            self._log("이미지 캡처 진행 중...")
            return

        self._pending_single_detection = True

        self._log("이미지 캡처 + 추론 시작...")
        self.mw.image_capture_service.capture_image(timeout_sec=3.0)

    def _on_capture_then_detect(self, cv_image):
        if not self._pending_single_detection:
            return
        self._pending_single_detection = False
        self.mw.current_camera_image = cv_image
        if self.mw.ai_detection_service and self.mw.ai_detection_service.is_model_loaded:
            self._log("추론 실행 중...")
            self.mw.ai_detection_service.run_inference(cv_image)


    def _run_detection(self):
        if not hasattr(self.mw, 'current_camera_image') or self.mw.current_camera_image is None:
            self._log("Image Capture를 먼저 실행하세요")
            return

        if not self.mw.ai_detection_service or not self.mw.ai_detection_service.is_model_loaded:
            return

        self.mw.ai_detection_service.run_inference(self.mw.current_camera_image)


    def _display_image(self, cv_image: np.ndarray):
        if not self.ui_widget or cv_image is None:
            return

        try:
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

            label = self.ui_widget.label_detectionImage
            label_width = label.width()
            label_height = label.height()

            img_height, img_width = rgb_image.shape[:2]
            scale = min(label_width / img_width, label_height / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            resized = cv2.resize(rgb_image, (new_width, new_height))

            height, width, channel = resized.shape
            bytes_per_line = 3 * width
            q_image = QImage(resized.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)

            label.setPixmap(pixmap)

        except Exception as e:
            if self.ros_node:
                self.ros_node.get_logger().error(f'[AIDetectionTab] 이미지 표시 실패: {e}')

    def _update_results_table(self, detections: List):
        if not self.ui_widget:
            return

        table = self.ui_widget.tableWidget_detections
        table.setRowCount(len(detections))

        for i, detection in enumerate(detections):
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            table.setItem(i, 1, QTableWidgetItem(detection.class_name))

            table.setItem(i, 2, QTableWidgetItem(f"{detection.confidence:.3f}"))

            x, y, w, h = detection.bbox
            bbox_str = f"({x}, {y}, {w}, {h})"
            table.setItem(i, 3, QTableWidgetItem(bbox_str))

            cx, cy = detection.center
            center_str = f"({cx}, {cy})"
            table.setItem(i, 4, QTableWidgetItem(center_str))

            angle_str = f"{detection.angle:.1f}°" if detection.angle is not None else "-"
            table.setItem(i, 5, QTableWidgetItem(angle_str))

            state_str = detection.state if detection.state else "-"
            table.setItem(i, 6, QTableWidgetItem(state_str))
