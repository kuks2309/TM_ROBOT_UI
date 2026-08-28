# TM Robot Task Manager - 코드 리뷰 보고서

**리뷰 일자:** 2026-01-31
**프로젝트 경로:** `/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/`
**리뷰 도구:** Claude Code (Opus 4.5) - 병렬 에이전트 리뷰

---

## 종합 판정: **수정 필요 (REVISE)**

프로젝트는 견고한 기반을 갖추고 있으나, 운영 배포 전 아키텍처 준수 및 보안 이슈 수정이 필요합니다.

---

## 요약

| 카테고리 | 심각도 분포 | 상태 |
|----------|-------------|------|
| **아키텍처 준수** | HIGH 3건 | ❌ 수정 필요 |
| **코드 품질** | HIGH 5건, MEDIUM 12건 | ⚠️ 중간 수준 이슈 |
| **보안** | HIGH 2건, MEDIUM 5건 | ⚠️ 주의 필요 |
| **테스트 커버리지** | 테스트 파일 2개 | ⚠️ 부족 |

---

## 1. 아키텍처 위반 사항 (심각)

CLAUDE.md에서 규정한 UI/로직 분리 원칙 위반 사항입니다.

### 위반 목록

| 이슈 | 위치 | 설명 |
|------|------|------|
| ROS 노드에 비즈니스 로직 포함 | `main_window.py:36-381` | 346줄의 모션 제어 로직이 `services/`에 있어야 함 |
| 이미지 캡처 로직 | `main_window.py:879-937` | 58줄의 이미지 캡처 워크플로우가 UI 핸들러에 있음 |
| 카메라 캘리브레이션 | `main_window.py:972-1095` | 124줄의 ROS2 서비스 호출이 UI 코드에 있음 |

### 상세 설명

#### 1.1 TaskManagerNode 클래스 (main_window.py:36-381)

**현재 상태:**
```python
class TaskManagerNode(Node):
    def _call_set_positions(self, ...):  # 비즈니스 로직
    def _check_motion_complete(self, ...):  # 비즈니스 로직
    def _normalize_angle_deg(self, ...):  # 비즈니스 로직
```

**수정 방안:**
- `services/robot_motion_service.py` 파일 생성
- 모션 제어 로직을 새 서비스 클래스로 이동

```python
# services/robot_motion_service.py
class RobotMotionService:
    def call_set_positions(self, ...): ...
    def check_motion_complete(self, ...): ...
    def normalize_angle_deg(self, ...): ...
```

#### 1.2 이미지 캡처 메서드 (main_window.py:879-937)

**현재 상태:**
- `_on_image_capture` 메서드가 로봇 명령 전송, ROS2 구독 관리, 타이밍 처리를 직접 수행

**수정 방안:**
- `VisionManager` 확장 또는 `ImageCaptureService` 생성

#### 1.3 카메라 캘리브레이션 (main_window.py:972-1095)

**현재 상태:**
- `_on_detect_chessboard`, `_on_capture_calib_image`, `_on_run_calibration`, `_on_save_calibration`이 ROS2 서비스를 직접 호출

**수정 방안:**
- `services/camera_calibration_service.py` 생성

### 아키텍처 준수 파일 (통과)

| 파일 | 상태 | 비고 |
|------|------|------|
| `job_executor.py` | ✅ 통과 | UI 조작 없음, 콜백 패턴 사용 |
| `services/vision_manager.py` | ✅ 통과 | PyQt 시그널로 UI 통신 |
| `services/coordinate_transformer.py` | ✅ 통과 | 순수 유틸리티 클래스 |
| `services/tm_robot_script_motion.py` | ✅ 통과 | 콜백 주입 패턴 사용 |

---

## 2. 보안 이슈

### HIGH 심각도

#### 2.1 스크립트 인젝션 취약점

**위치:** `global_variable_script.py:137`

**현재 코드:**
```python
def write_variable(self, variable_name: str, value: any, ...):
    script = f"{variable_name}={value}"  # 검증 없음
    request.script = script
```

**위험:** 악의적인 변수명으로 TM 스크립트 명령 주입 가능

**공격 예시:**
```python
# variable_name = "g_var; MaliciousCommand()"
# script = "g_var; MaliciousCommand()=value"
```

