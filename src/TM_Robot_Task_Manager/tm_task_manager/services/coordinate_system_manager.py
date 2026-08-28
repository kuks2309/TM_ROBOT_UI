import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any
from .config_manager import ConfigManager
from .. import paths

try:
    from tf2_ros import StaticTransformBroadcaster
    from geometry_msgs.msg import TransformStamped
    from rclpy.node import Node
    import rclpy
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


class CoordinateSystemManager:
    ROBOT_BASE = 'robot_base'
    JIG_LANDMARK = 'jig_landmark'
    JIG_PLATE = 'jig_plate'

    TYPE_FIXED = 'fixed'
    TYPE_SINGLE_LANDMARK = 'single_landmark'
    TYPE_MULTI_LANDMARK = 'multi_landmark'

    SUPPORTED_SYSTEMS = [ROBOT_BASE, JIG_LANDMARK, JIG_PLATE]

    SYSTEM_TYPES = {
        ROBOT_BASE: TYPE_FIXED,
        JIG_LANDMARK: TYPE_SINGLE_LANDMARK,
        JIG_PLATE: TYPE_MULTI_LANDMARK
    }

    DEFAULT_TOOL_POSE = {
        ROBOT_BASE: {
            'x': 0.0, 'y': 0.0, 'z': 0.0,
            'rx': 180.0, 'ry': 0.0, 'rz': 180.0
        },
        JIG_LANDMARK: {
            'x': 0.0, 'y': 0.0, 'z': 0.0,
            'rx': 0.0, 'ry': 0.0, 'rz': 0.0
        },
        JIG_PLATE: {
            'x': 0.0, 'y': 0.0, 'z': 0.0,
            'rx': 0.0, 'ry': 0.0, 'rz': 0.0
        }
    }

    TF_FRAME_ROBOT_BASE = 'robot_base'
    TF_FRAME_JIG_LANDMARK = 'jig_landmark'
    TF_FRAME_JIG_PLATE = 'jig_plate'

    def __init__(self, config_manager: ConfigManager = None, log_callback=None, ros_node=None):
        self.config_manager = config_manager or ConfigManager()
        self._log_callback = log_callback
        self._ros_node = ros_node

        self._definitions: Dict[str, Dict[str, Any]] = {}

        self._current_system: str = self.ROBOT_BASE

        self._tf_broadcaster = None
        self._tf_timer = None
        self._tf_enabled = False

        self.load_from_config()

    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)

    def _create_pose_dict(self, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0) -> Dict[str, float]:
        return {'x': x, 'y': y, 'z': z, 'rx': rx, 'ry': ry, 'rz': rz}

    def _create_default_definition(self, name: str) -> Dict[str, Any]:
        system_type = self.SYSTEM_TYPES.get(name, self.TYPE_FIXED)
        tool_pose = self.DEFAULT_TOOL_POSE.get(name, self._create_pose_dict()).copy()

        definition = {
            'type': system_type,
            'tool_pose': tool_pose,
            'scan_data': None
        }

        if system_type == self.TYPE_SINGLE_LANDMARK:
            definition['scan_data'] = {
                'landmark': None,
                'tcp_pose': None
            }
        elif system_type == self.TYPE_MULTI_LANDMARK:
            definition['scan_data'] = []

        return definition


    def get_tool_pose(self, name: str) -> Optional[Dict[str, float]]:
        if name not in self.SUPPORTED_SYSTEMS:
            self._log(f"지원하지 않는 좌표계: {name}")
            return None

        if name in self._definitions and 'tool_pose' in self._definitions[name]:
            return self._definitions[name]['tool_pose'].copy()
        else:
            return self.DEFAULT_TOOL_POSE.get(name, self._create_pose_dict()).copy()

    def set_tool_pose(
        self,
        name: str,
        x: float, y: float, z: float,
        rx: float, ry: float, rz: float
    ) -> bool:
        if name not in self.SUPPORTED_SYSTEMS:
            self._log(f"지원하지 않는 좌표계: {name}")
            return False

        if name == self.ROBOT_BASE:
            self._log("robot_base는 수정할 수 없습니다")
            return False

        if name not in self._definitions:
            self._definitions[name] = self._create_default_definition(name)

        self._definitions[name]['tool_pose'] = self._create_pose_dict(x, y, z, rx, ry, rz)
        self._log(f"tool_pose 설정: {name} = ({x:.2f}, {y:.2f}, {z:.2f}, {rx:.2f}, {ry:.2f}, {rz:.2f})")
        return True

    def set_tool_pose_from_list(self, name: str, values: List[float]) -> bool:
        if len(values) < 6:
            self._log(f"값이 6개 미만입니다: {len(values)}")
            return False
        return self.set_tool_pose(name, values[0], values[1], values[2], values[3], values[4], values[5])


    def get_scan_data(self, name: str) -> Optional[Any]:
        if name not in self.SUPPORTED_SYSTEMS:
            return None

        if name in self._definitions:
            return self._definitions[name].get('scan_data')
        return None

    def set_single_landmark_scan(
        self,
        name: str,
        landmark: Dict[str, float],
        tcp_pose: Dict[str, float]
    ) -> bool:
        if name not in self.SUPPORTED_SYSTEMS:
            self._log(f"지원하지 않는 좌표계: {name}")
            return False

        if self.SYSTEM_TYPES.get(name) != self.TYPE_SINGLE_LANDMARK:
            self._log(f"{name}은 single_landmark 타입이 아닙니다")
            return False

        if name not in self._definitions:
            self._definitions[name] = self._create_default_definition(name)

        self._definitions[name]['scan_data'] = {
            'landmark': landmark.copy(),
            'tcp_pose': tcp_pose.copy()
        }

        self._definitions[name]['tool_pose'] = landmark.copy()

        self._log(f"scan_data 설정: {name} (single_landmark)")
        return True

    def add_multi_landmark_scan(
        self,
        name: str,
        landmark: Dict[str, float],
        tcp_pose: Dict[str, float]
    ) -> bool:
        if name not in self.SUPPORTED_SYSTEMS:
            self._log(f"지원하지 않는 좌표계: {name}")
            return False

        if self.SYSTEM_TYPES.get(name) != self.TYPE_MULTI_LANDMARK:
            self._log(f"{name}은 multi_landmark 타입이 아닙니다")
            return False

        if name not in self._definitions:
            self._definitions[name] = self._create_default_definition(name)

        if not isinstance(self._definitions[name]['scan_data'], list):
            self._definitions[name]['scan_data'] = []

        self._definitions[name]['scan_data'].append({
            'landmark': landmark.copy(),
            'tcp_pose': tcp_pose.copy()
        })

        count = len(self._definitions[name]['scan_data'])
        self._log(f"scan_data 추가: {name} (multi_landmark, {count}개)")
        return True

    def clear_multi_landmark_scan(self, name: str) -> bool:
        if name not in self.SUPPORTED_SYSTEMS:
            return False

        if self.SYSTEM_TYPES.get(name) != self.TYPE_MULTI_LANDMARK:
            return False

        if name in self._definitions:
            self._definitions[name]['scan_data'] = []
            self._log(f"scan_data 초기화: {name}")
        return True

    def get_landmark_count(self, name: str) -> int:
        if name not in self._definitions:
            return 0
        scan_data = self._definitions[name].get('scan_data')
        if isinstance(scan_data, list):
            return len(scan_data)
        return 0


    def get_current_system(self) -> str:
        return self._current_system

    def set_current_system(self, name: str) -> bool:
        if name not in self.SUPPORTED_SYSTEMS:
            self._log(f"지원하지 않는 좌표계: {name}")
            return False

        self._current_system = name
        self._log(f"현재 좌표계 변경: {name}")
        return True

    def get_current_tcp_orientation(self) -> Tuple[float, float, float]:
        tool_pose = self.get_tool_pose(self._current_system)
        if tool_pose:
            return (tool_pose['rx'], tool_pose['ry'], tool_pose['rz'])
        else:
            return (180.0, 0.0, 180.0)

    def get_current_tool_pose(self) -> Optional[Dict[str, float]]:
        return self.get_tool_pose(self._current_system)


    def save_to_config(self, backup_type: str = None) -> bool:
        try:
            if backup_type:
                self._save_coordinate_backup(backup_type)

            for name in self.SUPPORTED_SYSTEMS:
                if name in self._definitions:
                    self.config_manager.set(f'coordinate_definitions.{name}', self._definitions[name])

            self.config_manager.set('coordinate_definitions.current', self._current_system)
            self._log("좌표계 설정 저장 완료")
            return True
        except Exception as e:
            self._log(f"좌표계 설정 저장 실패: {e}")
            return False

    def _save_coordinate_backup(self, coordinate_type: str) -> bool:
        try:
            config_path = self.config_manager.get_config_path()
            if not config_path or not Path(config_path).exists():
                self._log("백업할 설정 파일이 없습니다")
                print(f"[백업] 설정 파일 없음: {config_path}")
                return False

            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            datetime_str = now.strftime("%Y%m%d_%H%M%S")

            src_package_dir = paths.PACKAGE_ROOT
            backup_dir = src_package_dir / "data" / "jig_mark" / date_str

            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_name = f"{coordinate_type}_{datetime_str}.yaml"
            backup_path = backup_dir / backup_name

            shutil.copy2(config_path, backup_path)
            self._log(f"백업 생성: data/jig_mark/{date_str}/{backup_name}")
            print(f"[백업] 생성 완료: {backup_path}")
            return True
        except Exception as e:
            self._log(f"백업 생성 실패: {e}")
            print(f"[백업] 생성 실패: {e}")
            return False

    def load_from_config(self) -> bool:
        try:
            for name in self.SUPPORTED_SYSTEMS:
                data = self.config_manager.get(f'coordinate_definitions.{name}')
                if data and isinstance(data, dict):
                    self._definitions[name] = data
                else:
                    self._definitions[name] = self._create_default_definition(name)

            current = self.config_manager.get('coordinate_definitions.current')
            if current and current in self.SUPPORTED_SYSTEMS:
                self._current_system = current
            else:
                self._current_system = self.ROBOT_BASE

            return True
        except Exception as e:
            self._log(f"좌표계 설정 로드 실패: {e}")
            return False


    def get_system_type(self, name: str) -> Optional[str]:
        return self.SYSTEM_TYPES.get(name)

    def get_system_names(self) -> List[str]:
        return self.SUPPORTED_SYSTEMS.copy()

    def get_definition(self, name: str) -> Optional[Dict[str, Any]]:
        if name not in self.SUPPORTED_SYSTEMS:
            return None
        if name in self._definitions:
            return self._definitions[name].copy()
        return self._create_default_definition(name)

    def reset_to_defaults(self, name: str = None) -> bool:
        if name is None:
            for sys_name in self.SUPPORTED_SYSTEMS:
                self._definitions[sys_name] = self._create_default_definition(sys_name)
            self._current_system = self.ROBOT_BASE
            self._log("모든 좌표계 기본값으로 초기화")
            return True
        elif name in self.SUPPORTED_SYSTEMS:
            self._definitions[name] = self._create_default_definition(name)
            self._log(f"좌표계 {name} 기본값으로 초기화")
            return True
        else:
            self._log(f"지원하지 않는 좌표계: {name}")
            return False


    def set_ros_node(self, ros_node) -> None:
        self._ros_node = ros_node
        if ROS2_AVAILABLE and ros_node:
            self._tf_broadcaster = StaticTransformBroadcaster(ros_node)
            self._log("TF broadcaster 초기화 완료")

    def _euler_to_quaternion(self, rx: float, ry: float, rz: float) -> Tuple[float, float, float, float]:
        roll = math.radians(rx)
        pitch = math.radians(ry)
        yaw = math.radians(rz)

        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        qw = cr * cp * cy + sr * sp * sy
        qx = sr * cp * cy - cr * sp * sy
        qy = cr * sp * cy + sr * cp * sy
        qz = cr * cp * sy - sr * sp * cy

        return (qx, qy, qz, qw)

    def _create_transform_stamped(
        self,
        parent_frame: str,
        child_frame: str,
        pose: Dict[str, float]
    ) -> 'TransformStamped':
        if not ROS2_AVAILABLE:
            return None

        t = TransformStamped()
        t.header.stamp = self._ros_node.get_clock().now().to_msg()
        t.header.frame_id = parent_frame
        t.child_frame_id = child_frame

        t.transform.translation.x = pose['x'] / 1000.0
        t.transform.translation.y = pose['y'] / 1000.0
        t.transform.translation.z = pose['z'] / 1000.0

        qx, qy, qz, qw = self._euler_to_quaternion(pose['rx'], pose['ry'], pose['rz'])
        t.transform.rotation.x = qx
        t.transform.rotation.y = qy
        t.transform.rotation.z = qz
        t.transform.rotation.w = qw

        return t

    def publish_tf(self) -> bool:
        if not ROS2_AVAILABLE:
            self._log("ROS2를 사용할 수 없습니다")
            return False

        if not self._ros_node:
            self._log("ROS2 노드가 설정되지 않았습니다")
            return False

        if not self._tf_broadcaster:
            self._tf_broadcaster = StaticTransformBroadcaster(self._ros_node)

        transforms = []

        jig_landmark_data = self.get_scan_data(self.JIG_LANDMARK)
        if jig_landmark_data and jig_landmark_data.get('landmark'):
            landmark_pose = jig_landmark_data['landmark']
            t1 = self._create_transform_stamped(
                self.TF_FRAME_ROBOT_BASE,
                self.TF_FRAME_JIG_LANDMARK,
                landmark_pose
            )
            if t1:
                transforms.append(t1)
                self._log(f"TF: {self.TF_FRAME_ROBOT_BASE} → {self.TF_FRAME_JIG_LANDMARK}")

        jig_plate_data = self.get_scan_data(self.JIG_PLATE)
        jig_landmark_pose = jig_landmark_data.get('landmark') if jig_landmark_data else None

        if jig_plate_data and isinstance(jig_plate_data, list) and len(jig_plate_data) > 0:
            center_pose = self._calculate_center_pose(jig_plate_data)
            if center_pose:
                if jig_landmark_pose:
                    relative_pose = self._calculate_relative_pose(jig_landmark_pose, center_pose)
                else:
                    relative_pose = center_pose

                t2 = self._create_transform_stamped(
                    self.TF_FRAME_JIG_LANDMARK,
                    self.TF_FRAME_JIG_PLATE,
                    relative_pose
                )
                if t2:
                    transforms.append(t2)

                for i, data in enumerate(jig_plate_data, start=1):
                    landmark = data.get('landmark')
                    if landmark:
                        mark_relative = self._calculate_relative_pose(center_pose, landmark)
                        mark_frame = f"mark_jig_plate{i}"
                        t_mark = self._create_transform_stamped(
                            self.TF_FRAME_JIG_PLATE,
                            mark_frame,
                            mark_relative
                        )
                        if t_mark:
                            transforms.append(t_mark)

        if transforms:
            self._tf_broadcaster.sendTransform(transforms)
            self._log(f"TF 발행 완료 ({len(transforms)}개)")
            return True
        else:
            self._log("발행할 TF가 없습니다 (scan_data 미설정)")
            return False

    def _calculate_center_pose(self, scan_data_list: List[Dict]) -> Optional[Dict[str, float]]:
        if not scan_data_list:
            return None

        n = len(scan_data_list)
        sum_x = sum_y = sum_z = 0.0
        sum_rx = sum_ry = sum_rz = 0.0

        for data in scan_data_list:
            landmark = data.get('landmark', {})
            sum_x += landmark.get('x', 0.0)
            sum_y += landmark.get('y', 0.0)
            sum_z += landmark.get('z', 0.0)
            sum_rx += landmark.get('rx', 0.0)
            sum_ry += landmark.get('ry', 0.0)
            sum_rz += landmark.get('rz', 0.0)

        return {
            'x': sum_x / n,
            'y': sum_y / n,
            'z': sum_z / n,
            'rx': sum_rx / n,
            'ry': sum_ry / n,
            'rz': sum_rz / n
        }

    def _calculate_relative_pose(
        self,
        parent_pose: Dict[str, float],
        child_pose: Dict[str, float]
    ) -> Dict[str, float]:
        return {
            'x': child_pose['x'] - parent_pose['x'],
            'y': child_pose['y'] - parent_pose['y'],
            'z': child_pose['z'] - parent_pose['z'],
            'rx': child_pose['rx'] - parent_pose['rx'],
            'ry': child_pose['ry'] - parent_pose['ry'],
            'rz': child_pose['rz'] - parent_pose['rz']
        }

    def start_tf_publishing(self, interval_sec: float = 1.0) -> bool:
        if not ROS2_AVAILABLE or not self._ros_node:
            self._log("TF 발행을 시작할 수 없습니다")
            return False

        if self._tf_timer:
            self._tf_timer.cancel()

        self._tf_timer = self._ros_node.create_timer(interval_sec, self._tf_timer_callback)
        self._tf_enabled = True
        self._log(f"TF 발행 시작 (주기: {interval_sec}초)")
        return True

    def stop_tf_publishing(self) -> None:
        if self._tf_timer:
            self._tf_timer.cancel()
            self._tf_timer = None
        self._tf_enabled = False
        self._log("TF 발행 중지")

    def _tf_timer_callback(self) -> None:
        if self._tf_enabled:
            self.publish_tf()


    def compute_jig_plate_coordinates(self) -> bool:
        from ..tools.jig_plane_calculator import JigPlaneCalculator, Mark

        scan_data = self.get_scan_data(self.JIG_PLATE)
        if not scan_data or len(scan_data) != 4:
            self._log("jig_plate 좌표 계산에는 4개 landmark가 필요합니다")
            return False

        marks = [
            Mark(
                x=item['landmark']['x'],
                y=item['landmark']['y'],
                z=item['landmark']['z'],
                rx=item['landmark']['rx'],
                ry=item['landmark']['ry'],
                rz=item['landmark']['rz']
            )
            for item in scan_data
        ]

        calc = JigPlaneCalculator()
        calc.load_from_marks(marks)

        result = calc.to_full_dict()
        if result is None:
            self._log("jig_plate 좌표 계산 실패")
            return False

        if self.JIG_PLATE not in self._definitions:
            self._definitions[self.JIG_PLATE] = self._create_default_definition(self.JIG_PLATE)

        self._definitions[self.JIG_PLATE]['computed'] = result
        self._log(f"jig_plate 좌표 계산 완료: center=({result['plane_pose']['x']:.2f}, {result['plane_pose']['y']:.2f}, {result['plane_pose']['z']:.2f})")
        return True

    def get_computed_data(self, name: str) -> Optional[Dict[str, Any]]:
        if name in self._definitions:
            return self._definitions[name].get('computed')
        return None
