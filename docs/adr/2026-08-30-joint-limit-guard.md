# ADR 2026-08-30 — 조인트 각도 한계 가드 (사전 거부 + 실시간 자동 정지)

- **Status**: Accepted — 2026-08-30 15:00 (사용자 승인: "진행해주세요", "자동정지 5도 맞음")
- 관련: 사용자 보고(2026-08-30 13:11·13:13) "로봇 기동시에 못가는 영역 확인 안 함", "조인트 각도에서 못 가는 영역으로 가서 로봇의 낌이 발생" + "끼는 조인트와 각도 범위 ← 로봇 모델이 있음"
- 대상: `config/safety_area.yaml`(joint_limits 절) · `safety/safety_area.py`(스키마·검증·판정) · `safety/joint_guard.py`(신규) · `main_window.py`(배선 3곳) · `test/test_joint_guard.py`(신설)

## Context

기존 안전 체계(MotionGuard·BoundaryMonitor)는 카르테시안(mm 박스) 전용으로, 조인트 공간 한계는 어디에서도 검사하지 않는다. 실기에서 조인트가 못 가는 영역으로 들어가 낌이 발생했다.

로봇 모델은 **TM20M**(TMSVR `Robot_Model` 재질의 2회 일관, 실기 2026-08-30 14:57). 조인트 한계는 벤더 URDF(`tm_description/xacro/macro.tm20-nominal.urdf.xacro:7-12`) 기준 J1·J6 ±270°, J2·J4·J5 ±180°, J3 ±166°. 사용자의 TM14 가능성 문의에 대해 차이는 J3(±163° vs ±166°)뿐이므로 **J3 는 보수값 ±163° 채택** — 모델 판정과 무관하게 안전.

## Decision

1. **설정**: `safety_area.yaml` 에 `joint_limits:` 절 — enabled·margin_deg(기본 5.0)·auto_stop(기본 true)·limits_deg(j1~j6 [lo, hi] deg, 위 모델값). 판정 기준 = 한계 ± margin 안쪽.
2. **사전 거부**: 조인트 목표 이동(PTP_J)의 목표가 (한계−margin) 밖이면 `_call_set_positions` 에서 전송 전 거부 — 모든 조인트 목표 명령의 단일 관문.
3. **실시간 감시 + 자동 정지**: `/joint_states` 수신 콜백(`_on_joint_state`)에서 `JointGuard.update` — (한계−margin) 위반 순간 로그 + `RobotStopService.stop`(fire-and-forget — 감시 콜백 스레드 안전) 1회 호출. 복귀 후 1° 이력(hysteresis)으로 재무장. 경고/정지 2단계 대신 margin 안쪽 단일 문턱에서 즉시 정지 — margin 이 곧 낌 전 정지 여유다.
4. 비활성(enabled: false) 시 기존 동작 불변. 카르테시안 안전구역과 독립적으로 켜고 끌 수 있다.

## Consequences

- 이득: 낌 발생 전 자동 정지. LINE/TCP 이동처럼 조인트 결과를 예측할 수 없는 명령도 실시간 감시로 커버.
- 비용: joint_states 콜백마다 6회 비교(무시 가능). 남는 위험: margin 5° 가 실제 낌 각도보다 안쪽인지 실기 확인 필요 — 낌이 모델 한계가 아니라 특정 각도대(자세 간섭)에서 나면 limits_deg 를 그 조인트만 좁혀 재설정(YAML만 수정).
- 실기 미검증(배포 후 확인 예정).

## Rollback

N/A (가역) — joint_limits 절 enabled: false 로 끄거나, 코드 원복(가드 클래스·배선 3곳·판정 함수 제거). 영속 상태·스키마 변경 없음.
