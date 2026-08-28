import os
import threading
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from .base_tab import BaseTab
from ..macros import MacroContext, run_macro, validate_sequence
from ..macros.pallet_teach import (
    list_measurement_files, package_root, resolve_measurement_dir,
)

TAB_TITLE = '팔레트 티칭'

TAB_INSERT_INDEX = 1

FIXED_SEQUENCE = ['pallet_scan_4corners', 'pallet_center_approach',
                  'pallet_capture_teach', 'pallet_emit_recipes']
FLOATING_SEQUENCE = ['pallet_capture_marker'] + FIXED_SEQUENCE


class PalletTeachTab(BaseTab):

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

        self.ui_widget: Optional[QWidget] = None
        self.blackboard: Dict[str, Any] = {}

        self._busy = False
        self._result = None
        self._done = False
        self._poll_timer: Optional[QTimer] = None
        self._widgets: Dict[str, Any] = {}


    def init_ui(self):
        ok, problems = validate_sequence(FLOATING_SEQUENCE)
        if not ok:
            self._log(f"[팔레트 티칭] 매크로 순서 검증 실패: {'; '.join(problems)}")

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setAlignment(Qt.AlignTop)

        layout.addWidget(self._build_step1())
        layout.addWidget(self._build_step2())
        layout.addWidget(self._build_step3())
        layout.addWidget(self._build_step3_alt())
        layout.addWidget(self._build_step4())
        layout.addWidget(self._build_step5())
        layout.addWidget(self._build_log())

        scroll.setWidget(body)
        outer.addWidget(scroll)

        tab_widget = getattr(self.mw, 'tabWidget_main', None)
        if tab_widget is None:
            print('[PalletTeachTab] ERROR: tabWidget_main 이 없습니다 — 탭을 추가하지 못했습니다')
            return

        tab_widget.insertTab(TAB_INSERT_INDEX, page, TAB_TITLE)
        self.ui_widget = page
        self._refresh_enabled()

        index = tab_widget.indexOf(page)
        self._log(f'[팔레트 티칭] 탭 등록됨 — {index + 1}번째 / 총 {tab_widget.count()}개')
        print(f'[PalletTeachTab] 탭 등록 완료 (index={index}, total={tab_widget.count()})')

    def _build_step1(self) -> QGroupBox:
        box = QGroupBox('1. 팔레트 종류와 마커 간격')
        form = QFormLayout(box)

        fixed = QRadioButton('고정식 — 자리가 고정된 팔레트')
        floating = QRadioButton('비고정식 — 옮겨 다니는 팔레트 (위치 마커 사용)')
        fixed.setChecked(True)
        group = QButtonGroup(box)
        group.addButton(fixed)
        group.addButton(floating)
        fixed.toggled.connect(self._refresh_enabled)

        row = QHBoxLayout()
        row.addWidget(fixed)
        row.addWidget(floating)
        holder = QWidget()
        holder.setLayout(row)
        form.addRow('종류', holder)

        for key, label, default in (('pitch_x', '마커 가로 간격 (mm)', 140.0),
                                    ('pitch_y', '마커 세로 간격 (mm)', 200.0)):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 5000.0)
            spin.setDecimals(2)
            spin.setValue(default)
            self._widgets[key] = spin
            form.addRow(label, spin)

        for key, label in (('trim_x', '마지막 지점 X 보정 (mm)'),
                           ('trim_y', '마지막 지점 Y 보정 (mm)')):
            spin = QDoubleSpinBox()
            spin.setRange(-500.0, 500.0)
            spin.setDecimals(2)
            spin.setValue(0.0)
            self._widgets[key] = spin
            form.addRow(label, spin)

        note = QLabel('마커 간격은 팔레트 고유값입니다 — 1사분면에서 나머지 3점까지의 거리입니다.')
        note.setWordWrap(True)
        note.setStyleSheet('color: #808080;')
        form.addRow(note)

        self._widgets['mount_fixed'] = fixed
        self._widgets['mount_floating'] = floating
        return box

    def _build_step2(self) -> QGroupBox:
        box = QGroupBox('2. 위치 마커 촬영 (비고정식만)')
        layout = QVBoxLayout(box)
        note = QLabel('조그로 위치 마커가 화면에 들어오게 맞춘 뒤 누르세요. '
                      '실행 시점에 이 마커를 다시 찍어 팔레트 위치를 알아냅니다.')
        note.setWordWrap(True)
        layout.addWidget(note)

        button = QPushButton('위치 마커 촬영·저장')
        button.clicked.connect(self._on_capture_marker)
        layout.addWidget(button)

        status = QLabel('아직 촬영하지 않았습니다')
        status.setStyleSheet('color: #808080;')
        layout.addWidget(status)

        self._widgets['marker_button'] = button
        self._widgets['marker_status'] = status
        self._widgets['step2'] = box
        return box

    def _build_step3(self) -> QGroupBox:
        box = QGroupBox('3. 4점 측정')
        layout = QVBoxLayout(box)
        note = QLabel('조그로 헤드를 <b>1사분면 마커</b> 위에 맞춘 뒤 승인하세요. '
                      '나머지 3점은 마커 간격만큼 이동하며 자동으로 측정합니다.')
        note.setWordWrap(True)
        layout.addWidget(note)

        button = QPushButton('4점 측정 승인 — 로봇이 움직입니다')
        button.clicked.connect(self._on_scan_corners)
        layout.addWidget(button)

        status = QLabel('아직 측정하지 않았습니다')
        status.setStyleSheet('color: #808080;')
        status.setWordWrap(True)
        layout.addWidget(status)

        self._widgets['scan_button'] = button
        self._widgets['scan_status'] = status
        return box

    def _build_step3_alt(self) -> QGroupBox:
        box = QGroupBox('3-대안. 이미 측정한 값으로 대체 (로봇 무동작)')
        layout = QVBoxLayout(box)

        note = QLabel('같은 팔레트를 여러 번 측정해 뒀다면 그 파일들을 골라 평균내 쓸 수 '
                      '있습니다. 여러 개를 고를수록 튀는 측정의 영향이 줄어듭니다.')
        note.setWordWrap(True)
        layout.addWidget(note)

        picker = QHBoxLayout()
        pick_files = QPushButton('파일 선택… (여러 개 가능)')
        pick_files.clicked.connect(self._on_pick_files)
        picker.addWidget(pick_files, 2)
        pick_folder = QPushButton('폴더 전체')
        pick_folder.setToolTip('폴더를 골라 그 안의 측정 파일을 최신순으로 채웁니다')
        pick_folder.clicked.connect(self._on_pick_folder)
        picker.addWidget(pick_folder, 1)
        clear = QPushButton('목록 비우기')
        clear.clicked.connect(self._on_clear_files)
        picker.addWidget(clear, 1)
        layout.addLayout(picker)

        files = QListWidget()
        files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        files.setMaximumHeight(160)
        files.setToolTip('여기 있는 파일을 전부 씁니다. 빼려면 골라서 Delete 를 누르세요')
        layout.addWidget(files)
        self._widgets['src_files'] = files

        remove = QPushButton('고른 항목 목록에서 빼기')
        remove.clicked.connect(self._on_remove_selected_files)
        layout.addWidget(remove)

        hint = QLabel('<b>목록에 있는 파일을 전부 씁니다.</b> 파일 창에서 드래그하거나 '
                      'Shift·Ctrl 로 여러 개를 고를 수 있습니다. 목록이 비어 있으면 '
                      '아래 폴더에서 최신 N개를 자동으로 씁니다.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #808080;')
        layout.addWidget(hint)

        form = QFormLayout()
        source = QLineEdit('data/plate_pose_calc')
        source.setPlaceholderText('data/plate_pose_calc/pallet0')
        source.setToolTip('파일 창이 열릴 기본 폴더 · 목록이 비었을 때 자동 선택할 폴더')
        form.addRow('기본 폴더', source)

        count = QSpinBox()
        count.setRange(0, 100)
        count.setValue(5)
        count.setToolTip('목록이 비어 있을 때만 쓰입니다 (0 이면 폴더 전체)')
        form.addRow('자동일 때 최신 몇 개', count)

        method = QComboBox()
        method.addItems(['iqr', '3sigma', 'none'])
        form.addRow('Outlier 제거', method)
        layout.addLayout(form)

        self._widgets['src_path'] = source
        self._widgets['src_count'] = count
        self._widgets['src_method'] = method
        self._widgets['src_pick_files'] = pick_files
        self._widgets['src_pick_folder'] = pick_folder

        apply_button = QPushButton('선택한 측정값으로 평면 만들기')
        apply_button.clicked.connect(self._on_load_measurements)
        layout.addWidget(apply_button)

        status = QLabel('아직 불러오지 않았습니다')
        status.setStyleSheet('color: #808080;')
        status.setWordWrap(True)
        layout.addWidget(status)

        self._widgets['src_remove'] = remove
        self._widgets['src_clear'] = clear
        self._widgets['src_apply'] = apply_button
        self._widgets['src_status'] = status
        return box

    def _build_step4(self) -> QGroupBox:
        box = QGroupBox('4. 중심 접근 후 상세 티칭')
        layout = QVBoxLayout(box)

        form = QFormLayout()
        standoff = QDoubleSpinBox()
        standoff.setRange(1.0, 1000.0)
        standoff.setDecimals(1)
        standoff.setValue(150.0)
        form.addRow('평면에서 띄울 높이 (mm)', standoff)
        self._widgets['standoff'] = standoff

        align = QComboBox()
        align.addItem('팔레트에 정렬 (기울기 + 긴 변 회전)', 'plane')
        align.addItem('기울기만 맞추고 현재 공구 회전 유지', 'keep')
        align.setToolTip('공구 면은 두 경우 모두 평면과 평행해집니다 — 다른 것은 '
                         '법선축 둘레의 회전뿐입니다')
        form.addRow('정렬', align)
        self._widgets['align_mode'] = align
        layout.addLayout(form)

        approach = QPushButton('평면 중심 위로 이동 — 로봇이 움직입니다')
        approach.clicked.connect(self._on_center_approach)
        layout.addWidget(approach)

        note = QLabel('도착하면 박스를 파지하고, 조그로 <b>박스가 팔레트 가드에 닿지 않고 '
                      '면에 안착하는 자세</b>를 잡은 뒤 아래 버튼으로 저장하세요.')
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()
        pick = QPushButton('현재 자세를 픽으로 저장')
        pick.clicked.connect(lambda: self._on_capture_teach('pick'))
        place = QPushButton('현재 자세를 플레이스로 저장')
        place.clicked.connect(lambda: self._on_capture_teach('place'))
        row.addWidget(pick)
        row.addWidget(place)
        layout.addLayout(row)

        status = QLabel('픽 · 플레이스 모두 저장해야 레시피를 만들 수 있습니다')
        status.setStyleSheet('color: #808080;')
        status.setWordWrap(True)
        layout.addWidget(status)

        self._widgets['approach_button'] = approach
        self._widgets['pick_button'] = pick
        self._widgets['place_button'] = place
        self._widgets['teach_status'] = status
        return box

    def _build_step5(self) -> QGroupBox:
        box = QGroupBox('5. 이름 붙여 저장')
        layout = QVBoxLayout(box)

        form = QFormLayout()
        name = QLineEdit()
        name.setPlaceholderText('예: pallet6 (영숫자·밑줄·하이픈)')
        form.addRow('팔레트 이름', name)
        operator = QLineEdit()
        operator.setPlaceholderText('작업자 이름')
        form.addRow('작업자', operator)
        layout.addLayout(form)
        self._widgets['name'] = name
        self._widgets['operator'] = operator

        gripper_row = QHBoxLayout()
        gripper_row.addWidget(QLabel('그리퍼'))
        gripper_group = QButtonGroup(box)
        for key, text in (('', '자동 감지'), ('smc', 'SMC (MK4)'), ('schunk', 'SCHUNK (MK2)')):
            radio = QRadioButton(text)
            radio.setProperty('gripper_id', key)
            gripper_group.addButton(radio)
            gripper_row.addWidget(radio)
            if key == '':
                radio.setChecked(True)
        probe_button = QPushButton('지금 감지')
        probe_button.clicked.connect(self._on_probe_gripper)
        gripper_row.addWidget(probe_button)
        gripper_row.addStretch(1)
        layout.addLayout(gripper_row)
        self._widgets['gripper_group'] = gripper_group

        gripper_state = QLabel('감지 안 함 — [지금 감지] 를 누르거나 자동 감지로 둡니다')
        gripper_state.setWordWrap(True)
        layout.addWidget(gripper_state)
        self._widgets['gripper_state'] = gripper_state

        descent_row = QHBoxLayout()
        descent_row.addWidget(QLabel('최종 하강/상승'))
        descent_group = QButtonGroup(box)
        for key, text in (('plane_normal', '법선 직선 (평면 기준)'),
                          ('tcp_linear', '공구축 직선 (TCP 리니어)')):
            radio = QRadioButton(text)
            radio.setProperty('descent_id', key)
            descent_group.addButton(radio)
            descent_row.addWidget(radio)
            if key == 'plane_normal':
                radio.setChecked(True)
        descent_row.addStretch(1)
        layout.addLayout(descent_row)
        self._widgets['descent_group'] = descent_group

        button = QPushButton('티칭 저장 — 레시피 3개 생성')
        button.clicked.connect(self._on_emit_recipes)
        layout.addWidget(button)

        status = QLabel('')
        status.setWordWrap(True)
        layout.addWidget(status)

        self._widgets['emit_button'] = button
        self._widgets['emit_status'] = status
        return box


    def _selected_gripper(self) -> str:
        group = self._widgets.get('gripper_group')
        button = group.checkedButton() if group is not None else None
        return str(button.property('gripper_id') or '') if button is not None else ''

    def _selected_descent(self) -> str:
        group = self._widgets.get('descent_group')
        button = group.checkedButton() if group is not None else None
        if button is None:
            return 'plane_normal'
        return str(button.property('descent_id') or 'plane_normal')

    def _on_probe_gripper(self):
        from ..hardware.gripper import LIVE, survey
        node = getattr(self.mw, 'ros_node', None)
        rows = survey(node)
        self._widgets['gripper_state'].setText(
            ' · '.join('%s: %s' % (b.label, s) for b, s in rows))
        for backend, state in rows:
            if state == LIVE:
                group = self._widgets.get('gripper_group')
                for candidate in (group.buttons() if group is not None else []):
                    if str(candidate.property('gripper_id') or '') == backend.id:
                        candidate.setChecked(True)
                self._append_log('[그리퍼] 감지됨 — %s' % backend.label)
                return
        self._append_log('[그리퍼] LIVE 인 그리퍼를 찾지 못했습니다')

    def _build_log(self) -> QGroupBox:
        box = QGroupBox('진행 기록')
        layout = QVBoxLayout(box)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setMaximumBlockCount(500)
        layout.addWidget(view)
        self._widgets['log'] = view
        return box


    def _is_floating(self) -> bool:
        return bool(self._widgets['mount_floating'].isChecked())

    def _refresh_enabled(self):
        if not self._widgets:
            return
        floating = self._is_floating()
        has_marker = 'position_marker_pose' in self.blackboard
        has_plate = 'plate_pose' in self.blackboard
        teach = self.blackboard.get('teach_poses') or {}
        ready = has_plate and 'pick' in teach and 'place' in teach
        if floating:
            ready = ready and has_marker

        idle = not self._busy
        self._widgets['step2'].setEnabled(floating)
        self._widgets['marker_button'].setEnabled(idle and floating)
        self._widgets['scan_button'].setEnabled(idle and (has_marker or not floating))
        for key in ('src_pick_files', 'src_pick_folder', 'src_clear',
                    'src_remove', 'src_apply'):
            self._widgets[key].setEnabled(idle)
        self._widgets['approach_button'].setEnabled(idle and has_plate)
        self._widgets['pick_button'].setEnabled(idle and has_plate)
        self._widgets['place_button'].setEnabled(idle and has_plate)
        self._widgets['emit_button'].setEnabled(idle and ready)

        slots = ', '.join(sorted(teach)) if teach else '없음'
        self._widgets['teach_status'].setText(f'저장된 티칭: {slots}')

    def _append_log(self, message: str):
        view = self._widgets.get('log')
        if view is not None:
            view.appendPlainText(message)
        self._log(f'[팔레트 티칭] {message}')


    def _run(self, macro_name: str, params: Dict[str, Any],
             on_done: Callable[[Any], None]):
        if self._busy:
            return
        executor = self.job_executor
        if executor is None:
            QMessageBox.warning(self.mw, '팔레트 티칭', 'JobExecutor 가 없습니다')
            return

        self._busy = True
        self._done = False
        self._result = None
        self._refresh_enabled()
        self._append_log(f'{macro_name} 실행…')

        context = MacroContext(executor, self.blackboard)
        context.clear_stop_request()

        def worker():
            try:
                self._result = run_macro(macro_name, context, params)
            except Exception as exc:
                self._result = exc
            finally:
                self._done = True

        def poll():
            if not self._done:
                return
            self._poll_timer.stop()
            self._busy = False
            result = self._result
            if isinstance(result, Exception):
                self._append_log(f'예외: {result}')
                QMessageBox.critical(self.mw, '팔레트 티칭', f'{macro_name} 실행 중 예외:\n{result}')
            else:
                self._append_log(result.message or macro_name)
                if not result.ok:
                    QMessageBox.warning(self.mw, '팔레트 티칭', result.message)
                on_done(result)
            self._refresh_enabled()

        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(poll)
        self._poll_timer.start(150)
        threading.Thread(target=worker, daemon=True).start()

    def _confirm_motion(self, title: str, body: str) -> bool:
        answer = QMessageBox.question(
            self.mw, title, body + '\n\n로봇이 실제로 움직입니다. 진행할까요?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes


    def _on_capture_marker(self):
        def done(result):
            if result.ok:
                marker = self.blackboard.get('position_marker_pose', {})
                self._widgets['marker_status'].setText(
                    f"촬영됨 — X{marker.get('x', 0):.2f} Y{marker.get('y', 0):.2f} "
                    f"Z{marker.get('z', 0):.2f} · Rz {marker.get('rz', 0):.2f}°")
        self._run('pallet_capture_marker', {}, done)


    def _start_dir(self) -> str:
        resolved = resolve_measurement_dir(self._widgets['src_path'].text().strip())
        return resolved if os.path.isdir(resolved) else str(package_root())

    def _listed_paths(self) -> List[str]:
        files: QListWidget = self._widgets['src_files']
        return [files.item(row).data(Qt.UserRole) for row in range(files.count())]

    def _set_listed_paths(self, paths: List[str]):
        files: QListWidget = self._widgets['src_files']
        files.clear()
        for path in paths:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            files.addItem(item)
        self._widgets['src_status'].setText(
            f'{len(paths)}개 선택됨 — 이대로 평면을 만듭니다' if paths
            else '선택된 파일 없음 — 비워 두면 기본 폴더에서 최신 N개를 씁니다')

    def _on_pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self.mw, '측정 파일 선택 (여러 개 가능)', self._start_dir(),
            '측정 YAML (*.yaml *.yml);;모든 파일 (*)')
        if not paths:
            return
        merged = self._listed_paths()
        merged += [p for p in paths if p not in merged]
        self._set_listed_paths(merged)

    def _on_pick_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self.mw, '측정 폴더 선택', self._start_dir())
        if not directory:
            return
        self._widgets['src_path'].setText(directory)
        paths = list_measurement_files(directory, '', 0)
        if not paths:
            self._widgets['src_status'].setText(
                f'{directory} 에 측정 YAML 이 없습니다')
            return
        self._set_listed_paths(paths)

    def _on_clear_files(self):
        self._set_listed_paths([])

    def _on_remove_selected_files(self):
        files: QListWidget = self._widgets['src_files']
        drop = {item.data(Qt.UserRole) for item in files.selectedItems()}
        if not drop:
            self._widgets['src_status'].setText('뺄 항목을 먼저 고르세요')
            return
        self._set_listed_paths([p for p in self._listed_paths() if p not in drop])

    def _on_load_measurements(self):
        chosen = self._listed_paths()

        def done(result):
            if result.ok:
                plate = self.blackboard.get('plate_pose', {})
                sources = self.blackboard.get('measurement_sources', [])
                self._widgets['src_status'].setText(
                    f"측정 {len(sources)}개 평균 — 중심 X{plate.get('x', 0):.2f} "
                    f"Y{plate.get('y', 0):.2f} Z{plate.get('z', 0):.2f}")
                self._widgets['scan_status'].setText(
                    '저장된 측정값으로 대체됨 — 4점 측정을 건너뛰었습니다')

        self._run('pallet_load_measurements', {
            'source_path': self._widgets['src_path'].text().strip(),
            'max_files': self._widgets['src_count'].value(),
            'outlier_method': self._widgets['src_method'].currentText(),
            'file_paths': chosen or None,
        }, done)

    def _on_scan_corners(self):
        pitch_x = self._widgets['pitch_x'].value()
        pitch_y = self._widgets['pitch_y'].value()
        if pitch_x <= 0 or pitch_y <= 0:
            QMessageBox.warning(self.mw, '팔레트 티칭',
                                '마커 가로·세로 간격을 입력하세요 — 0 이면 측정을 시작할 수 없습니다')
            return
        if not self._confirm_motion(
                '4점 측정',
                f'현재 위치를 1사분면으로 보고 {pitch_x:.0f} × {pitch_y:.0f}mm 간격으로 '
                f'4점을 측정합니다.\n지점당 10회 측정하므로 수 분이 걸립니다.'):
            return

        def done(result):
            if result.ok:
                plate = self.blackboard.get('plate_pose', {})
                self._widgets['scan_status'].setText(
                    f"측정 완료 — 중심 X{plate.get('x', 0):.2f} Y{plate.get('y', 0):.2f} "
                    f"Z{plate.get('z', 0):.2f} · 자세 {plate.get('rx', 0):.2f}, "
                    f"{plate.get('ry', 0):.2f}, {plate.get('rz', 0):.2f}°")

        self._run('pallet_scan_4corners', {
            'pitch_x': pitch_x,
            'pitch_y': pitch_y,
            'trim_x': self._widgets['trim_x'].value(),
            'trim_y': self._widgets['trim_y'].value(),
        }, done)

    def _on_center_approach(self):
        standoff = self._widgets['standoff'].value()
        mode = self._widgets['align_mode'].currentData()
        plate = self.blackboard.get('plate_pose') or {}
        detail = (f"팔레트 회전 {plate.get('rz', 0.0):.2f}° 에 맞춰 공구를 돌립니다."
                  if mode == 'plane' else '현재 공구 회전을 유지합니다.')
        if not self._confirm_motion(
                '중심 접근',
                f'측정한 평면의 중심 위 {standoff:.0f}mm 로 이동합니다.\n'
                f'공구 면이 평면과 평행해집니다 (기울기 추종). {detail}'):
            return
        self._run('pallet_center_approach',
                  {'standoff_mm': standoff, 'rz_mode': mode}, lambda result: None)

    def _on_capture_teach(self, slot: str):
        self._run('pallet_capture_teach', {'slot': slot}, lambda result: None)

    def _on_emit_recipes(self):
        name = self._widgets['name'].text().strip()
        if not name:
            QMessageBox.warning(self.mw, '팔레트 티칭', '팔레트 이름을 입력하세요')
            return

        def done(result):
            if result.ok:
                paths: List[str] = self.blackboard.get('recipe_paths', [])
                self._widgets['emit_status'].setText(
                    '생성됨:\n' + '\n'.join(paths))
                QMessageBox.information(
                    self.mw, '팔레트 티칭',
                    f'레시피 {len(paths)}개를 만들었습니다.\n\n' + '\n'.join(paths))

        self._run('pallet_emit_recipes', {
            'pallet_name': name,
            'mount': 'floating' if self._is_floating() else 'fixed',
            'pitch_x': self._widgets['pitch_x'].value(),
            'pitch_y': self._widgets['pitch_y'].value(),
            'trim_x': self._widgets['trim_x'].value(),
            'trim_y': self._widgets['trim_y'].value(),
            'operator': self._widgets['operator'].text().strip(),
            'gripper': self._selected_gripper(),
            'descent': self._selected_descent(),
            'overwrite': False,
        }, done)
