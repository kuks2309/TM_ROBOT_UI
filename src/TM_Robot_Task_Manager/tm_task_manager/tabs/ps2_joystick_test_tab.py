from PyQt5.QtWidgets import QVBoxLayout
from PyQt5 import uic

from .base_tab import BaseTab
from .. import paths


class PS2JoystickTestTab(BaseTab):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.joystick_ui = None
        self._button_states = [False] * 12
        self._axis_values = [0.0] * 8

    def connect_signals(self):
        pass

    def init_ui(self):
        ui_path = paths.ui('ps2_joystick_test_tab.ui')
        self.joystick_ui = uic.loadUi(ui_path)

        layout = QVBoxLayout(self.mw.tab_ps2JoystickTest)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.joystick_ui)

        self._connect_joystick_signals()

        self._connect_worker_signals()

        self._init_display()

    def _connect_joystick_signals(self):
        js = self.mw.joystick_service
        js.mode_changed.connect(self._on_mode_changed)
        js.connection_changed.connect(self._on_connection_changed)
        js.status_changed.connect(self._on_status_changed)

    def _connect_worker_signals(self):
        js = self.mw.joystick_service
        if js._worker:
            js._worker.axis_changed.connect(self._on_axis_changed)
            js._worker.button_changed.connect(self._on_button_changed)

    def _init_display(self):
        ui = self.joystick_ui

        self._update_connection_display(False)

        js = self.mw.joystick_service
        config = js._config['joystick']
        ui.label_devicePath.setText(f"장치: {config['device_path']}")
        ui.label_deadzone.setText(f"Deadzone: {config['deadzone']}")
        
        if 'deadman_axes' in config:
            threshold = config['deadman_axes'].get('threshold', 0.5)
            ui.label_threshold.setText(f"Threshold: {threshold}")
        else:
            ui.label_threshold.setText("Threshold: N/A")

        ui.label_currentMode.setText("모드: None")

        for i in range(8):
            progress_bar = getattr(ui, f'progressBar_axis{i}', None)
            if progress_bar:
                progress_bar.setValue(50)
            value_label = getattr(ui, f'label_axisValue{i}', None)
            if value_label:
                value_label.setText("+0.00")


    def _on_axis_changed(self, axis_id: int, value: float):
        if axis_id >= 8:
            return
        self._axis_values[axis_id] = value
        self._update_axis_display(axis_id, value)

    def _on_button_changed(self, button_id: int, pressed: bool):
        if button_id >= 12:
            return
        self._button_states[button_id] = pressed
        self._update_button_display(button_id, pressed)

    def _on_mode_changed(self, mode: str):
        ui = self.joystick_ui
        ui.label_currentMode.setText(f"모드: {mode}")
        colors = {'None': '#888888', 'XYZ': '#4CAF50', 'RxRyRz': '#2196F3'}
        color = colors.get(mode, '#888888')
        ui.label_modeIndicator.setStyleSheet(f"background-color: {color}; border-radius: 5px;")

    def _on_connection_changed(self, connected: bool):
        self._update_connection_display(connected)
        if connected:
            self._connect_worker_signals()

    def _on_status_changed(self, message: str):
        self.joystick_ui.label_statusMessage.setText(message)


    def _update_connection_display(self, connected: bool):
        ui = self.joystick_ui
        if connected:
            ui.label_connectionStatus.setText("연결됨")
            ui.label_connectionIndicator.setStyleSheet(
                "background-color: #4CAF50; border-radius: 10px;"
            )
        else:
            ui.label_connectionStatus.setText("연결 안됨")
            ui.label_connectionIndicator.setStyleSheet(
                "background-color: #F44336; border-radius: 10px;"
            )

    def _update_axis_display(self, axis_id: int, value: float):
        ui = self.joystick_ui
        progress_value = int((value + 1.0) * 50)
        progress_value = max(0, min(100, progress_value))
        
        progress_bar = getattr(ui, f'progressBar_axis{axis_id}', None)
        if progress_bar:
            progress_bar.setValue(progress_value)
        
        value_label = getattr(ui, f'label_axisValue{axis_id}', None)
        if value_label:
            value_label.setText(f"{value:+.2f}")

    def _update_button_display(self, button_id: int, pressed: bool):
        ui = self.joystick_ui
        indicator = getattr(ui, f'frame_buttonIndicator{button_id}', None)
        if indicator:
            color = '#4CAF50' if pressed else '#888888'
            indicator.setStyleSheet(f"background-color: {color}; border-radius: 8px;")
