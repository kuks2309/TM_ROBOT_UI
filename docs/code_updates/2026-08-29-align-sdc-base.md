# 2026-08-29 — sdc_tcp_base 위치 Job 신설 (positions.yaml 자세 읽기)

루트 집계 병기 — 정본: `src/TM_Robot_Task_Manager/docs/code_updates/2026-08-29-align-sdc-base.md`

- `config/positions.yaml` `positions.sdc_tcp_base`(tcp_orientation, [90, -22, -90]) + `recipe_manager.py` JOB_TYPES `sdc_tcp_base`(Motion, velocity·wait) + `job_executor.py` `_exec_sdc_tcp_base`(yaml 자세 읽기 → 위치 유지·자세만 LINE_T, 정본 경로) 신설.
- 테스트 `test/test_sdc_tcp_base.py` 9건 PASS, 전체 회귀 883 passed (선재 실패 1건 무관).
- 커밋·orin 배포·실기 구동 미수행. 초안 파라미터화는 사용자 정의 확정으로 개정(ADR §개정, mistake `docs/claude-mistake/2026-08-29-002.md`).

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
