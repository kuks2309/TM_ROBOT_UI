# ADR 2026-08-29 — SDC_base 정렬 Job 신설 (align_sdc_base)

- **Status**: Accepted — 2026-08-29 (사용자 구조 승인, 실기 미검증)
- 관련: 사용자 지시(2026-08-29) "SDC_base 정렬 은 rx,ry,rz를 90, -22, -90도로 만든 것임", "메뉴도 분명히 정할수 있는데" — 신규 구현 지시(기존 정렬 재사용 아님)
- 대상: `tm_task_manager/recipe_manager.py`(JOB_TYPES 1항목) · `tm_task_manager/job_executor.py`(분기 1줄 + 함수 1개) · `test/test_align_sdc_base.py`(신설)

## Context

MK4 프로젝트의 기본 TCP(Tool Center Point) 자세는 약 (Rx=90, Ry=-22, Rz=-90)° — 카메라가 약 -22° 기울어 장착된 구성이다. SDC_base 기준 측정값(`data/landmark_pose/SDC_base_기준측정값_20260829_134941.yaml`)도 이 자세에서 취득했다.

기존 정렬 수단은 이 구성에 맞지 않는다:

- `LandmarkAlignService.align_to_landmark`(`services/tm_landmark_align_service.py:116-134`)는 vision base 전환 후 자세 (180, 0, 180) 고정 — "카메라가 랜드마크를 내려다보는 전제"(docstring)의 옛 바닥-마커 구성용.
- `_exec_align_tm_landmark`(`job_executor.py:1538`)는 목표 자세를 직전 스캔 landmark 자세에서 가져오며, mm/deg 값을 set_positions 에 직접 넣는 자체 클라이언트 경로(정본 `_call_set_positions` 는 m·rad 요구 — `main_window.py:376`)라 재사용하지 않는다.

사용자는 기존 재사용이 아닌 **신규 Job** 을 지시했고, "SDC_base 정렬"의 명세를 "위치 유지, 자세만 (90, -22, -90)° 로" 확정했다.

## Decision

Job `align_sdc_base`("SDC_base 정렬", category Landmark)를 신설한다.

1. **동작**: 현재 TCP 위치(x, y, z)는 유지하고 자세만 목표 (rx, ry, rz)로 LINE_T 이동.
2. **목표 자세는 파라미터** — 기본값 (90, -22, -90). 옛 구성의 (180, 0, 180) 하드코딩이 이번 혼선의 원인이므로, 상수 하드코딩을 반복하지 않고 Job 파라미터로 노출한다.
3. **이동 경로는 정본 재사용**: `_move_to_position_line`(`job_executor.py:445`) → `_convert_to_robot_positions`(mm/deg→m·rad) → `ros_node._call_set_positions`(MotionGuard 게이트웨이 경유). 전용 클라이언트를 만들지 않는다.
4. 실행 전제(현재 TCP 미수신, ros_node 부재)는 오류 로그 + False — 조용한 통과 금지.

## Consequences

- 이득: 레시피/Task 메뉴에서 기본 자세 복귀가 1개 Job 으로 가능. MotionGuard 안전 판정 경유. 목표 자세가 파라미터라 다른 구성(로봇/카메라 변경)에도 재사용 가능.
- 비용: JOB_TYPES 50→51종.
- 남는 위험: 실기 검증 전(orin 배포 후 저속 검증 필요). `_exec_align_tm_landmark` 의 단위 의심(mm/deg 직접 전달)은 본 건 범위 밖 — debt 후보로 식별만 남긴다.

## Rollback

N/A (가역) — JOB_TYPES 항목·dispatch 분기·실행 함수·테스트 파일·positions.yaml 항목 제거로 원복. 영속 상태·스키마 변경 없음.

## 개정 (2026-08-29 14:20 — 사용자 정의 확정)

사용자 확정: "내가 원하는 기능은 rx,ry,rz 를 90 -22 -90으로 정하는 sdc_tcp_base위치 명령", "yaml 파일에 넣고 읽으면 되는데". 이에 따라 본 결정의 §Decision 2(목표 자세 파라미터화)를 폐기하고 다음으로 대체한다:

1. Job 이름: `align_sdc_base` → **`sdc_tcp_base`** ("sdc_tcp_base 위치", category **Motion**).
2. 목표 자세는 Job 파라미터가 아니라 **`config/positions.yaml` 의 `positions.sdc_tcp_base`** 항목(type `tcp_orientation`, values [rx, ry, rz] = [90, -22, -90])에서 실행 시마다 읽는다 — `ConfigManager.get_position` 재사용(기존 `move_to_named_position` 과 동일 접근 경로). rx/ry/rz Job 파라미터는 제거, velocity(%)·wait_after_command 만 유지.
3. 동작(위치 유지·자세만 LINE_T·정본 이동 경로)·실패 처리(§Decision 1·3·4)는 유지.
