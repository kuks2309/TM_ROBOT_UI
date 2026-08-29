# 2026-08-29 — sdc_palette_inlet_move Job 신설 (마커 상대 입구 위치 이동)

루트 집계 병기 — 정본: `src/TM_Robot_Task_Manager/docs/code_updates/2026-08-29-sdc-palette-inlet-move.md`

- 목표 = 최신 스캔 마커위치 + R_marker@offset(positions.yaml, 마커 frame [65.4, 220.74, -310.54] — 2026-08-29 실기 티칭), 자세 유지·위치만 LINE_T.
- `job_executor.py` `_exec_sdc_palette_inlet_move` + `recipe_manager.py` JOB_TYPES(53종) + `positions.yaml` 항목 신설.
- 테스트 9건 PASS(티칭 좌표 0.1mm 재현), 전체 회귀 902 passed. 실기 구동 미수행.

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
