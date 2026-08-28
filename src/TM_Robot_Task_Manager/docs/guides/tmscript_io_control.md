# TM Robot IO 제어 매뉴얼

## 개요

TM Robot의 IO(Input/Output)를 TMscript 또는 ROS2를 통해 읽고 제어하는 방법을 설명합니다.

---

## 1. 지원 모듈 및 채널 정보

### 1.1 Control Box

| IO 타입 | 채널 수 | 인덱스 범위 | 모드 | 전압 범위 |
|---------|---------|-------------|------|-----------|
| DI (Digital Input) | 16채널 | [0] ~ [15] | R (읽기) | 0: Low, 1: High |
| DO (Digital Output) | 16채널 | [0] ~ [15] | R/W (읽기/쓰기) | 0: Low, 1: High |
| AI (Analog Input) | 2채널 | [0] ~ [1] | R (읽기) | -10.24V ~ +10.24V |
| AO (Analog Output) | 2채널 | [0] ~ [1] | R/W (읽기/쓰기) | -10.00V ~ +10.00V |

### 1.2 End Module

| IO 타입 | 채널 수 | 인덱스 범위 | 모드 | 전압 범위 |
|---------|---------|-------------|------|-----------|
| DI (Digital Input) | 4채널 | [0] ~ [3] | R (읽기) | 0: Low, 1: High |
| DO (Digital Output) | 4채널 | [0] ~ [3] | R/W (읽기/쓰기) | 0: Low, 1: High |
| AI (Analog Input) | 1채널 | [0] | R (읽기) | -10.24V ~ +10.24V |

### 1.3 External Module (ExtModuleN)

외부 모듈의 채널 수는 실제 연결된 하드웨어에 따라 다릅니다.

### 1.4 Safety Module

| IO 타입 | 채널 수 | 인덱스 범위 | 모드 | 설명 |
|---------|---------|-------------|------|------|
| SI (Safety Input) | 8채널 | [0] ~ [7] | R (읽기) | 안전 입력 |
| SO (Safety Output) | 8채널 | [0] ~ [7] | R (읽기) | 안전 출력 |

**Safety Input 할당:**
- SI[0] = SF1: User Connected ESTOP Input
- SI[1] = SF3: User Connected External Safeguard Input
- SI[2] ~ SI[7]: Safety Input Ports 설정에 따름

---

## 2. TMscript를 이용한 IO 제어

### 2.1 기본 구문

```c
IO[모듈이름].속성[인덱스]
```

**모듈 이름:**
- `ControlBox` - 컨트롤 박스
- `EndModule` - 엔드 모듈
- `ExtModuleN` - 외부 모듈 (N = 0, 1, 2...)
- `Safety` - 안전 모듈

### 2.2 Digital Input 읽기

```c
// Control Box 전체 DI 읽기
byte[] di = IO["ControlBox"].DI

// 특정 채널 읽기
byte di0 = IO["ControlBox"].DI[0]      // DI[0] 상태
byte di5 = IO["ControlBox"].DI[5]      // DI[5] 상태

// End Module DI 읽기
byte ee_di0 = IO["EndModule"].DI[0]

// DI 채널 수 확인
int dilen = Length(IO["ControlBox"].DI)  // 결과: 16
```

### 2.3 Digital Output 읽기/쓰기

```c
// DO 상태 읽기
byte[] do_all = IO["ControlBox"].DO
byte do2 = IO["ControlBox"].DO[2]

// DO 쓰기 (개별 채널)
IO["ControlBox"].DO[0] = 1    // DO[0]을 High로 설정
IO["ControlBox"].DO[0] = 0    // DO[0]을 Low로 설정

// End Module DO 쓰기
IO["EndModule"].DO[1] = 1     // End Module DO[1]을 High로 설정
```

### 2.4 Analog Input 읽기

```c
// Control Box AI 읽기
float[] ai = IO["ControlBox"].AI
float ai0 = IO["ControlBox"].AI[0]     // AI[0] 전압값 (-10.24V ~ +10.24V)

// End Module AI 읽기
float ee_ai0 = IO["EndModule"].AI[0]
```

### 2.5 Analog Output 읽기/쓰기