**수정 방안:**
```python
import re

def write_variable(self, variable_name: str, value: any, ...):
    # 변수명 화이트리스트 검증
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', variable_name):
        raise ValueError(f"유효하지 않은 변수명: {variable_name}")

    # 값 타입 검증
    if not isinstance(value, (int, float, str, bool)):
        raise ValueError(f"지원하지 않는 값 타입: {type(value)}")

    script = f"{variable_name}={value}"
    request.script = script
```

#### 2.2 ast.literal_eval() 사용자 입력 처리

**위치:** `task_edit_tab.py:428`

**현재 코드:**
```python
if text.startswith('[') and text.endswith(']'):
    try:
        import ast
        job.params[param_name] = ast.literal_eval(text)
    except:
        job.params[param_name] = text
```

**위험:** 신뢰할 수 없는 소스(레시피 파일 등)에서 입력 시 DoS 또는 예상치 못한 동작 가능

**수정 방안:**
- 입력 형식 엄격 검증
- 예상 리스트 형식에 대한 커스텀 파서 구현
- 입력 길이 제한 추가

### MEDIUM 심각도

| 이슈 | 위치 | 설명 |
|------|------|------|
| 경로 순회 취약점 | `recipe_manager.py:378-382` | `../../etc/passwd` 같은 경로로 디렉토리 외부 파일 접근 가능 |
| 불충분한 IP 검증 | `network_manager.py:178-198` | 기본 검증만 수행, 예약된 IP 범위 미차단 |
| 하드코딩된 기본 로봇 IP | `task_manager.launch.py:111` | `169.254.183.219` 하드코딩됨 |
| subprocess 입력 미검증 | `handeye_test_tab.py:418` | csv_path 검증 없이 subprocess 실행 |
| ROS2 서비스 인증 없음 | 전체 ROS2 클라이언트 | 네트워크 접근 시 누구나 로봇 명령 전송 가능 |

### 경로 순회 수정 방안

```python
def load_recipe(self, file_path: str) -> Recipe:
    if not os.path.isabs(file_path):
        file_path = os.path.join(self.recipe_dir, file_path)

    # 경로 검증 추가
    resolved_path = os.path.realpath(file_path)
    if not resolved_path.startswith(os.path.realpath(self.recipe_dir)):
        raise ValueError("접근 거부: 레시피 디렉토리 외부 경로")

    with open(resolved_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
```

---

## 3. 코드 품질 이슈

### HIGH 심각도

| 이슈 | 위치 | 설명 |
|------|------|------|
| 미완성 구현이 True 반환 | `job_executor.py:459, 523, 741, 772` | 실제 구현 없이 True 반환하여 잘못된 성공 신호 |
| 프로덕션 코드에 디버그 출력 | `vision_manager.py:274-411` | `print("[DEBUG]...")` 문장 다수 존재 |

### 미완성 구현 예시

```python
# 현재 (나쁨) - job_executor.py:459-461
def _exec_move_to_ar_offset(self, params: Dict[str, Any]) -> bool:
    ...
    # TODO: ROS2 서비스 호출 구현 필요
    self._log(f"Move to AR offset: ...")
    return True  # 임시 - 실제로는 구현 안 됨!

# 권장 (좋음)
def _exec_move_to_ar_offset(self, params: Dict[str, Any]) -> bool:
    ...
    self._log("[WARNING] move_to_ar_offset 미구현")
    return False  # 미구현 상태 명시
```

### MEDIUM 심각도

| 이슈 | 위치 | 설명 |
|------|------|------|
| 메서드 내부 import 문 | 여러 파일 | `import time`, `from tm_msgs.srv import ...` 등 |
| stop 플래그 미확인 sleep | `job_executor.py` 그리퍼 메서드 | `time.sleep(delay)` 중 `_stop_requested` 미확인 |
| 하드코딩된 UI 파일 경로 | `main_window.py:402` | 절대 경로 하드코딩 |
| 중복 코드 패턴 | `vision_manager.py:61-145` | pause/resume 메서드 80% 중복 |
| 불완전한 타입 어노테이션 | `vision_manager.py` | `tuple` 대신 `Tuple[bool, str]` 사용 권장 |

### LOW 심각도

| 이슈 | 위치 | 설명 |
|------|------|------|
| 매직 넘버 | 여러 파일 | 상수 정의 없이 숫자 직접 사용 |
| 일관성 없는 로그 메시지 형식 | `job_executor.py` | `[ERROR]`, `[WAIT]`, `[DI READ]` 등 혼재 |
| 혼합 언어 에러 메시지 | `vision_manager.py` | 한국어, 영어 혼용 |
| 빈 메서드 구현 | `main_window.py:870-875` | `_on_start_camera`, `_on_stop_camera`가 `pass`만 있음 |

