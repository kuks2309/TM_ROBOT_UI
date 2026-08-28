# 현재 아키텍처 분석

## 개요

TM Robot Task Manager는 Techman Robot의 작업(Task)을 관리하는 ROS2 기반 GUI 애플리케이션입니다.

**주요 기능:**
- Recipe 기반 작업 시퀀스 편집
- 로봇 위치 티칭 (Teaching Mode)
- 자동 작업 실행 (Execution Mode)
- AR 태그 기반 비전 시스템 통합
- 글로벌 변수 읽기/쓰기

## 파일 구조

```
/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/
├── main.py                                    # 진입점
├── tm_task_manager/
│   ├── __init__.py                            # 패키지 초기화
│   ├── main_window.py                         # 메인 UI (2,114 lines) ⚠️
│   ├── recipe_manager.py                      # Recipe/Job 모델 + YAML 저장
│   ├── job_executor.py                        # 작업 실행 엔진
│   ├── robot_connection.py                    # ROS2 연결 관리
│   ├── global_variable_script.py              # 글로벌 변수 I/O
│   └── global_variable_service.py             # 글로벌 변수 서비스
├── launch/
│   ├── task_manager.launch.py                 # Task Manager 단독 실행
│   └── tm_system.launch.py                    # 전체 시스템 실행
├── ui/
│   └── main_window.ui                         # Qt Designer UI (1,762 lines)
├── config/
│   ├── positions.yaml                         # 로봇 IP, HOME 위치
│   └── recipes/                               # 사용자 Recipe 파일
│       └── pallet_pickup_example.yaml
└── docs/                                      # 문서 (현재 작성 중)
```

## 컴포넌트 분석

### 1. main.py
**역할:** ROS2 노드 초기화 + PyQt5 애플리케이션 실행

```python
def main():
    rclpy.init()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # ROS2 spin을 Qt 타이머로 처리
    timer = QTimer()
    timer.timeout.connect(lambda: rclpy.spin_once(window.ros_node, timeout_sec=0))
    timer.start(10)

    sys.exit(app.exec_())
```

**상태:** 정상 - 변경 불필요

---

### 2. tm_task_manager/main_window.py ⚠️ 문제 파일

**크기:** 2,114 lines
**책임:** 8가지 (God Class 패턴)

#### 2.1 책임 분석

| 책임 | 라인 범위 | 코드량 | 문제점 |
|------|----------|--------|--------|
| **1. Qt UI 관리** | 415-1450 | ~1000 lines | ✓ 정상 (유지) |
| **2. 로봇 모션 제어** | 1259-1686 | ~420 lines | ✗ 비즈니스 로직이 UI에 혼재 |
| **3. 네트워크 설정** | 500-713 | ~200 lines | ✗ 유틸리티가 UI에 혼재 |
| **4. 설정 파일 관리** | 570-606, 1715-1747 | ~80 lines | ✗ 중복된 YAML 접근 |
| **5. 파일 관리** | 1810-1903 | ~90 lines | ✗ RecipeManager 책임 침범 |
| **6. 비전 상태 관리** | 759-813 | ~60 lines | ✗ 도메인 데이터가 UI에 저장 |
| **7. 파라미터 UI** | 1090-1257 | ~170 lines | △ 위젯 분리 고려 |
| **8. 글로벌 변수 UI** | 1913-2062 | ~150 lines | △ 위젯 분리 고려 |

#### 2.2 주요 메서드 및 문제점

##### 로봇 모션 제어 (분리 필요)
```python
def _on_teach_position(self):
    """현재 로봇 위치를 파라미터로 입력"""
    # 문제: 로봇 상태 읽기 + UI 업데이트가 혼재
    if self.current_joint_position:
        self.param_widgets['X'].setValue(self.current_joint_position[0])
        # ...

def _on_move_to_params(self):
    """파라미터 값으로 로봇 이동"""
    # 문제: 좌표 변환 + 모션 명령이 UI 코드에 존재
    positions = [x * math.pi / 180.0, ...]
    success, msg = self._move_to_position(SetPositions.Request.PTP_J, positions)

def _on_jog(self, axis, direction):
    """TCP 좌표계 Jog 제어"""
    # 문제: 회전 행렬 계산이 UI 코드에 존재 (40+ lines)
    R = [[cos_rz*cos_ry, ...], [...], [...]]
    base_delta = [R[0][0]*tool_delta[0] + ...]
```

