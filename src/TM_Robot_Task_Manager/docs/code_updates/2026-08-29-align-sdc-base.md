# 2026-08-29 — sdc_tcp_base 위치 Job 신설 (positions.yaml 자세 읽기)

- **배경**: MK4 기본 TCP 자세 (90, -22, -90)° 로 자세만 복귀시키는 명령 부재. 사용자 정의: "rx,ry,rz 를 90 -22 -90으로 정하는 sdc_tcp_base위치 명령", 값은 yaml 에 넣고 읽기. 초안(align_sdc_base, 자세 파라미터화)은 사용자 정의 확정으로 개정 — ADR `docs/adr/2026-08-29-align-sdc-base-job.md` §개정.
- **변경**:
  - `config/positions.yaml` — `positions.sdc_tcp_base` 항목 신설 (type `tcp_orientation`, values [90, -22, -90]).
  - `recipe_manager.py` — JOB_TYPES 에 `sdc_tcp_base`("sdc_tcp_base 위치", Motion, params: velocity(%)·wait_after_command) 등록.
  - `job_executor.py` — dispatch 분기 + `_exec_sdc_tcp_base` 신설: positions.yaml 에서 rx/ry/rz 3값 읽기(`ConfigManager.get_position` 재사용) → 현 위치 유지, 자세만 LINE_T — 정본 경로 `_move_to_position_line`(MotionGuard 게이트웨이 경유). 항목 부재·values 개수 오류·TCP 미수신·노드 부재는 오류 로그 + False.
- **테스트**: `test/test_sdc_tcp_base.py` 신설 9건 전부 PASS (yaml 실등록 검증 포함). 전체 회귀 883 passed / 42 skipped / 1 failed — 실패 1건(scan_ar_tag Vision 카테고리)은 선재 결함(2026-08-15 이슈 로그 기존 등재, 본 변경 무관, 해당 테스트 파일 타 세션 점유로 미접촉).
- **미실행**: 커밋·orin 배포·실기 구동 미수행 — 실기 검증은 orin rsync + 재기동 후 저속(velocity 10%)으로 필요.
- **연계**: 함수표 `src/TM_Robot_Task_Manager/docs/function_table.md` — job_executor 56a 행·recipe_manager JOB_TYPES 행·test_sdc_tcp_base 절. 기준 측정값 `data/landmark_pose/SDC_base_기준측정값_20260829_134941.yaml`(본 PC·orin 등록). 관련 실수 기록 `docs/claude-mistake/2026-08-29-002.md`.

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
