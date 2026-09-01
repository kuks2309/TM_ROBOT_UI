"""Recipe 편집 탭 — Job 추가/삭제/이동, 타입별 파라미터 폼 동적 생성, 개별 Task 수동 실행·티칭을 담당한다."""
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
    QCheckBox, QComboBox, QTreeWidgetItem, QListWidgetItem,
    QPlainTextEdit, QMenu, QWidget, QHBoxLayout, QPushButton, QFileDialog
)

from .. import paths
from .base_tab import BaseTab


class TaskEditTab(BaseTab):
    """Task 시퀀스 편집·파라미터 폼·수동 실행(job.type 분기 디스패치)·오차 preset·PS2 jog 연동을 담당하는 탭."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.param_widgets = {}
        self.param_labels = {}
        self._offset_preset_combo = None
        self._pending_ai_inspection = False
        self._init_ps2_jog()

    def _init_ps2_jog(self):
        self.joystick_service = self.mw.joystick_service

        self.mw.checkBox_ps2JogEnable.toggled.connect(self._on_ps2_jog_toggled)

        self.joystick_service.jog_requested.connect(self._on_ps2_jog_requested)
        self.joystick_service.mode_changed.connect(self._on_ps2_mode_changed)
        self.joystick_service.connection_changed.connect(self._on_ps2_connection_changed)
        self.joystick_service.status_changed.connect(self._on_ps2_status_changed)

    def connect_signals(self):
        self.mw.listWidget_taskSequence.currentRowChanged.connect(
            self._on_task_sequence_selected
        )

        self.mw.pushButton_addTask.clicked.connect(self._on_add_task_to_sequence)
        self.mw.pushButton_removeTask.clicked.connect(self._on_delete_task_from_sequence)
        self.mw.pushButton_moveUp.clicked.connect(self._on_move_task_up)
        self.mw.pushButton_moveDown.clicked.connect(self._on_move_task_down)
        self.mw.pushButton_copyTask.clicked.connect(self._on_copy_task_in_sequence)

        self.mw.listWidget_taskSequence.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mw.listWidget_taskSequence.customContextMenuRequested.connect(
            self._on_task_sequence_context_menu
        )

        self.mw.pushButton_applyParams.clicked.connect(self._on_apply_params)
        self.mw.pushButton_teachPosition.clicked.connect(self._on_teach_position)
        self.mw.pushButton_moveToParams.clicked.connect(self._on_move_to_params)

        self.mw.treeWidget_availableTasks.itemDoubleClicked.connect(
            self._on_available_task_double_clicked
        )

    def init_ui(self):
        self._init_available_tasks()

    def _init_available_tasks(self):
        self.mw.treeWidget_availableTasks.clear()

        category_order = self.recipe_manager.CATEGORY_ORDER
        categories = {cat: [] for cat in category_order}

        for task_id, task_info in self.recipe_manager.JOB_TYPES.items():
            category = task_info.get('category', 'Control')
            if category in categories:
                categories[category].append(task_id)

        for category in category_order:
            tasks = categories[category]
            if tasks:
                category_item = QTreeWidgetItem(
                    self.mw.treeWidget_availableTasks, [category]
                )
                for task_id in tasks:
                    QTreeWidgetItem(category_item, [task_id])

        self.mw.treeWidget_availableTasks.expandAll()


    def _on_available_task_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item.parent() is not None:
            self._on_add_task_to_sequence()

    def _on_add_task_to_sequence(self):
        selected = self.mw.treeWidget_availableTasks.currentItem()
        if selected is None or selected.parent() is None:
            self._log("추가할 Task를 선택하세요")
            return

        task_type = selected.text(0)
        try:
            job = self.recipe_manager.create_job(task_type)
            self.recipe_manager.current_recipe.add_job(job)
            self._update_task_sequence()
            self._log(f"Task 추가됨: {job.name}")
        except ValueError as e:
            self._log(f"Task 추가 실패: {e}")

    def _on_delete_task_from_sequence(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        if current_row >= 0:
            recipe = self.recipe_manager.current_recipe
            if recipe and current_row < len(recipe.jobs):
                task = recipe.jobs[current_row]
                recipe.remove_job(current_row)
                self._update_task_sequence()
                self._log(f"Task 삭제됨: {task.name}")

    def _on_move_task_up(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if recipe and recipe.move_job_up(current_row):
            self._update_task_sequence()
            self.mw.listWidget_taskSequence.setCurrentRow(current_row - 1)
            self._log("Task 위로 이동")

    def _on_move_task_down(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if recipe and recipe.move_job_down(current_row):
            self._update_task_sequence()
            self.mw.listWidget_taskSequence.setCurrentRow(current_row + 1)
            self._log("Task 아래로 이동")

    def _on_copy_task_in_sequence(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        if current_row < 0:
            self._log("복사할 Task를 선택하세요")
            return
        recipe = self.recipe_manager.current_recipe
        if recipe and recipe.duplicate_job(current_row):
            self._update_task_sequence()
            self.mw.listWidget_taskSequence.setCurrentRow(current_row + 1)
            self._log(f"Task 복사됨: {recipe.jobs[current_row + 1].name}")

    def _on_task_sequence_context_menu(self, position):
        item = self.mw.listWidget_taskSequence.itemAt(position)
        if item is None:
            return

        menu = QMenu(self.mw.listWidget_taskSequence)

        copy_action = menu.addAction("복사")
        menu.addSeparator()
        move_up_action = menu.addAction("위로 이동")
        move_down_action = menu.addAction("아래로 이동")
        menu.addSeparator()
        delete_action = menu.addAction("삭제")

        action = menu.exec_(self.mw.listWidget_taskSequence.mapToGlobal(position))

        if action == copy_action:
            self._on_copy_task_in_sequence()
        elif action == move_up_action:
            self._on_move_task_up()
        elif action == move_down_action:
            self._on_move_task_down()
        elif action == delete_action:
            self._on_delete_task_from_sequence()

    def _update_task_sequence(self):
        self.mw.listWidget_taskSequence.clear()
        recipe = self.recipe_manager.current_recipe
        if recipe:
            for job in recipe.jobs:
                display_name = getattr(job, 'caption', '') or job.name
                item_text = f"{job.id}. [{job.type}] {display_name}"
                item = QListWidgetItem(item_text)
                self.mw.listWidget_taskSequence.addItem(item)


    def _on_apply_params(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if recipe and 0 <= current_row < len(recipe.jobs):
            job = recipe.jobs[current_row]
            self._save_params_from_ui(job)
            self._update_task_sequence()
            self.mw.listWidget_taskSequence.setCurrentRow(current_row)
            display_name = job.caption if job.caption else job.name
            self._log(f"파라미터 적용됨: {display_name}")

    def _on_task_sequence_selected(self, row: int):
        recipe = self.recipe_manager.current_recipe
        if recipe and 0 <= row < len(recipe.jobs):
            job = recipe.jobs[row]
            self._display_task_params(job)
        else:
            self._clear_params_ui()

    def _display_task_params(self, job):
        self._clear_params_ui()

        self.mw.label_selectedTask.setText(f"선택된 Task: {job.name} [{job.type}]")

        layout = self.mw.formLayout_params
        self.param_widgets = {}
        self.param_labels = {}

        caption_label = QLabel("캡션:")
        caption_label.setStyleSheet("font-weight: bold;")
        caption_label.setToolTip("Task 목록에 표시될 사용자 정의 이름")
        caption_edit = QLineEdit()
        caption_text = getattr(job, 'caption', '') or ""
        caption_edit.setText(caption_text)
        caption_edit.setPlaceholderText("사용자 정의 이름 (선택사항)")
        caption_edit.setToolTip("Task 목록에 표시될 사용자 정의 이름")
        layout.addRow(caption_label, caption_edit)
        self.param_widgets['_caption'] = caption_edit

        job_def = self.recipe_manager.JOB_TYPES.get(job.type, {})
        param_defs = job_def.get('params', {})
        for param_name, param_def in param_defs.items():
            param_value = job.params.get(param_name, param_def.get('default'))
            param_type = param_def.get('type', 'str')
            description = param_def.get('description', param_name)
            choices = param_def.get('choices', [])

            label = QLabel(f"{param_name}:")
            label.setToolTip(description)

            if param_type == 'choice' and choices:
                widget = QComboBox()
                widget.addItems(choices)
                if param_value in choices:
                    widget.setCurrentText(param_value)
                if param_name == 'motion_type':
                    widget.currentTextChanged.connect(self._on_motion_type_changed)
            elif param_type == 'float':
                widget = QDoubleSpinBox()
                widget.setRange(-10000, 10000)
                widget.setDecimals(2)
                step = param_def.get('step', 0.01)
                widget.setSingleStep(step)
                widget.setValue(float(param_value) if param_value is not None else 0.0)
                if param_name == 'velocity':
                    if job.type == 'move_linear':
                        widget.setSuffix(' mm/s')
                        widget.setToolTip("속도 (mm/s). LINE_T 명령에 직접 사용됩니다.")
                        widget.setRange(0.0, 2000.0)
                    else:
                        widget.setSuffix(' %')
                        widget.setToolTip("속도 (%)")
            elif param_type == 'int':
                widget = QSpinBox()
                min_val = param_def.get('min', 0)
                max_val = param_def.get('max', 100000)
                widget.setRange(min_val, max_val)
                step = param_def.get('step', 1)
                widget.setSingleStep(step)
                if param_name in ['duration', 'wait_after_command']:
                    widget.setSuffix(' ms')
                widget.setValue(int(param_value) if param_value is not None else 0)
            elif param_type == 'bool':
                widget = QCheckBox()
                widget.setChecked(bool(param_value) if param_value is not None else False)
            elif param_type == 'dict' and param_name == 'offset':
                if isinstance(param_value, dict):
                    x_val = param_value.get('x', 0.0)
                    y_val = param_value.get('y', 0.0)
                    z_val = param_value.get('z', 0.0)
                else:
                    x_val, y_val, z_val = 0.0, 0.0, 0.0

                x_label = QLabel("offset X:")
                x_label.setToolTip("X 오프셋 (mm)")
                x_spin = QDoubleSpinBox()
                x_spin.setRange(-10000, 10000)
                x_spin.setDecimals(2)
                x_spin.setSingleStep(1.0)
                x_spin.setValue(float(x_val))
                x_spin.setToolTip("X 오프셋 (mm)")
                layout.addRow(x_label, x_spin)
                self.param_widgets['offset_x'] = x_spin
                self.param_labels['offset_x'] = x_label

                y_label = QLabel("offset Y:")
                y_label.setToolTip("Y 오프셋 (mm)")
                y_spin = QDoubleSpinBox()
                y_spin.setRange(-10000, 10000)
                y_spin.setDecimals(2)
                y_spin.setSingleStep(1.0)
                y_spin.setValue(float(y_val))
                y_spin.setToolTip("Y 오프셋 (mm)")
                layout.addRow(y_label, y_spin)
                self.param_widgets['offset_y'] = y_spin
                self.param_labels['offset_y'] = y_label

                z_label = QLabel("offset Z:")
                z_label.setToolTip("Z 오프셋 (mm)")
                z_spin = QDoubleSpinBox()
                z_spin.setRange(-10000, 10000)
                z_spin.setDecimals(2)
                z_spin.setSingleStep(1.0)
                z_spin.setValue(float(z_val))
                z_spin.setToolTip("Z 오프셋 (mm)")
                layout.addRow(z_label, z_spin)
                self.param_widgets['offset_z'] = z_spin
                self.param_labels['offset_z'] = z_label

                continue
            elif param_type == 'dirpath':
                container = QWidget()
                hbox = QHBoxLayout(container)
                hbox.setContentsMargins(0, 0, 0, 0)

                path_edit = QLineEdit()
                path_edit.setText(str(param_value) if param_value is not None else "")
                path_edit.setPlaceholderText("저장 폴더 경로 (비우면 저장 안 함)")
                path_edit.setToolTip(description)

                browse_button = QPushButton("폴더 선택...")
                browse_button.setToolTip(description)
                browse_button.clicked.connect(
                    lambda _checked=False, edit=path_edit:
                    self._on_browse_dirpath(edit)
                )

                hbox.addWidget(path_edit)
                hbox.addWidget(browse_button)

                layout.addRow(label, container)
                self.param_widgets[param_name] = path_edit
                self.param_labels[param_name] = label

                continue
            elif param_type == 'text':
                widget = QPlainTextEdit()
                widget.setPlainText(str(param_value) if param_value is not None else "")
                widget.setMaximumHeight(120)
            elif param_type == 'list':
                widget = QLineEdit()
                widget.setText(str(param_value) if param_value is not None else "[]")
            else:
                widget = QLineEdit()
                widget.setText(str(param_value) if param_value is not None else "")

            widget.setToolTip(description)
            layout.addRow(label, widget)
            self.param_widgets[param_name] = widget
            self.param_labels[param_name] = label

        if job.type == 'align_to_plane_normal':
            self._add_offset_preset_row(layout)

        if 'motion_type' in self.param_widgets:
            self._update_param_labels(self.param_widgets['motion_type'].currentText())

        if job.type == 'scan_tm_landmark':
            self.mw.pushButton_moveToParams.setText("Landmark 인식")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'find_landmark':
            self.mw.pushButton_moveToParams.setText("Landmark 검색")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'scan_tm_landmark_jig':
            self.mw.pushButton_moveToParams.setText("Landmark Jig 인식")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'scan_align_tm_landmark':
            self.mw.pushButton_moveToParams.setText("Landmark 인식 및 정렬")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'align_tm_landmark':
            self.mw.pushButton_moveToParams.setText("Landmark 정렬")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'align_to_plane_normal':
            self.mw.pushButton_moveToParams.setText("평면 수직 정렬")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'measure_plane_distance':
            self.mw.pushButton_moveToParams.setText("평면 거리 측정")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'gripper_open':
            self.mw.pushButton_moveToParams.setText("Gripper Open")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'gripper_close':
            self.mw.pushButton_moveToParams.setText("Gripper Close")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'gripper_home':
            self.mw.pushButton_moveToParams.setText("Gripper Home")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'read_digital_io':
            self.mw.pushButton_moveToParams.setText("IO 읽기")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'write_digital_io':
            self.mw.pushButton_moveToParams.setText("IO 쓰기")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'read_analog_io':
            self.mw.pushButton_moveToParams.setText("AD 읽기")
            self.mw.label_tmLandmarkResult.setText("")
        elif job.type == 'ai_inspection':
            self.mw.pushButton_moveToParams.setText("AI 인식 실행")
            self.mw.label_tmLandmarkResult.setText("")
        else:
            self.mw.pushButton_moveToParams.setText(self._exec_button_label(job))
            self.mw.label_tmLandmarkResult.setText("")

    def _exec_button_label(self, job) -> str:
        if 'motion_type' in self.param_widgets:
            return "이 위치로 이동"
        spec = self.recipe_manager.JOB_TYPES.get(job.type) if self.recipe_manager else None
        name = (spec or {}).get('name')
        return name or "이 위치로 이동"

    def _on_motion_type_changed(self, motion_type):
        self._update_param_labels(motion_type)

    def _update_param_labels(self, motion_type):
        if not self.param_labels:
            return

        if motion_type == 'tcp':
            if 'X' in self.param_labels:
                self.param_labels['X'].setText("X 위치 (mm):")
            if 'Y' in self.param_labels:
                self.param_labels['Y'].setText("Y 위치 (mm):")
            if 'Z' in self.param_labels:
                self.param_labels['Z'].setText("Z 위치 (mm):")
            if 'Rx' in self.param_labels:
                self.param_labels['Rx'].setText("Rx 회전 (deg):")
            if 'Ry' in self.param_labels:
                self.param_labels['Ry'].setText("Ry 회전 (deg):")
            if 'Rz' in self.param_labels:
                self.param_labels['Rz'].setText("Rz 회전 (deg):")
        else:
            if 'X' in self.param_labels:
                self.param_labels['X'].setText("J1 (deg):")
            if 'Y' in self.param_labels:
                self.param_labels['Y'].setText("J2 (deg):")
            if 'Z' in self.param_labels:
                self.param_labels['Z'].setText("J3 (deg):")
            if 'Rx' in self.param_labels:
                self.param_labels['Rx'].setText("J4 (deg):")
            if 'Ry' in self.param_labels:
                self.param_labels['Ry'].setText("J5 (deg):")
            if 'Rz' in self.param_labels:
                self.param_labels['Rz'].setText("J6 (deg):")

    def _clear_params_ui(self):
        self.mw.label_selectedTask.setText("선택된 Task: 없음")

        layout = self.mw.formLayout_params
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.param_widgets = {}
        self.param_labels = {}
        self._offset_preset_combo = None

    def _on_browse_dirpath(self, path_edit):
        current = path_edit.text().strip()
        if current:
            start_dir = current if os.path.isabs(current) else str(paths.PACKAGE_ROOT / current)
        else:
            start_dir = str(paths.DATA_DIR)

        dir_path = QFileDialog.getExistingDirectory(self.mw, "저장 폴더 선택", start_dir)
        if dir_path:
            path_edit.setText(dir_path)

    def _save_params_from_ui(self, job):
        if not self.param_widgets:
            return

        param_defs = self.recipe_manager.JOB_TYPES.get(job.type, {}).get('params', {})
        has_offset_dict = param_defs.get('offset', {}).get('type') == 'dict'

        if has_offset_dict and all(
            k in self.param_widgets for k in ('offset_x', 'offset_y', 'offset_z')
        ):
            job.params['offset'] = {
                'x': self.param_widgets['offset_x'].value(),
                'y': self.param_widgets['offset_y'].value(),
                'z': self.param_widgets['offset_z'].value()
            }

        for param_name, widget in self.param_widgets.items():
            if param_name == '_caption':
                if isinstance(widget, QLineEdit):
                    job.caption = widget.text().strip()
                continue

            if has_offset_dict and param_name in (
                'offset', 'offset_x', 'offset_y', 'offset_z'
            ):
                continue

            if isinstance(widget, QComboBox):
                job.params[param_name] = widget.currentText()
            elif isinstance(widget, QDoubleSpinBox):
                job.params[param_name] = widget.value()
            elif isinstance(widget, QSpinBox):
                job.params[param_name] = widget.value()
            elif isinstance(widget, QCheckBox):
                job.params[param_name] = widget.isChecked()
            elif isinstance(widget, QPlainTextEdit):
                job.params[param_name] = widget.toPlainText()
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                # 대괄호로 감싼 텍스트는 리스트로 역직렬화 시도 — 실패하면 원문 문자열을 그대로 보존
                if text.startswith('[') and text.endswith(']'):
                    try:
                        import ast
                        job.params[param_name] = ast.literal_eval(text)
                    except:
                        job.params[param_name] = text
                else:
                    job.params[param_name] = text

        job.sync_robot_base()


    def _selected_job(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            return None
        return recipe.jobs[current_row]

    def _on_teach_position(self):
        """현재 로봇 위치를 선택 Job 의 파라미터 폼에 티칭한다 (job.type·파라미터 구성별 분기)."""
        if not self.param_widgets:
            self._log("먼저 Task를 선택하세요")
            return

        teaching_service = self.mw.teaching_service

        job = self._selected_job()
        if job is not None and job.type == 'align_to_plane_normal':
            self._teach_plane_align_offset(job)
            return

        if job is not None and job.type == 'move_to_landmark_pose':
            self._teach_landmark_frame_offset(job)
            return

        if 'motion_type' in self.param_widgets:
            motion_type = self.param_widgets['motion_type'].currentText()

            taught_data = teaching_service.teach_current_position(
                self.mw.current_joint_position,
                self.mw.current_tcp_pose,
                motion_type
            )

            if taught_data:
                success = teaching_service.set_position_to_params(
                    self.param_widgets,
                    taught_data['motion_type'],
                    taught_data['positions']
                )
                if not success:
                    self._log(f"{motion_type} 위치 정보가 없습니다")
            else:
                self._log(f"{motion_type} 위치 정보가 없습니다")

        elif 'positions' in self.param_widgets:
            taught_data = teaching_service.teach_current_position(
                self.mw.current_joint_position,
                self.mw.current_tcp_pose,
                'joint'
            )
            if taught_data:
                widget = self.param_widgets['positions']
                pos_str = str(taught_data['positions'])
                widget.setText(pos_str)
            else:
                self._log("Joint 위치 정보가 없습니다")

        elif 'target_position' in self.param_widgets:
            taught_data = teaching_service.teach_current_position(
                self.mw.current_joint_position,
                self.mw.current_tcp_pose,
                'tcp'
            )
            if taught_data:
                widget = self.param_widgets['target_position']
                pos_str = str(taught_data['positions'])
                widget.setText(pos_str)
            else:
                self._log("TCP 위치 정보가 없습니다")

        else:
            self._log("입력 가능한 위치 파라미터가 없습니다")

    def _on_move_to_params(self):
        # command_gate 로 수동 실행 동시 진입을 막는다 — 획득 실패 시 실행하지 않고, 성공 시 finally 에서 반드시 해제
        gate = getattr(self.mw, 'command_gate', None)
        if gate is not None and not gate.acquire("Task 수동 실행"):
            return

        try:
            self._move_to_params()
        finally:
            if gate is not None:
                gate.release()

    def _move_to_params(self):
        """선택 Job 을 type 별 수동 실행 핸들러(_exec_*)로 디스패치한다 — 동기 실행이라 로봇 동작 완료까지 GUI 가 멈춘다."""
        if not self.param_widgets:
            self._log("먼저 Task를 선택하세요")
            return

        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            self._log("선택된 Task가 없습니다")
            return

        current_job = recipe.jobs[current_row]

        if current_job.type == 'scan_tm_landmark':
            self._exec_scan_tm_landmark()
            return

        if current_job.type == 'find_landmark':
            self._exec_find_landmark()
            return

        if current_job.type == 'scan_tm_landmark_jig':
            self._exec_scan_tm_landmark_jig()
            return

        if current_job.type == 'scan_align_tm_landmark':
            self._exec_scan_align_tm_landmark()
            return

        if current_job.type == 'align_tm_landmark':
            self._exec_align_tm_landmark()
            return

        if current_job.type == 'move_linear':
            self._exec_move_linear()
            return

        if current_job.type == 'line_move_to_point':
            self._exec_line_move_to_point()
            return

        if current_job.type == 'pose_keep_move_to_point':
            self._exec_pose_keep_move_to_point()
            return

        if current_job.type == 'align_to_plane_normal':
            self._exec_align_to_plane_normal()
            return

        if current_job.type == 'move_to_landmark_pose':
            self._exec_selected_job('마커 좌표계 이동')
            return

        if current_job.type == 'move_to_plane_pose':
            self._exec_selected_job('평면 좌표계 이동')
            return

        if current_job.type == 'measure_plane_distance':
            self._exec_measure_plane_distance()
            return

        if current_job.type == 'gripper_open':
            self._exec_gripper_command(10, "Gripper Open")
            return

        if current_job.type == 'gripper_close':
            self._exec_gripper_command(9, "Gripper Close")
            return

        if current_job.type == 'gripper_home':
            self._exec_gripper_command(11, "Gripper Home")
            return

        if current_job.type == 'read_digital_io':
            self._exec_read_digital_io()
            return

        if current_job.type == 'write_digital_io':
            self._exec_write_digital_io()
            return

        if current_job.type == 'read_analog_io':
            self._exec_read_analog_io()
            return

        if current_job.type == 'ai_inspection':
            self._exec_ai_inspection()
            return

        if 'motion_type' in self.param_widgets:
            self._exec_motion_move()
            return

        label = self._exec_button_label(current_job)
        if current_job.type not in self.recipe_manager.JOB_TYPES:
            self._log(f"등록되지 않은 Task 타입입니다: {current_job.type}")
            return
        self._exec_selected_job(label)

    def _exec_gripper_command(self, command_value: int, command_name: str):
        self._log(f"{command_name} 실행 (g_robot_command={command_value})")

        if not self.vision_manager:
            self._log("VisionManager가 초기화되지 않았습니다")
            return

        if self.vision_manager.write_variable('g_robot_command', command_value):
            self._log(f"{command_name} 명령 전송 완료")
        else:
            self._log(f"{command_name} 명령 전송 실패")

    def _exec_read_digital_io(self):
        di_name = 'Ctrl_DI0'
        if 'di_name' in self.param_widgets:
            di_name = self.param_widgets['di_name'].currentText()

        io_service = self.mw.io_control_service
        if not io_service:
            self._log("IOControlService가 초기화되지 않았습니다")
            return

        success, value, msg = io_service.read_digital_input(di_name)
        if success:
            self._log(f"[DI READ] {msg}")
            self.mw.label_tmLandmarkResult.setText(msg)
        else:
            self._log(f"[DI READ] 실패: {msg}")
            self.mw.label_tmLandmarkResult.setText(f"읽기 실패: {msg}")

    def _exec_write_digital_io(self):
        do_name = 'Ctrl_DO0'
        state = 'ON'

        if 'do_name' in self.param_widgets:
            do_name = self.param_widgets['do_name'].currentText()
        if 'state' in self.param_widgets:
            state = self.param_widgets['state'].currentText()

        io_service = self.mw.io_control_service
        if not io_service:
            self._log("IOControlService가 초기화되지 않았습니다")
            return

        success, msg = io_service.write_digital_output_by_name(do_name, state)
        if success:
            self._log(f"[DO WRITE] {msg}")
            self.mw.label_tmLandmarkResult.setText(msg)
        else:
            self._log(f"[DO WRITE] 실패: {msg}")
            self.mw.label_tmLandmarkResult.setText(f"쓰기 실패: {msg}")

    def _exec_read_analog_io(self):
        ai_name = 'Ctrl_AI0'
        if 'ai_name' in self.param_widgets:
            ai_name = self.param_widgets['ai_name'].currentText()

        io_service = self.mw.io_control_service
        if not io_service:
            self._log("IOControlService가 초기화되지 않았습니다")
            return

        success, value, msg = io_service.read_analog_input(ai_name)
        if success:
            self._log(f"[AI READ] {msg}")
            self.mw.label_tmLandmarkResult.setText(msg)
        else:
            self._log(f"[AI READ] 실패: {msg}")
            self.mw.label_tmLandmarkResult.setText(f"읽기 실패: {msg}")

    def _exec_find_landmark(self):
        grid_step = 30.0
        grid_size = 3
        scan_timeout_ms = 500
        velocity = 30.0
        on_found = 'store_position'

        if 'grid_step' in self.param_widgets:
            grid_step = self.param_widgets['grid_step'].value()
        if 'grid_size' in self.param_widgets:
            grid_size = self.param_widgets['grid_size'].value()
        if 'scan_timeout' in self.param_widgets:
            scan_timeout_ms = self.param_widgets['scan_timeout'].value()
        if 'velocity' in self.param_widgets:
            velocity = self.param_widgets['velocity'].value()
        if 'on_found' in self.param_widgets:
            on_found = self.param_widgets['on_found'].currentText()

        from ..recipe_manager import Job
        temp_job = Job(
            job_id=0,
            job_type='find_landmark',
            name='Landmark 검색',
            params={
                'grid_step': grid_step,
                'grid_size': grid_size,
                'scan_timeout': scan_timeout_ms,
                'velocity': velocity,
                'on_found': on_found,
                'on_not_found': 'continue'
            }
        )

        self._log(f"Landmark 검색 시작: 격자={grid_size}x{grid_size}, 간격={grid_step}mm")
        self.mw.label_tmLandmarkResult.setText("검색 중...")

        success = self.job_executor._exec_find_landmark(temp_job)

        if success and self.job_executor.detected_landmark_pose:
            result = self.job_executor.detected_landmark_pose
            result_text = f"발견! X={result['x']:.2f}  Y={result['y']:.2f}  Z={result['z']:.2f}\n"
            result_text += f"Rx={result['rx']:.2f}  Ry={result['ry']:.2f}  Rz={result['rz']:.2f}"
            self.mw.label_tmLandmarkResult.setText(result_text)
            self._log("Landmark 검색 완료 - 발견됨")
        else:
            self.mw.label_tmLandmarkResult.setText("Landmark 미발견")
            self._log("Landmark 검색 완료 - 미발견")

    def _exec_scan_tm_landmark(self):
        wait_time_ms = 400
        if 'wait_after_command' in self.param_widgets:
            wait_time_ms = self.param_widgets['wait_after_command'].value()
        wait_time = wait_time_ms / 1000.0

        success, msg = self.vision_manager.execute_tm_landmark_scan(wait_time, pause_ethernet=False)
        self._log(msg)

        if success:
            read_success, result = self.vision_manager.execute_tm_landmark_read()

            if read_success and isinstance(result, dict):
                self.job_executor.detected_landmark_pose = result
                self._log(f"Landmark 저장: X={result['x']:.3f}, Y={result['y']:.3f}, Z={result['z']:.3f}, "
                         f"Rx={result['rx']:.2f}, Ry={result['ry']:.2f}, Rz={result['rz']:.2f}")

            if read_success and isinstance(result, dict):
                result_text = f"X: {result['x']:.2f}  Y: {result['y']:.2f}  Z: {result['z']:.2f}\n"
                result_text += f"Rx: {result['rx']:.2f}  Ry: {result['ry']:.2f}  Rz: {result['rz']:.2f}"
                self.mw.label_tmLandmarkResult.setText(result_text)
            else:
                self.mw.label_tmLandmarkResult.setText(result if isinstance(result, str) else "결과 읽기 실패")

    def _exec_scan_tm_landmark_jig(self):
        jig_number = 1
        if 'jig_number' in self.param_widgets:
            jig_number = self.param_widgets['jig_number'].value()

        wait_time_ms = 400
        if 'wait_after_command' in self.param_widgets:
            wait_time_ms = self.param_widgets['wait_after_command'].value()
        wait_time = wait_time_ms / 1000.0

        success, msg = self.vision_manager.execute_tm_landmark_jig_scan(jig_number, wait_time, pause_ethernet=False)
        self._log(msg)

        if success:
            read_success, result = self.vision_manager.execute_tm_landmark_jig_read(jig_number)

            if read_success and isinstance(result, dict):
                if result.get('detected', False):
                    self.job_executor.detected_landmark_pose = result
                    self._log(f"Landmark Jig{jig_number} 저장: Rx={result['rx']:.2f}, Ry={result['ry']:.2f}, Rz={result['rz']:.2f}")
                    result_text = f"Jig{jig_number}: X={result['x']:.2f}  Y={result['y']:.2f}  Z={result['z']:.2f}\n"
                    result_text += f"Rx: {result['rx']:.2f}  Ry: {result['ry']:.2f}  Rz: {result['rz']:.2f}"
                    self.mw.label_tmLandmarkResult.setText(result_text)
                else:
                    self._log(f"[경고] Jig{jig_number} Landmark 미인식 (detected=False)")
                    self.mw.label_tmLandmarkResult.setText(f"Jig{jig_number}: 미인식 (detected=False)")
            else:
                self.mw.label_tmLandmarkResult.setText(result if isinstance(result, str) else "결과 읽기 실패")

    def _exec_scan_align_tm_landmark(self):
        wait_time_ms = 400
        if 'wait_after_command' in self.param_widgets:
            wait_time_ms = self.param_widgets['wait_after_command'].value()
        wait_time = wait_time_ms / 1000.0

        success, msg = self.vision_manager.execute_scan_align_tm_landmark(wait_time, pause_ethernet=False)
        self._log(msg)

        if success:
            read_success, result = self.vision_manager.execute_tm_landmark_read()

            if read_success and isinstance(result, dict):
                result_text = f"X: {result['x']:.2f}  Y: {result['y']:.2f}  Z: {result['z']:.2f}\n"
                result_text += f"Rx: {result['rx']:.2f}  Ry: {result['ry']:.2f}  Rz: {result['rz']:.2f}"
                self.mw.label_tmLandmarkResult.setText(result_text)
            else:
                self.mw.label_tmLandmarkResult.setText(result if isinstance(result, str) else "결과 읽기 실패")

    def _exec_align_tm_landmark(self):
        z_distance = self.param_widgets['z_distance'].value() if 'z_distance' in self.param_widgets else 100.0
        velocity = self.param_widgets['velocity'].value() if 'velocity' in self.param_widgets else 100.0
        wait_time = self.param_widgets['wait_after_command'].value() if 'wait_after_command' in self.param_widgets else 0.5

        success, msg = self.mw.landmark_align_service.align_to_landmark(
            z_distance=z_distance,
            velocity=velocity,
            wait_time=wait_time
        )
        self._log(msg)

    def _exec_move_linear(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            self._log("선택된 Task가 없습니다")
            return

        job = recipe.jobs[current_row]
        self._save_params_from_ui(job)

        success = self.job_executor._exec_move_linear(job)
        if success:
            self._log("직선 이동 완료")
        else:
            self._log("직선 이동 실패")

    def _exec_line_move_to_point(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            self._log("선택된 Task가 없습니다")
            return

        job = recipe.jobs[current_row]
        self._save_params_from_ui(job)

        success = self.job_executor._exec_line_move_to_point(job)
        if success:
            self._log("직선 포인트 이동 완료")
        else:
            self._log("직선 포인트 이동 실패")

    def _exec_pose_keep_move_to_point(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            self._log("선택된 Task가 없습니다")
            return

        job = recipe.jobs[current_row]
        self._save_params_from_ui(job)

        success = self.job_executor._exec_pose_keep_move_to_point(job)
        if success:
            self._log("자세유지 포인트 이동 완료")
        else:
            self._log("자세유지 포인트 이동 실패")

    def _exec_selected_job(self, label: str):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            self._log("선택된 Task가 없습니다")
            return

        job = recipe.jobs[current_row]
        self._save_params_from_ui(job)

        if self.job_executor._execute_job(job):
            self._log(f"{label} 완료")
        else:
            self._log(f"{label} 실패")

    def _exec_align_to_plane_normal(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            self._log("선택된 Task가 없습니다")
            return

        job = recipe.jobs[current_row]
        self._save_params_from_ui(job)

        success = self.job_executor._exec_align_to_plane_normal(job)
        if success:
            self._log("평면 수직 정렬 완료")
        else:
            self._log("평면 수직 정렬 실패")

    OFFSET_PRESET_KEYS = ('x', 'y', 'rx', 'ry', 'rz')

    def _add_offset_preset_row(self, layout):
        service = getattr(self.mw, 'offset_preset_service', None)
        if service is None:
            return

        container = QWidget()
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)

        combo = QComboBox()
        combo.setEditable(True)
        combo.setToolTip("그리퍼 오차 preset 이름 (직접 입력해 새 이름으로 저장 가능)")
        combo.addItems(service.list_names())
        combo.setCurrentText("")

        apply_button = QPushButton("적용")
        apply_button.setToolTip("선택한 preset 값을 오차 입력칸에 채웁니다")
        apply_button.clicked.connect(self._on_apply_offset_preset)

        save_button = QPushButton("저장")
        save_button.setToolTip("현재 오차 입력칸 값을 이 이름으로 저장합니다")
        save_button.clicked.connect(self._on_save_offset_preset)

        delete_button = QPushButton("삭제")
        delete_button.setToolTip("선택한 preset 을 삭제합니다")
        delete_button.clicked.connect(self._on_delete_offset_preset)

        hbox.addWidget(combo)
        hbox.addWidget(apply_button)
        hbox.addWidget(save_button)
        hbox.addWidget(delete_button)

        label = QLabel("오차 preset:")
        label.setToolTip("그리퍼 오차 묶음 저장/불러오기")
        layout.addRow(label, container)

        self._offset_preset_combo = combo

    def _read_offset_widgets(self):
        if not all(f'offset_{k}' in self.param_widgets for k in self.OFFSET_PRESET_KEYS):
            return None
        return {
            k: self.param_widgets[f'offset_{k}'].value()
            for k in self.OFFSET_PRESET_KEYS
        }

    def _write_offset_widgets(self, offset: dict) -> bool:
        if not all(f'offset_{k}' in self.param_widgets for k in self.OFFSET_PRESET_KEYS):
            return False
        for k in self.OFFSET_PRESET_KEYS:
            self.param_widgets[f'offset_{k}'].setValue(float(offset.get(k, 0.0)))
        return True

    def _offset_preset_name(self) -> str:
        combo = getattr(self, '_offset_preset_combo', None)
        if combo is None:
            return ""
        return combo.currentText().strip()

    def _on_apply_offset_preset(self):
        name = self._offset_preset_name()
        if not name:
            self._log("적용할 오차 preset 이름을 선택하세요")
            return

        offset = self.mw.offset_preset_service.get(name)
        if offset is None:
            self._log(f"오차 preset '{name}' 이(가) 없습니다")
            return

        if not self._write_offset_widgets(offset):
            self._log("오차 입력칸이 없습니다 (평면 수직 정렬 Task 를 선택하세요)")
            return

        self._log(f"오차 preset '{name}' 적용 — '파라미터 적용' 을 눌러야 Task 에 저장됩니다")

    def _on_save_offset_preset(self):
        name = self._offset_preset_name()
        offset = self._read_offset_widgets()
        if offset is None:
            self._log("오차 입력칸이 없습니다 (평면 수직 정렬 Task 를 선택하세요)")
            return

        ok, message = self.mw.offset_preset_service.save(name, offset)
        self._log(message)
        if not ok:
            return

        combo = self._offset_preset_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(self.mw.offset_preset_service.list_names())
        combo.setCurrentText(name)
        combo.blockSignals(False)

    def _on_delete_offset_preset(self):
        name = self._offset_preset_name()
        if not name:
            self._log("삭제할 오차 preset 이름을 선택하세요")
            return

        ok, message = self.mw.offset_preset_service.delete(name)
        self._log(message)
        if not ok:
            return

        combo = self._offset_preset_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(self.mw.offset_preset_service.list_names())
        combo.setCurrentText("")
        combo.blockSignals(False)

    LANDMARK_FRAME_OFFSET_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')

    def _teach_landmark_frame_offset(self, job):
        self._save_params_from_ui(job)

        offset, message = self.job_executor.estimate_landmark_frame_tool_offset(job.params)
        self._log(message)
        if offset is None:
            return

        missing = [k for k in self.LANDMARK_FRAME_OFFSET_KEYS
                   if f'tool_offset_{k}' not in self.param_widgets]
        if missing:
            self._log(f"그리퍼 오차 입력칸을 찾지 못했습니다: {missing}")
            return

        for k in self.LANDMARK_FRAME_OFFSET_KEYS:
            self.param_widgets[f'tool_offset_{k}'].setValue(float(offset[k]))

        self._log("추산된 그리퍼 오차를 입력칸에 채웠습니다 — '파라미터 적용' 을 눌러야 Task 에 저장됩니다")

    def _teach_plane_align_offset(self, job):
        self._save_params_from_ui(job)

        offset, message = self.job_executor.estimate_plane_align_tool_offset(job.params)
        self._log(message)
        if offset is None:
            return

        if not self._write_offset_widgets(offset):
            self._log("오차 입력칸을 찾지 못했습니다")
            return

        self._log("추산된 오차를 입력칸에 채웠습니다 — '파라미터 적용' 을 눌러야 Task 에 저장됩니다")

    def _exec_measure_plane_distance(self):
        current_row = self.mw.listWidget_taskSequence.currentRow()
        recipe = self.recipe_manager.current_recipe
        if not recipe or current_row < 0 or current_row >= len(recipe.jobs):
            self._log("선택된 Task가 없습니다")
            return

        job = recipe.jobs[current_row]
        self._save_params_from_ui(job)

        success = self.job_executor._exec_measure_plane_distance(job)
        if success:
            distance = self.job_executor.measured_plane_distance
            self._log(f"평면 거리 측정 완료: {distance:+.3f}mm")
        else:
            self._log("평면 거리 측정 실패")

    def _exec_motion_move(self):
        teaching_service = self.mw.teaching_service

        result = teaching_service.extract_position_from_params(self.param_widgets)
        if result is None:
            self._log("위치 파라미터를 읽을 수 없습니다")
            return

        motion_type, positions = result
        velocity = self.param_widgets['velocity'].value() if 'velocity' in self.param_widgets else 20.0

        decomposed_tcp = False
        if 'decomposed_tcp' in self.param_widgets:
            decomposed_tcp = self.param_widgets['decomposed_tcp'].isChecked()

        if motion_type == 'joint':
            self._log(f"Joint 이동 시작: J1={positions[0]:.2f}°, J2={positions[1]:.2f}°, J3={positions[2]:.2f}°, "
                     f"J4={positions[3]:.2f}°, J5={positions[4]:.2f}°, J6={positions[5]:.2f}°, 속도={velocity}%")
        else:
            mode = " [대각선 금지: 축 분해]" if decomposed_tcp else ""
            self._log(f"TCP 이동 시작{mode}: X={positions[0]:.2f}mm, Y={positions[1]:.2f}mm, Z={positions[2]:.2f}mm, "
                     f"Rx={positions[3]:.2f}°, Ry={positions[4]:.2f}°, Rz={positions[5]:.2f}°, 속도={velocity}%")

        success, msg = teaching_service.move_to_position(
            motion_type,
            positions,
            velocity,
            self.mw._move_to_position,
            decomposed_tcp=decomposed_tcp
        )

        if success:
            self._log("이동 완료")
        else:
            self._log(f"이동 실패: {msg}")

    def _on_ps2_jog_toggled(self, enabled: bool):
        self.joystick_service.set_enabled(enabled)

    def _on_ps2_jog_requested(self, axis: str, direction: int):
        self.mw.jog_service.jog_continuous(axis, direction)

    def _on_ps2_mode_changed(self, mode: str):
        self.mw.label_ps2Mode.setText(f"Mode: {mode}")

    def _on_ps2_connection_changed(self, connected: bool):
        status = "Connected" if connected else "Disconnected"
        self.mw.label_ps2Status.setText(f"Status: {status}")

    def _on_ps2_status_changed(self, message: str):
        print(f"[PS2 Jog] {message}")

    def _exec_ai_inspection(self):
        detection_task = self.param_widgets.get('detection_task')
        runtime_widget = self.param_widgets.get('runtime')
        conf_widget = self.param_widgets.get('confidence_threshold')

        if not detection_task or not runtime_widget:
            self._log("AI 파라미터가 없습니다")
            return

        task_name = detection_task.currentText()
        runtime = runtime_widget.currentText()
        confidence = conf_widget.value() if conf_widget else 0.5

        angle_widget = self.param_widgets.get('angle_threshold')
        angle_threshold = angle_widget.value() if angle_widget else 15.0

        service = self.mw.ai_detection_service
        if not service:
            self._log("AIDetectionService가 없습니다")
            return

        models = service.get_available_models(task=task_name, runtime=runtime)
        if not models:
            self._log(f"모델을 찾을 수 없음: task={task_name}, runtime={runtime}")
            return

        model_path = models[0][1]
        for name, path in models:
            if name.startswith('best'):
                model_path = path
                break

        self._log(f"모델 로드: {os.path.basename(model_path)}")
        service.load_model(model_path)
        service.set_confidence_threshold(confidence)
        service.set_angle_threshold(angle_threshold)

        if not hasattr(self.mw, 'image_capture_service') or not self.mw.image_capture_service:
            self._log("ImageCaptureService가 없습니다")
            return

        if self.mw.image_capture_service.is_capturing:
            self._log("이미지 캡처 진행 중...")
            return

        # 일회성 동적 연결 — 결과/에러 콜백이 수신 시 disconnect 한다 (플래그로 본 요청 여부 구분)
        self._pending_ai_inspection = True
        service.detection_completed.connect(self._on_ai_inspection_result)
        service.detection_error.connect(self._on_ai_inspection_error)

        # AI 탭의 단건 캡처 경로도 함께 활성화 — 캡처 완료 시 그 탭이 추론을 트리거한다
        if hasattr(self.mw, 'ai_detection_tab') and self.mw.ai_detection_tab:
            self.mw.ai_detection_tab._pending_single_detection = True

        self._log(f"AI 인식 실행: task={task_name}, conf={confidence}")
        self.mw.image_capture_service.capture_image(timeout_sec=3.0)

    def _on_ai_inspection_result(self, detections, annotated_image, fps):
        if not self._pending_ai_inspection:
            return
        self._pending_ai_inspection = False

        service = self.mw.ai_detection_service
        if service:
            try:
                service.detection_completed.disconnect(self._on_ai_inspection_result)
                service.detection_error.disconnect(self._on_ai_inspection_error)
            except TypeError:
                pass

        if detections:
            result_texts = []
            for d in detections:
                if d.angle is not None and d.state:
                    result_texts.append(
                        f"{d.class_name}({d.confidence:.0%}) {d.angle}° {d.state}"
                    )
                else:
                    result_texts.append(f"{d.class_name}({d.confidence:.0%})")
            result_str = " | ".join(result_texts)
            self.mw.label_tmLandmarkResult.setText(result_str)
            self._log(f"AI 인식 완료: {len(detections)}개 검출 - {result_str}")
        else:
            self.mw.label_tmLandmarkResult.setText("검출 없음")
            self._log("AI 인식 완료: 검출 없음")

    def _on_ai_inspection_error(self, error_msg):
        if not self._pending_ai_inspection:
            return
        self._pending_ai_inspection = False

        service = self.mw.ai_detection_service
        if service:
            try:
                service.detection_completed.disconnect(self._on_ai_inspection_result)
                service.detection_error.disconnect(self._on_ai_inspection_error)
            except TypeError:
                pass

        self.mw.label_tmLandmarkResult.setText(f"에러: {error_msg}")
        self._log(f"AI 인식 에러: {error_msg}")
