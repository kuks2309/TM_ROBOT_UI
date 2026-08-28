# TM Vision Base 이동 명령 모음

## 개요
TM Landmark를 인식한 후 Vision Base 좌표계를 사용하여 로봇을 이동시키는 명령 모음입니다.

## Vision Base 좌표계

### 원점 (0, 0, 0)
- TM Landmark 인식 위치 = Vision Base 원점
- TCP가 (0, 0, 0)으로 이동하면 랜드마크 표면에 정렬됨

### 축 방향
| 축 | 방향 | 설명 |
|----|------|------|
| X+ | Landmark 오른쪽 | TM 로고 기준 |
| Y+ | Landmark 아래쪽 | |
| Z+ | Landmark 방향 (가까워짐) | |
| Z- | Landmark 반대 방향 (멀어짐) | |

---

## 좌표계 변경 명령

### Vision Base로 변경
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "ChangeBase(\"vision_TM_Landmark_detection\")"}'
```

### Robot Base로 복원
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "ChangeBase(\"RobotBase\")"}'
```

---

## Line 이동 명령

### 명령 형식
```
Line("타입", X, Y, Z, Rx, Ry, Rz, velocity_mm/s, acc_time_ms, blend_percent, fine_goal)
```

### 타입
| 타입 | 설명 |
|------|------|
| CPP | 절대 좌표 이동 (현재 Base 기준) |
| CAP | 상대 좌표 이동 (현재 위치 기준) |

---

## 실제 테스트된 명령 예시

### 1. 랜드마크 중심에서 100mm 떨어진 위치로 이동 (절대 좌표)
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CPP\", 0, 0, -100, 0, 0, 0, 50, 200, 0, true)"}'
```
- X=0, Y=0: 랜드마크 중심
- Z=-100: 랜드마크에서 100mm 멀어진 위치
- Rx=0, Ry=0, Rz=0: 현재 자세 유지
- velocity=50mm/s, acc_time=200ms

### 2. 랜드마크 표면으로 이동 (절대 좌표)
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CPP\", 0, 0, 0, 0, 0, 0, 50, 200, 0, true)"}'
```

### 3. 상대 이동 - Z축 아래로 15mm
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CAP\", 0, 0, 15, 0, 0, 0, 50, 200, 0, true)"}'
```

### 4. 상대 이동 - Z축 위로 50mm
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CAP\", 0, 0, -50, 0, 0, 0, 50, 200, 0, true)"}'
```

### 5. 상대 이동 - X축 50mm
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CAP\", 50, 0, 0, 0, 0, 0, 50, 200, 0, true)"}'
```

### 6. 상대 이동 - Y축 -50mm
```bash
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CAP\", 0, -50, 0, 0, 0, 0, 50, 200, 0, true)"}'
```

---

## 전체 워크플로우 예시

```bash
# 1. TM Landmark 스캔 (TMFlow Vision Job 실행)
# scan_tm_landmark 명령으로 Vision Base 생성

# 2. Vision Base로 좌표계 변경
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "ChangeBase(\"vision_TM_Landmark_detection\")"}'

# 3. 랜드마크 중심에서 100mm 떨어진 위치로 이동
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CPP\", 0, 0, -100, 0, 0, 0, 50, 200, 0, true)"}'

# 4. 필요한 작업 수행...

# 5. Robot Base로 복원
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "ChangeBase(\"RobotBase\")"}'
```

---

## 주의사항

1. **Vision Base 생성 필수**: `ChangeBase("vision_TM_Landmark_detection")` 실행 전에 반드시 TM Landmark 스캔이 완료되어야 함

2. **TCP vs 카메라 중심**: Vision Base (0, 0, 0)은 TCP 기준이며, 카메라 중심과는 다름

3. **Z축 부호**:
   - Z- = 랜드마크에서 멀어짐 (안전한 거리 확보)
   - Z+ = 랜드마크로 가까워짐 (충돌 주의)

4. **Vision Base는 원점만 변경됨 (중요!)**:
   - Vision Base로 변환하면 **원점(X, Y, Z)만 Landmark 위치로 변경**됨
   - **좌표축 방향(Rx, Ry, Rz)은 RobotBase와 동일**하게 유지됨
   - 따라서 `Line("CPP", 0, 0, Z, 0, 0, 0, ...)`으로 이동해도 TCP 자세가 Landmark와 자동으로 일치하지 않음
   - **자세 정렬이 필요하면 g_TM_Landmark의 Rx, Ry, Rz 값을 직접 사용해야 함**

5. **Robot Base 복원**: 작업 완료 후 반드시 Robot Base로 복원할 것

---

## Landmark 자세 정렬 방법

### g_TM_Landmark 변수
TM Landmark 스캔 후 `g_TM_Landmark` 변수에 Landmark 위치와 자세가 저장됨:
- X, Y, Z: Landmark 위치 (RobotBase 기준)
- Rx, Ry, Rz: Landmark 자세 (RobotBase 기준)

### 방법 1: Vision Base에서 자세 정렬 (권장)
Vision Base 좌표계에서 `Line("CAP", 0, 0, 0, 0, 0, 0, ...)` 명령으로 자세 정렬:
```bash
# 1. Vision Base로 변경
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "ChangeBase(\"vision_TM_Landmark_detection\")"}'

# 2. 현재 위치 유지하면서 Landmark와 자세 정렬
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CAP\", 0, 0, 0, 0, 0, 0, 50, 200, 0, true)"}'
```
- **CAP**: 상대 이동 (현재 위치 기준)
- **위치 (0, 0, 0)**: 현재 위치 유지
- **자세 (0, 0, 0)**: Vision Base에서 0, 0, 0 = Landmark와 수직 정렬
- **테스트 결과**: 0.1° 이내 정렬 정확도 확인 (2026-01-12)

### 방법 2: RobotBase에서 자세 정렬
RobotBase 좌표계에서 절대 좌표로 자세 정렬:
```bash
# g_TM_Landmark 읽기
ros2 service call /ask_item tm_msgs/srv/AskItem "{id: 'gv', item: 'g_TM_Landmark', wait_time: 1.0}"

# Landmark 자세로 이동 (X, Y는 현재 위치 유지, Z와 자세는 Landmark 값 사용)
ros2 service call /send_script tm_msgs/srv/SendScript '{id: "gv", script: "Line(\"CPP\", 현재X, 현재Y, 목표Z, Landmark_Rx, Landmark_Ry, Landmark_Rz, 50, 200, 0, true)"}'
```

---

## 중요: SendScript ID
- **id는 반드시 "gv" 사용** (Listen Node에서 인식)
- `id: "demo"`, `id: "gv"` 등은 오류 발생 가능

---

## 테스트 일자
- 2026-01-06: 초기 문서 작성
- 2026-01-12: Vision Base 자세 정렬 명령 추가 (Line CAP 0,0,0,0,0,0)
