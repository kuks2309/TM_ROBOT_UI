import os
import yaml
from typing import List, Optional, Tuple
from PyQt5.QtCore import QObject, pyqtSignal
from tm_msgs.srv import SetIO


class IOControlService(QObject):
    cb_di_updated = pyqtSignal(list)
    cb_do_updated = pyqtSignal(list)
    ee_di_updated = pyqtSignal(list)
    ee_do_updated = pyqtSignal(list)
    cb_ai_updated = pyqtSignal(list)
    ee_ai_updated = pyqtSignal(list)
    io_error = pyqtSignal(str)

    CB_DI_COUNT = 16
    CB_DO_COUNT = 16
    EE_DI_COUNT = 4
    EE_DO_COUNT = 4

    CB_AI_COUNT = 2
    EE_AI_COUNT = 1

    MODULE_CONTROL_BOX = 0
    MODULE_END_MODULE = 1
    IO_TYPE_DO = 1

    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node

        self._cb_di: List[bool] = [False] * self.CB_DI_COUNT
        self._cb_do: List[bool] = [False] * self.CB_DO_COUNT
        self._ee_di: List[bool] = [False] * self.EE_DI_COUNT
        self._ee_do: List[bool] = [False] * self.EE_DO_COUNT

        self._cb_ai: List[float] = [0.0] * self.CB_AI_COUNT
        self._ee_ai: List[float] = [0.0] * self.EE_AI_COUNT

        self._first_update_done = False

        self._gripper_config = self._load_gripper_config()

    def _load_gripper_config(self) -> dict:
        config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'io_config.yaml'
        )
        default_config = {
            'module': self.MODULE_END_MODULE,
            'grip_pin': 0,
            'release_pin': 1
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    return config.get('gripper', default_config)
        except Exception:
            pass

        return default_config


    @property
    def cb_di(self) -> List[bool]:
        return self._cb_di.copy()

    @property
    def cb_do(self) -> List[bool]:
        return self._cb_do.copy()

    @property
    def ee_di(self) -> List[bool]:
        return self._ee_di.copy()

    @property
    def ee_do(self) -> List[bool]:
        return self._ee_do.copy()


    def update_io_state(self, cb_di: List[bool], cb_do: List[bool],
                        ee_di: List[bool], ee_do: List[bool],
                        cb_ai: List[float] = None, ee_ai: List[float] = None):
        first_update = not self._first_update_done
        if first_update:
            self._first_update_done = True
            if self.ros_node:
                self.ros_node.get_logger().info(f'[IOControlService] First IO update: cb_di={cb_di[:4]}...')

        new_cb_di = self._normalize_list(cb_di, self.CB_DI_COUNT)
        if first_update or new_cb_di != self._cb_di:
            self._cb_di = new_cb_di
            self.cb_di_updated.emit(self._cb_di.copy())

        new_cb_do = self._normalize_list(cb_do, self.CB_DO_COUNT)
        if first_update or new_cb_do != self._cb_do:
            self._cb_do = new_cb_do
            self.cb_do_updated.emit(self._cb_do.copy())

        new_ee_di = self._normalize_list(ee_di, self.EE_DI_COUNT)
        if first_update or new_ee_di != self._ee_di:
            self._ee_di = new_ee_di
            self.ee_di_updated.emit(self._ee_di.copy())

        new_ee_do = self._normalize_list(ee_do, self.EE_DO_COUNT)
        if first_update or new_ee_do != self._ee_do:
            self._ee_do = new_ee_do
            self.ee_do_updated.emit(self._ee_do.copy())

        if cb_ai is not None:
            for i, val in enumerate(cb_ai[:self.CB_AI_COUNT]):
                self._cb_ai[i] = float(val)
            self.cb_ai_updated.emit(self._cb_ai.copy())

        if ee_ai is not None:
            for i, val in enumerate(ee_ai[:self.EE_AI_COUNT]):
                self._ee_ai[i] = float(val)
            self.ee_ai_updated.emit(self._ee_ai.copy())

    def _normalize_list(self, data: List, expected_len: int) -> List[bool]:
        result = [False] * expected_len
        if data:
            for i in range(min(len(data), expected_len)):
                result[i] = bool(data[i])
        return result


    def set_digital_output(self, module: int, pin: int, state: bool) -> bool:
        if not self.ros_node or not hasattr(self.ros_node, 'set_io_client'):
            self.io_error.emit("ROS 노드 또는 set_io_client 없음")
            return False

        max_pin = self.CB_DO_COUNT if module == self.MODULE_CONTROL_BOX else self.EE_DO_COUNT
        if pin < 0 or pin >= max_pin:
            self.io_error.emit(f"잘못된 DO 핀 번호: {pin}")
            return False

        try:
            request = SetIO.Request()
            request.module = module
            request.type = self.IO_TYPE_DO
            request.pin = pin
            request.state = 1.0 if state else 0.0

            future = self.ros_node.set_io_client.call_async(request)
            return True
        except Exception as e:
            self.io_error.emit(f"DO 제어 실패: {e}")
            return False

    def set_cb_do(self, pin: int, state: bool) -> bool:
        return self.set_digital_output(self.MODULE_CONTROL_BOX, pin, state)

    def set_ee_do(self, pin: int, state: bool) -> bool:
        return self.set_digital_output(self.MODULE_END_MODULE, pin, state)


    def grip(self) -> bool:
        module = self._gripper_config.get('module', self.MODULE_END_MODULE)
        pin = self._gripper_config.get('grip_pin', 0)
        return self.set_digital_output(module, pin, True)

    def release(self) -> bool:
        module = self._gripper_config.get('module', self.MODULE_END_MODULE)
        pin = self._gripper_config.get('release_pin', 1)
        return self.set_digital_output(module, pin, True)

    def read_digital_input(self, di_name: str) -> Tuple[bool, Optional[bool], str]:
        if di_name.startswith('Ctrl_DI'):
            pin = int(di_name.replace('Ctrl_DI', ''))
            if 0 <= pin < self.CB_DI_COUNT:
                value = self._cb_di[pin]
                return True, value, f"{di_name} = {'ON' if value else 'OFF'}"
            else:
                return False, None, f"잘못된 DI 핀 번호: {pin}"
        elif di_name.startswith('End_DI'):
            pin = int(di_name.replace('End_DI', ''))
            if 0 <= pin < self.EE_DI_COUNT:
                value = self._ee_di[pin]
                return True, value, f"{di_name} = {'ON' if value else 'OFF'}"
            else:
                return False, None, f"잘못된 DI 핀 번호: {pin}"
        else:
            return False, None, f"알 수 없는 DI 이름: {di_name}"

    def write_digital_output_by_name(self, do_name: str, state: str) -> Tuple[bool, str]:
        state_bool = (state == 'ON')

        if do_name.startswith('Ctrl_DO'):
            pin = int(do_name.replace('Ctrl_DO', ''))
            success = self.set_cb_do(pin, state_bool)
            if success:
                return True, f"{do_name} = {state} 설정 요청 완료"
            else:
                return False, f"{do_name} 설정 실패"
        elif do_name.startswith('End_DO'):
            pin = int(do_name.replace('End_DO', ''))
            success = self.set_ee_do(pin, state_bool)
            if success:
                return True, f"{do_name} = {state} 설정 요청 완료"
            else:
                return False, f"{do_name} 설정 실패"
        else:
            return False, f"알 수 없는 DO 이름: {do_name}"

    def read_analog_input(self, ai_name: str) -> Tuple[bool, Optional[float], str]:
        if ai_name.startswith('Ctrl_AI'):
            pin = int(ai_name.replace('Ctrl_AI', ''))
            if 0 <= pin < self.CB_AI_COUNT:
                value = self._cb_ai[pin]
                return True, value, f"{ai_name} = {value:.3f}V"
            else:
                return False, None, f"잘못된 AI 핀 번호: {pin}"
        elif ai_name.startswith('End_AI'):
            pin = int(ai_name.replace('End_AI', ''))
            if 0 <= pin < self.EE_AI_COUNT:
                value = self._ee_ai[pin]
                return True, value, f"{ai_name} = {value:.3f}V"
            else:
                return False, None, f"잘못된 AI 핀 번호: {pin}"
        else:
            return False, None, f"알 수 없는 AI 이름: {ai_name}"
