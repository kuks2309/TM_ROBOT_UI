# 제안 아키텍처

## 개요

현재 God Class 패턴의 MainWindow(2,114 lines)를 책임별로 분리하여, 테스트 가능하고 유지보수하기 쉬운 계층화된 아키텍처로 전환합니다.

## 설계 원칙

### 1. 관심사의 분리 (Separation of Concerns)
- **UI Layer**: 사용자 인터랙션만 담당
- **Service Layer**: 비즈니스 로직 처리
- **Data Layer**: 데이터 모델 및 영속성

### 2. 단일 책임 원칙 (Single Responsibility Principle)
- 각 클래스는 하나의 명확한 책임만 가짐
- 변경 이유는 단 하나여야 함

### 3. 의존성 역전 원칙 (Dependency Inversion Principle)
- 상위 모듈이 하위 모듈에 직접 의존하지 않음
- 인터페이스(콜백, 시그널)를 통한 간접 의존

### 4. 테스트 가능성 (Testability)
- 모든 서비스 클래스는 ROS 노드 Mock으로 단위 테스트 가능
- UI는 서비스 Mock으로 통합 테스트 가능

---

## 제안하는 파일 구조

```
/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/
├── main.py                                    # 진입점 (변경 없음)
│
├── tm_task_manager/
│   ├── __init__.py                            # 패키지 초기화
│   │
│   ├── main_window.py                         # UI 관리만 (~800-1000 lines)
│   │   └─ Qt 시그널/슬롯, 위젯 업데이트, 다이얼로그
│   │
│   ├── services/                              # ✨ 새로 추가: 비즈니스 로직 레이어
│   │   ├── __init__.py
│   │   ├── teaching_service.py                # 티칭 모드 제어
│   │   ├── coordinate_transformer.py          # 좌표계 변환 수학
│   │   ├── config_manager.py                  # positions.yaml 관리
│   │   ├── network_manager.py                 # 네트워크 유틸리티
│   │   └── vision_manager.py                  # 비전 상태 관리
│   │
│   ├── widgets/                               # ✨ 새로 추가: 재사용 가능 위젯
│   │   ├── __init__.py
│   │   ├── parameter_editor.py                # 파라미터 편집 위젯
│   │   └── global_variable_widget.py          # 글로벌 변수 위젯
│   │
│   ├── recipe_manager.py                      # 📝 확장: 파일 관리 추가
│   ├── job_executor.py                        # 🔧 수정: VisionManager 사용
│   ├── robot_connection.py                    # ✓ 유지
│   ├── global_variable_script.py              # ✓ 유지
│   └── global_variable_service.py             # ✓ 유지
│
├── launch/                                    # ✓ 유지
├── ui/                                        # ✓ 유지
├── config/                                    # ✓ 유지
├── tests/                                     # ✨ 새로 추가: 테스트
│   ├── __init__.py
│   ├── test_teaching_service.py
│   ├── test_vision_manager.py
│   ├── test_config_manager.py
│   └── mocks/
│       └── mock_ros_node.py
└── docs/                                      # ✓ 현재 작업 중
```

---

## 계층별 상세 설계

### Layer 1: UI Layer (사용자 인터페이스)

#### MainWindow (main_window.py)
**책임:** Qt UI 관리만

**현재:** 2,114 lines (8가지 책임)
**목표:** ~800-1000 lines (1가지 책임)

