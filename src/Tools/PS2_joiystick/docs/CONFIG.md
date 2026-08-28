# PS2 Joystick 설정 가이드

## 설정 파일 위치

```
/home/amap/TM_Robot_ros2_ws/src/TM_Robot_Task_Manager/config/joystick_config.yaml
```

## 설정 파일 구조

```yaml
# PS2/Xbox 조이스틱 설정
joystick:
  # 장치 경로
  device_path: "/dev/input/js0"

  # 데드존 (0.0 ~ 1.0)
  deadzone: 0.15

  # 폴링 간격 (ms)
  poll_interval_ms: 50

  # 버튼 매핑
  buttons:
    deadman_xyz: 2      # XYZ 이동 데드맨 버튼
    deadman_rxryrz: 5   # RxRyRz 회전 데드맨 버튼

  # 축 매핑
  axes:
    # XYZ 이동
    x: 0                # X축 이동
    y: 1                # Y축 이동
    z: 7                # Z축 이동
    # RxRyRz 회전
    rx: 3               # Rx 회전
    ry: 4               # Ry 회전
    rz: 7               # Rz 회전

  # 조그 파라미터
  jog:
    step_mm: 1.0          # 위치 조그 스텝 (mm)
    step_deg: 0.5         # 회전 조그 스텝 (deg)
    velocity_percent: 10  # 조그 속도 (%)
    continuous_interval_ms: 100  # 연속 명령 간격
```

## 설정 항목 설명

### device_path
조이스틱 장치 경로. 기본값: `/dev/input/js0`

여러 조이스틱이 연결된 경우 `/dev/input/js1`, `/dev/input/js2` 등을 사용.

### deadzone
데드존 (불감대). 0.0 ~ 1.0 범위.

- **0.0**: 데드존 없음 (매우 민감)
- **0.15**: 기본값 (권장)
- **0.3**: 큰 데드존 (둔감)

조이스틱 중립 위치에서 약간의 흔들림을 무시합니다.

### buttons

| 키 | 설명 | 기본값 |
|----|------|--------|
| `deadman_xyz` | XYZ 이동 활성화 버튼 | 2 |
| `deadman_rxryrz` | RxRyRz 회전 활성화 버튼 | 5 |

버튼 번호는 `joystick_test.py` 스크립트로 확인하세요.

### axes

| 키 | 설명 | 기본값 |
|----|------|--------|
| `x` | X축 이동 (버튼 2 누름 시) | 0 |
| `y` | Y축 이동 (버튼 2 누름 시) | 1 |
| `z` | Z축 이동 (버튼 2 누름 시) | 7 |
| `rx` | Rx 회전 (버튼 5 누름 시) | 3 |
| `ry` | Ry 회전 (버튼 5 누름 시) | 4 |
| `rz` | Rz 회전 (버튼 5 누름 시) | 7 |

축 번호는 `joystick_test.py` 스크립트로 확인하세요.

### jog 파라미터

| 키 | 설명 | 기본값 | 권장 범위 |
|----|------|--------|-----------|
| `step_mm` | 이동 거리 (mm) | 1.0 | 0.1 ~ 10.0 |
| `step_deg` | 회전 각도 (deg) | 0.5 | 0.1 ~ 5.0 |
| `velocity_percent` | 이동 속도 (%) | 10 | 5 ~ 50 |
| `continuous_interval_ms` | 명령 간격 (ms) | 100 | 50 ~ 200 |

## Xbox 360 컨트롤러 기본 매핑

| 요소 | 번호 | 설명 |
|------|------|------|
| 축 0 | 왼쪽 스틱 X | 좌우 |
| 축 1 | 왼쪽 스틱 Y | 상하 |
| 축 2 | LT 트리거 | 0~1 |
| 축 3 | 오른쪽 스틱 X | 좌우 |
| 축 4 | 오른쪽 스틱 Y | 상하 |
| 축 5 | RT 트리거 | 0~1 |
| 축 6 | D-패드 X | 좌우 |
| 축 7 | D-패드 Y | 상하 |
| 버튼 0 | A | |
| 버튼 1 | B | |
| 버튼 2 | X | |
| 버튼 3 | Y | |
| 버튼 4 | LB | 왼쪽 범퍼 |
| 버튼 5 | RB | 오른쪽 범퍼 |
| 버튼 6 | Back | |
| 버튼 7 | Start | |
| 버튼 8 | Xbox | 가운데 |
| 버튼 9 | 왼쪽 스틱 클릭 | |
| 버튼 10 | 오른쪽 스틱 클릭 | |

**참고**: PS2 컨트롤러를 USB 어댑터로 연결하면 Xbox 360으로 에뮬레이션됩니다.

## 설정 변경 후

설정 파일을 변경한 후에는 **프로그램을 재시작**해야 적용됩니다.

또는 Task 편집 탭에서:
1. "Enable PS2 Jog" 체크 해제
2. 다시 체크

## 예제: 안전 우선 설정

```yaml
joystick:
  device_path: "/dev/input/js0"
  deadzone: 0.2           # 큰 데드존
  poll_interval_ms: 50

  buttons:
    deadman_xyz: 4        # LB 버튼
    deadman_rxryrz: 5     # RB 버튼

  axes:
    x: 0
    y: 1
    z: 4                  # 오른쪽 스틱 Y
    rx: 0
    ry: 1
    rz: 3                 # 오른쪽 스틱 X

  jog:
    step_mm: 0.5          # 작은 스텝
    step_deg: 0.2         # 작은 회전
    velocity_percent: 5   # 낮은 속도
    continuous_interval_ms: 150
```
