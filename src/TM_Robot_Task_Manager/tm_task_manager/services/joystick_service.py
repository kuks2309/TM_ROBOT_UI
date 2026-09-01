"""리눅스 joydev(/dev/input/js*) 기반 PS2 조이스틱 조그 서비스."""
import os
import struct
import select
import yaml
from typing import Optional, Dict, Any
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer

# joydev 이벤트 레코드: u32 time(ms) + s16 value + u8 type + u8 number = 8바이트
JS_EVENT_SIZE = 8
JS_EVENT_FORMAT = 'IhBB'
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80   # 장치 초기 상태 통지 비트 — 실이벤트와 구분용


class JoystickWorker(QThread):
    """joydev 장치를 select 로 읽어 축/버튼 이벤트를 Qt 시그널로 바꾸는 워커."""

    axis_changed = pyqtSignal(int, float)
    button_changed = pyqtSignal(int, bool)
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, device_path: str):
        super().__init__()
        self.device_path = device_path
        self._running = False

    def run(self):
        """(워커 스레드) 8바이트 이벤트 루프 — 축 값은 -32767~32767 을 ±1.0 으로 정규화."""
        self._running = True

        try:
            with open(self.device_path, 'rb') as js:
                self.connection_changed.emit(True)

                while self._running:
                    # 0.1s 타임아웃 select — 종료 플래그를 주기적으로 확인하기 위해
                    readable, _, _ = select.select([js], [], [], 0.1)

                    if not readable:
                        continue

                    event_data = js.read(JS_EVENT_SIZE)
                    if not event_data or len(event_data) < JS_EVENT_SIZE:
                        self.connection_changed.emit(False)
                        break

                    time, value, event_type, number = struct.unpack(
                        JS_EVENT_FORMAT, event_data
                    )

                    event_type &= ~JS_EVENT_INIT

                    if event_type == JS_EVENT_BUTTON:
                        self.button_changed.emit(number, bool(value))
                    elif event_type == JS_EVENT_AXIS:
                        normalized = value / 32767.0
                        self.axis_changed.emit(number, normalized)

        except FileNotFoundError:
            self.error_occurred.emit(f"장치를 찾을 수 없습니다: {self.device_path}")
            self.connection_changed.emit(False)
        except PermissionError:
            self.error_occurred.emit(
                f"장치 권한 없음: {self.device_path}\n"
                "해결: sudo usermod -a -G input $USER 후 재로그인"
            )
            self.connection_changed.emit(False)
        except Exception as e:
            self.error_occurred.emit(f"조이스틱 오류: {str(e)}")
            self.connection_changed.emit(False)

    def stop(self):
        # GUI 스레드가 세우고 워커 루프가 확인하는 bool — 단순 대입이라 락 없음
        self._running = False