```python
class MainWindow(QMainWindow):
    """메인 윈도우 - UI 관리만 담당"""

    def __init__(self):
        super().__init__()
        self._init_services()
        self._init_ui()
        self._connect_signals()

    def _init_services(self):
        """서비스 레이어 초기화"""
        self.ros_node = TaskManagerNode()
        self.config_manager = ConfigManager()
        self.vision_manager = VisionManager()
        self.teaching_service = TeachingService(self.ros_node)
        self.recipe_manager = RecipeManager()
        self.job_executor = JobExecutor(self.ros_node, self.vision_manager)

    def _init_ui(self):
        """UI 초기화"""
        # Qt Designer 파일 로드
        # 위젯 초기화
        # 탭/메뉴/툴바 설정

    def _connect_signals(self):
        """시그널/슬롯 연결"""
        # 버튼 클릭 → 서비스 호출
        self.btn_teach_position.clicked.connect(self._on_teach_position)
        self.btn_jog_x_plus.clicked.connect(lambda: self._on_jog('X', 1))

        # 서비스 콜백 → UI 업데이트
        self.vision_manager.tag_updated.connect(self._update_tag_table)
        self.job_executor.job_started.connect(self._on_job_started)

    # ==================== 이벤트 핸들러 ====================
    def _on_teach_position(self):
        """위치 티칭 버튼 클릭"""
        motion_type = self.param_widgets['motion_type'].currentText()
        params = self.teaching_service.teach_current_position(motion_type)
        self._update_param_widgets(params)  # UI 업데이트만

    def _on_jog(self, axis, direction):
        """Jog 버튼 클릭"""
        step_size = self.spinBox_jogStep.value()
        success, msg = self.teaching_service.jog_tcp(axis, direction, step_size)
        self.statusBar().showMessage(msg)  # UI 업데이트만

    # ==================== UI 업데이트 ====================
    def _update_param_widgets(self, params):
        """파라미터 위젯 값 업데이트"""
        for key, value in params.items():
            if key in self.param_widgets:
                self.param_widgets[key].setValue(value)

    def _update_tag_table(self, tag_id, tag_data):
        """AR 태그 테이블 업데이트"""
        # 테이블 위젯 업데이트
```

**제거되는 메서드:**
- ✗ `_on_jog()` 내부 회전 행렬 계산 → TeachingService
- ✗ `_load_robot_ip_from_config()` → ConfigManager
- ✗ `_on_find_robot_ip()` → NetworkManager
- ✗ `_update_tag_pose()` 내부 상태 저장 → VisionManager
- ✗ `_load_recent_files()` → RecipeManager

**남아있는 책임:**
- ✓ Qt 위젯 관리
- ✓ 시그널/슬롯 연결
- ✓ UI 상태 업데이트 (서비스 결과 표시)
- ✓ 다이얼로그 표시

---

#### ParameterEditorWidget (widgets/parameter_editor.py)
**책임:** Job 타입별 파라미터 편집 UI

```python
class ParameterEditorWidget(QWidget):
    """동적 파라미터 편집 위젯"""

    parameters_changed = pyqtSignal(dict)  # 파라미터 변경 시그널

    def __init__(self, parent=None):
        super().__init__(parent)
        self.param_widgets = {}
        self._init_ui()

    def display_parameters(self, job: Job):
        """Job 타입에 따라 파라미터 위젯 동적 생성"""
        self._clear_widgets()

        if job.type == 'move_to_point':
            self._add_combo('motion_type', ['joint', 'tcp'])
            self._add_spinbox('X', -180, 180, job.params.get('X', 0))
            self._add_spinbox('Y', -180, 180, job.params.get('Y', 0))
            # ...

        elif job.type == 'scan_ar_tag':
            self._add_spinbox('target_tag_id', 0, 100)
            self._add_spinbox('timeout', 1, 60)

    def get_parameters(self) -> dict:
        """현재 UI 값을 딕셔너리로 반환"""
        params = {}
        for key, widget in self.param_widgets.items():
            if isinstance(widget, QDoubleSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QComboBox):
                params[key] = widget.currentText()
        return params

    def _add_spinbox(self, name, min_val, max_val, default=0):
        """SpinBox 위젯 추가"""
        # ...

    def _add_combo(self, name, options):
        """ComboBox 위젯 추가"""
        # ...
```

**장점:**
- 재사용 가능 (다른 프로젝트에서도 사용 가능)
- 독립적 테스트 가능
- MainWindow 코드 ~170 lines 감소

---

### Layer 2: Service Layer (비즈니스 로직)

#### TeachingService (services/teaching_service.py)
**책임:** 티칭 모드에서 로봇 제어