##### 비전 상태 관리 (분리 필요)
```python
def __init__(self):
    self.detected_tags = {}  # 문제: UI에 도메인 데이터 저장

def _update_tag_pose(self, pose_msg):
    """AR 태그 포즈 업데이트"""
    # 문제: JobExecutor가 이 딕셔너리를 직접 참조
    self.detected_tags[tag_id] = {'x': x, 'y': y, 'z': z}
```

##### 설정 파일 관리 (분리 필요)
```python
def _load_robot_ip_from_config(self):
    config_path = os.path.join(..., 'config', 'positions.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    # 문제: 동일한 YAML 파일을 여러 메서드에서 중복 접근

def _load_home_from_config(self):
    config_path = os.path.join(..., 'config', 'positions.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    # 문제: 위와 동일한 패턴 반복
```

---

### 3. tm_task_manager/recipe_manager.py ✓

**역할:** Recipe 및 Job 데이터 모델 + YAML 저장/로드

**주요 클래스:**
```python
class Job:
    """개별 작업 단위"""
    id: int
    name: str
    type: str  # 'go_home', 'move_to_point', 'scan_ar_tag', ...
    params: dict
    caption: str

class Recipe:
    """작업 시퀀스"""
    name: str
    jobs: List[Job]

class RecipeManager:
    """Recipe CRUD 관리"""
    def new_recipe(self)
    def load_recipe(self, file_path)
    def save_recipe(self, file_path)
    def add_job(self, job_type)
    def delete_job(self, job_id)
```

**상태:** 양호
**개선 사항:** 최근 파일 관리 기능 추가 필요 (현재 MainWindow에 있음)

---

### 4. tm_task_manager/job_executor.py ✓

**역할:** Recipe의 Job을 순차 실행

**주요 메서드:**
```python
class JobExecutor:
    def __init__(self, ros_node, detected_tags):
        self.ros_node = ros_node
        self.detected_tags = detected_tags  # ⚠️ MainWindow 직접 참조

    def run(self):
        """Recipe 실행 시작"""

    def _execute_next_job(self):
        """다음 Job 실행"""

    def _execute_job(self, job):
        """Job 타입별 라우팅"""
        if job.type == 'go_home':
            return self._exec_go_home(job.params)
        elif job.type == 'scan_ar_tag':
            return self._exec_scan_ar_tag(job.params)
        # ...

    def _exec_scan_ar_tag(self, params):
        """AR 태그 스캔 작업"""
        target_id = str(params.get('target_tag_id', 0))
        if target_id in self.detected_tags:  # ⚠️ MainWindow 데이터 직접 접근
            tag_data = self.detected_tags[target_id]
```

**상태:** 양호 (구조는 좋음)
**문제점:** `detected_tags` 직접 참조 - VisionManager로 변경 필요

---

### 5. tm_task_manager/robot_connection.py ✓

**역할:** ROS2 TaskManagerNode와의 연결 관리

```python
class RobotConnectionManager:
    def __init__(self, ros_node):
        self.ros_node = ros_node

    def connect(self, ip, port):
        """로봇 연결"""

    def disconnect(self):
        """연결 해제"""

    def is_connected(self):
        """연결 상태 확인"""
```

**상태:** 정상 - 변경 불필요

---

### 6. tm_task_manager/global_variable_script.py ✓

**역할:** 로봇 글로벌 변수 읽기/쓰기

```python
class GlobalVariableScript:
    def read_variable(self, variable_name):
        """글로벌 변수 읽기"""

    def write_variable(self, variable_name, value):
        """글로벌 변수 쓰기"""
```

**상태:** 정상 - 변경 불필요

---

## 의존성 다이어그램 (현재)

```
┌─────────────────────────────────────────────────────────┐
│                     main.py                             │
│  - ROS2 init                                            │
│  - QApplication init                                    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│              MainWindow (God Class)                     │
│  ┌───────────────────────────────────────────────────┐ │
│  │ UI 관리 (정상)                                     │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 로봇 모션 제어 (분리 필요) ⚠️                      │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 네트워크 설정 (분리 필요) ⚠️                       │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 설정 파일 관리 (분리 필요) ⚠️                      │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 파일 관리 (분리 필요) ⚠️                           │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 비전 상태 관리 (분리 필요) ⚠️                      │ │
│  │  - self.detected_tags = {}                        │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 파라미터 UI (위젯 분리 고려) △                    │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 글로벌 변수 UI (위젯 분리 고려) △                 │ │
│  └───────────────────────────────────────────────────┘ │
└─────────┬────────────┬────────────┬─────────────────────┘
          │            │            │
          ▼            ▼            ▼
    ┌─────────┐  ┌──────────┐  ┌──────────────────┐
    │ Recipe  │  │   Job    │  │  JobExecutor     │
    │ Manager │  │ Executor │  │  - detected_tags │ ⚠️
    └─────────┘  └──────────┘  └──────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │ TaskManagerNode│
              │   (ROS2)      │
              └───────────────┘
```

