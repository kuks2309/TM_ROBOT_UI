from typing import List
from PyQt5 import uic
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QGroupBox, QPushButton, QLabel

from .base_tab import BaseTab
from .. import paths


class IOControlTab(BaseTab):
    LED_ON_STYLE = "background-color: #00ff00; border-radius: 8px; min-width: 16px; min-height: 16px;"
    LED_OFF_STYLE = "background-color: #404040; border-radius: 8px; min-width: 16px; min-height: 16px;"
    MGZ_PRESENT_STYLE = "background-color: #00b050; color: white; border-radius: 4px; padding: 4px;"
    MGZ_EMPTY_STYLE = "background-color: #404040; color: #b0b0b0; border-radius: 4px; padding: 4px;"
    MGZ_STALE_STYLE = "background-color: #7f6000; color: #ffd966; border-radius: 4px; padding: 4px;"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window

        self.ui_widget = None
        self._cb_di_leds: List[QLabel] = []
        self._cb_do_btns: List[QPushButton] = []
        self._ee_di_leds: List[QLabel] = []
        self._ee_do_btns: List[QPushButton] = []
        self._mgz_labels: List[QLabel] = []

    def init_ui(self):
        if self.ros_node:
            self.ros_node.get_logger().info('[IOControlTab] init_ui() 시작')

        ui_path = paths.ui('io_control_tab.ui')
        self.ui_widget = uic.loadUi(ui_path)
        if self.ros_node:
            self.ros_node.get_logger().info(f'[IOControlTab] UI 로드 완료')

        if not hasattr(self.mw, 'tab_ioControl'):
            print("[IOControlTab] ERROR: tab_ioControl이 main_window에 없음!")
            return

        layout = QVBoxLayout(self.mw.tab_ioControl)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_widget)
        print("[IOControlTab] 레이아웃 설정 완료")

        self._cache_widget_references()
        self._init_led_styles()
        self._build_magazine_group(layout)
        print(f"[IOControlTab] init_ui() 완료 - CB DI LEDs: {len(self._cb_di_leds)}, CB DO Btns: {len(self._cb_do_btns)}")

    def _cache_widget_references(self):
        if not self.ui_widget:
            return

        for i in range(16):
            led = getattr(self.ui_widget, f'label_cb_di_{i}', None)
            if led:
                self._cb_di_leds.append(led)

        for i in range(16):
            btn = getattr(self.ui_widget, f'btn_cb_do_{i}', None)
            if btn:
                self._cb_do_btns.append(btn)

        for i in range(4):
            led = getattr(self.ui_widget, f'label_ee_di_{i}', None)
            if led:
                self._ee_di_leds.append(led)

        for i in range(4):
            btn = getattr(self.ui_widget, f'btn_ee_do_{i}', None)
            if btn:
                self._ee_do_btns.append(btn)

    def _init_led_styles(self):
        for led in self._cb_di_leds + self._ee_di_leds:
            led.setStyleSheet(self.LED_OFF_STYLE)

    def _build_magazine_group(self, layout: QVBoxLayout):
        service = getattr(self.mw, 'magazine_state_service', None)
        if service is None or not getattr(service, 'available', False):
            notice = QGroupBox('버퍼 매거진 (사용 불가)')
            inner = QGridLayout(notice)
            label = QLabel('magazine_detect 가 이 기계에 없습니다 — 재고를 읽지 않습니다.\n'
                           '매거진 인터록 Task 는 판정 불가로 처리됩니다.')
            label.setStyleSheet(self.MGZ_STALE_STYLE)
            label.setWordWrap(True)
            inner.addWidget(label, 0, 0)
            layout.addWidget(notice)
            return

        box = QGroupBox('버퍼 매거진 (팔레트 0~5)')
        grid = QGridLayout(box)
        for col, slot in enumerate((0, 2, 4)):
            grid.addWidget(self._make_magazine_label(slot), 0, col)
        for col, slot in enumerate((1, 3, 5)):
            grid.addWidget(self._make_magazine_label(slot), 1, col)
        layout.addWidget(box)

    def _make_magazine_label(self, slot: int) -> QLabel:
        service = self.mw.magazine_state_service
        label = QLabel(f'{slot} {service.slot_name(slot)}\n미수신')
        label.setStyleSheet(self.MGZ_STALE_STYLE)
        while len(self._mgz_labels) <= slot:
            self._mgz_labels.append(None)
        self._mgz_labels[slot] = label
        return label

    def _update_magazine(self, present: List[bool], raw: List[bool], valid: bool):
        service = getattr(self.mw, 'magazine_state_service', None)
        if service is None:
            return
        for slot, label in enumerate(self._mgz_labels):
            if label is None or slot >= len(present):
                continue
            name = service.slot_name(slot)
            if not valid:
                label.setText(f'{slot} {name}\n확인 불가')
                label.setStyleSheet(self.MGZ_STALE_STYLE)
            elif present[slot]:
                label.setText(f'{slot} {name}\n매거진 있음')
                label.setStyleSheet(self.MGZ_PRESENT_STYLE)
            else:
                label.setText(f'{slot} {name}\n비어 있음')
                label.setStyleSheet(self.MGZ_EMPTY_STYLE)

    def connect_signals(self):
        if self.ros_node:
            self.ros_node.get_logger().info('[IOControlTab] connect_signals() 시작')

        if not hasattr(self.mw, 'io_control_service') or not self.mw.io_control_service:
            if self.ros_node:
                self.ros_node.get_logger().error('[IOControlTab] ERROR: io_control_service가 없음!')
            return

        service = self.mw.io_control_service

        service.cb_di_updated.connect(self._update_cb_di_leds)
        service.cb_do_updated.connect(self._update_cb_do_leds)
        service.ee_di_updated.connect(self._update_ee_di_leds)
        service.ee_do_updated.connect(self._update_ee_do_leds)
        service.io_error.connect(self._log)

        mgz = getattr(self.mw, 'magazine_state_service', None)
        if mgz is not None and getattr(mgz, 'available', False):
            mgz.magazine_updated.connect(self._update_magazine)

        self._connect_do_buttons()

        if self.ui_widget:
            if hasattr(self.ui_widget, 'btn_grip'):
                self.ui_widget.btn_grip.clicked.connect(self._on_grip)
            if hasattr(self.ui_widget, 'btn_release'):
                self.ui_widget.btn_release.clicked.connect(self._on_release)

        if self.ros_node:
            self.ros_node.get_logger().info(f'[IOControlTab] 시그널 연결 완료 - CB DI LEDs: {len(self._cb_di_leds)}, CB DO Btns: {len(self._cb_do_btns)}')

    def _connect_do_buttons(self):
        service = self.mw.io_control_service

        for i, btn in enumerate(self._cb_do_btns):
            btn.setCheckable(True)
            btn.clicked.connect(
                lambda checked, pin=i: service.set_cb_do(pin, checked)
            )

        for i, btn in enumerate(self._ee_do_btns):
            btn.setCheckable(True)
            btn.clicked.connect(
                lambda checked, pin=i: service.set_ee_do(pin, checked)
            )


    def _update_cb_di_leds(self, states: List[bool]):
        if self.ros_node:
            self.ros_node.get_logger().info(f'[IOControlTab] CB DI 업데이트: {states[:4]}... LED위젯: {len(self._cb_di_leds)}개')
        for i, state in enumerate(states):
            if i < len(self._cb_di_leds):
                style = self.LED_ON_STYLE if state else self.LED_OFF_STYLE
                self._cb_di_leds[i].setStyleSheet(style)

    def _update_cb_do_leds(self, states: List[bool]):
        for i, state in enumerate(states):
            if i < len(self._cb_do_btns):
                self._cb_do_btns[i].setChecked(state)

    def _update_ee_di_leds(self, states: List[bool]):
        for i, state in enumerate(states):
            if i < len(self._ee_di_leds):
                style = self.LED_ON_STYLE if state else self.LED_OFF_STYLE
                self._ee_di_leds[i].setStyleSheet(style)

    def _update_ee_do_leds(self, states: List[bool]):
        for i, state in enumerate(states):
            if i < len(self._ee_do_btns):
                self._ee_do_btns[i].setChecked(state)


    def _on_grip(self):
        if self.mw.io_control_service:
            self.mw.io_control_service.grip()
            self._log("Grip 명령 전송")

    def _on_release(self):
        if self.mw.io_control_service:
            self.mw.io_control_service.release()
            self._log("Release 명령 전송")