```python
class TeachingService:
    """티칭 모드 로봇 제어 서비스"""

    def __init__(self, ros_node, coordinate_transformer=None):
        """
        Args:
            ros_node: TaskManagerNode 인스턴스
            coordinate_transformer: 좌표 변환기 (테스트용 Mock 가능)
        """
        self.ros_node = ros_node
        self.transformer = coordinate_transformer or CoordinateTransformer()

    def teach_current_position(self, motion_type: str) -> dict:
        """
        현재 로봇 위치를 읽어서 파라미터로 반환

        Args:
            motion_type: 'joint' 또는 'tcp'

        Returns:
            {'X': 10.5, 'Y': 20.3, 'Z': 30.1, ...}
        """
        if motion_type == 'joint':
            return self._teach_joint_position()
        else:
            return self._teach_tcp_position()

    def _teach_joint_position(self) -> dict:
        """Joint 각도 티칭"""
        joint_pos = self.ros_node.current_joint_position
        if not joint_pos or len(joint_pos) < 6:
            raise ValueError("로봇 Joint 위치를 읽을 수 없습니다")

        return {
            'X': round(joint_pos[0], 2),  # 이미 degree로 변환됨
            'Y': round(joint_pos[1], 2),
            'Z': round(joint_pos[2], 2),
            'A': round(joint_pos[3], 2),
            'B': round(joint_pos[4], 2),
            'C': round(joint_pos[5], 2),
        }

    def _teach_tcp_position(self) -> dict:
        """TCP 좌표 티칭"""
        tcp_pos = self.ros_node.current_tcp_pose
        if not tcp_pos:
            raise ValueError("로봇 TCP 위치를 읽을 수 없습니다")

        return {
            'X': round(tcp_pos[0], 2),
            'Y': round(tcp_pos[1], 2),
            'Z': round(tcp_pos[2], 2),
            'A': round(tcp_pos[3], 2),
            'B': round(tcp_pos[4], 2),
            'C': round(tcp_pos[5], 2),
        }

    def move_to_parameters(self, params: dict) -> tuple[bool, str]:
        """
        파라미터 값으로 로봇 이동 (티칭 확인용)

        Args:
            params: {'motion_type': 'joint', 'X': 10, 'Y': 20, ...}

        Returns:
            (success: bool, message: str)
        """
        motion_type = params.get('motion_type', 'joint')

        if motion_type == 'joint':
            return self._move_joint(params)
        else:
            return self._move_tcp(params)

    def _move_joint(self, params: dict) -> tuple[bool, str]:
        """Joint 각도로 이동"""
        import math
        from tm_msgs.srv import SetPositions

        positions = [
            params.get('X', 0.0) * math.pi / 180.0,
            params.get('Y', 0.0) * math.pi / 180.0,
            params.get('Z', 0.0) * math.pi / 180.0,
            params.get('A', 0.0) * math.pi / 180.0,
            params.get('B', 0.0) * math.pi / 180.0,
            params.get('C', 0.0) * math.pi / 180.0,
        ]

        velocity = params.get('velocity', 10) / 100.0
        return self.ros_node._move_to_position(
            SetPositions.Request.PTP_J,
            positions,
            velocity=velocity,
            acc_time=0.2
        )

    def _move_tcp(self, params: dict) -> tuple[bool, str]:
        """TCP 좌표로 이동"""
        from tm_msgs.srv import SetPositions

        positions = [
            params.get('X', 0.0) / 1000.0,
            params.get('Y', 0.0) / 1000.0,
            params.get('Z', 0.0) / 1000.0,
            params.get('A', 0.0),
            params.get('B', 0.0),
            params.get('C', 0.0),
        ]

        velocity = params.get('velocity', 100)  # mm/s
        return self.ros_node._move_to_position(
            SetPositions.Request.PTP_T,
            positions,
            velocity=velocity,
            acc_time=0.2
        )

    def jog_tcp(self, axis: str, direction: int, step_size: float) -> tuple[bool, str]:
        """
        TCP 좌표계 기준 Jog 제어

        Args:
            axis: 'X', 'Y', 'Z', 'RX', 'RY', 'RZ'
            direction: 1 (정방향) 또는 -1 (역방향)
            step_size: 이동 거리 (mm) 또는 회전 각도 (degree)

        Returns:
            (success: bool, message: str)
        """
        tcp_pos = self.ros_node.current_tcp_pose
        if not tcp_pos or len(tcp_pos) < 6:
            return False, "로봇 TCP 위치를 읽을 수 없습니다"

        target_pos = list(tcp_pos)  # 복사

        # Tool 좌표계 delta 계산
        tool_delta = [0.0, 0.0, 0.0]
        if axis == 'X':
            tool_delta[0] = direction * step_size
        elif axis == 'Y':
            tool_delta[1] = direction * step_size
        elif axis == 'Z':
            tool_delta[2] = direction * step_size

        # Tool 좌표계 → Base 좌표계 변환
        orientation = [target_pos[3], target_pos[4], target_pos[5]]
        base_delta = self.transformer.transform_tool_to_base(tool_delta, orientation)

        # 새로운 위치 계산
        target_pos[0] += base_delta[0]
        target_pos[1] += base_delta[1]
        target_pos[2] += base_delta[2]

        # 회전 축 처리
        if axis == 'RX':
            target_pos[3] += direction * step_size
        elif axis == 'RY':
            target_pos[4] += direction * step_size
        elif axis == 'RZ':
            target_pos[5] += direction * step_size

        # 로봇 이동
        from tm_msgs.srv import SetPositions
        positions = [p / 1000.0 if i < 3 else p for i, p in enumerate(target_pos)]

        return self.ros_node._move_to_position(
            SetPositions.Request.PTP_T,
            positions,
            velocity=50,  # mm/s
            acc_time=0.1
        )
```

