# ADR 2026-08-29 — sdc_palette_inlet_move Job 신설 (마커 상대 입구 위치 이동)

- **Status**: Accepted — 2026-08-29 15:50 (사용자 이름·정의·등록 승인, 실기 미검증)
- 관련: 사용자 지시(2026-08-29 15:47·15:49·15:50) "현재가 팔래트 입구 위치", "마커랑 상대거리로 이 위치로 이동하는 것은 sdc_palette_inlet_move로 하면될까요?", "네 등록해주세요"
- 대상: `config/positions.yaml`(항목 1) · `tm_task_manager/job_executor.py`(분기 1줄 + 함수 1개) · `tm_task_manager/recipe_manager.py`(JOB_TYPES 1항목) · `test/test_sdc_palette_inlet_move.py`(신설)

## Context

팔래트 진입 시퀀스는 scan(인식) → sdc_palette_tcp_align(자세) → 입구 이동 → move_linear 진입으로 구성된다. 입구 위치는 팔래트가 움직여도 마커와의 상대 관계가 불변이므로, 마커 frame 상대 오프셋으로 기억해야 재현된다. 2026-08-29 15:47 실측: 입구 TCP (-886.82, -14.21, 523.57) ↔ 마커 (-1195.283, -103.219, 738.902 / -90.787, -0.955, 93.686) → 마커 frame 오프셋 **(X +65.40, Y +220.74, Z -310.54) mm**.

## Decision

Job `sdc_palette_inlet_move`(category Landmark)를 신설한다.

1. **목표 위치** = 최신 스캔 마커 위치 + R_marker @ offset — offset은 `positions.yaml` `positions.sdc_palette_inlet_move`(type `marker_frame_offset`, values [65.40, 220.74, -310.54])에서 실행 시마다 재독(재티칭은 YAML 수정만).
2. **자세는 현재 자세 유지, 위치만 LINE_T** — 자세는 선행 sdc_palette_tcp_align 소관(역할 분리). 정본 `_move_to_position_line`(MotionGuard 경유).
3. 마커 출처는 직전 스캔(detected_landmark_pose) — 스캔 전 실행 거부. 항목 부재·values 개수·TCP 미수신·노드 부재 거부.
4. 파라미터: velocity(%)·wait_after_command — 자매 Job과 동일.

## Consequences

- 이득: scan→align→inlet_move→move_linear(Z+)로 팔래트 진입 시퀀스 완성. 마커 재장착·팔래트 이동에도 상대 오프셋으로 재현. JOB_TYPES 52→53종.
- 남는 위험: 실기 미검증. 오프셋은 2026-08-29 티칭값 — 지그·그리퍼 변경 시 재티칭(YAML) 필요.

## Rollback

N/A (가역) — JOB_TYPES 항목·dispatch 분기·실행 함수·테스트·positions.yaml 항목 제거로 원복. 영속 상태·스키마 변경 없음.
