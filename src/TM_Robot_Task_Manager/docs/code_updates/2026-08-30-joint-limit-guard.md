# 2026-08-30 — 조인트 각도 한계 가드 신설 (사전 거부 + 실시간 자동 정지)

- **배경**: 조인트가 못 가는 영역으로 들어가 낌 발생(사용자 보고) — 기존 안전 체계는 카르테시안 전용, 조인트 검사 부재. 모델 TM20M(TMSVR Robot_Model 실기 2회 확인), 한계는 벤더 URDF(tm20-nominal) 기준·J3 는 TM14 보수값 ±163°. ADR `docs/adr/2026-08-30-joint-limit-guard.md`.
- **변경**:
  - `config/safety_area.yaml` — `joint_limits:` 절 신설(enabled: true, margin 5°, auto_stop: true, j1~j6 한계).
  - `safety/safety_area.py` — DEFAULT_JOINT_LIMITS 상수 + load 병합 + `joint_limits_config/joint_limits_enabled/validate_joint_limits/check_joints`(#17~20) — 카르테시안 구역과 독립.
  - `safety/joint_guard.py`(신규) — `JointGuard.update`: 위반 첫 표본에서 로그+정지(fire-and-forget) 1회 latch, 복귀+1° 이력으로 재무장.
  - `main_window.py` — 배선 3곳: `_init_safety_guard`(가드 생성·검증·기동 로그), `_on_joint_state`(실시간 감시), `_call_set_positions`(PTP_J 목표 사전 거부) + `import math`.
- **테스트**: `test/test_joint_guard.py` 신설 7건 전부 PASS(기본 한계값·margin 판정·latch/재무장·auto_stop off·검증기). 전체 회귀 925 passed / 42 skipped / 1 failed(선재 scan_ar_tag — 무관).
- **미실행**: 실기 검증 잔여(배포 후 — 조그로 margin 근처 접근해 자동 정지 확인 필요).
- **연계**: 함수표 safety_area #17~20·상수 5행·joint_guard 절·test_joint_guard 절.

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