```c
// AO 상태 읽기
float[] ao = IO["ControlBox"].AO
float ao0 = IO["ControlBox"].AO[0]

// AO 쓰기 (전압값 설정)
IO["ControlBox"].AO[0] = 3.3   // AO[0]을 3.3V로 설정
IO["ControlBox"].AO[1] = -5.0  // AO[1]을 -5.0V로 설정
```

### 2.6 Safety IO 읽기

```c
// Safety Input 읽기 (읽기 전용)
byte si0 = IO["Safety"].SI[0]    // ESTOP 상태
byte si1 = IO["Safety"].SI[1]    // External Safeguard 상태

// Safety Output 읽기 (읽기 전용)
byte so0 = IO["Safety"].SO[0]
```

**주의:** Safety IO는 읽기만 가능합니다.

---

## 3. Queue 명령 vs Instant 명령

### 3.1 차이점

| 구분 | Queue 명령 | Instant 명령 |
|------|------------|--------------|
| 속성 | DI, DO, AI, AO | InstantDI, InstantDO, InstantAI, InstantAO |
| 실행 시점 | 이전 모션 완료 후 순차 실행 | 모션 중에도 즉시 실행 |
| 사용 상황 | 모션과 동기화 필요 시 | 실시간 제어 필요 시 |

### 3.2 사용 예시

```c
// Queue 명령 - 모션 완료 후 실행
PTP("JPP", P1, 100, 200, 100, false)
IO["ControlBox"].DO[0] = 1              // P1 도착 후 DO[0] = High

// Instant 명령 - 모션 중 즉시 실행
PTP("JPP", P2, 100, 200, 100, false)
IO["ControlBox"].InstantDO[1] = 1       // 모션 중에도 즉시 DO[1] = High
```

### 3.3 Instant 명령 구문

```c
// Instant Digital Input 읽기
byte di7 = IO["ControlBox"].InstantDI[7]

// Instant Digital Output 쓰기
IO["ControlBox"].InstantDO[0] = 1

// Instant Analog Input 읽기
float ai0 = IO["ControlBox"].InstantAI[0]

// Instant Analog Output 쓰기
IO["ControlBox"].InstantAO[0] = 5.0
```

---

## 4. ROS2를 이용한 IO 제어

### 4.1 IO 상태 읽기 (토픽 구독)

**토픽:** `/feedback_states`  
**메시지 타입:** `tm_msgs/msg/FeedbackState`

#### 포함된 IO 필드

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `cb_digital_input` | uint8[] | Control Box DI (16채널) |
| `cb_digital_output` | uint8[] | Control Box DO (16채널) |
| `cb_analog_input` | float32[] | Control Box AI |
| `cb_analog_output` | float32[] | Control Box AO |
| `ee_digital_input` | uint8[] | End Effector DI (4채널) |
| `ee_digital_output` | uint8[] | End Effector DO (4채널) |
| `ee_analog_input` | float32[] | End Effector AI |
| `ee_analog_output` | float32[] | End Effector AO |

#### 명령어 예시

```bash
# 토픽 한 번 확인
ros2 topic echo /feedback_states --once

# IO 필드만 필터링
ros2 topic echo /feedback_states --field cb_digital_input
ros2 topic echo /feedback_states --field cb_digital_output
```

#### Python 코드 예시

```python
import rclpy
from rclpy.node import Node
from tm_msgs.msg import FeedbackState

class IOMonitor(Node):
    def __init__(self):
        super().__init__('io_monitor')
        self.subscription = self.create_subscription(
            FeedbackState,
            '/feedback_states',
            self.feedback_callback,
            10
        )
    
    def feedback_callback(self, msg):
        # Control Box DI 읽기
        cb_di = msg.cb_digital_input
        self.get_logger().info(f'CB DI: {list(cb_di)}')
        
        # Control Box DO 읽기
        cb_do = msg.cb_digital_output
        self.get_logger().info(f'CB DO: {list(cb_do)}')
        
        # End Effector DI 읽기
        ee_di = msg.ee_digital_input
        self.get_logger().info(f'EE DI: {list(ee_di)}')
```

### 4.2 IO 쓰기 (서비스 호출)

**서비스:** `/set_io`  
**서비스 타입:** `tm_msgs/srv/SetIO`

#### 파라미터 정의

**Module:**
```
MODULE_CONTROLBOX = 0
MODULE_ENDEFFECTOR = 1
```

