# PS2 Joystick 사용법

## 1. 조이스틱 연결 확인

### 장치 확인
```bash
ls /dev/input/js*
# 출력 예: /dev/input/js0
```

### 장치 정보 확인
```bash
cat /proc/bus/input/devices | grep -A 5 "js0"
```

### 권한 문제 해결
```bash
# input 그룹에 사용자 추가
sudo usermod -a -G input $USER

# 재로그인 필요
```

## 2. 조이스틱 테스트

### 테스트 스크립트 실행
```bash
cd /home/amap/TM_Robot_ros2_ws/src/Tools/PS2_joiystick
python3 scripts/joystick_test.py
```

### 출력 예시
```
조이스틱 테스트: /dev/input/js0
종료: Ctrl+C
--------------------------------------------------
연결됨: /dev/input/js0

축 0: +0.523 ( +17134)
축 1: -0.312 ( -10234)
버튼 2: 눌림
버튼 2: 해제
버튼 5: 눌림
```

### 버튼/축 번호 확인
테스트 스크립트로 실제 조이스틱의 버튼/축 번호를 확인하고, 필요 시 설정 파일을 수정하세요.

## 3. TM Robot Task Manager에서 사용

### 활성화
1. TM Robot Task Manager 실행
2. **Task 편집** 탭 선택 (첫 번째 탭)
3. **"Enable PS2 Jog"** 체크박스 활성화
4. 연결 상태 확인: "Status: Connected"

### 조작 방법

#### XYZ 이동 (버튼 2)
| 조이스틱 | 로봇 동작 |
|----------|-----------|
| 축 0 (좌우) | X축 이동 |
| 축 1 (상하) | Y축 이동 |
| 축 7 | Z축 이동 |

#### RxRyRz 회전 (버튼 5)
| 조이스틱 | 로봇 동작 |
|----------|-----------|
| 축 3 | Rx 회전 |
| 축 4 | Ry 회전 |
| 축 7 | Rz 회전 |

### 조그 파라미터 조정
설정 파일 (`config/joystick_config.yaml`)에서 조정:

```yaml
jog:
  step_mm: 1.0          # 이동 거리 (mm)
  step_deg: 0.5         # 회전 각도 (deg)
  velocity_percent: 10  # 속도 (%)
```

## 4. 트러블슈팅

### 문제: "장치를 찾을 수 없습니다"
- 조이스틱이 USB에 연결되어 있는지 확인
- `ls /dev/input/js*` 로 장치 확인
- 다른 js 번호면 설정 파일의 `device_path` 수정

### 문제: "장치 권한 없음"
```bash
sudo usermod -a -G input $USER
# 로그아웃 후 다시 로그인
```

### 문제: 조이스틱이 반응하지 않음
1. 테스트 스크립트로 입력 확인
2. 데드맨 버튼(2 또는 5)을 누르고 있는지 확인
3. 데드존 설정 확인 (기본 0.15)

### 문제: 잘못된 축/버튼 매핑
1. 테스트 스크립트로 실제 번호 확인
2. `config/joystick_config.yaml` 수정
3. 프로그램 재시작
