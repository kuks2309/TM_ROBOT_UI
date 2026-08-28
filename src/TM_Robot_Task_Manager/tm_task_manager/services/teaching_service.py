import time
from typing import Optional, List, Dict, Any, Tuple, Callable
from PyQt5.QtCore import QObject, pyqtSignal

from .coordinate_transformer import CoordinateTransformer
from .decomposed_move_planner import build_decomposed_tcp_waypoints


class TeachingService(QObject):
    position_taught = pyqtSignal(dict)
    jog_completed = pyqtSignal(str)
    move_completed = pyqtSignal(bool, str)

    def __init__(self, ros_node=None):
        super().__init__()
        self.ros_node = ros_node

        self.jog_in_progress = False
        self.last_jog_time = 0.0

    def teach_current_position(self,
                              current_joint_position: Optional[List[float]],
                              current_tcp_pose: Optional[List[float]],
                              motion_type: str = 'tcp') -> Optional[Dict[str, Any]]:
        if motion_type == 'joint':
            if current_joint_position and len(current_joint_position) >= 6:
                taught_data = {
                    'motion_type': 'joint',
                    'positions': [round(p, 2) for p in current_joint_position],
                    'unit': 'degrees'
                }
                self.position_taught.emit(taught_data)
                return taught_data
            else:
                return None
        else:
            if current_tcp_pose and len(current_tcp_pose) >= 6:
                taught_data = {
                    'motion_type': 'tcp',
                    'positions': [round(p, 2) for p in current_tcp_pose],
                    'unit': 'mm/degrees'
                }
                self.position_taught.emit(taught_data)
                return taught_data
            else:
                return None

    def jog_tcp(self,
                axis: str,
                direction: int,
                step_mm: float,
                velocity_percent: float,
                current_tcp_pose: Optional[List[float]],
                current_tcp_orientation: List[float],
                move_callback: Callable) -> Tuple[bool, str]:
        if not current_tcp_pose:
            return False, "현재 로봇 위치를 알 수 없습니다"

        if self.jog_in_progress:
            return False, "이전 조그 명령이 진행 중입니다. 잠시 기다려주세요."

        current_time = time.time()
        if current_time - self.last_jog_time < 0.5:
            return False, "조그 명령이 너무 빠릅니다. 잠시 후 다시 시도하세요."

        self.jog_in_progress = True
        self.last_jog_time = current_time

        step = step_mm * direction

        target_pos = current_tcp_pose.copy()

        is_rotation = axis in ['rx', 'ry', 'rz']

        if is_rotation:
            if axis == 'rx':
                target_pos[3] += step
            elif axis == 'ry':
                target_pos[4] += step
            elif axis == 'rz':
                target_pos[5] += step
        else:
            tool_delta = [0.0, 0.0, 0.0]
            if axis == 'x':
                tool_delta[0] = step
            elif axis == 'y':
                tool_delta[1] = step
            elif axis == 'z':
                tool_delta[2] = -step

            current_orientation = [current_tcp_pose[3], current_tcp_pose[4], current_tcp_pose[5]]
            base_delta = CoordinateTransformer.transform_tool_to_base(tool_delta, current_orientation)

            target_pos[0] += base_delta[0]
            target_pos[1] += base_delta[1]
            target_pos[2] += base_delta[2]

        target_pos_service = CoordinateTransformer.convert_tcp_to_service_format(target_pos)

        from tm_msgs.srv import SetPositions
        success, msg = move_callback(
            SetPositions.Request.PTP_T,
            target_pos_service,
            velocity_percent,
            0.2
        )

        self.jog_in_progress = False

        unit = "deg" if axis in ['rx', 'ry', 'rz'] else "mm"
        result_msg = f"{axis.upper()}{'+' if direction > 0 else ''}{step:.1f}{unit} 이동 (속도: {velocity_percent}%)"
        self.jog_completed.emit(result_msg)

        return success, result_msg

    def jog_tcp_continuous(self,
                          axis: str,
                          direction: int,
                          step_mm: float,
                          velocity_percent: float,
                          current_tcp_pose: Optional[List[float]],
                          current_tcp_orientation: List[float],
                          move_callback: Callable) -> Tuple[bool, str]:
        if not current_tcp_pose:
            return False, "현재 로봇 위치를 알 수 없습니다"

        if self.jog_in_progress:
            return False, "이전 조그 명령이 진행 중입니다. 잠시 기다려주세요."


        self.jog_in_progress = True

        step = step_mm * direction

        target_pos = current_tcp_pose.copy()

        is_rotation = axis in ['rx', 'ry', 'rz']

        if is_rotation:
            if axis == 'rx':
                target_pos[3] += step
            elif axis == 'ry':
                target_pos[4] += step
            elif axis == 'rz':
                target_pos[5] += step
        else:
            tool_delta = [0.0, 0.0, 0.0]
            if axis == 'x':
                tool_delta[0] = step
            elif axis == 'y':
                tool_delta[1] = step
            elif axis == 'z':
                tool_delta[2] = -step

            current_orientation = [current_tcp_pose[3], current_tcp_pose[4], current_tcp_pose[5]]
            base_delta = CoordinateTransformer.transform_tool_to_base(tool_delta, current_orientation)

            target_pos[0] += base_delta[0]
            target_pos[1] += base_delta[1]
            target_pos[2] += base_delta[2]

        target_pos_service = CoordinateTransformer.convert_tcp_to_service_format(target_pos)

        from tm_msgs.srv import SetPositions
        success, msg = move_callback(
            SetPositions.Request.PTP_T,
            target_pos_service,
            velocity_percent,
            0.2
        )

        self.jog_in_progress = False

        unit = "deg" if axis in ['rx', 'ry', 'rz'] else "mm"
        result_msg = f"{axis.upper()}{'+' if direction > 0 else ''}{step:.1f}{unit} 이동 (속도: {velocity_percent}%)"
        self.jog_completed.emit(result_msg)

        return success, result_msg

    def move_to_position(self,
                        motion_type: str,
                        positions: List[float],
                        velocity: float,
                        move_callback: Callable,
                        decomposed_tcp: bool = False) -> Tuple[bool, str]:
        from tm_msgs.srv import SetPositions

        if motion_type == 'joint':
            positions_service = CoordinateTransformer.convert_joint_to_service_format(positions)
            success, msg = move_callback(
                SetPositions.Request.PTP_J,
                positions_service,
                velocity,
                0.2
            )
        elif decomposed_tcp:
            return self._move_decomposed_tcp(positions, velocity, move_callback)
        else:
            positions_service = CoordinateTransformer.convert_tcp_to_service_format(positions)
            success, msg = move_callback(
                SetPositions.Request.PTP_T,
                positions_service,
                velocity,
                0.2
            )

        self.move_completed.emit(success, msg)
        return success, msg

    def _move_decomposed_tcp(self,
                             positions: List[float],
                             velocity: float,
                             move_callback: Callable) -> Tuple[bool, str]:
        from tm_msgs.srv import SetPositions

        current_tcp_pose = getattr(self.ros_node, 'current_tcp_pose', None)
        if not current_tcp_pose or len(current_tcp_pose) < 6:
            msg = "현재 TCP 위치를 알 수 없어 축 분해 이동을 할 수 없습니다"
            self.move_completed.emit(False, msg)
            return False, msg

        waypoints, order_label = build_decomposed_tcp_waypoints(
            list(current_tcp_pose[:6]), list(positions[:6])
        )

        if not waypoints:
            msg = "축 분해 이동: 이동량이 없어 현재 위치를 유지합니다"
            self.move_completed.emit(True, msg)
            return True, msg

        total = len(waypoints)
        for step_no, (label, waypoint) in enumerate(waypoints, start=1):
            success, msg = move_callback(
                SetPositions.Request.LINE_T,
                CoordinateTransformer.convert_tcp_to_service_format(waypoint),
                velocity,
                0.2
            )
            if not success:
                fail_msg = f"축 분해 이동 {step_no}/{total} {label} 실패: {msg}"
                self.move_completed.emit(False, fail_msg)
                return False, fail_msg

        done_msg = f"축 분해 이동 완료 ({order_label}, {total}단계: " \
                   f"{' → '.join(label for label, _ in waypoints)})"
        self.move_completed.emit(True, done_msg)
        return True, done_msg

    def extract_position_from_params(self, param_widgets: Dict[str, Any]) -> Optional[Tuple[str, List[float]]]:
        if 'motion_type' in param_widgets:
            motion_type = param_widgets['motion_type'].currentText()

            x = param_widgets['X'].value() if 'X' in param_widgets else 0.0
            y = param_widgets['Y'].value() if 'Y' in param_widgets else 0.0
            z = param_widgets['Z'].value() if 'Z' in param_widgets else 0.0
            rx = param_widgets['Rx'].value() if 'Rx' in param_widgets else 0.0
            ry = param_widgets['Ry'].value() if 'Ry' in param_widgets else 0.0
            rz = param_widgets['Rz'].value() if 'Rz' in param_widgets else 0.0

            positions = [x, y, z, rx, ry, rz]
            return motion_type, positions
        else:
            return None

    def set_position_to_params(self,
                               param_widgets: Dict[str, Any],
                               motion_type: str,
                               positions: List[float]) -> bool:
        if 'motion_type' in param_widgets:
            current_type = param_widgets['motion_type'].currentText()
            if current_type != motion_type:
                return False

            if 'X' in param_widgets:
                param_widgets['X'].setValue(round(positions[0], 2))
            if 'Y' in param_widgets:
                param_widgets['Y'].setValue(round(positions[1], 2))
            if 'Z' in param_widgets:
                param_widgets['Z'].setValue(round(positions[2], 2))
            if 'Rx' in param_widgets:
                param_widgets['Rx'].setValue(round(positions[3], 2))
            if 'Ry' in param_widgets:
                param_widgets['Ry'].setValue(round(positions[4], 2))
            if 'Rz' in param_widgets:
                param_widgets['Rz'].setValue(round(positions[5], 2))

            return True
        elif 'positions' in param_widgets and motion_type == 'joint':
            widget = param_widgets['positions']
            pos_str = str([round(p, 2) for p in positions])
            widget.setText(pos_str)
            return True
        elif 'target_position' in param_widgets and motion_type == 'tcp':
            widget = param_widgets['target_position']
            pos_str = str([round(p, 2) for p in positions])
            widget.setText(pos_str)
            return True
        else:
            return False
