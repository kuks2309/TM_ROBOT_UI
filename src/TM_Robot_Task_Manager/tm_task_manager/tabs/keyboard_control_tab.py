"""키보드 컨트롤 탭 — 방향키로 XY축, < > 로 Z축(상하) jog + 숫자키 스텝 제어.

기존 조이스틱/jog 로직을 재사용한다(jog_service.jog / set_params). 이 파일은 입력 표면만 추가한다.
탭은 PS2 조이스틱 탭 바로 뒤에 코드로 삽입한다(main_window.ui 미편집).

'키보드 모드' 버튼을 켜면 grabKeyboard 로 키 입력을 장악한다(화면 클릭으로 포커스 줄 필요 없음).
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt5.QtCore import Qt

from .base_tab import BaseTab

_STEP_MIN_MM = 1.0        # `-` 로 줄여도 이 아래로는 안 내려간다(0/음수 방지)
_STEP_RESET_MM = 10.0     # `0` 초기화 값(JOG 기본 스텝)
_STEP_BIG_MM = 10.0       # `=`/`-` 증감 폭


class _KeyCaptureWidget(QWidget):
    """방향키/<>/숫자키 입력을 받아 jog_service 를 호출하는 위젯.

    한 번 누를 때마다 한 스텝(오토리핏 무시). 명령 누적은 jog_service 의 command gate 가 막는다.
    on_action(str): 상태 텍스트 콜백. on_hidden(): 탭이 숨겨질 때(키보드 해제·모드 OFF용).
    """

    _AXIS_KEYMAP = {
        Qt.Key_Up: ('x', 1),
        Qt.Key_Down: ('x', -1),
        Qt.Key_Right: ('y', 1),
        Qt.Key_Left: ('y', -1),
        Qt.Key_Period: ('z', 1),
        Qt.Key_Greater: ('z', 1),
        Qt.Key_Comma: ('z', -1),
        Qt.Key_Less: ('z', -1),
    }

    def __init__(self, jog_service):
        super().__init__()
        self._jog_service = jog_service
        self.on_action = None
        self.on_hidden = None
        self.setFocusPolicy(Qt.StrongFocus)

    def _current_step(self) -> float:
        step, _velocity = self._jog_service.get_params()
        return step

    def _set_step(self, mm: float) -> float:
        mm = max(_STEP_MIN_MM, float(mm))
        self._jog_service.set_params(step_mm=mm)
        return mm

    def _notify(self, text: str):
        if self.on_action:
            self.on_action(text)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return  # 한 번=한 스텝
        key = event.key()

        # 축 이동
        axis = self._AXIS_KEYMAP.get(key)
        if axis is not None:
            a, direction = axis
            self._notify(f"이동 {a.upper()}{'+' if direction > 0 else '-'}")
            self._jog_service.jog(a, direction)
            event.accept()
            return

        # 스텝 설정 — 1~9: N mm, 0: 초기화, =: +10mm, -: -10mm
        if Qt.Key_1 <= key <= Qt.Key_9:
            mm = self._set_step(float(key - Qt.Key_0))
            self._notify(f"스텝 = {mm:.0f} mm")
            event.accept()
            return
        if key == Qt.Key_0:
            mm = self._set_step(_STEP_RESET_MM)
            self._notify(f"스텝 초기화 = {mm:.0f} mm")
            event.accept()
            return
        if key == Qt.Key_Equal:
            mm = self._set_step(self._current_step() + _STEP_BIG_MM)
            self._notify(f"스텝 = {mm:.0f} mm")
            event.accept()
            return
        if key == Qt.Key_Minus:
            mm = self._set_step(self._current_step() - _STEP_BIG_MM)
            self._notify(f"스텝 = {mm:.0f} mm")
            event.accept()
            return

        super().keyPressEvent(event)

    def hideEvent(self, event):
        # 탭을 벗어나면 키보드 장악을 반드시 푼다(다른 화면 입력 방해 방지).
        self.releaseKeyboard()
        if self.on_hidden:
            self.on_hidden()
        super().hideEvent(event)


class KeyboardControlTab(BaseTab):
    """방향키/<>/숫자키로 로봇 TCP jog + 스텝 제어 (PS2 조이스틱 탭 옆)."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.capture = None
        self.mode_button = None
        self.status_label = None
        self.step_label = None
        self.force_open_button = None

    def connect_signals(self):
        pass

    def init_ui(self):
        capture = _KeyCaptureWidget(self.mw.jog_service)
        layout = QVBoxLayout(capture)

        title = QLabel("키보드 컨트롤 — 방향키: XY / < > : Z / 숫자키: 스텝")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.mode_button = QPushButton("키보드 모드: OFF (클릭해서 켜기)")
        self.mode_button.setCheckable(True)
        self.mode_button.setMinimumHeight(40)
        self.mode_button.toggled.connect(self._on_mode_toggled)

        keymap = QLabel(
            "  ↑ : X+      ↓ : X−        → : Y+      ← : Y−\n"
            "  > : Z+ (위)   < : Z− (아래)\n"
            "  1~9 : 스텝 N mm      0 : 초기화(10mm)      = : +10mm      − : −10mm\n\n"
            "※ '키보드 모드' 버튼을 켜면 키 입력이 활성화됩니다(화면 클릭 불필요).\n"
            "   탭을 벗어나면 자동으로 꺼집니다."
        )
        keymap.setStyleSheet("font-size: 13px;")

        step0, _velocity = self.mw.jog_service.get_params()
        self.step_label = QLabel(f"스텝: {step0:.0f} mm")
        self.step_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.status_label = QLabel("모드: OFF")

        # 그리퍼 강제 열기 — 인터록 우회 탈출구. 상세는 GripperOverrideService docstring.
        self.force_open_button = QPushButton("그리퍼 강제 열기 (인터록 우회)")
        self.force_open_button.setMinimumHeight(40)
        self.force_open_button.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.force_open_button.clicked.connect(self._on_force_open)
        override = self.mw.gripper_override_service
        if override.available():
            # 어느 그리퍼로 나갈지 버튼이 미리 밝힌다 — 누르고 나서 알면 늦다.
            self.force_open_button.setToolTip(
                "시도 순서: " + " → ".join(override.backends()))
        else:
            # 규칙: 못 하면 «알리고 실행하지 않는다». 눌리지 않게 막고 사유를 붙인다.
            self.force_open_button.setEnabled(False)
            self.force_open_button.setText("그리퍼 강제 열기 (사용 불가)")
            self.force_open_button.setStyleSheet("color: gray;")
            self.force_open_button.setToolTip(override.unavailable_reason())

        layout.addWidget(title)
        layout.addWidget(self.mode_button)
        layout.addWidget(keymap)
        layout.addWidget(self.step_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.force_open_button)
        layout.addStretch(1)

        capture.on_action = self._on_capture_action
        capture.on_hidden = self._on_capture_hidden
        self.capture = capture

        # 스텝이 외부(설정 탭 등)에서 바뀌면 라벨 반영
        self.mw.jog_service.params_changed.connect(self._on_params_changed)

        # PS2 조이스틱 탭 바로 뒤에 삽입
        tw = self.mw.tabWidget_main
        idx = tw.indexOf(self.mw.tab_ps2JoystickTest)
        insert_at = idx + 1 if idx >= 0 else tw.count()
        tw.insertTab(insert_at, capture, "Manual Control")

    def _on_mode_toggled(self, checked: bool):
        if checked:
            self.capture.grabKeyboard()
            self.mode_button.setText("키보드 모드: ON (다시 클릭해서 끄기)")
            self.status_label.setText("모드 ON — 방향키/<>/숫자키 입력 가능")
        else:
            self.capture.releaseKeyboard()
            self.mode_button.setText("키보드 모드: OFF (클릭해서 켜기)")
            self.status_label.setText("모드: OFF")

    def _on_capture_action(self, text: str):
        self.status_label.setText(text)

    def _on_capture_hidden(self):
        # 탭을 벗어날 때 모드 버튼도 OFF 로 되돌린다(토글 콜백이 releaseKeyboard 처리).
        if self.mode_button is not None and self.mode_button.isChecked():
            self.mode_button.setChecked(False)

    def _on_force_open(self):
        """인터록을 우회해 그리퍼를 연다. 낙하 위험을 사람이 지는 선택이라 확인을 받는다."""
        answer = QMessageBox.warning(
            self.capture,
            "그리퍼 강제 열기",
            "매거진 인터록을 무시하고 그리퍼를 엽니다.\n\n"
            "박스를 물고 있으면 떨어집니다. 아래를 비우고 진행하세요.\n\n"
            "계속할까요?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.force_open_button.setEnabled(False)
        try:
            ok, reason = self.mw.gripper_override_service.force_release()
        finally:
            self.force_open_button.setEnabled(True)

        if ok:
            self.status_label.setText("그리퍼 강제 열기: 성공")
        else:
            self.status_label.setText(f"그리퍼 강제 열기 실패: {reason}")
            QMessageBox.critical(self.capture, "그리퍼 강제 열기 실패", reason)

    def _on_params_changed(self, step_mm: float, velocity_percent: int):
        if self.step_label is not None:
            self.step_label.setText(f"스텝: {step_mm:.0f} mm")
