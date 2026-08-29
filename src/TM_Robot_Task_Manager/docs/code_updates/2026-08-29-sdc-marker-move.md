# 2026-08-29 — sdc_marker_move Job 신설 (마커 frame 상대 이동, move_linear 대체)

- **배경**: `move_linear`(TM 스크립트 `Move_Line("TPP")`) 좌표계 의미 미검증 상태 사용으로 실기 충돌 사고(16:38) — 상세 `docs/issues_and_fixes/issues_and_fixes.md` [Fix], mistake `docs/claude-mistake/2026-08-29-003.md`, debt-025. ADR `docs/adr/2026-08-29-sdc-marker-move-job.md`.
- **변경**:
  - `job_executor.py` — dispatch + `_exec_sdc_marker_move`(#56d): (dx,dy,dz) 마커 frame 상대 이동 → 절대 목표 LINE_T(정본 경로), 자세 유지. 스캔 전·TCP 미수신·노드 부재 거부.
  - `recipe_manager.py` — JOB_TYPES `sdc_marker_move`(Landmark, dx/dy/dz/velocity/wait) — 54종.
  - `config/recipes/sdc_palette_entry.yaml` — 5번 진입 스텝 move_linear → sdc_marker_move(dz=+50, 10%).
  - `docs/debt/registry.md` — debt-025(이해): Move_Line("TPP") docstring 좌표계 주장 미검증, 매뉴얼 확보 시 원문 대조.
- **테스트**: `test/test_sdc_marker_move.py` 7건 PASS — dz 이동벡터 ≡ 마커 법선×거리, dx·dy 법선 성분 0(표면 평행) 수학 검증 포함. 전체 회귀 915 passed / 42 skipped / 1 failed(선재 scan_ar_tag — 무관).
- **미실행**: 실기 구동 미수행 — 배포 후 저속 Step 재검증 필요.
- **연계**: 함수표 56d 행·JOB_TYPES 행(54종)·test_sdc_marker_move 절.

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