**장점:**
- 테스트 가능: ROS 노드를 Mock으로 대체 가능
- 재사용 가능: CLI 툴에서도 사용 가능
- MainWindow 코드 ~420 lines 감소

---

#### CoordinateTransformer (services/coordinate_transformer.py)
**책임:** 좌표계 변환 수학 계산

```python
import math

class CoordinateTransformer:
    """좌표계 변환 유틸리티"""

    @staticmethod
    def euler_to_rotation_matrix(rx: float, ry: float, rz: float) -> list[list[float]]:
        """
        오일러각(degree)을 회전 행렬로 변환

        Args:
            rx, ry, rz: X, Y, Z 축 회전 각도 (degree)

        Returns:
            3x3 회전 행렬 [[R00, R01, R02], [R10, R11, R12], [R20, R21, R22]]
        """
        rx_rad = rx * math.pi / 180.0
        ry_rad = ry * math.pi / 180.0
        rz_rad = rz * math.pi / 180.0

        cos_rx, sin_rx = math.cos(rx_rad), math.sin(rx_rad)
        cos_ry, sin_ry = math.cos(ry_rad), math.sin(ry_rad)
        cos_rz, sin_rz = math.cos(rz_rad), math.sin(rz_rad)

        R = [
            [
                cos_rz * cos_ry,
                cos_rz * sin_ry * sin_rx - sin_rz * cos_rx,
                cos_rz * sin_ry * cos_rx + sin_rz * sin_rx
            ],
            [
                sin_rz * cos_ry,
                sin_rz * sin_ry * sin_rx + cos_rz * cos_rx,
                sin_rz * sin_ry * cos_rx - cos_rz * sin_rx
            ],
            [
                -sin_ry,
                cos_ry * sin_rx,
                cos_ry * cos_rx
            ]
        ]

        return R

    @staticmethod
    def transform_tool_to_base(tool_delta: list[float], orientation: list[float]) -> list[float]:
        """
        Tool 좌표계 delta를 Base 좌표계로 변환

        Args:
            tool_delta: [dx, dy, dz] in Tool frame (mm)
            orientation: [rx, ry, rz] current TCP orientation (degree)

        Returns:
            [dx, dy, dz] in Base frame (mm)
        """
        R = CoordinateTransformer.euler_to_rotation_matrix(
            orientation[0], orientation[1], orientation[2]
        )

        base_delta = [
            R[0][0] * tool_delta[0] + R[0][1] * tool_delta[1] + R[0][2] * tool_delta[2],
            R[1][0] * tool_delta[0] + R[1][1] * tool_delta[1] + R[1][2] * tool_delta[2],
            R[2][0] * tool_delta[0] + R[2][1] * tool_delta[1] + R[2][2] * tool_delta[2],
        ]

        return base_delta

    @staticmethod
    def quaternion_to_euler(qx: float, qy: float, qz: float, qw: float) -> list[float]:
        """
        쿼터니언을 오일러각(degree)으로 변환

        Args:
            qx, qy, qz, qw: 쿼터니언 성분

        Returns:
            [rx, ry, rz] in degrees
        """
        # Roll (X축)
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
        rx = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (Y축)
        sinp = 2 * (qw * qy - qz * qx)
        if abs(sinp) >= 1:
            ry = math.copysign(math.pi / 2, sinp)
        else:
            ry = math.asin(sinp)

        # Yaw (Z축)
        siny_cosp = 2 * (qw * qz + qx * qy)
        cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
        rz = math.atan2(siny_cosp, cosy_cosp)

        return [
            rx * 180.0 / math.pi,
            ry * 180.0 / math.pi,
            rz * 180.0 / math.pi
        ]
```

