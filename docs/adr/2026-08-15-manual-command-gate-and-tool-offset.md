# ADR 2026-08-15 — 수동 명령 단일 실행 게이트 + 평면 수직 정렬 공구 오차

- 날짜: 2026-08-15 (KST, Korea Standard Time)
- 관련: 사용자 지시(2026-08-15) "조그 명령이나, 수동 명령은, 현재 수행중 작업이 있을떈 새 명령을 받음 안되고, 새 명령은 첫번쨰꺼 하나만 받아야 함", "평면 수직 정렬 RZ mode plane 일떄 rz 값은 +90", "x, y, rz, ry, rx 오차 … z축 오차는 안 만들어도 됨", [ADR 2026-07-27 팔레트 평면 정렬](2026-07-27-pallet-plane-align.md)
- 대상: `services/command_gate.py`(신설) · `services/offset_preset_service.py`(신설) · `services/jog_service.py` · `tabs/task_edit_tab.py` · `job_executor.py` · `tools/jig_plane_calculator.py` · `recipe_manager.py`

## Status

**Accepted — 2026-08-15 (실기 미검증).** 사용자 승인 2026-08-15(계획 제시 후 "ㄱㄱ"). 부작용 2건(조이스틱 연속 조그 반응 변화, 저장된 `rz_mode: plane` 레시피 자세 90° 변경)을 명시적으로 고지하고 받은 승인이다.

## Context

### 1. 스팸 클릭이 전부 실행되던 경로 (실측)

- `main_window._send_set_positions` 는 GUI 스레드에서 동기 블로킹으로 모션 완료까지 최대 30초 대기한다(`rclpy.spin_once` + `time.sleep(0.05)` 루프).
- `main_window._log` 는 매 줄마다 `QApplication.processEvents()` 를 호출한다(main_window.py:1026 — 본 변경 전 기준).
- 따라서 블로킹 대기 중 쌓인 버튼 클릭이 로그 출력 시점에 **재진입 실행**된다. 사용자가 본 "다 기억했다가 전부 실행"의 원인은 로봇 드라이버 큐가 아니라 GUI 이벤트 큐다.

진입점은 `JogService.jog`(settings_tab 12버튼 + vision_tab 12버튼), `JogService.jog_continuous`(조이스틱), `TaskEditTab._on_move_to_params`(수동 실행) 이다.

`processEvents()` 제거는 대안이 아니다 — 그것이 장시간 모션 중 로그 갱신과 창 응답을 유지하는 유일한 수단이다.

### 2. `rz_mode='plane'` 이 짧은 변을 따르던 문제

`tcp_pose_for_plane_normal` 이 공구 X축을 평면 X축에 맞췄다. 평면 좌표계 정의상 X = 짧은 변, Y = 긴 변이므로(`pose_in_plane_frame` docstring) 팔레트 긴 변에 박스 짧은 변이 맞았다.

### 3. 그리퍼 오차 입력 부재

공구 장착 오차를 반영할 통로가 없어 매번 조그로 보정해야 했다.

## Decision

### 1. 단일 실행 게이트 — 창 전체가 하나를 공유

`CommandGate.acquire(label)/release()`. 실행 중 `acquire` 는 `False` 를 돌려주고 **무시 건수만 센다**. 거부를 즉시 로그하지 않는 이유: 로그 콜백이 `processEvents()` 를 부르므로 거부 로그가 다음 대기 클릭을 다시 배달해 재귀가 깊어진다. 해제 시점에 `[무시] '<label>' 실행 중 들어온 명령 N건을 버렸습니다` 한 줄로 모아 알린다.

게이트는 `MainWindow` 가 1개 보유한다. 진입점마다 따로 두면 한쪽 실행 중 다른 쪽 명령이 끼어든다.

적용 범위는 지시대로 **조그 + Task 수동 실행**이다. `_on_move_to_params` 는 모든 `_exec_*` 분기가 통과하는 단일 지점이라 그 한 곳만 감싼다. 레시피 Run/Step 은 이번 범위 밖.

`try/finally` 로 해제한다 — 한 번 잠긴 채 남으면 이후 모든 수동 명령이 죽는다.

### 2. `rz_mode='plane'` 은 평면 Y축(긴 변)을 따른다

공구 X축의 원천을 평면 X축 → 평면 Y축으로 바꾼다. 이는 **평면 법선축 기준 +90° 회전**이므로 수직 정렬(공구 Z ∥ 법선)이 정확히 보존된다. euler `rz` 에 90 을 더하는 방식은 베이스 Z축 회전이라 평면이 기울면 정렬이 틀어지므로 채택하지 않았다.

`rz_mode='keep'` 의 투영 실패 fallback 은 **기존대로 평면 X축**을 쓴다(keep 의미 보존).

### 3. 그리퍼 오차는 공구 좌표계 5축 — z 축은 없다

`apply_tool_offset(base_pose, offset)`: 위치 `p + R_base @ [dx, dy, 0]`, 자세 `R_base @ R_offset`.

