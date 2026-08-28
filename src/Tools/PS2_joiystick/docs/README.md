# PS2 Joystick for TM Robot

PS2/Xbox 조이스틱을 사용하여 TM Robot을 조그(Jog) 제어하는 기능입니다.

## 개요

- **데드맨 스위치 방식**: 안전 버튼을 누른 상태에서만 로봇이 움직입니다
- **듀얼 버튼 제어**: XYZ 이동과 RxRyRz 회전을 별도 버튼으로 제어
- **설정 파일**: YAML 파일로 버튼/축 매핑 변경 가능

## 조작 방법

| 버튼 | 기능 | 축 매핑 |
|------|------|---------|
| **버튼 2** 누름 | XYZ 이동 모드 | 축0→X, 축1→Y, 축7→Z |
| **버튼 5** 누름 | RxRyRz 회전 모드 | 축3→Rx, 축4→Ry, 축7→Rz |

## 파일 구조

```
PS2_joiystick/
├── docs/
│   ├── README.md       # 이 파일
│   ├── USAGE.md        # 상세 사용법
│   └── CONFIG.md       # 설정 파일 가이드
└── scripts/
    └── joystick_test.py  # 조이스틱 테스트 스크립트
```

## 관련 파일 (TM_Robot_Task_Manager)

| 파일 | 경로 | 설명 |
|------|------|------|
| 설정 파일 | `config/joystick_config.yaml` | 버튼/축 매핑 설정 |
| 서비스 | `tm_task_manager/services/joystick_service.py` | 조이스틱 입력 처리 |
| UI 통합 | `tm_task_manager/tabs/task_edit_tab.py` | Task 편집 탭 연결 |

## 빠른 시작

1. 조이스틱 연결 확인:
   ```bash
   ls /dev/input/js0
   ```

2. 조이스틱 테스트:
   ```bash
   python3 scripts/joystick_test.py
   ```

3. TM Robot Task Manager에서:
   - Task 편집 탭으로 이동
   - "Enable PS2 Jog" 체크박스 활성화
   - 버튼 2 또는 5를 누른 상태로 조이스틱 조작

## 안전 주의사항

- **항상 데드맨 버튼을 누른 상태에서만 조작**하세요
- 비상 시 데드맨 버튼을 놓으면 즉시 정지합니다
- 처음 사용 시 낮은 속도로 테스트하세요 (설정 파일에서 `velocity_percent` 조정)
