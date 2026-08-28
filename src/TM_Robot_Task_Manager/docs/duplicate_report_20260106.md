# 중복 함수/변수 분석 리포트

**날짜**: 2026-01-06
**분석 대상**: `src/TM_Robot_Task_Manager/tm_task_manager/`
**분석 도구**: Claude Code

---

## 요약

| 중복 유형 | 개수 | 심각도 |
|----------|------|--------|
| 좌표 변환 로직 중복 | 3회 | 높음 |
| TM Landmark 메서드 중복 | 4개 | 높음 |
| g_robot_command 설정 중복 | 4개 | 중간 |
| 위치 데이터 중복 저장 | 3개 | 중간 |
| ScriptExit 메서드 중복 | 2개 | 낮음 |

---

## 1. 좌표 변환 로직 중복 (심각도: 높음)

### 설명
`job_executor.py`에서 동일한 좌표 변환 코드가 3개의 메서드에서 반복됩니다.

### 중복 위치

| 메서드 | 라인 | Joint 변환 | TCP 변환 |
|--------|------|-----------|----------|
| `_exec_go_home()` | 220-277 | 241-248 | 257-264 |
| `_exec_move_to_point()` | 279-336 | 300-307 | 316-323 |
| `_exec_measure_point()` | 892-976 | 935-942 | 951-958 |

### 중복 코드 예시

**Joint 변환 (degree → radian):**
```python
# 3곳에서 동일하게 반복
positions = [
    x * math.pi / 180.0,
    y * math.pi / 180.0,
    z * math.pi / 180.0,
    rx * math.pi / 180.0,
    ry * math.pi / 180.0,
    rz * math.pi / 180.0,
]
```

**TCP 변환 (mm → m, degree → radian):**
```python
# 3곳에서 동일하게 반복
positions = [
    x / 1000.0,
    y / 1000.0,
    z / 1000.0,
    rx * math.pi / 180.0,
    ry * math.pi / 180.0,
    rz * math.pi / 180.0,
]
```

### 권장 수정

헬퍼 메서드 추출:
```python
def _convert_positions(self, x, y, z, rx, ry, rz, motion_type: str) -> list:
    """좌표 변환 (Joint: deg→rad, TCP: mm→m, deg→rad)"""
    if motion_type == 'joint':
        return [v * math.pi / 180.0 for v in [x, y, z, rx, ry, rz]]
    else:  # TCP
        return [
            x / 1000.0, y / 1000.0, z / 1000.0,
            rx * math.pi / 180.0, ry * math.pi / 180.0, rz * math.pi / 180.0
        ]
```

---

## 2. TM Landmark 메서드 중복 (심각도: 높음)

### 설명
TM Landmark 스캔 기능이 `job_executor.py`와 `vision_manager.py`에 중복 구현되어 있습니다.

### 중복 위치

| 파일 | 라인 | 메서드 | 기능 |
|------|------|--------|------|
| job_executor.py | 764-820 | `_exec_scan_tm_landmark()` | g_robot_command=2 설정 후 ScriptExit |
| job_executor.py | 884-890 | `_exec_scan_align_tm_landmark()` | 위 메서드 단순 래퍼 (완전 중복) |
| vision_manager.py | 115-141 | `execute_tm_landmark_scan()` | g_robot_command=2 설정 후 ScriptExit |
| vision_manager.py | 143-169 | `execute_scan_align_tm_landmark()` | 동일 기능 |

### 권장 수정

- `vision_manager.py`에만 구현 유지
- `job_executor.py`에서는 `vision_manager` 메서드 호출

```python
# job_executor.py
def _exec_scan_tm_landmark(self, params: dict) -> bool:
    return self.vision_manager.execute_tm_landmark_scan()
```

---

## 3. g_robot_command 설정 중복 (심각도: 중간)

### 설명
글로벌 변수 `g_robot_command` 설정이 여러 곳에서 중복 구현되어 있습니다.

### 중복 위치

| 파일 | 라인 | 메서드/코드 | 방식 |
|------|------|------------|------|
| job_executor.py | 670-718 | `_set_robot_command()` | Script |
| global_variable_script.py | 118-168 | `write_variable()` | Script |
| main_window.py | 1638 | `gv_modbus.write_variable('g_robot_command', 1)` | ModBus |
| main_window.py | 1671 | `gv_modbus.write_variable('g_robot_command', 2)` | ModBus |
| main_window.py | 1696 | `gv_manager.write_variable('g_robot_command', 3)` | Script |

### 권장 수정

- `GlobalVariableScript.write_variable()` 또는 `GlobalVariableModbus.write_variable()` 중 하나로 통일
- `job_executor._set_robot_command()` 제거하고 기존 클래스 메서드 사용

---

## 4. 위치 데이터 중복 저장 (심각도: 중간)

### 설명
AR 태그 및 Landmark 위치 데이터가 여러 곳에 중복 저장됩니다.

### 중복 위치

| 파일 | 라인 | 변수 | 저장 데이터 |
|------|------|------|------------|
| job_executor.py | 45 | `self.detected_ar_pose` | AR 태그 위치 |
| job_executor.py | 48 | `self.detected_landmark_pose` | Landmark 위치 |
| vision_manager.py | 37 | `self.detected_tags` | AR 태그 데이터 |

### 권장 수정

- `vision_manager`만 데이터 저장소로 사용
- `job_executor`에서는 `vision_manager`의 데이터 참조

```python
# job_executor.py - 수정 후
@property
def detected_ar_pose(self):
    return self.vision_manager.detected_tags
```

---

## 5. ScriptExit 메서드 중복 (심각도: 낮음)

### 설명
ScriptExit 명령 전송 기능이 중복 구현되어 있습니다.

### 중복 위치

| 파일 | 라인 | 메서드 |
|------|------|--------|
| job_executor.py | 720-762 | `_send_script_exit()` |
| global_variable_script.py | 240-280 | `send_script_exit()` |

### 권장 수정

- `GlobalVariableScript.send_script_exit()` 메서드만 유지
- `job_executor`에서는 해당 메서드 호출

---

## 리팩토링 우선순위

| 순위 | 항목 | 예상 영향 | 난이도 |
|------|------|----------|--------|
| 1 | 좌표 변환 헬퍼 메서드 추출 | 코드 50줄 감소 | 낮음 |
| 2 | TM Landmark 메서드 통합 | 코드 100줄 감소 | 중간 |
| 3 | g_robot_command 메서드 통합 | 유지보수성 향상 | 중간 |
| 4 | 위치 데이터 저장소 통일 | 데이터 일관성 향상 | 중간 |
| 5 | ScriptExit 메서드 통합 | 코드 40줄 감소 | 낮음 |

---

## 참고

- 아키텍처 원칙: UI와 로직 분리 (`main_window.py` ↔ `services/*.py`)
- 리팩토링 시 기존 테스트 및 동작 확인 필수
