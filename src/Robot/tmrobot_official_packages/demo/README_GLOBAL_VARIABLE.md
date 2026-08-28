# Global Variable Demo

C++ 프로그램으로 TM Flow의 글로벌 변수를 읽고 쓰는 기능입니다.

## 사용 방법

### 1. TM Driver 실행 필요
먼저 TM Driver가 실행되어 있어야 합니다.

### 2. 글로벌 변수 읽기
```bash
ros2 run demo demo_global_variable read <변수이름>
```

예시:
```bash
ros2 run demo demo_global_variable read g_robot_command
```

### 3. 글로벌 변수 쓰기
```bash
ros2 run demo demo_global_variable write <변수이름> <값>
```

예시:
```bash
ros2 run demo demo_global_variable write g_robot_command 5
```

## 구현 파일
- 소스 파일: `/home/amap/TM_Robot_ros2_ws/src/Robot/tmrobot_official_packages/demo/src/demo_global_variable.cpp`
- 빌드: `colcon build --packages-select demo`

## 사용하는 서비스
- `/ask_item` - 변수 읽기
- `/write_item` - 변수 쓰기

## UI와 통합
Python UI에서 이 프로그램을 subprocess로 실행하여 사용할 수 있습니다.

예시:
```python
import subprocess

# 읽기
result = subprocess.run(
    ['ros2', 'run', 'demo', 'demo_global_variable', 'read', 'g_robot_command'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print(f"Success: {result.stdout}")
else:
    print(f"Error: {result.stderr}")

# 쓰기
result = subprocess.run(
    ['ros2', 'run', 'demo', 'demo_global_variable', 'write', 'g_robot_command', '5'],
    capture_output=True,
    text=True
)
```
