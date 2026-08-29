# 2026-08-29 — sdc_palette_inlet_move Job 신설 (마커 상대 입구 위치 이동)

- **배경**: 팔래트 진입 시퀀스의 위치 단계 — 입구 위치는 마커와의 상대 관계로만 재현 가능. 2026-08-29 15:47 실기 티칭: 입구 TCP (-886.82, -14.21, 523.57) ↔ 마커 → 마커 frame 오프셋 (65.40, 220.74, -310.54) mm. ADR `docs/adr/2026-08-29-sdc-palette-inlet-move-job.md`.
- **변경**:
  - `config/positions.yaml` — `positions.sdc_palette_inlet_move`(type `marker_frame_offset`, values [65.4, 220.74, -310.54]) 등록. 재티칭은 YAML만 수정.
  - `job_executor.py` — dispatch 분기 + `_exec_sdc_palette_inlet_move`(#56c): 목표 = 최신 스캔 마커위치 + R_marker@offset, **자세는 현재 유지·위치만 LINE_T**(정본 `_move_to_position_line`, MotionGuard 경유). 스캔 전·항목 부재·값 개수·TCP 미수신·노드 부재 거부.
  - `recipe_manager.py` — JOB_TYPES `sdc_palette_inlet_move`(Landmark, velocity·wait) — 53종.
- **테스트**: `test/test_sdc_palette_inlet_move.py` 신설 9건 전부 PASS — 실기 티칭 입구 좌표를 0.1mm 이내 재현하는 목표 계산 검증 포함. 전체 회귀 902 passed / 42 skipped / 1 failed(선재 scan_ar_tag — 무관).
- **표준 시퀀스**: `scan_tm_landmark` → `sdc_palette_tcp_align`(자세) → `sdc_palette_inlet_move`(입구) → `move_linear` offset Z+(진입, 공구 Z축이 마커 법선 방향).
- **미실행**: 실기 구동 미수행(배포 후 사용자 확인 예정).
- **연계**: 함수표 `docs/function_table.md` 56c 행·JOB_TYPES 행(53종)·test_sdc_palette_inlet_move 절.

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