**장점:**
- 순수 함수 (static methods): 테스트 용이
- 재사용 가능: 다른 로봇 프로젝트에서도 사용 가능
- MainWindow 코드 ~80 lines 감소

---

#### VisionManager (services/vision_manager.py)
**책임:** 비전 시스템 상태 관리

```python
from PyQt5.QtCore import QObject, pyqtSignal

class VisionManager(QObject):
    """비전 시스템 상태 관리 (AR 태그 감지 등)"""

    tag_updated = pyqtSignal(str, dict)  # (tag_id, tag_data)
    tag_removed = pyqtSignal(str)  # (tag_id)

    def __init__(self):
        super().__init__()
        self.detected_tags: dict[str, dict] = {}

    def update_tag_pose(self, tag_id: str, pose_data: dict):
        """
        AR 태그 포즈 업데이트

        Args:
            tag_id: 태그 ID (문자열)
            pose_data: {'x': float, 'y': float, 'z': float, 'pose': PoseStamped}
        """
        self.detected_tags[tag_id] = pose_data
        self.tag_updated.emit(tag_id, pose_data)

    def get_tag(self, tag_id: str) -> dict | None:
        """
        특정 태그 데이터 반환

        Args:
            tag_id: 태그 ID

        Returns:
            {'x': float, 'y': float, 'z': float, 'pose': PoseStamped} or None
        """
        return self.detected_tags.get(tag_id)

    def get_all_tags(self) -> dict[str, dict]:
        """모든 태그 데이터 반환"""
        return self.detected_tags.copy()

    def clear_tags(self):
        """모든 태그 데이터 삭제"""
        tag_ids = list(self.detected_tags.keys())
        self.detected_tags.clear()
        for tag_id in tag_ids:
            self.tag_removed.emit(tag_id)

    def remove_tag(self, tag_id: str):
        """특정 태그 데이터 삭제"""
        if tag_id in self.detected_tags:
            del self.detected_tags[tag_id]
            self.tag_removed.emit(tag_id)
```

**변경 사항:**
- `MainWindow.detected_tags` → `VisionManager.detected_tags`
- `MainWindow._update_tag_pose()` → `VisionManager.update_tag_pose()`
- `JobExecutor.__init__(detected_tags=dict)` → `JobExecutor.__init__(vision_manager=VisionManager)`

**장점:**
- 도메인 데이터가 UI에서 분리됨
- JobExecutor의 의존성 명확화 (dict → VisionManager)
- Qt Signal을 통한 느슨한 결합

---

#### ConfigManager (services/config_manager.py)
**책임:** positions.yaml 관리

