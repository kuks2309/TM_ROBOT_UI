# ADR 2026-08-29 — sdc_palette_tcp_align Job 신설 (마커 수직 TCP 자세 정렬)

- **Status**: Accepted — 2026-08-29 (사용자 정의·진행 승인, 실기 미검증)
- 관련: 사용자 지시(2026-08-29 14:31·14:32) "tm_landmark가 palette에 붙어 있으므로 Ry -22를 제외하고 rx,rz를 마커와 수직이게 TCP를 수정", "(-87.5, -0.7-22, 90.8) 이렇게 하면 되고", "변수표 함수표 만들면서 진행"
- 대상: `config/positions.yaml`(항목 1) · `tm_task_manager/job_executor.py`(분기 1줄 + 함수 1개) · `tm_task_manager/recipe_manager.py`(JOB_TYPES 1항목) · `test/test_sdc_palette_tcp_align.py`(신설)

## Context

palette에 부착된 TM landmark를 스캔한 뒤, 그리퍼를 지그에 넣으려면 TCP(Tool Center Point) 자세를 마커에 수직으로 맞추되 카메라 회전(-22°)은 Ry에 유지해야 한다.

사용자 예시는 "마커 (-87.5, -0.7, 90.8) → 목표 (rx_m, ry_m-22, rz_m)"였으나, **기준 실측 데이터로 검증한 결과 문자 그대로의 식은 기준 TCP와 137.4° 어긋난다**(SDC_base 기준 측정: 마커 (-87.513, -0.691, 90.802) ↔ 그 시점 실측 TCP (88.105, -20.008, -90.587), `data/landmark_pose/SDC_base_기준측정값_20260829_134941.yaml`). 후보식 4종 수치 대조:

| 후보 | 실측 대비 회전각 차이 |
| --- | --- |
| (rx_m, ry_m-22, rz_m) 문자 그대로 | 137.39° |
| **(-rx_m, ry_m-22, -rz_m)** | **2.77°** |
| (-rx_m, ry_m-20, -rz_m) | 0.98° |
| (rx_m+180, ry_m-22, rz_m+180) | 5.72° |

"마커와 수직"의 수치적 실체는 rx·rz 부호 반전이다. 잔차 ~2°는 ry offset -22 대 실측 -20 차이로, 사용자가 카메라 각을 -22로 확정했으므로 -22를 기본값으로 하되 YAML에서 조정 가능하게 둔다.

## Decision

Job `sdc_palette_tcp_align`("sdc_palette_tcp_align", category Landmark)을 신설한다.

1. **목표 자세 식**: `(‑rx_m + o_rx, ry_m + o_ry, ‑rz_m + o_rz)` — (rx_m, ry_m, rz_m)은 직전 스캔 마커 자세, offset (o_rx, o_ry, o_rz)은 `positions.yaml` `positions.sdc_palette_tcp_align`(type `tcp_orientation_offset`, values 기본 [0, -22, 0])에서 실행 시마다 읽는다(sdc_tcp_base와 동일 패턴, 하드코딩 금지).
2. **마커 출처**: `self.detected_landmark_pose`(직전 scan_tm_landmark 결과) — `align_tm_landmark`(#56)와 동일한 소스·오류 문구. 스캔 전 실행은 거부.
3. **위치는 현 위치 유지, 자세만 LINE_T** — 정본 `_move_to_position_line`(MotionGuard 게이트웨이 경유), sdc_tcp_base와 동일.
4. 실패 조건(항목 부재·values 개수·TCP 미수신·노드 부재)은 오류 로그 + False.

## Consequences

- 이득: 스캔 → sdc_palette_tcp_align 두 Job으로 지그 삽입 전 자세 정렬 완성. 식이 기준 실측으로 검증됨(2.8°). offset 조정은 YAML만 수정.
- 비용: JOB_TYPES 51→52종.
- 남는 위험: 실기 미검증(orin 배포 후 저속 확인 필요). 잔차 ~2°가 지그 삽입 공차를 초과하면 o_ry를 -20으로 조정(YAML)하는 튜닝 여지.

## Rollback

N/A (가역) — JOB_TYPES 항목·dispatch 분기·실행 함수·테스트·positions.yaml 항목 제거로 원복. 영속 상태·스키마 변경 없음.