축은 `x, y, rx, ry, rz` 5종이다. 수직 정렬은 법선 방향 거리를 `standoff_mm` 이 이미 정하므로 z 오차 축을 두면 같은 양을 정하는 손잡이가 2개가 된다.

### 4. '현재위치 입력' 이 오차를 역산한다

`tool_offset_from_poses` 는 `apply_tool_offset` 의 역변환이다. `JobExecutor.estimate_plane_align_tool_offset` 은 **오차를 0 으로 놓고** 기준 목표를 다시 계산한 뒤 현재 TCP 와의 차이를 잰다 — 이미 들어있는 오차 위에 오차가 겹쳐 쌓이는 것을 막는다. 무시한 공구 Z 방향 차이는 `standoff_mm` 으로 조정하라는 메시지로만 알린다.

### 5. preset 은 파일 저장소 + 동적 UI 행

`OffsetPresetService` 가 `config/plane_align_offsets.yaml` 을 읽고 쓴다. UI(`TaskEditTab`)는 서비스만 호출하고 파일을 직접 열지 않는다. 콤보 + 적용/저장/삭제 버튼은 파라미터 폼에 동적 생성하므로 `.ui` 파일을 고치지 않는다.

## Alternatives

- **`is_moving`(피드백 속도 기반) 으로 게이트 판정** — 명령 직후에는 아직 로봇이 움직이지 않아 판정이 늦다. 100ms 내 더블클릭을 놓친다. 기각.
- **`processEvents()` 제거** — 재진입 원인은 사라지나 장시간 모션 중 창이 얼어붙는다. 기각.
- **euler `rz + 90`** — 지시 문구에 가장 가깝지만 베이스 Z축 회전이라 기운 평면에서 수직 정렬이 깨진다. 기각(사용자에게 선택지로 제시 후 법선축 안이 채택됨).
- **오차를 평면 좌표계로 정의** — 기존 `move_to_plane_pose` 와 일관되나, "그리퍼 오차"는 공구에 붙은 양이라 공구 좌표계가 의미에 맞다. 사용자 선택으로 공구 좌표계 채택.

## Consequences

**이득**

- 스팸 클릭이 로봇을 연속 구동시키지 못한다 — 첫 명령만 실행된다
- `rz_mode='plane'` 이 팔레트 긴 변에 그리퍼 긴 변을 맞춘다
- 그리퍼 오차를 손으로 맞춘 자세에서 그대로 뽑아 쓰고, 이름 붙여 재사용할 수 있다

**비용 · 동작 변화 (사용자 고지 완료)**

- **조이스틱 연속 조그**도 게이트에 걸린다. 스틱을 밀고 있어도 "이전 모션 완료 후 다음 명령"이 되어 반응이 끊기게 느껴질 수 있다.
- **저장된 레시피의 `rz_mode: plane` 실제 자세가 90° 바뀐다.** `config/recipes/pallet0_align*.yaml` 등 기존 레시피는 실행 전 확인이 필요하다.
- `_save_params_from_ui` 의 `offset_x/y/z` 건너뛰기를 선언 타입 기준으로 고쳤다 — 그 부수효과로 기존 `move_to_plane_pose` 의 flat offset 파라미터도 이제 UI 에서 저장된다(이전에는 이름만 보고 건너뛰어 저장되지 않던 결함).

**남는 위험**

- 게이트는 GUI 스레드 재진입만 막는다. 다른 스레드나 외부(웹 브리지) 경로에서 들어오는 명령은 대상이 아니다.
- 오차 rx/ry 를 크게 넣으면 수직 정렬이 그만큼 깨진다. 상한 검사는 두지 않았다(사용자가 의도적으로 넣는 값이므로).

## Rollback

가역. 되돌리는 절차:

1. `JogService.__init__` 의 `command_gate` 인자와 `jog`/`jog_continuous` 의 게이트 래퍼 제거(내부 `_jog`/`_jog_continuous` 를 원래 이름으로 환원)
2. `TaskEditTab._on_move_to_params` 의 래퍼 제거(`_move_to_params` 본문을 원래 이름으로 환원)
3. `MainWindow` 의 `command_gate`·`offset_preset_service` 생성 제거
4. `jig_plane_calculator` 의 `source_axis` 분기를 `plane_rotation[:, 0]` 고정으로 환원
5. `apply_tool_offset`·`tool_offset_from_poses`·`TOOL_OFFSET_KEYS` 및 `JOB_TYPES` 의 `offset_*` 5개 제거
6. `services/command_gate.py`·`services/offset_preset_service.py`·`test/test_command_gate.py`·`test/test_offset_preset.py` 삭제

되돌린 뒤 레시피에 `offset_*` 값이 남아 있어도 `params.get` 이 읽지 않으므로 무시된다 — 조용한 오동작이 아니다. 단 4번을 되돌리면 `rz_mode: plane` 자세가 다시 90° 이동하므로, 그 사이 오차로 보정해 둔 레시피는 재조정이 필요하다.
