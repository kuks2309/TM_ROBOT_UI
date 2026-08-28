"""탭 패키지 공개 인터페이스 — 13개 탭 클래스를 re-export 한다 (전 모듈 eager import: 어느 탭의 import 실패도 앱 기동 실패로 이어짐)."""
from .base_tab import BaseTab
from .task_edit_tab import TaskEditTab
from .vision_tab import VisionTab
from .run_monitor_tab import RunMonitorTab
from .settings_tab import SettingsTab
from .global_variables_tab import GlobalVariablesTab
from .precision_test_tab import PrecisionTestTab
from .handeye_test_tab import HandEyeTestTab
from .ps2_joystick_test_tab import PS2JoystickTestTab
from .keyboard_control_tab import KeyboardControlTab
from .io_control_tab import IOControlTab
from .ai_detection_tab import AIDetectionTab
from .pallet_teach_tab import PalletTeachTab

__all__ = [
    'BaseTab',
    'TaskEditTab',
    'VisionTab',
    'RunMonitorTab',
    'SettingsTab',
    'GlobalVariablesTab',
    'PrecisionTestTab',
    'HandEyeTestTab',
    'PS2JoystickTestTab',
    'KeyboardControlTab',
    'IOControlTab',
    'AIDetectionTab',
    'PalletTeachTab',
]