```python
import os
import yaml
from typing import Any

class ConfigManager:
    """positions.yaml 설정 파일 관리"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'config', 'positions.yaml'
            )
        self.config_path = config_path
        self._config_cache = None

    def _load_config(self) -> dict:
        """설정 파일 로드 (캐시 사용)"""
        if self._config_cache is None:
            if not os.path.exists(self.config_path):
                self._config_cache = {}
            else:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config_cache = yaml.safe_load(f) or {}
        return self._config_cache

    def _save_config(self, config: dict):
        """설정 파일 저장"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        self._config_cache = config

    def reload(self):
        """설정 파일 재로드 (캐시 무효화)"""
        self._config_cache = None
        return self._load_config()

    # ==================== Robot IP ====================
    def get_robot_ip(self) -> str | None:
        """로봇 IP 주소 반환"""
        config = self._load_config()
        return config.get('robot', {}).get('ip')

    def set_robot_ip(self, ip: str):
        """로봇 IP 주소 저장"""
        config = self._load_config()
        if 'robot' not in config:
            config['robot'] = {}
        config['robot']['ip'] = ip
        self._save_config(config)

    # ==================== HOME Position ====================
    def get_home_position(self) -> dict:
        """
        HOME 위치 반환

        Returns:
            {'motion_type': 'joint', 'X': 0, 'Y': 0, 'Z': 90, ...}
        """
        config = self._load_config()
        return config.get('positions', {}).get('home', {})

    def set_home_position(self, values: dict):
        """
        HOME 위치 저장

        Args:
            values: {'motion_type': 'joint', 'X': 0, 'Y': 0, ...}
        """
        config = self._load_config()
        if 'positions' not in config:
            config['positions'] = {}
        config['positions']['home'] = values
        self._save_config(config)

    # ==================== 일반 Key-Value ====================
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        점(.) 구분자로 중첩된 키 읽기

        Example:
            config_manager.get('robot.ip')
            config_manager.get('positions.home.X')
        """
        config = self._load_config()
        keys = key_path.split('.')
        value = config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key_path: str, value: Any):
        """
        점(.) 구분자로 중첩된 키 쓰기

        Example:
            config_manager.set('robot.port', 5890)
        """
        config = self._load_config()
        keys = key_path.split('.')
        target = config
        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value
        self._save_config(config)
```

**장점:**
- YAML 접근 중복 제거 (3곳 → 1곳)
- 캐시 메커니즘으로 성능 향상
- 테스트 가능 (Mock 파일 경로 사용)
- MainWindow 코드 ~80 lines 감소

---

#### NetworkManager (services/network_manager.py)
**책임:** 네트워크 유틸리티

