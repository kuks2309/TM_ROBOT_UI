# 2026-08-29 — sdc_palette_tcp_align Job 신설 (palette 마커 수직 TCP 자세 정렬)

루트 집계 병기 — 정본: `src/TM_Robot_Task_Manager/docs/code_updates/2026-08-29-sdc-palette-tcp-align.md`

- 목표 자세식 **(-rx_m, ry_m-22, -rz_m)** — 사용자 예시(문자 그대로 식)는 기준 실측 대비 137.4° 불일치, 후보 4종 수치 대조로 확정(2.77°, ADR 참조). offset [0,-22,0]은 `positions.yaml`.
- `job_executor.py` `_exec_sdc_palette_tcp_align` + `recipe_manager.py` JOB_TYPES(Landmark) + `positions.yaml` 항목 신설.
- 테스트 9건 PASS, 전체 회귀 892 passed(선재 실패 1건 무관). 커밋·배포·실기 구동 미수행.
- 개정(2026-08-29 15:00): 실기 법선 오차 2.52° → 목표 계산을 회전행렬 스냅으로 교체(법선각 0°, 테스트 10건 PASS·회귀 893). issues_and_fixes [Fix]·ADR §개정 참조.

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
