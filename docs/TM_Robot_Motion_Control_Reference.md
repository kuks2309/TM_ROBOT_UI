# TM Robot Motion/Control Reference Guide

TM 로봇의 모션 및 제어 옵션 완벽 가이드

---

## 목차

1. [모션 타입 (Motion Types)](#1-모션-타입-motion-types)
2. [모션 파라미터 (Motion Parameters)](#2-모션-파라미터-motion-parameters)
3. [좌표 시스템 (Coordinate Systems)](#3-좌표-시스템-coordinate-systems)
4. [고급 모션 모드 (Advanced Motion Modes)](#4-고급-모션-모드-advanced-motion-modes)
5. [제어 명령 (Control Commands)](#5-제어-명령-control-commands)
6. [동기화 (Synchronization)](#6-동기화-synchronization)
7. [IO 제어 (IO Control)](#7-io-제어-io-control)
8. [ROS2 서비스 인터페이스](#8-ros2-서비스-인터페이스)
9. [TMscript 명령어](#9-tmscript-명령어)
10. [사용 예시](#10-사용-예시)

---

## 1. 모션 타입 (Motion Types)

### 1.1 PTP (Point to Point)

최단 경로로 이동하며, 경로가 직선이 아닐 수 있음. 가장 빠른 이동 방식.

```
시작점 ─────────────────→ 끝점
        (최단 경로, 곡선 가능)
```

| 타입 | 코드 | 함수 | 설명 |
|------|------|------|------|
| **PTP_J** | 1 | `set_joint_pos_PTP()` | 관절 좌표 기준 PTP |
| **PTP_T** | 2 | `set_tool_pose_PTP()` | TCP 좌표 기준 PTP |

**특징:**
- 가장 빠른 이동 속도
- 경로 예측이 어려움 (곡선 경로)
- 충돌 주의 필요
- 빈 공간 이동에 적합

**사용 시점:**
- 장애물이 없는 빈 공간 이동
- 빠른 위치 전환이 필요할 때
- 정확한 경로가 중요하지 않을 때

---

### 1.2 LINE (직선 이동)

TCP가 직선 경로를 따라 이동.

```
시작점 ━━━━━━━━━━━━━━━━━━→ 끝점
        (직선 경로)
```

| 타입 | 코드 | 함수 | 설명 |
|------|------|------|------|
| **LINE_T** | 4 | `set_tool_pose_Line()` | TCP 직선 이동 |

**특징:**
- TCP가 정확히 직선으로 이동
- PTP보다 느림
- 경로 예측 가능
- 정밀 작업에 적합

**사용 시점:**
- 픽업/배치 접근 시 (하강/상승)
- 용접, 도포 등 경로가 중요한 작업
- 장애물 근처 이동

---

### 1.3 CIRC (원호 이동)

3개의 점(시작점, 중간점, 끝점)을 지나는 원호 경로.

```
        ╭─────╮
시작점 ╯   P1  ╰→ 끝점
      (중간점 경유 원호)
```

| 타입 | 코드 | 설명 |
|------|------|------|
| **CIRC_T** | 6 | TCP 원호 이동 |

**특징:**
- 부드러운 곡선 경로
- 3점 지정 필요 (시작, 중간, 끝)
- 장애물 회피에 활용

**TMscript 문법:**
```
Circle("CAP", via_x, via_y, via_z, via_rx, via_ry, via_rz,
       end_x, end_y, end_z, end_rx, end_ry, end_rz, speed, acc, blend, fine)
```

---

### 1.4 PLINE (다중 포인트 직선)

여러 포인트를 연속된 직선으로 연결하여 이동.

```
시작점 ━━→ P1 ━━→ P2 ━━→ P3 ━━→ 끝점
      (여러 점을 직선으로 연결)
```

| 타입 | 코드 | 설명 |
|------|------|------|
| **PLINE_T** | 8 | 다중 포인트 직선 연결 |

**특징:**
- 블렌딩으로 부드러운 경로 생성
- 복잡한 경로에 활용
- 연속 동작에 효율적

---

### 1.5 모션 타입 비교표

| 항목 | PTP_J | PTP_T | LINE_T | CIRC_T | PLINE_T |
|------|-------|-------|--------|--------|---------|
| 속도 | 가장 빠름 | 빠름 | 중간 | 중간 | 중간 |
| 경로 정확도 | 낮음 | 낮음 | 높음 | 높음 | 높음 |
| 경로 예측 | 어려움 | 어려움 | 직선 | 원호 | 직선 연결 |
| 사용 용도 | 빈 공간 이동 | 빈 공간 이동 | 정밀 접근 | 회피 경로 | 복잡 경로 |

---

## 2. 모션 파라미터 (Motion Parameters)

### 2.1 속도 (Velocity)

| 파라미터 | 설명 | 단위 | 범위 |
|----------|------|------|------|
| `velocity` | 이동 속도 | rad/s (Joint), m/s (TCP) | 0 ~ max |
| `vel_percent` | 속도 비율 | % | 0 ~ 100 |

**최대 속도 제한:**
- Joint 속도: 최대 π rad/s (180 deg/s)
- TCP 속도: 최대 1.0 m/s (기본값)

**예시:**
```python
# 50% 속도로 이동
velocity = 50  # percent

# 0.3 m/s로 직선 이동
velocity = 0.3  # m/s (LINE_T)
```

---

### 2.2 가속 시간 (Acceleration Time)

| 파라미터 | 설명 | 단위 | 권장값 |
|----------|------|------|--------|
| `acc_time` | 최대 속도 도달 시간 | ms | 100 ~ 500 |

**특징:**
- 값이 작을수록 급격한 가속
- 값이 클수록 부드러운 가속
- 너무 작으면 로봇에 충격

**예시:**
```python
acc_time = 200  # 200ms 동안 가속
```

---

### 2.3 블렌딩 (Blending)

연속 동작 시 포인트 간 부드러운 연결.

```
블렌딩 0%:        블렌딩 50%:
P1 ──┐            P1 ──╮
     │                 ╰──→ P2
     └── P2
(정지 후 이동)     (부드럽게 연결)
```

| 파라미터 | 설명 | 단위 | 범위 |
|----------|------|------|------|
| `blend_percent` | 블렌딩 비율 | % | 0 ~ 100 |

**특징:**
- 0%: 각 포인트에서 완전 정지
- 100%: 최대 블렌딩 (포인트 통과)
- 연속 동작에서 사이클 타임 단축

---

### 2.4 정밀 도달 모드 (Fine Goal)

| 파라미터 | 설명 | 타입 |
|----------|------|------|
| `fine_goal` | 정밀 위치 도달 | bool |

**특징:**
- `true`: 목표 위치에 정확히 도달 후 다음 동작
- `false`: 목표 근처 도달 시 다음 동작 시작
- 정밀 작업 시 `true` 권장

---

### 2.5 파라미터 조합 예시

| 작업 | velocity | acc_time | blend | fine_goal |
|------|----------|----------|-------|-----------|
| 빠른 이동 | 80% | 150ms | 50% | false |
| 정밀 접근 | 20% | 300ms | 0% | true |
| 픽업 하강 | 10% | 200ms | 0% | true |
| 연속 경로 | 50% | 200ms | 30% | false |

---

## 3. 좌표 시스템 (Coordinate Systems)

### 3.1 Joint 좌표 (관절각)

6개의 관절 각도로 로봇 자세 표현.

```
[J1, J2, J3, J4, J5, J6]
```

| 관절 | 설명 | 단위 | 범위 (예시) |
|------|------|------|-------------|
| J1 | 베이스 회전 | rad/deg | ±270° |
| J2 | 숄더 | rad/deg | ±180° |
| J3 | 엘보 | rad/deg | ±166° |
| J4 | 손목1 | rad/deg | ±180° |
| J5 | 손목2 | rad/deg | ±180° |
| J6 | 손목3 | rad/deg | ±270° |

**사용 시점:**
- 특정 자세로 이동 시
- 특이점(Singularity) 회피 시
- 홈 포지션 이동 시

---

### 3.2 TCP 좌표 (Cartesian/Tool Center Point)

툴 끝점의 위치와 자세.

```
[X, Y, Z, Rx, Ry, Rz]
```

| 요소 | 설명 | 단위 |
|------|------|------|
| X | X축 위치 | mm |
| Y | Y축 위치 | mm |
| Z | Z축 위치 | mm |
| Rx | X축 회전 (Roll) | degree |
| Ry | Y축 회전 (Pitch) | degree |
| Rz | Z축 회전 (Yaw) | degree |

**자세(Orientation) 설명:**
```
Rx = 180°, Ry = 0°, Rz = 0°  → 툴이 아래를 향함 (수직 하강)
Rx = 180°, Ry = 0°, Rz = 90° → 툴이 아래를 향하고 90° 회전
Rx = 90°,  Ry = 0°, Rz = 0°  → 툴이 전방을 향함 (수평)
```

---

### 3.3 좌표 프레임 (Coordinate Frame)

| 프레임 | 코드 | 설명 |
|--------|------|------|
| **Base** | "CPP" | 로봇 베이스 기준 (World) |
| **Tool** | "TCP" | 현재 툴 끝점 기준 |
| **User** | 사용자 정의 | 사용자 지정 좌표계 |

**TMscript 좌표 프레임:**
```
"CPP" - Cartesian Position (Base Frame)
"JPP" - Joint Position
"CAP" - Cartesian Arc Position (Circle용)
```

---

### 3.4 단위 변환

| 변환 | 공식 |
|------|------|
| degree → radian | rad = deg × (π / 180) |
| radian → degree | deg = rad × (180 / π) |
| mm → m | m = mm / 1000 |
| m → mm | mm = m × 1000 |

**코드 예시:**
```python
import math

def deg_to_rad(deg):
    return deg * (math.pi / 180.0)

def rad_to_deg(rad):
    return rad * (180.0 / math.pi)
```

---

## 4. 고급 모션 모드 (Advanced Motion Modes)

### 4.1 PVT 모드 (Position-Velocity-Time)

경로 상의 각 포인트에서 위치, 속도, 시간을 정밀 제어.

```
P0(t=0) ──→ P1(t=0.5s) ──→ P2(t=1.0s) ──→ P3(t=1.5s)
   v0           v1              v2             v3
```

**구조:**
```python
class TmPvtPoint:
    time: float           # 시간 (초)
    positions: List[float]  # 위치 (6개)
    velocities: List[float] # 속도 (6개)

class TmPvtTraj:
    mode: TmPvtMode       # Joint 또는 Tool
    points: List[TmPvtPoint]
    total_time: float
```

**모드:**
| 모드 | 설명 |
|------|------|
| `Joint` | 관절 좌표 기준 PVT |
| `Tool` | TCP 좌표 기준 PVT |

**함수:**
| 함수 | 설명 |
|------|------|
| `set_pvt_enter(mode)` | PVT 모드 시작 |
| `set_pvt_point(mode, t, pos, vel)` | 포인트 추가 |
| `set_pvt_traj(pvts)` | 전체 궤적 전송 |
| `set_pvt_exit()` | PVT 모드 종료 |

**사용 시점:**
- 정밀 궤적 제어
- 시간 동기화 필요 시
- 부드러운 연속 동작

---

### 4.2 Velocity 모드 (실시간 속도 제어)

실시간으로 속도 명령을 전송하여 로봇 제어.

**함수:**
| 함수 | 설명 |
|------|------|
| `set_vel_mode_start(mode, timeout_zero_vel, timeout_stop)` | 속도 모드 시작 |
| `set_vel_mode_target(mode, vel)` | 목표 속도 설정 |
| `set_vel_mode_stop()` | 속도 모드 종료 |

**파라미터:**
| 파라미터 | 설명 | 단위 |
|----------|------|------|
| `mode` | Joint 또는 Tool | - |
| `timeout_zero_vel` | 속도 0 유지 타임아웃 | 초 |
| `timeout_stop` | 정지 타임아웃 | 초 |
| `vel` | 목표 속도 (6개) | rad/s 또는 m/s |

**사용 시점:**
- 실시간 비전 추적
- 컨베이어 동기화
- 조이스틱/원격 제어
- 서보 제어

---

## 5. 제어 명령 (Control Commands)

### 5.1 기본 제어

| 함수 | TMscript | 설명 |
|------|----------|------|
| `set_stop()` | `StopAndClearBuffer()` | 정지 및 버퍼 클리어 |
| `set_pause()` | `Pause()` | 일시 정지 |
| `set_resume()` | `Resume()` | 재개 |
| `script_exit()` | `ScriptExit()` | 외부 제어 모드 종료 |

---

### 5.2 정지 동작 비교

| 명령 | 동작 | 버퍼 | 재개 가능 |
|------|------|------|-----------|
| `Stop` | 즉시 정지 | 클리어 | X |
| `Pause` | 감속 정지 | 유지 | O (Resume) |

---

## 6. 동기화 (Synchronization)

모션 명령과 다른 작업(IO, 대기 등)의 동기화.

### 6.1 태그 (Tag)

| 함수 | 설명 |
|------|------|
| `set_tag(tag, wait)` | 태그 설정 |
| `set_wait_tag(tag, timeout)` | 태그 도달 대기 |

**파라미터:**
| 파라미터 | 설명 |
|----------|------|
| `tag` | 태그 번호 (정수) |
| `wait` | 대기 여부 (0=즉시, 1=대기) |
| `timeout` | 대기 타임아웃 (ms, 0=무한) |

**사용 예시:**
```python
# 이동 명령
set_tool_pose_PTP(pose1, ...)
set_tag(1)  # 태그 1 설정

# 다른 스레드에서
set_wait_tag(1, 5000)  # 태그 1 대기 (5초 타임아웃)
set_io(...)  # 태그 도달 후 IO 제어
```

---

### 6.2 TMscript 동기화

| 명령 | 설명 |
|------|------|
| `QueueTag(n)` | 큐에 태그 삽입 |
| `WaitQueueTag(n)` | 태그 도달 대기 |

---

## 7. IO 제어 (IO Control)

### 7.1 IO 모듈

| 모듈 | 코드 | 설명 |
|------|------|------|
| `ControlBox` | 0 | 제어박스 IO |
| `EndEffector` | 1 | 엔드이펙터 IO |

---

### 7.2 IO 타입

| 타입 | 코드 | 설명 | 방향 |
|------|------|------|------|
| `DI` | 0 | 디지털 입력 | 입력 |
| `DO` | 1 | 디지털 출력 | 출력 |
| `InstantDO` | 2 | 즉시 디지털 출력 | 출력 |
| `AI` | 3 | 아날로그 입력 | 입력 |
| `AO` | 4 | 아날로그 출력 | 출력 |
| `InstantAO` | 5 | 즉시 아날로그 출력 | 출력 |

**DO vs InstantDO:**
- `DO`: 모션 큐에 삽입 (동기화)
- `InstantDO`: 즉시 실행 (비동기)

---

### 7.3 IO 상태

| 상태 | 값 | 설명 |
|------|-----|------|
| `OFF` | 0 | 꺼짐 / LOW |
| `ON` | 1 | 켜짐 / HIGH |
| 아날로그 | 0.0 ~ 10.0 | 전압값 (V) |

---

### 7.4 함수

```python
set_io(module, type, pin, state)
```

| 파라미터 | 설명 |
|----------|------|
| `module` | ControlBox(0) 또는 EndEffector(1) |
| `type` | IO 타입 (DO, InstantDO, AO, InstantAO) |
| `pin` | 핀 번호 |
| `state` | 상태값 (0/1 또는 아날로그 값) |

---

### 7.5 그리퍼 제어 예시

```python
# 그리퍼 닫기 (EndEffector DO0 ON)
set_io(EndEffector, DO, 0, 1)

# 그리퍼 열기 (EndEffector DO0 OFF)
set_io(EndEffector, DO, 0, 0)

# 즉시 그리퍼 닫기
set_io(EndEffector, InstantDO, 0, 1)
```

---

## 8. ROS2 서비스 인터페이스

### 8.1 연결 서비스

**서비스:** `/tm_driver/connect_tm`

```yaml
# ConnectTM.srv
Request:
  int8 server      # 0: TMSVR, 1: TMSCT
  bool connect     # 연결 여부
  bool reconnect   # 재연결 여부
  float64 timeout  # 타임아웃 (초)
  float64 timeval  # 재연결 간격 (초)
Response:
  bool ok          # 성공 여부
```

---

### 8.2 모션 서비스

**서비스:** `/tm_driver/set_positions`

```yaml
# SetPositions.srv
Constants:
  int8 PTP_J = 1
  int8 PTP_T = 2
  int8 LINE_T = 4
  int8 CIRC_T = 6
  int8 PLINE_T = 8

Request:
  int8 motion_type       # 모션 타입
  float64[] positions    # 좌표 (Joint 또는 TCP)
  float64 velocity       # 속도 (rad/s 또는 m/s)
  float64 acc_time       # 가속 시간 (ms)
  int32 blend_percentage # 블렌딩 (%)
  bool fine_goal         # 정밀 모드
Response:
  bool ok
```

---

### 8.3 IO 서비스

**서비스:** `/tm_driver/set_io`

```yaml
# SetIO.srv
Constants:
  int8 MODULE_CONTROLBOX = 0
  int8 MODULE_ENDEFFECTOR = 1
  int8 TYPE_DIGITAL_IN = 0
  int8 TYPE_DIGITAL_OUT = 1
  int8 TYPE_INSTANT_DO = 2
  int8 TYPE_ANALOG_IN = 3
  int8 TYPE_ANALOG_OUT = 4
  int8 TYPE_INSTANT_AO = 5

Request:
  int8 module   # 모듈
  int8 type     # IO 타입
  int8 pin      # 핀 번호
  float32 state # 상태값
Response:
  bool ok
```

---

### 8.4 스크립트 서비스

**서비스:** `/tm_driver/send_script`

```yaml
# SendScript.srv
Request:
  string id      # 스크립트 ID
  string script  # TMscript 명령어
Response:
  bool ok
```

---

## 9. TMscript 명령어

### 9.1 모션 명령

| 명령 | 문법 |
|------|------|
| **PTP** | `PTP(mode, x, y, z, rx, ry, rz, speed, acc, blend, fine)` |
| **Line** | `Line(mode, x, y, z, rx, ry, rz, speed, acc, blend, fine)` |
| **Circle** | `Circle(mode, via_pose, end_pose, speed, acc, blend, fine)` |

**mode:**
- `"CPP"`: Cartesian Position (TCP)
- `"JPP"`: Joint Position

---

### 9.2 IO 명령

| 명령 | 문법 | 설명 |
|------|------|------|
| `SetDO` | `SetDO(pin, state)` | 디지털 출력 |
| `SetAO` | `SetAO(pin, value)` | 아날로그 출력 |
| `GetDI` | `GetDI(pin)` | 디지털 입력 읽기 |
| `GetAI` | `GetAI(pin)` | 아날로그 입력 읽기 |

---

### 9.3 제어 명령

| 명령 | 문법 | 설명 |
|------|------|------|
| `Pause` | `Pause()` | 일시 정지 |
| `Resume` | `Resume()` | 재개 |
| `StopAndClearBuffer` | `StopAndClearBuffer()` | 정지 및 클리어 |
| `ScriptExit` | `ScriptExit()` | 스크립트 종료 |

---

### 9.4 동기화 명령

| 명령 | 문법 | 설명 |
|------|------|------|
| `QueueTag` | `QueueTag(n)` | 태그 삽입 |
| `WaitQueueTag` | `WaitQueueTag(n)` | 태그 대기 |
| `Sleep` | `Sleep(ms)` | 대기 (밀리초) |

---

## 10. 사용 예시

### 10.1 기본 PTP 이동 (Python/ROS2)

```python
from tm_msgs.srv import SetPositions

# 서비스 클라이언트 생성
client = node.create_client(SetPositions, '/tm_driver/set_positions')

# PTP_T로 TCP 좌표 이동
request = SetPositions.Request()
request.motion_type = 2  # PTP_T
request.positions = [400.0, 0.0, 300.0, 180.0, 0.0, 0.0]  # X,Y,Z,Rx,Ry,Rz (mm, deg)
request.velocity = 1.0  # rad/s
request.acc_time = 200.0  # ms
request.blend_percentage = 0
request.fine_goal = True

future = client.call_async(request)
```

---

### 10.2 직선 이동 (LINE_T)

```python
request = SetPositions.Request()
request.motion_type = 4  # LINE_T
request.positions = [400.0, 0.0, 200.0, 180.0, 0.0, 0.0]
request.velocity = 0.1  # m/s
request.acc_time = 200.0
request.blend_percentage = 0
request.fine_goal = True
```

---

### 10.3 그리퍼 제어

```python
from tm_msgs.srv import SetIO

request = SetIO.Request()
request.module = 1  # EndEffector
request.type = 1    # DO
request.pin = 0     # DO0
request.state = 1.0 # ON (닫기)
```

---

### 10.4 TMscript 전송

```python
from tm_msgs.srv import SendScript

# 복합 동작: 이동 후 그리퍼 닫기
script = '''
PTP("CPP", 400, 0, 300, 180, 0, 0, 100, 200, 0, false)
QueueTag(1)
WaitQueueTag(1)
SetDO(0, 1)
'''

request = SendScript.Request()
request.id = "pick_action"
request.script = script
```

---

### 10.5 팔레트 픽업 시퀀스

```python
# 1. 홈 → AR 검색 위치 (PTP_J, 빠른 이동)
move_ptp_j(home_joints, vel=80, acc=150, blend=0)

# 2. AR 검색 위치 → 접근 위치 (PTP_T)
move_ptp_t(approach_pose, vel=50, acc=200, blend=0)

# 3. 접근 → 픽업 위치 (LINE_T, 직선 하강)
move_line_t(pick_pose, vel=0.05, acc=200, blend=0, fine=True)

# 4. 그리퍼 닫기
set_io(EndEffector, DO, 0, 1)
sleep(500)

# 5. 들어올리기 (LINE_T, 직선 상승)
move_line_t(lift_pose, vel=0.05, acc=200, blend=0, fine=True)

# 6. 배치 위치로 이동 (PTP_T)
move_ptp_t(place_approach, vel=50, acc=200, blend=0)

# 7. 배치 (LINE_T, 직선 하강)
move_line_t(place_pose, vel=0.05, acc=200, blend=0, fine=True)

# 8. 그리퍼 열기
set_io(EndEffector, DO, 0, 0)
sleep(300)

# 9. 후퇴 (LINE_T)
move_line_t(retreat_pose, vel=0.1, acc=200, blend=0)
```

---

## 부록: 권장 파라미터

### A. 작업별 권장 설정

| 작업 | 모션 | 속도 | 가속 | 블렌딩 | 정밀 |
|------|------|------|------|--------|------|
| 빈 공간 이동 | PTP_J/T | 70-100% | 100-200ms | 30-50% | false |
| 픽업 접근 | LINE_T | 0.05-0.1 m/s | 200-300ms | 0% | true |
| 픽업 하강 | LINE_T | 0.02-0.05 m/s | 200-300ms | 0% | true |
| 들어올리기 | LINE_T | 0.05-0.1 m/s | 200-300ms | 0% | true |
| 배치 하강 | LINE_T | 0.02-0.05 m/s | 200-300ms | 0% | true |

---

### B. 안전 고려사항

1. **충돌 방지**: 빈 공간이 아니면 LINE_T 사용
2. **속도 제한**: 사람 근처에서는 속도 50% 이하
3. **정밀 모드**: 픽업/배치 시 fine_goal = true
4. **블렌딩 주의**: 정확한 위치 필요 시 blend = 0%
5. **비상 정지**: 항상 비상 정지 버튼 접근 가능하게

---

*문서 버전: 1.0*
*최종 수정: 2025-12-15*
