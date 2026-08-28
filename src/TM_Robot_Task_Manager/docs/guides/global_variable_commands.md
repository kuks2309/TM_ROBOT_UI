# TM Robot 글로벌 변수 읽기/쓰기 명령어

## ROS2 서비스를 이용한 글로벌 변수 제어

TM Robot의 글로벌 변수를 ROS2 서비스를 통해 읽고 쓸 수 있습니다.

### 1. 글로벌 변수 읽기

#### 기본 형식
```bash
ros2 service call /ask_item tm_msgs/srv/AskItem "{id: 'gv', item: '<변수이름>', wait_time: 0.2}"
```

#### 예시

**정수형 변수 읽기 (g_robot_command)**
```bash
ros2 service call /ask_item tm_msgs/srv/AskItem "{id: 'gv', item: 'g_robot_command', wait_time: 0.2}"
```

응답 예시:
```
tm_msgs.srv.AskItem_Response(ok=True, id='gv', value='g_robot_command=0')
```

**Base 배열 변수 읽기 (g_TM_Landmark)**
```bash
ros2 service call /ask_item tm_msgs/srv/AskItem "{id: 'gv', item: 'g_TM_Landmark', wait_time: 0.2}"
```

응답 예시:
```
tm_msgs.srv.AskItem_Response(ok=True, id='gv', value='g_TM_Landmark={-8.400841,819.9467,-29.613598,-179.51918,-0.0433814,179.44727}')
```

**Float 변수 읽기**
```bash
ros2 service call /ask_item tm_msgs/srv/AskItem "{id: 'gv', item: 'g_TM_ObjectX', wait_time: 0.2}"
```

### 2. 글로벌 변수 쓰기

#### 기본 형식
```bash
ros2 service call /send_script tm_msgs/srv/SendScript "{id: 'gv', script: '<변수이름>=<값>'}"
```

#### 예시

**정수형 변수 쓰기**
```bash
ros2 service call /send_script tm_msgs/srv/SendScript "{id: 'gv', script: 'g_robot_command=2'}"
```

**Float 변수 쓰기**
```bash
ros2 service call /send_script tm_msgs/srv/SendScript "{id: 'gv', script: 'g_TM_ObjectX=123.45'}"
```

**Base 배열 변수 쓰기**
```bash
ros2 service call /send_script tm_msgs/srv/SendScript "{id: 'gv', script: 'g_TM_Landmark={100,200,300,0,0,0}'}"
```

### 3. 파라미터 설명

#### AskItem 서비스 파라미터
- `id`: 식별자 (글로벌 변수는 'gv' 사용)
- `item`: 읽을 변수 이름
- `wait_time`: 대기 시간 (초 단위, 보통 0.2 사용)

#### SendScript 서비스 파라미터
- `id`: 식별자 (글로벌 변수는 'gv' 사용)
- `script`: 실행할 TMscript 명령어

### 4. 응답 해석

#### 성공 시
```
ok=True
value='<변수이름>=<값>'
```

#### 실패 시
```
ok=False
value='<에러 메시지>'
```

### 5. Python 코드에서 사용

프로젝트에서는 `GlobalVariableService` 클래스를 사용합니다:

```python
from tm_task_manager.global_variable_service import GlobalVariableService

# 읽기
success, result = gv_service.read_variable('g_robot_command')
if success:
    print(f"Value: {result}")

# 쓰기
success, result = gv_service.write_variable('g_robot_command', 2)
if success:
    print("Write successful")
```

자세한 내용은 [global_variable_service.py](../../tm_task_manager/global_variable_service.py) 참조

### 6. 주의사항

1. **id는 반드시 'gv'로 설정해야 합니다**
   - ❌ `id: ''` (빈 문자열)
   - ✅ `id: 'gv'`

2. **변수 이름은 정확히 입력해야 합니다**
   - 대소문자 구분
   - TM Flow에서 정의한 변수명과 동일해야 함

3. **TM Driver가 실행 중이어야 합니다**
   - 서비스 사용 전 TM Robot과 연결 필요

4. **wait_time은 0.2초 권장**
   - 너무 짧으면 타임아웃 발생 가능
   - 너무 길면 응답 지연

### 7. 트러블슈팅

**문제: waiting for service to become available...**
- 원인: TM Driver가 실행되지 않음
- 해결: TM Driver 실행 확인

**문제: ok=False 응답**
- 원인: 변수 이름이 잘못되었거나 변수가 존재하지 않음
- 해결: TM Flow에서 변수 이름 확인

**문제: 타임아웃**
- 원인: TM Robot 연결 끊김
- 해결: 네트워크 연결 및 TM Robot 상태 확인

## 참고 문서
- [test_global_variable.py](../../test_global_variable.py) - 테스트 스크립트
- [global_variable_service.py](../../tm_task_manager/global_variable_service.py) - 서비스 클래스