**Type:**
```
TYPE_DIGITAL_IN = 0      # (사용 안 함 - 읽기 전용)
TYPE_DIGITAL_OUT = 1     # Digital Output (Queue)
TYPE_INSTANT_DO = 2      # Digital Output (Instant)
TYPE_ANALOG_IN = 3       # (사용 안 함 - 읽기 전용)
TYPE_ANALOG_OUT = 4      # Analog Output (Queue)
TYPE_INSTANT_AO = 5      # Analog Output (Instant)
```

**State:**
```
STATE_OFF = 0
STATE_ON = 1
# Analog의 경우 전압값 (예: 3.3, -5.0)
```

#### 명령어 예시

```bash
# Control Box DO[0] = ON
ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 1, pin: 0, state: 1.0}"

# Control Box DO[0] = OFF
ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 1, pin: 0, state: 0.0}"

# Control Box Instant DO[2] = ON
ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 2, pin: 2, state: 1.0}"

# End Effector DO[1] = ON
ros2 service call /set_io tm_msgs/srv/SetIO "{module: 1, type: 1, pin: 1, state: 1.0}"

# Control Box AO[0] = 3.3V
ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 4, pin: 0, state: 3.3}"

# Control Box Instant AO[0] = 5.0V
ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 5, pin: 0, state: 5.0}"
```

#### Python 코드 예시

```python
import rclpy
from rclpy.node import Node
from tm_msgs.srv import SetIO

class IOController(Node):
    def __init__(self):
        super().__init__('io_controller')
        self.client = self.create_client(SetIO, '/set_io')
        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /set_io service...')
    
    def set_digital_output(self, module: int, pin: int, state: bool, instant: bool = False):
        """
        Digital Output 설정
        
        Args:
            module: 0=ControlBox, 1=EndEffector
            pin: 핀 번호 (0~15 for CB, 0~3 for EE)
            state: True=ON, False=OFF
            instant: True=Instant 명령, False=Queue 명령
        """
        request = SetIO.Request()
        request.module = module
        request.type = 2 if instant else 1  # TYPE_INSTANT_DO or TYPE_DIGITAL_OUT
        request.pin = pin
        request.state = 1.0 if state else 0.0
        
        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        return future.result().ok
    
    def set_analog_output(self, module: int, pin: int, voltage: float, instant: bool = False):
        """
        Analog Output 설정
        
        Args:
            module: 0=ControlBox, 1=EndEffector
            pin: 핀 번호
            voltage: 전압값 (-10.0V ~ +10.0V)
            instant: True=Instant 명령, False=Queue 명령
        """
        request = SetIO.Request()
        request.module = module
        request.type = 5 if instant else 4  # TYPE_INSTANT_AO or TYPE_ANALOG_OUT
        request.pin = pin
        request.state = voltage
        
        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        return future.result().ok

# 사용 예시
def main():
    rclpy.init()
    controller = IOController()
    
    # Control Box DO[0] = ON
    controller.set_digital_output(module=0, pin=0, state=True)
    
    # Control Box DO[0] = OFF (Instant)
    controller.set_digital_output(module=0, pin=0, state=False, instant=True)
    
    # Control Box AO[0] = 3.3V
    controller.set_analog_output(module=0, pin=0, voltage=3.3)
    
    rclpy.shutdown()
```

---

## 5. 주의사항

### 5.1 읽기 전용 속성

다음 속성은 **읽기만 가능**합니다:
- `DI`, `InstantDI` (Digital Input)
- `AI`, `InstantAI` (Analog Input)
- `SI`, `SO` (Safety IO)

```c
// ❌ 잘못된 사용 - 에러 발생
IO["ControlBox"].DI[0] = 1        // DI는 읽기 전용
IO["Safety"].SI[0] = 0            // SI는 읽기 전용
IO["Safety"].SO[4] = 1            // SO는 읽기 전용

// ✅ 올바른 사용
byte di0 = IO["ControlBox"].DI[0]  // 읽기
IO["ControlBox"].DO[0] = 1         // DO는 쓰기 가능
```

### 5.2 배열 범위 초과

인덱스가 배열 범위를 초과하면 에러가 발생합니다.

```c
// ❌ 에러 - Control Box DI는 [0]~[15]
byte di32 = IO["ControlBox"].DI[32]

// ❌ 에러 - End Module DI는 [0]~[3]
byte ee_di5 = IO["EndModule"].DI[5]
```