---

## 4. 테스트 커버리지

### 현재 상태

발견된 테스트 파일:
- `test/test_coordinate_transformer.py`
- `test/test_recipe_manager.py`

### 테스트 부족 컴포넌트

| 컴포넌트 | 중요도 | 테스트 상태 |
|----------|--------|-------------|
| `job_executor.py` | 높음 | ❌ 없음 |
| `main_window.py` | 높음 | ❌ 없음 |
| `services/vision_manager.py` | 높음 | ❌ 없음 |
| `services/tm_robot_script_motion.py` | 중간 | ❌ 없음 |
| `tools/jig_plane_calculator.py` | 중간 | ❌ 없음 |

---

## 5. 긍정적 발견 사항

| 항목 | 설명 |
|------|------|
| ✅ 서비스 레이어 아키텍처 | `VisionManager`, `CoordinateTransformer`, `TmRobotScriptMotion` 관심사 분리 적절 |
| ✅ 콜백 패턴 구현 | Service → UI 통신에 PyQt 시그널과 콜백 적절히 사용 |
| ✅ YAML safe_load 일관 사용 | 역직렬화 취약점 없음 |
| ✅ Job 실행 에러 처리 | `_execute_current_job`에 try/except + traceback 로깅 |
| ✅ 중지 요청 처리 | `_exec_wait`에서 `_stop_requested` 플래그 확인 |

---

## 6. 필수 조치 사항

### 우선순위 1: 아키텍처 수정

1. **`TaskManagerNode` 모션 제어 로직 분리**
   - 새 파일: `services/robot_motion_service.py`
   - 이동 대상: `_call_set_positions`, `_check_motion_complete`, `_normalize_angle_deg` 등

2. **이미지 캡처 워크플로우 분리**
   - `VisionManager` 확장 또는 `services/image_capture_service.py` 생성

3. **카메라 캘리브레이션 서비스 생성**
   - 새 파일: `services/camera_calibration_service.py`

### 우선순위 2: 보안 수정

1. **`write_variable()` 입력 검증 추가**
   - 변수명 화이트리스트 검증 (정규식)
   - 값 타입 검증

2. **경로 순회 보호 추가**
   - `load_recipe()`, `save_recipe()`에 경로 검증 로직 추가

3. **모션 파라미터 범위 검증**
   - 로봇 작업 공간 한계 내 검증
   - 속도 범위 검증

### 우선순위 3: 코드 품질

1. **디버그 출력문 제거**
   - `print("[DEBUG]...")` → 적절한 로깅으로 대체

2. **미완성 구현 수정**
   - `return True` → `return False` + 경고 로그

3. **import 문 파일 상단 이동**
   - 메서드 내부 import → 파일 최상단

---

## 7. 권장 개선 사항 (선택)

| 항목 | 설명 |
|------|------|
| 상수 정의 | 매직 넘버를 클래스 상수 또는 설정 파일로 |
| 로그 형식 통일 | 일관된 로그 메시지 접두사 규칙 정의 |
| 타입 힌트 개선 | `tuple` → `Tuple[bool, str]` 등 구체적 타입 |
| 테스트 추가 | `job_executor.py`, `vision_manager.py` 단위 테스트 |
| ROS2 보안 설정 | DDS 보안 기능 활성화 (인증, 암호화) |

---

## 8. 결론

### 판정 근거

| 기준 | 평가 |
|------|------|
| 명확성 (Clarity) | 양호 - 코드 구조 명확 |
| 테스트 가능성 (Testability) | 부분적 - 일부 컴포넌트 리팩토링 필요 |
| 검증 가능성 (Verification) | 양호 - 파일 참조 정확 |
| 구체성 (Specificity) | 양호 - 구현 구체적 |

### 최종 판정

**REVISE (수정 필요)**

`main_window.py`의 아키텍처 리팩토링과 보안 강화가 운영 배포 전 필요합니다.
서비스 레이어와 Job Executor는 아키텍처적으로 견고합니다.

---

*이 보고서는 Claude Code (Opus 4.5)의 병렬 리뷰 에이전트에 의해 자동 생성되었습니다.*