class JoystickService(QObject):
    """데드맨 축 상태로 XYZ/RxRyRz 모드를 전환하며 jog_requested 를 발행한다.

    워커 시그널은 큐드 커넥션으로 GUI 스레드 슬롯에서 처리되므로 내부 상태는
    전부 GUI 스레드 단일 접근이다. 장치 분리 시 5초 주기 재연결을 시도한다.
    """

    jog_requested = pyqtSignal(str, int)
    mode_changed = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)
    status_changed = pyqtSignal(str)

    # z 와 rz 가 같은 물리축(7)을 공유한다 — 데드맨 두 개를 동시에 쥐면
    # 두 모드의 조그가 같은 틱에 함께 발행될 수 있다
    DEFAULT_CONFIG = {
        'joystick': {
            'device_path': '/dev/input/js0',
            'deadzone': 0.15,
            'poll_interval_ms': 50,
            'deadman_axes': {
                'xyz': 2,
                'rxryrz': 5,
                'threshold': 0.5
            },
            'axes': {
                'x': 0, 'y': 1, 'z': 7,
                'rx': 3, 'ry': 4, 'rz': 7
            },
            'jog': {
                'step_mm': 1.0,
                'step_deg': 0.5,
                'velocity_percent': 10,
                'continuous_interval_ms': 100
            }
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self._config = self._load_config(config_path)
        self._worker: Optional[JoystickWorker] = None
        self._enabled = False
        self._deadman_xyz_active = False
        self._deadman_rxryrz_active = False
        self._current_mode = 'None'
        self._axis_values: Dict[int, float] = {}

        self._jog_timer = QTimer()
        self._jog_timer.timeout.connect(self._process_jog)

        self._reconnect_timer = QTimer()
        self._reconnect_timer.timeout.connect(self._try_reconnect)
        self._reconnect_timer.setInterval(5000)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """yaml 설정 로드 (실패 시 DEFAULT_CONFIG 얕은 사본).

        사용자 yaml 은 기본값과 병합하지 않는다 — joystick 하위 키가 빠진
        파일을 주면 이후 접근에서 KeyError 가 난다 (완전한 파일 전제).
        """
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"[JoystickService] 설정 로드 실패: {e}, 기본값 사용")
        return self.DEFAULT_CONFIG.copy()


    def get_jog_step_mm(self) -> float:
        return self._config['joystick']['jog']['step_mm']

    def get_jog_step_deg(self) -> float:
        return self._config['joystick']['jog']['step_deg']

    def get_jog_velocity(self) -> float:
        return float(self._config['joystick']['jog']['velocity_percent'])

    def get_current_mode(self) -> str:
        return self._current_mode


    def start(self):
        """장치 읽기 워커를 만들어 기동한다 (이미 있으면 무시)."""
        if self._worker is not None:
            return

        device_path = self._config['joystick']['device_path']
        self._worker = JoystickWorker(device_path)

        self._worker.axis_changed.connect(self._on_axis_changed)
        self._worker.button_changed.connect(self._on_button_changed)
        self._worker.connection_changed.connect(self._on_connection_changed)
        self._worker.error_occurred.connect(self._on_error)

        self._worker.start()

    def stop(self):
        """타이머·워커를 모두 멈춘다 (워커 종료 최대 0.5s 대기)."""
        self._jog_timer.stop()
        self._reconnect_timer.stop()

        if self._worker:
            self._worker.stop()
            self._worker.wait(500)
            self._worker = None

    def set_enabled(self, enabled: bool):
        """조그 발행 on/off — 켜면 워커 기동 + 폴링 타이머 시작."""
        self._enabled = enabled
        if enabled:
            self.start()
            interval = self._config['joystick']['jog']['continuous_interval_ms']
            self._jog_timer.start(interval)
            self.status_changed.emit("PS2 조그 활성화")
        else:
            self._jog_timer.stop()
            self.status_changed.emit("PS2 조그 비활성화")


    def _on_axis_changed(self, axis_id: int, value: float):
        """(GUI 슬롯) 데드맨 판정·모드 전환 후 데드존 적용 값을 저장한다.

        데드맨 축은 트리거(누르면 +1)라 value > threshold 로 판정한다.
        """
        deadzone = self._config['joystick']['deadzone']
        deadman_axes = self._config['joystick']['deadman_axes']
        threshold = deadman_axes.get('threshold', 0.5)

        if axis_id == deadman_axes['xyz']:
            was_active = self._deadman_xyz_active
            self._deadman_xyz_active = value > threshold
            if self._deadman_xyz_active and not was_active:
                self._current_mode = 'XYZ'
                self.mode_changed.emit('XYZ')
                self.status_changed.emit("XYZ 이동 모드")
            elif not self._deadman_xyz_active and was_active:
                if not self._deadman_rxryrz_active:
                    self._current_mode = 'None'
                    self.mode_changed.emit('None')
                self.status_changed.emit("XYZ 데드맨 해제")

        elif axis_id == deadman_axes['rxryrz']:
            was_active = self._deadman_rxryrz_active
            self._deadman_rxryrz_active = value > threshold
            if self._deadman_rxryrz_active and not was_active:
                self._current_mode = 'RxRyRz'
                self.mode_changed.emit('RxRyRz')
                self.status_changed.emit("RxRyRz 회전 모드")
            elif not self._deadman_rxryrz_active and was_active:
                if not self._deadman_xyz_active:
                    self._current_mode = 'None'
                    self.mode_changed.emit('None')
                self.status_changed.emit("RxRyRz 데드맨 해제")

        if abs(value) < deadzone:
            value = 0.0
        self._axis_values[axis_id] = value

    def _on_button_changed(self, button_id: int, pressed: bool):
        pass

    def _on_connection_changed(self, connected: bool):
        self.connection_changed.emit(connected)

        if not connected and self._enabled:
            self._reconnect_timer.start()
            self.status_changed.emit("조이스틱 연결 해제 - 재연결 시도 중...")

    def _on_error(self, message: str):
        self.status_changed.emit(message)

    def _try_reconnect(self):
        """(5s 타이머) 장치 파일이 다시 보이면 워커를 재기동한다."""
        device_path = self._config['joystick']['device_path']
        if os.path.exists(device_path):
            self._reconnect_timer.stop()
            self.stop()
            self.start()

    def _process_jog(self):
        """(폴링 타이머) 활성 데드맨 모드의 축별로 jog_requested(axis, ±1)를 발행한다."""
        if not self._enabled:
            return

        axes = self._config['joystick']['axes']
        deadzone = self._config['joystick']['deadzone']

        if self._deadman_xyz_active:
            xyz_map = {
                axes['x']: 'x',
                axes['y']: 'y',
                axes['z']: 'z'
            }
            for axis_id, axis_name in xyz_map.items():
                value = self._axis_values.get(axis_id, 0.0)
                if abs(value) > deadzone:
                    direction = 1 if value > 0 else -1
                    self.jog_requested.emit(axis_name, direction)

        if self._deadman_rxryrz_active:
            rxryrz_map = {
                axes['rx']: 'rx',
                axes['ry']: 'ry',
                axes['rz']: 'rz'
            }
            for axis_id, axis_name in rxryrz_map.items():
                value = self._axis_values.get(axis_id, 0.0)
                if abs(value) > deadzone:
                    direction = 1 if value > 0 else -1
                    self.jog_requested.emit(axis_name, direction)