```python
import socket
import netifaces
from concurrent.futures import ThreadPoolExecutor, as_completed

class NetworkManager:
    """네트워크 관련 유틸리티"""

    @staticmethod
    def get_all_network_interfaces() -> list[tuple[str, str]]:
        """
        모든 네트워크 인터페이스 반환

        Returns:
            [(interface_name, ip_address), ...]
            예: [('eth0', '192.168.1.100'), ('wlan0', '10.0.0.5')]
        """
        interfaces = []
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        if ip and ip != '127.0.0.1':
                            interfaces.append((iface, ip))
        except Exception as e:
            print(f"네트워크 인터페이스 조회 실패: {e}")

        return interfaces

    @staticmethod
    def get_local_ip(preferred_wired: bool = True) -> str | None:
        """
        로컬 IP 자동 감지

        Args:
            preferred_wired: True이면 유선(ethX) 우선, False이면 무선(wlanX) 우선

        Returns:
            IP 주소 문자열 또는 None
        """
        interfaces = NetworkManager.get_all_network_interfaces()

        if not interfaces:
            return None

        # 우선순위 정렬
        if preferred_wired:
            wired = [ip for name, ip in interfaces if 'eth' in name or 'enp' in name]
            wireless = [ip for name, ip in interfaces if 'wlan' in name or 'wlp' in name]
            candidates = wired + wireless
        else:
            wireless = [ip for name, ip in interfaces if 'wlan' in name or 'wlp' in name]
            wired = [ip for name, ip in interfaces if 'eth' in name or 'enp' in name]
            candidates = wireless + wired

        # 나머지
        other = [ip for name, ip in interfaces
                 if not any(prefix in name for prefix in ['eth', 'enp', 'wlan', 'wlp'])]
        candidates.extend(other)

        return candidates[0] if candidates else None

    @staticmethod
    def scan_for_robot(subnet: str, ports: list[int] = None, timeout: float = 0.1,
                       max_workers: int = 50) -> list[str]:
        """
        서브넷에서 로봇 IP 스캔 (병렬 처리)

        Args:
            subnet: 서브넷 주소 (예: '192.168.1')
            ports: 스캔할 포트 목록 (기본: [5890, 5891])
            timeout: 연결 타임아웃 (초)
            max_workers: 최대 동시 스레드 수

        Returns:
            발견된 IP 주소 목록 (예: ['192.168.1.10', '192.168.1.50'])
        """
        if ports is None:
            ports = [5890, 5891]  # TM Robot 기본 포트

        found_ips = set()

        def check_port(ip: str, port: int) -> str | None:
            """특정 IP:포트 연결 시도"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return ip
            except Exception:
                pass
            return None

        # 병렬 스캔
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(1, 255):
                ip = f"{subnet}.{i}"
                for port in ports:
                    futures.append(executor.submit(check_port, ip, port))

            for future in as_completed(futures):
                result = future.result()
                if result:
                    found_ips.add(result)

        return sorted(list(found_ips))

    @staticmethod
    def parse_subnet(ip: str) -> str:
        """
        IP 주소에서 서브넷 추출

        Args:
            ip: 전체 IP (예: '192.168.1.100')

        Returns:
            서브넷 (예: '192.168.1')
        """
        parts = ip.split('.')
        if len(parts) >= 3:
            return '.'.join(parts[:3])
        return ''
```

**장점:**
- UI와 완전 분리 (정적 메서드)
- 병렬 스캔으로 성능 향상
- CLI 툴에서 재사용 가능
- MainWindow 코드 ~200 lines 감소

---

### Layer 3: Data Layer (데이터 모델 및 영속성)

#### RecipeManager (확장)
**기존 책임:** Recipe/Job 모델 + YAML 저장/로드
**추가 책임:** 최근 파일 관리

```python
class RecipeManager:
    """Recipe 관리 + 파일 관리"""

    def __init__(self):
        self.current_recipe = None
        self.recipe_path = None
        self.recent_files: list[str] = []
        self._load_recent_files()

    # ==================== 기존 메서드 (유지) ====================
    def new_recipe(self, name: str = "New Recipe"):
        """새로운 Recipe 생성"""
        # ...

    def load_recipe(self, file_path: str):
        """Recipe 파일 로드"""
        # ...
        self.add_to_recent_files(file_path)  # ✨ 추가

    def save_recipe(self, file_path: str):
        """Recipe 파일 저장"""
        # ...
        self.add_to_recent_files(file_path)  # ✨ 추가

    # ==================== 새로 추가: 최근 파일 관리 ====================
    def _get_recent_files_path(self) -> str:
        """최근 파일 목록 저장 경로"""
        return os.path.join(
            os.path.dirname(__file__), '..', 'config', '.recent_files.txt'
        )

    def _load_recent_files(self):
        """최근 파일 목록 로드"""
        recent_file_path = self._get_recent_files_path()
        if os.path.exists(recent_file_path):
            with open(recent_file_path, 'r', encoding='utf-8') as f:
                self.recent_files = [
                    line.strip() for line in f.readlines()
                    if line.strip() and os.path.exists(line.strip())
                ]
        else:
            self.recent_files = []

    def _save_recent_files(self):
        """최근 파일 목록 저장"""
        recent_file_path = self._get_recent_files_path()
        os.makedirs(os.path.dirname(recent_file_path), exist_ok=True)
        with open(recent_file_path, 'w', encoding='utf-8') as f:
            for file_path in self.recent_files[:10]:  # 최대 10개
                f.write(file_path + '\n')

    def add_to_recent_files(self, file_path: str):
        """최근 파일에 추가 (중복 제거 + MRU 순서)"""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:10]  # 최대 10개 유지
        self._save_recent_files()

    def get_recent_files(self) -> list[str]:
        """최근 파일 목록 반환"""
        return self.recent_files.copy()

    def clear_recent_files(self):
        """최근 파일 목록 삭제"""
        self.recent_files = []
        self._save_recent_files()
```

