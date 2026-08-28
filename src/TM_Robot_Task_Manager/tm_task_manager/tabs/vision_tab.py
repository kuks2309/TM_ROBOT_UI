import cv2
from datetime import datetime

from PyQt5.QtWidgets import QTableWidgetItem, QFileDialog
from PyQt5.QtGui import QImage, QPixmap

from .base_tab import BaseTab


class VisionTab(BaseTab):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def connect_signals(self):
        self.mw.tableWidget_detectedTags.itemSelectionChanged.connect(
            self._on_tag_selection_changed
        )

        self.mw.pushButton_applyThreshold.clicked.connect(self._on_apply_threshold)
        self.mw.pushButton_saveProcessedImage.clicked.connect(self._on_save_processed_image)

        self.mw.horizontalSlider_threshold.valueChanged.connect(
            self.mw.spinBox_thresholdValue.setValue
        )
        self.mw.spinBox_thresholdValue.valueChanged.connect(
            self.mw.horizontalSlider_threshold.setValue
        )
        self.mw.spinBox_thresholdValue.valueChanged.connect(self._on_apply_threshold)

        self.mw.pushButton_useSelectedTag.clicked.connect(self._on_use_selected_tag)

        self.vision_manager.tag_updated.connect(self._on_tag_updated)

        self.mw.image_processing_service.processing_completed.connect(
            self._on_processing_completed
        )
        self.mw.image_processing_service.processing_error.connect(self._log)

        self._connect_jog_signals()

    def _connect_jog_signals(self):
        for axis, name in [('x', 'X'), ('y', 'Y'), ('z', 'Z'),
                           ('rx', 'Rx'), ('ry', 'Ry'), ('rz', 'Rz')]:
            getattr(self.mw, f'pushButton_visionJog{name}Minus').clicked.connect(
                lambda _checked=False, a=axis: self.mw.jog_service.jog(a, -1))
            getattr(self.mw, f'pushButton_visionJog{name}Plus').clicked.connect(
                lambda _checked=False, a=axis: self.mw.jog_service.jog(a, 1))

        self.mw.spinBox_visionJogStep.valueChanged.connect(
            lambda v: self.mw.jog_service.set_params(step_mm=v))
        self.mw.spinBox_visionJogVelocity.valueChanged.connect(
            lambda v: self.mw.jog_service.set_params(velocity_percent=v))
        self.mw.jog_service.params_changed.connect(self._on_jog_params_changed)

        step_mm, velocity_percent = self.mw.jog_service.get_params()
        self._on_jog_params_changed(step_mm, velocity_percent)

    def _on_jog_params_changed(self, step_mm: float, velocity_percent: int):
        self.mw.spinBox_visionJogStep.blockSignals(True)
        self.mw.spinBox_visionJogVelocity.blockSignals(True)
        self.mw.spinBox_visionJogStep.setValue(step_mm)
        self.mw.spinBox_visionJogVelocity.setValue(velocity_percent)
        self.mw.spinBox_visionJogStep.blockSignals(False)
        self.mw.spinBox_visionJogVelocity.blockSignals(False)

    def init_ui(self):
        pass


    def update_camera_image(self, cv_image):
        self.mw.current_camera_image = cv_image.copy()

        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(q_image)
        scaled_pixmap = pixmap.scaled(
            self.mw.label_cameraImage.size(),
            aspectRatioMode=1
        )
        self.mw.label_cameraImage.setPixmap(scaled_pixmap)


    def update_tag_pose(self, pose_msg):
        frame_id = pose_msg.header.frame_id
        tag_id = "unknown"
        if "aruco_marker_" in frame_id:
            tag_id = frame_id.replace("aruco_marker_", "")
        else:
            tag_id = "0"

        x = pose_msg.pose.position.x
        y = pose_msg.pose.position.y
        z = pose_msg.pose.position.z

        self.vision_manager.update_tag_pose(tag_id, {
            'x': x,
            'y': y,
            'z': z,
            'pose': pose_msg
        })

    def _on_tag_updated(self, tag_id: str, tag_data: dict):
        self._update_tag_table()

    def _update_tag_table(self):
        all_tags = self.vision_manager.get_all_tags()
        self.mw.tableWidget_detectedTags.setRowCount(len(all_tags))

        for row, (tag_id, data) in enumerate(all_tags.items()):
            self.mw.tableWidget_detectedTags.setItem(
                row, 0, QTableWidgetItem(str(tag_id))
            )
            self.mw.tableWidget_detectedTags.setItem(
                row, 1, QTableWidgetItem(f"{data['x']:.3f}")
            )
            self.mw.tableWidget_detectedTags.setItem(
                row, 2, QTableWidgetItem(f"{data['y']:.3f}")
            )
            self.mw.tableWidget_detectedTags.setItem(
                row, 3, QTableWidgetItem(f"{data['z']:.3f}")
            )

    def _on_tag_selection_changed(self):
        selected_items = self.mw.tableWidget_detectedTags.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            tag_id = self.mw.tableWidget_detectedTags.item(row, 0)
            if tag_id:
                tag_id_str = tag_id.text()
                self.mw.label_selectedTagIdValue.setText(tag_id_str)

                data = self.vision_manager.get_tag(tag_id_str)
                if data:
                    self.mw.label_selectedTagPosValue.setText(
                        f"({data['x']:.3f}, {data['y']:.3f}, {data['z']:.3f})"
                    )
                    pose = data['pose']
                    q = pose.pose.orientation
                    self.mw.label_selectedTagRotValue.setText(
                        f"({q.x:.3f}, {q.y:.3f}, {q.z:.3f}, {q.w:.3f})"
                    )

    def _on_use_selected_tag(self):
        selected_items = self.mw.tableWidget_detectedTags.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            tag_id_item = self.mw.tableWidget_detectedTags.item(row, 0)
            if tag_id_item:
                tag_id = tag_id_item.text()
                if self.vision_manager.has_tag(tag_id):
                    self.mw.spinBox_tagId.setValue(int(tag_id))
                    self._log(f"태그 ID {tag_id}를 기준으로 설정")
        else:
            self._log("선택된 태그가 없습니다")


    def _on_apply_threshold(self):
        if self.mw.current_camera_image is None:
            self._log("카메라 이미지가 없습니다. 먼저 카메라를 시작하세요.")
            return

        threshold_value = self.mw.spinBox_thresholdValue.value()
        self.mw.image_processing_service.apply_threshold(
            self.mw.current_camera_image, threshold_value
        )
        self._log(f"Threshold 적용: {threshold_value}")

    def _on_processing_completed(self, processed_image):
        self._display_processed_image(processed_image)

    def _display_processed_image(self, image):
        try:
            h, w = image.shape[:2]
            if len(image.shape) == 2:
                qimg = QImage(image.data, w, h, w, QImage.Format_Grayscale8)
            else:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                qimg = QImage(rgb_image.data, w, h, w * 3, QImage.Format_RGB888)

            pixmap = QPixmap.fromImage(qimg)
            scaled_pixmap = pixmap.scaled(
                self.mw.label_processedImage.size(),
                aspectRatioMode=1
            )
            self.mw.label_processedImage.setPixmap(scaled_pixmap)
        except Exception as e:
            self._log(f"이미지 표시 오류: {e}")

    def _on_save_processed_image(self):
        if not self.mw.image_processing_service.has_processed_image():
            self._log("저장할 처리된 이미지가 없습니다.")
            return

        default_name = f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self.mw, "처리 이미지 저장", default_name,
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )

        if file_path:
            if self.mw.image_processing_service.save_image(file_path):
                self._log(f"처리 이미지 저장: {file_path}")
