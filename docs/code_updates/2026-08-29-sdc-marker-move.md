# 2026-08-29 — sdc_marker_move Job 신설 (마커 frame 상대 이동, move_linear 대체)

루트 집계 병기 — 정본: `src/TM_Robot_Task_Manager/docs/code_updates/2026-08-29-sdc-marker-move.md`

- 실기 충돌 사고(16:38, Move_Line "TPP" 좌표계 미검증 — debt-025·mistake 2026-08-29-003) 대응: (dx,dy,dz) 마커 frame 상대 이동을 절대 목표 LINE_T 로 수행하는 `sdc_marker_move` 신설, 레시피 진입 스텝 교체.
- 테스트 7건 PASS(법선/표면평행 수학 검증), 전체 회귀 915 passed. 실기 저속 재검증 잔여(2026-08-29 기준).

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
