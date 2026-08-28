# ADR: 자세유지 포인트 이동 (pose_keep_move_to_point)

- 날짜: 2026-07-27 (KST, Korea Standard Time)
- 관련: [worklog 2026-07-27](../worklog/2026-07-27.md), 사용자 지시(2026-07-27 09:37) "moveit 없이 point 이동으로 엔드이펙터 이동 + 자세 최대 유지 + Z 먼저 / 회전 마지막"
- 대상: `JobExecutor` 신규 Job 타입 1종 (MoveIt 미사용, `tm_driver` `set_positions` LINE_T 직접 사용)

## Status

**Approved (사용자 결정 2026-07-27)** — 축 순서 = 적응형(안전순), 회전 = 현재 자세 완전 고정, 범위 = 신규 Job + PyQt/웹 브리지 양쪽 등록, 순서 = 구현 먼저·기동 후속.

## Context

**요구**: 엔드이펙터가 든 자세를 이동 중에도 최대한 유지. 축 순서는 Z 우선 또는 회전 최후.

**현 코드의 자세 변동 원인 2가지 (별개)**

1. **경로 중간 드리프트 — PTP(Point To Point) 보간**: `move_to_point` 는 PTP_T → 드라이버가 `PTP("CPP", …)` 생성([tm_command.cpp:55-67](../../src/Robot/tmrobot_official_packages/tm_driver/src/tm_command.cpp)). 목표만 직교좌표이고 보간은 관절공간이라 시작·끝 자세가 같아도 중간에 TCP(Tool Center Point) 자세가 휜다.
   LINE_T 는 `Line("CAP", x,y,z,rx,ry,rz, vel_mm/s, acc_ms, blend, fine)`([tm_command.cpp:68-81](../../src/Robot/tmrobot_official_packages/tm_driver/src/tm_command.cpp)) = 직교 직선 보간 → 양 끝 자세가 같으면 경로 전체 자세 변화가 원리상 0.
2. **목표 자세가 애초에 현재와 다름**: `move_to_point`([job_executor.py:590-598](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py))·`line_move_to_point`([job_executor.py:771-777](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py)) 모두 파라미터 Rx/Ry/Rz 를 그대로 목표로 전송 → 티칭값이 현재와 조금만 달라도 병진·회전이 섞여 동시 진행.

**중복 조사 (coding SOP §2)**

- 자세 고정 유사 로직: `recipe_mode == 'teaching'` 의 부분 기능만 존재(상대→절대 변환에서 위치만 변환, 자세는 마스터 유지 — [job_executor.py:606-621](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py)). 축 분해·자세 lock 전용 함수는 **활성 코드에 0건**(`pose_keep`/`axis_order`/`orientation_lock` grep 0).
- LINE_T 전송: `_move_to_position_line`(job_executor.py:441) **재사용**(신규 전송 함수 만들지 않음).
- 각도 최단차: `RobotMotionService._angle_difference_deg`(robot_motion_service.py:275) **재사용**(양 노드가 `motion_service` 보유 — main_window·bridge_node:60). private 접근 스멜은 debt-003 로 등록.
- 속도 단위: `%` → LINE_T 는 `MAX_TCP_SPEED=1.0 m/s` 비례 변환(coordinate_transformer.py:36-37) — 기존 경로 그대로.

## Decision

**신규 Job `pose_keep_move_to_point`("자세유지 포인트 이동") 1종 추가. 기존 Job·기존 로직 무수정.**

### 원리 (2단 메커니즘)

```
① 자세 lock  : 이동 시작 시점의 현재 TCP 자세(Rx,Ry,Rz)를 모든 구간의 목표 자세로 사용
               → 회전 명령을 아예 보내지 않음 (자세 변화 지령 0)
② 축 분해     : 적응형(안전순) — 상승(dZ>0): Z 상승 → XY
                                하강(dZ<0): XY → Z 하강
                                |dZ| < 0.1mm: XY 단일 구간
각 구간 = LINE_T(직교 직선) + 자세 동일 → 구간 내부에서도 자세 변화 0
```

회전 명령이 없으므로 "회전 최후" 는 자동 충족(회전 구간 부재).

### 구현 요소

| 파일 | 변경 | 내용 |
|---|---|---|
| `job_executor.py` | 추가 | 상수 `POSE_KEEP_MIN_SEGMENT_MM=0.1`, `_exec_pose_keep_move_to_point`, `_build_pose_keep_segments`(순수함수), `_log_orientation_deviation`, `_execute_job` 분기 1줄 |
| `recipe_manager.py` | 추가 | `JOB_TYPES['pose_keep_move_to_point']` 스키마 (`motion_type`(tcp)·`X`·`Y`·`Z`·`offset X/Y/Z`·`velocity`) — **Rx/Ry/Rz 파라미터 없음**(자세는 실행 시점 현재값 고정이라 두면 오해 유발) |
| `tabs/task_edit_tab.py` | 추가 | 단독 실행 분기 + 래퍼(`line_move_to_point` 패턴 미러) |
| `tm_web_bridge/bridge_node.py` | 추가 | `SEQUENCE_WHITELIST` 1줄 (속도 clamp 30% 는 기존 generic 로직이 자동 적용) |
| `test/test_pose_keep_move.py` | 신규 | 구간 분해·자세 lock·실패중단 단위 테스트(ROS mock, 로봇 무동작) |

### 설계 결정 세부