**장점:**
- 파일 관리 책임이 RecipeManager로 통합
- MainWindow 코드 ~90 lines 감소

---

#### JobExecutor (수정)
**변경 사항:** `detected_tags` dict → `VisionManager` 객체

```python
class JobExecutor:
    """Job 실행 엔진"""

    def __init__(self, ros_node, vision_manager):
        """
        Args:
            ros_node: TaskManagerNode 인스턴스
            vision_manager: VisionManager 인스턴스 (이전: detected_tags dict)
        """
        self.ros_node = ros_node
        self.vision_manager = vision_manager  # ✨ 변경
        # ...

    def _exec_scan_ar_tag(self, params):
        """AR 태그 스캔 작업"""
        target_id = str(params.get('target_tag_id', 0))
        timeout = params.get('timeout', 10)

        # ✨ 변경: dict 직접 접근 → VisionManager 메서드 호출
        tag_data = self.vision_manager.get_tag(target_id)

        if tag_data is not None:
            self._log(f"AR 태그 {target_id} 감지: {tag_data}")
            return True
        else:
            self._log(f"AR 태그 {target_id} 감지 실패 (timeout: {timeout}s)")
            return False
```

**장점:**
- 의존성 명확화 (dict → VisionManager 인터페이스)
- 테스트 가능 (VisionManager Mock 사용)

---

## 의존성 다이어그램 (개선 후)

```
┌─────────────────────────────────────────────────────────┐
│                     main.py                             │
│  - ROS2 init                                            │
│  - QApplication init                                    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              MainWindow (UI Layer)                      │
│  - Qt 위젯 관리                                          │
│  - 시그널/슬롯 연결                                       │
│  - UI 상태 업데이트                                       │
└─────────┬────────────┬────────────┬──────────────┬──────┘
          │            │            │              │
          ▼            ▼            ▼              ▼
    ┌──────────┐  ┌──────────┐ ┌─────────┐  ┌─────────────┐
    │Parameter │  │ Global   │ │ Recipe  │  │    Job      │
    │ Editor   │  │ Variable │ │ Manager │  │  Executor   │
    │ Widget   │  │  Widget  │ └─────────┘  └──────┬──────┘
    └──────────┘  └──────────┘                     │
                                                    │
          ┌─────────────────────────────────────────┤
          │                                         │
          ▼                                         ▼
┌─────────────────────────────────────────────────────────┐
│               Service Layer                             │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Teaching     │  │  Vision      │  │   Config     │ │
│  │  Service      │  │  Manager     │  │   Manager    │ │
│  └───────┬───────┘  └──────────────┘  └──────────────┘ │
│          │                                              │
│          ▼                                              │
│  ┌───────────────┐  ┌──────────────┐                   │
│  │ Coordinate    │  │   Network    │                   │
│  │ Transformer   │  │   Manager    │                   │
│  └───────────────┘  └──────────────┘                   │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
          ┌────────────────┐
          │ TaskManagerNode│
          │    (ROS2)      │
          └────────────────┘
```

**개선 사항:**
1. ✓ 계층 분리: UI → Service → Data
2. ✓ 단방향 의존성: 상위 → 하위만 의존
3. ✓ 느슨한 결합: 인터페이스(콜백, 시그널)를 통한 통신
4. ✓ 테스트 가능: 각 레이어 독립적 테스트

---

## 다음 문서

- [리팩토링 마스터 플랜](../refactoring/master_plan.md) - 단계별 실행 계획
- [1단계: 서비스 레이어 분리](../refactoring/phase1_service_layer.md)
- [테스트 작성 가이드](../guides/testing.md)
