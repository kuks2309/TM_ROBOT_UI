# 2026-08-30 — 조인트 각도 한계 가드 신설 (사전 거부 + 실시간 자동 정지)

루트 집계 병기 — 정본: `src/TM_Robot_Task_Manager/docs/code_updates/2026-08-30-joint-limit-guard.md`

- TM20M(실기 확인) URDF 한계(J3 는 TM14 보수값 ±163°) + margin 5° 기준 — PTP_J 목표 사전 거부(`_call_set_positions`) + `/joint_states` 실시간 감시·자동 정지(`safety/joint_guard.py` 신규, latch+1° 재무장).
- `safety_area.yaml` joint_limits 절(enabled: true), `safety_area.py` 판정 4함수, main_window 배선 3곳.
- 테스트 7건 PASS, 전체 회귀 925 passed. 실기 검증 잔여(2026-08-30 기준).

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