### 5.3 모듈별 지원 속성

각 모듈은 지원하는 속성이 다릅니다.

```c
// ❌ 에러 - ControlBox는 SI 미지원
byte si1 = IO["ControlBox"].SI[1]

// ❌ 에러 - Safety는 DI 미지원
byte di2 = IO["Safety"].DI[2]

// ❌ 에러 - ControlBox는 SO 미지원
IO["ControlBox"].SO[1] = 1
```

### 5.4 배열 전체 쓰기 시 크기 일치

배열 전체를 쓸 때는 크기가 정확히 일치해야 합니다.

```c
// ❌ 에러 - Control Box DO는 16채널
IO["ControlBox"].DO = {1,1,0,0}              // 4개만 제공

// ✅ 올바른 사용 - 개별 채널 쓰기
IO["ControlBox"].DO[0] = 1
IO["ControlBox"].DO[1] = 1
IO["ControlBox"].DO[2] = 0
IO["ControlBox"].DO[3] = 0
```

### 5.5 TM Driver 연결 필수

ROS2 서비스 사용 시 TM Driver가 실행 중이어야 합니다.

```bash
# TM Driver 실행 확인
ros2 node list | grep tm_driver

# 서비스 사용 가능 여부 확인
ros2 service list | grep set_io
```

---

## 6. 트러블슈팅

### 문제: 서비스 응답 ok=False

**원인:**
- 잘못된 module 값 (0 또는 1만 가능)
- 잘못된 type 값
- 존재하지 않는 pin 번호
- TM Robot 연결 끊김

**해결:**
```bash
# 파라미터 확인
# module: 0=ControlBox, 1=EndEffector
# type: 1=DO, 2=InstantDO, 4=AO, 5=InstantAO
# pin: 모듈별 유효 범위 내

# 연결 상태 확인
ros2 topic echo /feedback_states --field is_svr_connected --once
```

### 문제: 토픽에서 IO 값이 업데이트되지 않음

**원인:**
- TM Driver가 실행되지 않음
- 네트워크 연결 문제

**해결:**
```bash
# TM Driver 재시작
ros2 launch tm_driver tm_driver.launch.py

# 토픽 발행 확인
ros2 topic hz /feedback_states
```

### 문제: TMscript에서 IO 접근 에러

**원인:**
- 모듈 이름 오타
- 지원하지 않는 속성 접근
- 인덱스 범위 초과

**해결:**
- 모듈 이름 정확히 입력: `"ControlBox"`, `"EndModule"`, `"Safety"`
- 지원 속성 확인 (위 표 참조)
- 인덱스 범위 확인

---

## 7. 빠른 참조

### TMscript 명령어 요약

| 작업 | 명령어 |
|------|--------|
| Control Box DI 읽기 | `IO["ControlBox"].DI[n]` |
| Control Box DO 쓰기 | `IO["ControlBox"].DO[n] = 0 or 1` |
| Control Box AI 읽기 | `IO["ControlBox"].AI[n]` |
| Control Box AO 쓰기 | `IO["ControlBox"].AO[n] = voltage` |
| End Module DI 읽기 | `IO["EndModule"].DI[n]` |
| End Module DO 쓰기 | `IO["EndModule"].DO[n] = 0 or 1` |
| Safety Input 읽기 | `IO["Safety"].SI[n]` |
| Instant DO 쓰기 | `IO["ControlBox"].InstantDO[n] = 0 or 1` |

### ROS2 명령어 요약

| 작업 | 명령어 |
|------|--------|
| IO 상태 확인 | `ros2 topic echo /feedback_states --once` |
| CB DO 설정 | `ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 1, pin: N, state: 1.0}"` |
| CB Instant DO 설정 | `ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 2, pin: N, state: 1.0}"` |
| EE DO 설정 | `ros2 service call /set_io tm_msgs/srv/SetIO "{module: 1, type: 1, pin: N, state: 1.0}"` |
| CB AO 설정 | `ros2 service call /set_io tm_msgs/srv/SetIO "{module: 0, type: 4, pin: N, state: VOLTAGE}"` |

---

## 참고 문서

- TMscript Programming Language Manual (v2.18)
- TM Robot Expression Manual - Chapter 6.5 IO
- [global_variable_commands.md](./global_variable_commands.md) - 글로벌 변수 제어