- **기본 속도 10%**(= 0.1 m/s): 물건을 든 이동이므로 기존 `line_move_to_point`(25%)보다 보수적.
- **실패 시 PTP 폴백 금지**: 자세 고정 직교 직선은 경로 전체에 IK(Inverse Kinematics) 해가 필요 → 손목 한계·특이점에서 LINE_T 거절 가능. 폴백하면 자세가 깨지므로 **즉시 중단·보고**(이후 구간 미실행).
- **상대좌표(`coordinate_mode == 'relative'`)**: 기존 `_transform_relative_to_absolute` 재사용, **위치만** 변환(자세는 lock) = 기존 teaching 모드와 동일 취급.
- **자세 편차 검증 범위**: 구간 **종점** 기준 로깅만 코드로 수행. 경로 중간 자세는 이동 중 `feedback_states` 기록으로 별도 실측(실기 검증 단계) — 코드가 중간 검증을 했다고 주장하지 않는다.
- **미채택**: TMscript 다중 `Line` + blend 무정지 전송(스크립트 조립·검증 부담), 축 순서 선택 파라미터(사용자 결정은 적응형 1종 — 미요청 기능 추가 금지).

## Consequences

**긍정**

- 회전 지령 0 + 직교 직선 → 든 자세 유지. `move_to_point`(PTP) 대비 중간 드리프트 제거.
- 하강 시 XY 선행·상승 시 Z 선행 → 치구/바닥 간섭 위험 감소.
- 기존 Job 무수정이라 기존 레시피 동작 불변. 웹·PyQt 양쪽 사용 가능.

**부정·비용**

- 구간 경계마다 감속·정지(blend 0) → 사이클 타임 증가, 가감속 충격은 속도로만 완화(`acc_time` 0.2s 는 기존 `_move_to_position_line` 고정값 그대로).
- 자세 고정 제약으로 손목 한계·특이점에서 실패 가능(설계상 중단). 도달 실패 시 사용자가 자세/경로를 바꿔야 함.
- 스키마에 Rx/Ry/Rz 가 없어 "특정 자세로 이동" 은 이 Job 으로 불가 → 기존 `move_to_point`/`line_move_to_point` 사용.

**미검증(실기 대기)**: 실로봇 자세 편차 수치, LINE_T 거절 빈도. 실모션은 사용자 입회·저속·소량 원칙([robot-live-before-motion] 규칙) 하에서만.

## 추가 결정 (2026-07-27 오후) — 하강 접근 감속(댐핑) 이식

**Context**: `RhyGPU/Cobot-Web-GUI` @ `6f87112` 의 `ppCore.ts:83-134` 가 같은 축 순서 정책을 프론트에서 구현하면서, 본 구현에 없는 **하강 접근 감속**을 갖고 있다(대조: [code_review/Cobot-Web-GUI/2026-07-27.md](../code_review/Cobot-Web-GUI/2026-07-27.md) 부록). 드라이버로 나가는 구간이 전부 blend 0(구간마다 완전 정지)이라, 목표 직전만 저속 구간으로 쪼개면 "미리 감속"이 되어 배치 충격이 준다. 사용자 지시로 이식한다.

**Decision**: 하강 구간에만 적용하는 감속 분할을 `_build_descent_segments` 로 추가하고, 구간 표현을 `(라벨, x, y, z)` → `(라벨, x, y, z, 속도%)` 5-튜플로 확장한다.

- 신규 파라미터: `decel_zone_mm`(기본 40.0, `0` 이면 감속 없음) · `decel_velocity`(기본 10.0%)
- 규칙: `velocity <= decel_velocity` 또는 `decel_zone_mm <= 0` → 분할 없음 / 하강 길이 > `decel_zone_mm + 5mm` → [접근(velocity), 감속 진입(decel_velocity)] / 그 이하 → 통째로 `decel_velocity`
- 상승·XY 구간은 감속 대상 아님(원본과 동일)
- **원본과의 의도적 차이**: 원본은 짧은 하강에 `min(v, 15)` 고정값을 썼으나, 매직넘버를 늘리지 않고 `decel_velocity` 로 통일했다(더 보수적).
- 기본값을 원본과 같이 **켜짐(40mm/10%)** 으로 둔다 — 감속은 목표 직전 속도를 낮추기만 하므로 안전 방향이고, `velocity ≤ 10%` 로 쓰던 기존 사용 패턴에서는 분할 자체가 발생하지 않아 2026-07-27 오전 실기 검증 결과와 동일하게 동작한다.

**Consequences**: 하강이 40mm 초과일 때 구간이 1개 늘어 사이클 타임이 증가한다(감속 구간은 저속). 자세 유지 특성은 불변(모든 구간이 동일한 고정 자세). 미검증: 감속 분할이 실제로 배치 충격을 줄이는지는 실기 측정 필요(오전 검증은 속도 10%라 분할 미발생 경로였다).

**Rollback(추가분)**: `decel_zone_mm=0` 으로 두면 기능이 꺼진다. 코드 되돌림은 `_build_descent_segments` 삭제 + 5-튜플을 4-튜플로 환원 + 스키마 2개 파라미터 삭제.

## Rollback

가역. 되돌림 = 추가분 삭제만(영속 상태·스키마 마이그레이션 없음):

1. `job_executor.py` 추가 메서드 3개 + 상수 + `_execute_job` 분기 1줄 삭제
2. `recipe_manager.py` `JOB_TYPES` 항목 삭제
3. `task_edit_tab.py` 분기·래퍼 삭제, `bridge_node.py` whitelist 1줄 삭제
4. `test/test_pose_keep_move.py` 삭제

주의: 되돌리기 전 이 Job 을 사용한 레시피 YAML 이 있으면 해당 Job 은 "알 수 없는 Job 타입" 으로 실패한다(레시피 편집 필요). 저장된 레시피 파일 자체는 손상되지 않음.