**문제점:**
1. MainWindow가 모든 책임 보유 (God Class)
2. JobExecutor가 MainWindow의 `detected_tags` 직접 참조 (강결합)
3. 설정 파일(positions.yaml)을 여러 곳에서 중복 접근
4. 테스트 불가능한 구조 (UI와 비즈니스 로직 혼재)

---

## 작동 흐름

### 학습 모드 (Teaching Mode)

```
사용자 → MainWindow UI
    │
    ├─ [위치 티칭 버튼]
    │   └─ _on_teach_position()
    │       └─ ros_node.current_joint_position 읽기
    │       └─ param_widgets에 값 설정
    │
    ├─ [Jog 버튼 (+X, -X, ...)]
    │   └─ _on_jog(axis, direction)
    │       └─ 회전 행렬 계산 (40+ lines)
    │       └─ ros_node._call_set_positions()
    │       └─ 로봇 이동
    │
    ├─ [파라미터 적용]
    │   └─ _save_params_from_ui(job)
    │       └─ widget 값을 job.params에 저장
    │
    └─ [Recipe 저장]
        └─ recipe_manager.save_recipe()
            └─ YAML 파일 생성
```

### 실행 모드 (Execution Mode)

```
사용자 → [실행 버튼]
    │
    └─ MainWindow._on_run()
        └─ job_executor.run()
            └─ Loop: _execute_next_job()
                │
                ├─ _execute_job(job)
                │   ├─ 'go_home' → _exec_go_home()
                │   ├─ 'move_to_point' → _exec_move_to_point()
                │   ├─ 'scan_ar_tag' → _exec_scan_ar_tag()
                │   │   └─ detected_tags[target_id] 읽기 ⚠️
                │   └─ 'gripper_open' → _exec_gripper_open()
                │
                └─ Callbacks:
                    ├─ on_job_started(index, job)
                    │   └─ MainWindow: UI 업데이트
                    ├─ on_job_completed(index, job, success)
                    │   └─ MainWindow: 상태 표시 [O/X]
                    └─ on_log(message)
                        └─ MainWindow: 로그 출력
```

---

## 문제점 요약

### 1. God Class Anti-Pattern
- **main_window.py 2,114 lines**: 8가지 책임 혼재
- **테스트 불가능**: UI와 비즈니스 로직이 분리되지 않음
- **유지보수 어려움**: 한 파일에서 모든 것을 관리

### 2. 강결합 (Tight Coupling)
```python
# JobExecutor가 MainWindow 내부 데이터 직접 접근
self.job_executor = JobExecutor(
    ros_node=self.ros_node,
    detected_tags=self.detected_tags  # ⚠️ MainWindow 내부 상태
)
```

### 3. 중복 코드
```python
# 동일한 YAML 파일을 3곳에서 반복 접근
def _load_robot_ip_from_config(self):
    config_path = os.path.join(..., 'positions.yaml')
    with open(config_path) as f:
        config = yaml.safe_load(f)

def _load_home_from_config(self):
    config_path = os.path.join(..., 'positions.yaml')  # 중복
    with open(config_path) as f:  # 중복
        config = yaml.safe_load(f)  # 중복
```

### 4. 책임 경계 모호
- MainWindow가 Recipe 파일 관리 (RecipeManager 책임 침범)
- MainWindow가 비전 데이터 저장 (VisionManager 부재)
- MainWindow가 네트워크 스캔 (NetworkManager 부재)

---

## 개선 방향

### 단기 (1-2주)
1. VisionManager 분리 → JobExecutor 결합도 해소
2. ConfigManager 분리 → YAML 중복 접근 제거
3. TeachingService 분리 → 티칭 로직 독립화

### 중기 (3-4주)
4. NetworkManager 분리 → 유틸리티 모듈화
5. CoordinateTransformer 분리 → 좌표 계산 모듈화

### 장기 (선택적)
6. ParameterEditorWidget 분리 → 재사용 가능 위젯
7. GlobalVariableWidget 분리 → UI 모듈화
8. RecipeManager 확장 → 파일 관리 통합

---

## 다음 문서

- [제안 아키텍처](./proposed_architecture.md) - 리팩토링 후 목표 구조
- [의존성 다이어그램](./dependency_diagram.md) - 개선 후 의존성
- [리팩토링 마스터 플랜](../refactoring/master_plan.md) - 상세 실행 계획
