from PyQt5.QtWidgets import QMessageBox

from .base_tab import BaseTab
from tm_task_manager.tools.landmark_parser import parse_tm_landmark
from tm_task_manager.tools.jig_plane_calculator import JigPlaneCalculator, Mark
from tm_task_manager.services.vision_origin_check_service import POSE_KEYS


class SettingsTab(BaseTab):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

    def connect_signals(self):
        print("[DEBUG] SettingsTab.connect_signals() 시작")

        self.mw.actionConnect.triggered.connect(self._on_connect)
        self.mw.actionDisconnect.triggered.connect(self._on_disconnect)

        self.mw.btn_readBase.clicked.connect(self._on_read_base)
        self.mw.pushButton_applyCoordinateSystem.clicked.connect(self._on_apply_coordinate_system)

        self.mw.radioButton_robotBase.toggled.connect(
            lambda checked: self._on_tcp_pose_changed('robot_base', checked))
        self.mw.radioButton_jigLandmark.toggled.connect(
            lambda checked: self._on_tcp_pose_changed('jig_landmark', checked))
        self.mw.radioButton_jigPlate.toggled.connect(
            lambda checked: self._on_tcp_pose_changed('jig_plate', checked))

        self.mw.pushButton_applyTcpPose.clicked.connect(self._on_apply_tcp_pose)

        self.mw.pushButton_readJigLandmark.clicked.connect(self._on_read_jig_landmark)
        self.mw.pushButton_calculateJigPlate.clicked.connect(self._on_calculate_jig_plate)

        self.mw.pushButton_readMark1.clicked.connect(lambda: self._on_read_mark_jig_plate(1))
        self.mw.pushButton_readMark2.clicked.connect(lambda: self._on_read_mark_jig_plate(2))
        self.mw.pushButton_readMark3.clicked.connect(lambda: self._on_read_mark_jig_plate(3))
        self.mw.pushButton_readMark4.clicked.connect(lambda: self._on_read_mark_jig_plate(4))

        print(f"[DEBUG] pushButton_saveJigLandmark 존재: {hasattr(self.mw, 'pushButton_saveJigLandmark')}")
        print(f"[DEBUG] pushButton_saveJigPlate 존재: {hasattr(self.mw, 'pushButton_saveJigPlate')}")
        self.mw.pushButton_saveJigLandmark.clicked.connect(self._on_save_jig_landmark)
        self.mw.pushButton_saveJigPlate.clicked.connect(self._on_save_jig_plate)
        self.mw.pushButton_openJigValidator.clicked.connect(self._on_open_jig_validator)
        print("[DEBUG] 저장 버튼 시그널 연결 완료")

        self.mw.pushButton_jogXMinus.clicked.connect(lambda: self._on_jog('x', -1))
        self.mw.pushButton_jogXPlus.clicked.connect(lambda: self._on_jog('x', 1))
        self.mw.pushButton_jogYMinus.clicked.connect(lambda: self._on_jog('y', -1))
        self.mw.pushButton_jogYPlus.clicked.connect(lambda: self._on_jog('y', 1))
        self.mw.pushButton_jogZMinus.clicked.connect(lambda: self._on_jog('z', -1))
        self.mw.pushButton_jogZPlus.clicked.connect(lambda: self._on_jog('z', 1))
        self.mw.pushButton_jogRxMinus.clicked.connect(lambda: self._on_jog('rx', -1))
        self.mw.pushButton_jogRxPlus.clicked.connect(lambda: self._on_jog('rx', 1))
        self.mw.pushButton_jogRyMinus.clicked.connect(lambda: self._on_jog('ry', -1))
        self.mw.pushButton_jogRyPlus.clicked.connect(lambda: self._on_jog('ry', 1))
        self.mw.pushButton_jogRzMinus.clicked.connect(lambda: self._on_jog('rz', -1))
        self.mw.pushButton_jogRzPlus.clicked.connect(lambda: self._on_jog('rz', 1))

        self.mw.spinBox_jogStep.valueChanged.connect(
            lambda v: self.mw.jog_service.set_params(step_mm=v))
        self.mw.spinBox_jogVelocity.valueChanged.connect(
            lambda v: self.mw.jog_service.set_params(velocity_percent=v))
        self.mw.jog_service.params_changed.connect(self._on_jog_params_changed)

        step_mm, velocity_percent = self.mw.jog_service.get_params()
        self.mw.spinBox_jogStep.setValue(step_mm)
        self.mw.spinBox_jogVelocity.setValue(velocity_percent)

        self.mw.checkBox_enableTF.stateChanged.connect(self._on_tf_enable_changed)

        self.mw.pushButton_refLearn.clicked.connect(self._on_reference_learn)
        self.mw.pushButton_refCheckNow.clicked.connect(self._on_vision_origin_check_now)
        self.mw.pushButton_refSaveTolerance.clicked.connect(self._on_reference_save_tolerance)

        if self.mw.connection_manager:
            self.mw.connection_manager.on_state_changed = self._on_connection_state_changed
            self.mw.connection_manager.on_robot_status_changed = self._on_robot_status_changed

    def init_ui(self):
        robot_ip = self.config_manager.get_robot_ip()
        if robot_ip:
            self.mw.lineEdit_robotIp.setText(robot_ip)

        self._init_tcp_pose_radiobuttons()

        self.mw.checkBox_enableTF.setChecked(False)
        self.mw.label_tfStatus.setText("상태: 비활성")

        self._update_reference_display()


    def _on_connect(self):
        if not self.mw.connection_manager:
            self._log("연결 관리자가 초기화되지 않았습니다")
            return

        robot_ip = self.mw.lineEdit_robotIp.text().strip()
        if not robot_ip:
            self._log("로봇 IP를 입력하세요")
            return

        self._log(f"로봇 연결 시도: {robot_ip}...")
        self.mw.actionConnect.setEnabled(False)
        self.mw.actionDisconnect.setEnabled(False)

        success, message = self.mw.connection_manager.connect(robot_ip, timeout_sec=5.0)

        if success:
            self._log(f"연결 성공: {message}")
            if hasattr(self.mw, 'label_statusBar_connection'):
                self.mw.label_statusBar_connection.setText(f"연결됨: {robot_ip}")
            self.mw.actionConnect.setEnabled(False)
            self.mw.actionDisconnect.setEnabled(True)
        else:
            self._log(f"연결 실패: {message}")
            if hasattr(self.mw, 'label_statusBar_connection'):
                self.mw.label_statusBar_connection.setText("연결 실패")
            self.mw.actionConnect.setEnabled(True)

    def _on_disconnect(self):
        if not self.mw.connection_manager:
            self._log("연결 관리자가 초기화되지 않았습니다")
            return

        success, message = self.mw.connection_manager.disconnect()

        if success:
            self._log(message)
            if hasattr(self.mw, 'label_statusBar_connection'):
                self.mw.label_statusBar_connection.setText("연결: -")
            self.mw.actionConnect.setEnabled(True)
            self.mw.actionDisconnect.setEnabled(False)
        else:
            self._log(f"연결 해제 실패: {message}")

    def _on_connection_state_changed(self, state):
        from ..robot_connection import ConnectionState

        state_text = {
            ConnectionState.DISCONNECTED: "연결 해제",
            ConnectionState.CONNECTING: "연결 중...",
            ConnectionState.CONNECTED: "연결됨",
            ConnectionState.ERROR: "연결 오류"
        }.get(state, "알 수 없음")

        self._log(f"연결 상태: {state_text}")

        if state == ConnectionState.CONNECTED:
            self.mw.actionConnect.setEnabled(False)
            self.mw.actionDisconnect.setEnabled(True)
        elif state == ConnectionState.DISCONNECTED:
            self.mw.actionConnect.setEnabled(True)
            self.mw.actionDisconnect.setEnabled(False)
        elif state == ConnectionState.ERROR:
            self.mw.actionConnect.setEnabled(True)
            self.mw.actionDisconnect.setEnabled(False)

    def _on_robot_status_changed(self, is_ready: bool):
        if is_ready:
            self._log("로봇 준비 완료")
        else:
            self._log("로봇 준비 안됨")


    def _on_read_base(self):
        self._update_base_display()
        if self.gv_manager:
            base_name = self.gv_manager.read_base_name()
            if base_name:
                self._log(f"현재 좌표계: {base_name}")
                index = self.mw.comboBox_coordinateSystem.findText(base_name)
                if index >= 0:
                    self.mw.comboBox_coordinateSystem.setCurrentIndex(index)
            else:
                self._log("좌표계 읽기 실패")

    def _on_apply_coordinate_system(self):
        if not self.mw.landmark_align_service:
            self._log("LandmarkAlignService가 초기화되지 않았습니다")
            return

        selected_base = self.mw.comboBox_coordinateSystem.currentText()
        success, msg = self.mw.landmark_align_service.change_coordinate_system(selected_base)

        if success:
            self._log(msg)
            self._update_base_display()
        else:
            self._log(msg)

    def _update_base_display(self):
        if not self.gv_manager:
            return

        base_name = self.gv_manager.read_base_name()
        if base_name:
            self.ros_node.current_base_name = base_name

        is_vision_base = base_name and base_name != "RobotBase"

        if base_name:
            self.mw.label_tcpTitle.setText(f"TCP (mm, deg) - [{base_name}]:")
        else:
            self.mw.label_tcpTitle.setText("TCP (mm, deg):")

        if is_vision_base:
            self.mw.label_tcpTitle.setStyleSheet("color: red; font-weight: bold;")
            orange_style = "background-color: #FFE4B5;"
            self.mw.lineEdit_tcpX.setStyleSheet(orange_style)
            self.mw.lineEdit_tcpY.setStyleSheet(orange_style)
            self.mw.lineEdit_tcpZ.setStyleSheet(orange_style)
            self.mw.lineEdit_tcpRx.setStyleSheet(orange_style)
            self.mw.lineEdit_tcpRy.setStyleSheet(orange_style)
            self.mw.lineEdit_tcpRz.setStyleSheet(orange_style)
        else:
            self.mw.label_tcpTitle.setStyleSheet("font-weight: bold;")
            default_style = ""
            self.mw.lineEdit_tcpX.setStyleSheet(default_style)
            self.mw.lineEdit_tcpY.setStyleSheet(default_style)
            self.mw.lineEdit_tcpZ.setStyleSheet(default_style)
            self.mw.lineEdit_tcpRx.setStyleSheet(default_style)
            self.mw.lineEdit_tcpRy.setStyleSheet(default_style)
            self.mw.lineEdit_tcpRz.setStyleSheet(default_style)

        if hasattr(self.mw, 'label_statusBar_coordinate'):
            self.mw.label_statusBar_coordinate.setText(f"좌표계: {base_name if base_name else '-'}")

    def _on_jog(self, axis, direction):
        self.mw.jog_service.jog(axis, direction)

    def _on_jog_params_changed(self, step_mm: float, velocity_percent: int):
        self.mw.spinBox_jogStep.blockSignals(True)
        self.mw.spinBox_jogVelocity.blockSignals(True)
        self.mw.spinBox_jogStep.setValue(step_mm)
        self.mw.spinBox_jogVelocity.setValue(velocity_percent)
        self.mw.spinBox_jogStep.blockSignals(False)
        self.mw.spinBox_jogVelocity.blockSignals(False)


    def _init_tcp_pose_radiobuttons(self):
        csm = self.mw.coordinate_system_manager
        current = csm.get_current_system()

        if current == csm.ROBOT_BASE:
            self.mw.radioButton_robotBase.setChecked(True)
        elif current == csm.JIG_LANDMARK:
            self.mw.radioButton_jigLandmark.setChecked(True)
        elif current == csm.JIG_PLATE:
            self.mw.radioButton_jigPlate.setChecked(True)

        self._update_tcp_pose_labels()

    def _update_tcp_pose_labels(self):
        pass

    def _on_tcp_pose_changed(self, name: str, checked: bool):
        if not checked:
            return

        csm = self.mw.coordinate_system_manager
        if csm.set_current_system(name):
            self._log(f"TCP Pose 선택: {name}")
            orientation = csm.get_current_tcp_orientation()
            self._log(f"  → 목표 자세: ({orientation[0]:.1f}, {orientation[1]:.1f}, {orientation[2]:.1f})")

            if not self.mw.current_tcp_pose:
                self._log("현재 로봇 위치를 알 수 없습니다")
                return

            target_pos = self.mw.current_tcp_pose.copy()
            target_pos[3] = orientation[0]
            target_pos[4] = orientation[1]
            target_pos[5] = orientation[2]

            from tm_task_manager.services.coordinate_transformer import CoordinateTransformer
            from tm_msgs.srv import SetPositions
            target_pos_service = CoordinateTransformer.convert_tcp_to_service_format(target_pos)

            velocity = float(self.mw.spinBox_jogVelocity.value())
            success, msg = self.mw._move_to_position(
                SetPositions.Request.PTP_T,
                target_pos_service,
                velocity,
                0.2
            )

            if success:
                self._log(f"TCP 자세 변경 완료: {name}")
            else:
                self._log(f"TCP 자세 변경 실패: {msg}")

    def _on_apply_tcp_pose(self):
        if self.mw.radioButton_robotBase.isChecked():
            name = 'robot_base'
        elif self.mw.radioButton_jigLandmark.isChecked():
            name = 'jig_landmark'
        elif self.mw.radioButton_jigPlate.isChecked():
            name = 'jig_plate'
        else:
            self._log("선택된 TCP Pose가 없습니다")
            return

        csm = self.mw.coordinate_system_manager
        orientation = csm.get_current_tcp_orientation()
        self._log(f"TCP Pose 적용: {name} → ({orientation[0]:.1f}, {orientation[1]:.1f}, {orientation[2]:.1f})")

        if not self.mw.current_tcp_pose:
            self._log("현재 로봇 위치를 알 수 없습니다")
            return

        target_pos = self.mw.current_tcp_pose.copy()
        target_pos[3] = orientation[0]
        target_pos[4] = orientation[1]
        target_pos[5] = orientation[2]

        from tm_task_manager.services.coordinate_transformer import CoordinateTransformer
        from tm_msgs.srv import SetPositions
        target_pos_service = CoordinateTransformer.convert_tcp_to_service_format(target_pos)

        velocity = float(self.mw.spinBox_jogVelocity.value())
        success, msg = self.mw._move_to_position(
            SetPositions.Request.PTP_T,
            target_pos_service,
            velocity,
            0.2
        )

        if success:
            self._log(f"TCP 자세 변경 완료: {name}")
        else:
            self._log(f"TCP 자세 변경 실패: {msg}")


    def _on_read_jig_landmark(self):
        self._read_tm_landmark_to_ui(
            'jig_landmark',
            self.mw.doubleSpinBox_jigLandmarkX,
            self.mw.doubleSpinBox_jigLandmarkY,
            self.mw.doubleSpinBox_jigLandmarkZ,
            self.mw.doubleSpinBox_jigLandmarkRx,
            self.mw.doubleSpinBox_jigLandmarkRy,
            self.mw.doubleSpinBox_jigLandmarkRz
        )

    def _on_calculate_jig_plate(self):
        marks = []
        for i in range(1, 5):
            spin_x = getattr(self.mw, f'doubleSpinBox_mark{i}X', None)
            spin_y = getattr(self.mw, f'doubleSpinBox_mark{i}Y', None)
            spin_z = getattr(self.mw, f'doubleSpinBox_mark{i}Z', None)
            spin_rx = getattr(self.mw, f'doubleSpinBox_mark{i}Rx', None)
            spin_ry = getattr(self.mw, f'doubleSpinBox_mark{i}Ry', None)
            spin_rz = getattr(self.mw, f'doubleSpinBox_mark{i}Rz', None)

            if spin_x and spin_y and spin_z:
                marks.append(Mark(
                    x=spin_x.value(),
                    y=spin_y.value(),
                    z=spin_z.value(),
                    rx=spin_rx.value() if spin_rx else 0.0,
                    ry=spin_ry.value() if spin_ry else 0.0,
                    rz=spin_rz.value() if spin_rz else 0.0
                ))

        if len(marks) != 4:
            self._log(f"4개 Mark가 필요합니다 (현재: {len(marks)}개)")
            return

        all_zero = all(m.x == 0 and m.y == 0 and m.z == 0 for m in marks)
        if all_zero:
            self._log("Mark 좌표가 모두 0입니다. 먼저 각 Mark를 읽어주세요.")
            return

        calc = JigPlaneCalculator()
        if not calc.load_from_marks(marks):
            self._log("Mark 데이터 로드 실패")
            return

        result = calc.calculate_plane_pose()
        if result is None:
            self._log("평면 좌표 계산 실패")
            return

        self.mw.doubleSpinBox_jigPlateX.setValue(result.x)
        self.mw.doubleSpinBox_jigPlateY.setValue(result.y)
        self.mw.doubleSpinBox_jigPlateZ.setValue(result.z)
        self.mw.doubleSpinBox_jigPlateRx.setValue(result.rx)
        self.mw.doubleSpinBox_jigPlateRy.setValue(result.ry)
        self.mw.doubleSpinBox_jigPlateRz.setValue(result.rz)

        self._log(f"jig_plate 계산 완료: X={result.x:.2f}, Y={result.y:.2f}, Z={result.z:.2f}, "
                  f"Rx={result.rx:.2f}, Ry={result.ry:.2f}, Rz={result.rz:.2f}")

    def _on_open_jig_validator(self):
        import subprocess
        import sys
        from pathlib import Path

        validator_path = Path(__file__).parent.parent / "tools" / "jig_plate_validator.py"

        if not validator_path.exists():
            self._log(f"검증 도구를 찾을 수 없습니다: {validator_path}")
            return

        config_path = Path(__file__).parent.parent.parent / "config" / "positions.yaml"

        try:
            cmd = [sys.executable, str(validator_path)]
            if config_path.exists():
                cmd.extend(["--config", str(config_path)])

            subprocess.Popen(cmd)
            self._log("Jig Plate 3D 검증 도구 실행")
        except Exception as e:
            self._log(f"검증 도구 실행 실패: {e}")

    def _read_tm_landmark_to_ui(self, name, spin_x, spin_y, spin_z, spin_rx, spin_ry, spin_rz):
        if not self.gv_manager:
            self._log("Global Variable Manager가 없습니다")
            return

        success, value = self.gv_manager.read_variable('g_TM_Landmark')
        if not success:
            self._log(f"g_TM_Landmark 읽기 실패: {value}")
            return

        success, result = parse_tm_landmark(value)
        if not success:
            self._log(f"g_TM_Landmark {result}")
            return

        spin_x.setValue(result.x)
        spin_y.setValue(result.y)
        spin_z.setValue(result.z)
        spin_rx.setValue(result.rx)
        spin_ry.setValue(result.ry)
        spin_rz.setValue(result.rz)

        self._log(f"{name} 좌표 읽기 완료: X={result.x:.2f}, Y={result.y:.2f}, Z={result.z:.2f}, "
                  f"Rx={result.rx:.2f}, Ry={result.ry:.2f}, Rz={result.rz:.2f}")

    def _on_read_mark_jig_plate(self, mark_num: int):
        if not self.gv_manager:
            self._log("Global Variable Manager가 없습니다")
            return

        var_name = f'g_Jig_Landmark{mark_num}'
        success, value = self.gv_manager.read_variable(var_name)
        if not success:
            self._log(f"{var_name} 읽기 실패: {value}")
            return

        success, result = parse_tm_landmark(value)
        if not success:
            self._log(f"{var_name} {result}")
            return

        spin_x = getattr(self.mw, f'doubleSpinBox_mark{mark_num}X', None)
        spin_y = getattr(self.mw, f'doubleSpinBox_mark{mark_num}Y', None)
        spin_z = getattr(self.mw, f'doubleSpinBox_mark{mark_num}Z', None)
        spin_rx = getattr(self.mw, f'doubleSpinBox_mark{mark_num}Rx', None)
        spin_ry = getattr(self.mw, f'doubleSpinBox_mark{mark_num}Ry', None)
        spin_rz = getattr(self.mw, f'doubleSpinBox_mark{mark_num}Rz', None)

        if spin_x and spin_y and spin_z:
            spin_x.setValue(result.x)
            spin_y.setValue(result.y)
            spin_z.setValue(result.z)
            if spin_rx:
                spin_rx.setValue(result.rx)
            if spin_ry:
                spin_ry.setValue(result.ry)
            if spin_rz:
                spin_rz.setValue(result.rz)
            self._log(f"mark_jig_plate_{mark_num} 좌표 읽기 완료: X={result.x:.2f}, Y={result.y:.2f}, Z={result.z:.2f}")
        else:
            self._log(f"mark_jig_plate_{mark_num} UI 위젯을 찾을 수 없습니다")


    def _on_save_jig_landmark(self):
        print("[DEBUG] _on_save_jig_landmark() 호출됨")
        csm = self.mw.coordinate_system_manager
        if not csm:
            self._log("CoordinateSystemManager가 초기화되지 않았습니다")
            print("[DEBUG] csm이 None입니다")
            return

        landmark = {
            'x': self.mw.doubleSpinBox_jigLandmarkX.value(),
            'y': self.mw.doubleSpinBox_jigLandmarkY.value(),
            'z': self.mw.doubleSpinBox_jigLandmarkZ.value(),
            'rx': self.mw.doubleSpinBox_jigLandmarkRx.value(),
            'ry': self.mw.doubleSpinBox_jigLandmarkRy.value(),
            'rz': self.mw.doubleSpinBox_jigLandmarkRz.value()
        }

        tcp_pose = landmark.copy()

        if csm.set_single_landmark_scan('jig_landmark', landmark, tcp_pose):
            if csm.save_to_config(backup_type='jig_landmark'):
                msg = f"jig_landmark 저장 완료: X={landmark['x']:.2f}, Y={landmark['y']:.2f}, Z={landmark['z']:.2f}"
                self._log(msg)
                print(f"[저장] {msg}")
            else:
                self._log("jig_landmark 저장 실패")
                print("[저장] jig_landmark 저장 실패")
        else:
            self._log("jig_landmark 설정 실패")

    def _on_save_jig_plate(self):
        print("[DEBUG] _on_save_jig_plate() 호출됨")
        csm = self.mw.coordinate_system_manager
        if not csm:
            self._log("CoordinateSystemManager가 초기화되지 않았습니다")
            print("[DEBUG] csm이 None입니다")
            return

        jig_plate_pose = {
            'x': self.mw.doubleSpinBox_jigPlateX.value(),
            'y': self.mw.doubleSpinBox_jigPlateY.value(),
            'z': self.mw.doubleSpinBox_jigPlateZ.value(),
            'rx': self.mw.doubleSpinBox_jigPlateRx.value(),
            'ry': self.mw.doubleSpinBox_jigPlateRy.value(),
            'rz': self.mw.doubleSpinBox_jigPlateRz.value()
        }

        csm.set_tool_pose(
            'jig_plate',
            jig_plate_pose['x'], jig_plate_pose['y'], jig_plate_pose['z'],
            jig_plate_pose['rx'], jig_plate_pose['ry'], jig_plate_pose['rz']
        )

        csm.clear_multi_landmark_scan('jig_plate')

        for i in range(1, 5):
            spin_x = getattr(self.mw, f'doubleSpinBox_mark{i}X', None)
            spin_y = getattr(self.mw, f'doubleSpinBox_mark{i}Y', None)
            spin_z = getattr(self.mw, f'doubleSpinBox_mark{i}Z', None)
            spin_rx = getattr(self.mw, f'doubleSpinBox_mark{i}Rx', None)
            spin_ry = getattr(self.mw, f'doubleSpinBox_mark{i}Ry', None)
            spin_rz = getattr(self.mw, f'doubleSpinBox_mark{i}Rz', None)

            if spin_x and spin_y and spin_z:
                landmark = {
                    'x': spin_x.value(),
                    'y': spin_y.value(),
                    'z': spin_z.value(),
                    'rx': spin_rx.value() if spin_rx else 0.0,
                    'ry': spin_ry.value() if spin_ry else 0.0,
                    'rz': spin_rz.value() if spin_rz else 0.0
                }
                tcp_pose = landmark.copy()
                csm.add_multi_landmark_scan('jig_plate', landmark, tcp_pose)

        if csm.save_to_config(backup_type='jig_plate'):
            count = csm.get_landmark_count('jig_plate')
            msg = (f"jig_plate 저장 완료: {count}개 mark, "
                   f"X={jig_plate_pose['x']:.2f}, Y={jig_plate_pose['y']:.2f}, Z={jig_plate_pose['z']:.2f}")
            self._log(msg)
            print(f"[저장] {msg}")
        else:
            self._log("jig_plate 저장 실패")
            print("[저장] jig_plate 저장 실패")


    def _on_tf_enable_changed(self, state):
        csm = self.mw.coordinate_system_manager
        if not csm:
            self._log("CoordinateSystemManager가 초기화되지 않았습니다")
            return

        if state:
            interval = self.mw.doubleSpinBox_tfInterval.value()
            if csm.start_tf_publishing(interval):
                self.mw.label_tfStatus.setText(f"상태: 활성 (주기: {interval}초)")
                self._log(f"TF 발행 활성화 (주기: {interval}초)")
            else:
                self.mw.checkBox_enableTF.setChecked(False)
                self.mw.label_tfStatus.setText("상태: 비활성")
                self._log("TF 발행 시작 실패")
        else:
            csm.stop_tf_publishing()
            self.mw.label_tfStatus.setText("상태: 비활성")
            self._log("TF 발행 비활성화")


    def _reference_spinboxes(self):
        return [getattr(self.mw, f'doubleSpinBox_refLandmark{key.capitalize()}')
                for key in POSE_KEYS]

    def _update_reference_display(self):
        service = self.mw.vision_origin_check_service
        if not service:
            return

        tolerance = service.get_tolerance()
        self.mw.doubleSpinBox_refTolXYZ.setValue(tolerance['xyz'])
        self.mw.doubleSpinBox_refTolRPY.setValue(tolerance['rpy'])

        reference = service.load_reference()
        if reference is None:
            for spin in self._reference_spinboxes():
                spin.setValue(0.0)
            self.mw.lineEdit_referenceTcpPose.setText("")
            self.mw.label_refLearnedInfo.setText("학습 이력: 없음 — [기준점 학습]을 먼저 수행하세요")
            return

        landmark = reference['landmark']
        for key, spin in zip(POSE_KEYS, self._reference_spinboxes()):
            spin.setValue(float(landmark[key]))

        tcp_pose = reference['tcp_pose']
        self.mw.lineEdit_referenceTcpPose.setText(
            "  ".join(f"{key.capitalize()}={float(tcp_pose[key]):.2f}" for key in POSE_KEYS)
        )

        measure = reference.get('measure', {})
        info = f"학습 시각: {reference.get('learned_at', '-')}"
        if measure:
            info += f" / 조건: {measure.get('repeat_count', '-')}회, {measure.get('outlier_method', '-')}"
            self.mw.spinBox_refRepeat.setValue(int(measure.get('repeat_count', 5)))
            index = self.mw.comboBox_refOutlier.findText(str(measure.get('outlier_method', 'iqr')))
            if index >= 0:
                self.mw.comboBox_refOutlier.setCurrentIndex(index)

        std = reference.get('learned_std')
        if isinstance(std, dict):
            info += ("\n학습 산포 σ: "
                     f"X={float(std.get('x', 0.0)):.4f} Y={float(std.get('y', 0.0)):.4f} "
                     f"Z={float(std.get('z', 0.0)):.4f} mm — 허용범위는 이보다 크게 잡으세요")
        self.mw.label_refLearnedInfo.setText(info)

    def _on_reference_save_tolerance(self):
        service = self.mw.vision_origin_check_service
        if not service:
            self._log("기준점 확인 서비스가 초기화되지 않았습니다")
            return

        service.set_tolerance(
            self.mw.doubleSpinBox_refTolXYZ.value(),
            self.mw.doubleSpinBox_refTolRPY.value()
        )
        self._update_reference_display()

    def _on_reference_learn(self):
        service = self.mw.vision_origin_check_service
        if not service:
            self._log("기준점 확인 서비스가 초기화되지 않았습니다")
            return

        if not self.vision_manager:
            self._log("VisionManager가 없습니다")
            return

        if not self.ros_node:
            self._log("ROS2 노드가 없습니다 — 로봇 연결을 확인하세요")
            return

        current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
        if current_base and current_base != 'RobotBase':
            self._log(f"[경고] 기준점 학습은 RobotBase 좌표계에서 해야 합니다 (현재: {current_base})")
            return

        tcp_pose = getattr(self.ros_node, 'current_tcp_pose', None)
        if not tcp_pose or len(tcp_pose) < 6:
            self._log("현재 TCP 위치를 알 수 없습니다 — 로봇 연결을 확인하세요")
            return

        if service.has_reference():
            reply = QMessageBox.question(
                self.mw,
                "기준점 재학습",
                "이미 학습된 기준점이 있습니다.\n현재 위치의 측정값으로 덮어쓰시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        repeat_count = self.mw.spinBox_refRepeat.value()
        outlier_method = self.mw.comboBox_refOutlier.currentText()

        landmark, analysis = self.job_executor.scan_landmark_averaged(
            repeat_count, outlier_method, 0.1
        )
        if landmark is None:
            self._log("기준점 학습 실패: 유효한 측정값이 없습니다")
            self.mw.label_refCheckResult.setText("결과: 학습 실패 (측정값 없음)")
            return

        saved = service.save_reference(
            tcp_pose={key: float(value) for key, value in zip(POSE_KEYS, tcp_pose[:6])},
            landmark=landmark,
            measure={'repeat_count': repeat_count, 'outlier_method': outlier_method},
            std=analysis['std']
        )
        if saved:
            self._update_reference_display()
            self.mw.label_refCheckResult.setText("결과: 학습 완료")

    def _on_vision_origin_check_now(self):
        service = self.mw.vision_origin_check_service
        if not service:
            self._log("기준점 확인 서비스가 초기화되지 않았습니다")
            return

        if not service.has_reference():
            self._log("기준점이 학습되지 않았습니다 — [기준점 학습]을 먼저 수행하세요")
            self.mw.label_refCheckResult.setText("결과: 미학습")
            return

        passed = self.job_executor.vision_origin_check(
            repeat_count=self.mw.spinBox_refRepeat.value(),
            outlier_method=self.mw.comboBox_refOutlier.currentText()
        )

        result = self.job_executor.last_origin_check_result
        if result is None:
            self.mw.label_refCheckResult.setText("결과: 확인 실패 (측정 또는 이동 실패)")
            self.mw.label_refCheckResult.setStyleSheet("color: red;")
            return

        verdict = "PASS" if passed else f"FAIL (초과 축: {', '.join(result.failed_axes)})"
        self.mw.label_refCheckResult.setText(
            f"결과: {verdict}\n{service.format_deltas(result.deltas)}"
        )
        self.mw.label_refCheckResult.setStyleSheet(
            "color: green;" if passed else "color: red;"
        )
