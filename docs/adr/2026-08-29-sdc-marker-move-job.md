# ADR 2026-08-29 — sdc_marker_move Job 신설 (마커 frame 상대 이동, Move_Line 대체)

- **Status**: Accepted — 2026-08-29 16:41 (사용자 승인, 실기 미검증)
- 관련: 실기 충돌 사고(2026-08-29 16:38, mistake `docs/claude-mistake/2026-08-29-003.md`) — `move_linear`(TM 스크립트 `Move_Line("TPP")`)의 좌표계 의미가 매뉴얼 미검증 상태에서 코드 docstring("공구 좌표계")과 실기 거동이 불일치. 사용자 요구: "x,y 이동이 마커와 평행하게 움직여야"
- 대상: `tm_task_manager/job_executor.py`(분기 1줄 + 함수 1개) · `tm_task_manager/recipe_manager.py`(JOB_TYPES 1항목) · `config/recipes/sdc_palette_entry.yaml`(5번 스텝 교체) · `test/test_sdc_marker_move.py`(신설)

## Context

팔래트 작업의 미세 이동·진입은 마커 frame 축(X·Y=표면 평행, Z=법선)을 따라야 한다. `Move_Line("TPP")` 상대 이동은 좌표계 의미가 벤더 매뉴얼로 검증되지 않았고(로컬에 TM 스크립트 매뉴얼 부재), 실기에서 기대(공구 frame)와 다른 방향으로 움직여 충돌했다. 반면 마커 frame 변환 + SetPositions LINE_T 절대 목표 경로는 `sdc_palette_tcp_align`(법선 0.033~0.080°)·`sdc_palette_inlet_move`(입구 재현)로 **실기 검증 완료** 상태다.

## Decision

Job `sdc_marker_move`(category Landmark)를 신설하고, 팔래트 레시피의 진입 스텝에서 `move_linear` 를 이것으로 교체한다.

1. **파라미터 (dx, dy, dz) mm 는 마커 frame 기준** — 목표 위치 = 현재 위치 + R_marker@(dx,dy,dz), R_marker 는 직전 스캔(detected_landmark_pose). 자세는 현재 유지, 위치만 LINE_T(정본 `_move_to_position_line`, MotionGuard 경유).
2. X·Y = 마커 표면 평행, Z+ = 마커 법선 방향(마커 쪽) — 좌표 변환으로 보장, 스크립트 좌표계 의미에 무의존.
3. 스캔 전 실행·TCP 미수신·노드 부재 거부. velocity(%)·wait 파라미터는 자매 Job 동일.
4. `move_linear` 는 TM 매뉴얼 원문으로 TPP/CPP 의미가 검증될 때까지 팔래트 레시피에서 사용하지 않는다(원문 검증은 debt 로 추적).

## Consequences

- 이득: 마커 평행/법선 이동이 검증된 수학으로 보장. 진입(dz=+50: 입구 Z -310 → -260, 마커 평면 접근)·미세 조정 모두 한 Job 으로. JOB_TYPES 53→54종.
- 남는 위험: 실기 미검증(저속 재검증 필요). `move_linear` docstring 의 좌표계 주장은 이해 부채로 남음(매뉴얼 확보 시 검증).

## Rollback

N/A (가역) — JOB_TYPES 항목·dispatch 분기·실행 함수·테스트 제거, 레시피 5번 스텝 원복. 영속 상태·스키마 변경 없음.
