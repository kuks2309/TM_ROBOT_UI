# 2026-08-29 — sdc_palette_tcp_align Job 신설 (palette 마커 수직 TCP 자세 정렬)

- **배경**: palette 부착 마커 스캔 후 그리퍼를 지그에 넣으려면 TCP 자세를 마커에 수직으로(카메라 회전 -22°는 Ry에 유지) 맞춰야 함. 사용자 예시 식(마커 rx,ry-22,rz 문자 그대로)은 기준 실측 대비 137.4° 불일치 — 후보식 4종 수치 대조로 **(-rx_m, ry_m-22, -rz_m)** 확정(기준 실측 대비 2.77°, ADR `docs/adr/2026-08-29-sdc-palette-tcp-align-job.md`).
- **변경**:
  - `config/positions.yaml` — `positions.sdc_palette_tcp_align`(type `tcp_orientation_offset`, values [0, -22, 0]) 등록. offset 조정은 YAML만 수정(실행 시 재독).
  - `job_executor.py` — dispatch 분기 + `_exec_sdc_palette_tcp_align`(#56b): 직전 스캔(detected_landmark_pose) 필수, 목표 = (-rx_m+o_rx, ry_m+o_ry, -rz_m+o_rz), 현 위치 유지·자세만 LINE_T(정본 `_move_to_position_line`, MotionGuard 경유). 스캔 전·항목 부재·값 개수·TCP 미수신·노드 부재 거부.
  - `recipe_manager.py` — JOB_TYPES `sdc_palette_tcp_align`(Landmark, velocity·wait) 등록(52종).
- **테스트**: `test/test_sdc_palette_tcp_align.py` 신설 9건 전부 PASS(YAML 실등록·부호반전 식·기준 실측값 사용). 전체 회귀 892 passed / 42 skipped / 1 failed(선재 결함 scan_ar_tag — 무관).
- **미실행**: 커밋·orin 배포·실기 구동 미수행. 실기에서 잔차 ~2°가 지그 공차를 넘으면 o_ry를 -20으로 튜닝(YAML).
- **개정(2026-08-29 15:00)**: 실기 실측 법선 오차 2.52°(공차 ~0.4° 초과) → 목표 계산을 오일러 근사에서 **회전행렬 스냅**(근사식 Z축을 마커 법선에 정확 일치)으로 교체. 법선각 0.0000°(수치)·테스트 0.01° 고정, 10건 PASS·회귀 893 passed. 상세: issues_and_fixes 2026-08-29 [Fix], ADR §개정.
- **연계**: 함수표 `docs/function_table.md` — job_executor 56b 행·JOB_TYPES 행(52종)·test_sdc_palette_tcp_align 절.

Session: 8748628e-e7f8-4230-9548-cf3f978111a3
