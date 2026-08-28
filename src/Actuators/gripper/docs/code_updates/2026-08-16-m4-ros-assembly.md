# M4 — gripper_ros 조립층 (2026-08-16)

M0~M3 의 ROS-free 코어를 ROS 2 에 결선했다. 결정 근거는 [ADR-001-gripper-ros-assembly](../adr/ADR-001-gripper-ros-assembly.md).

## 만든 것

| 파일 | 역할 |
|---|---|
| `src/config_loader.{hpp,cpp}` | yaml → `MotionConfig`·`SignalMap`. **누락 키를 기본값으로 채우지 않고 거부**하며 코어 `validate()` 를 그대로 위임 |
| `src/result_map.{hpp,cpp}` | `MotionResult`·`MotionState` → 액션 `RESULT_*`·`PHASE_*`, 알람 그룹 4비트 판정 |
| `src/ros_station_io_client.{hpp,cpp}` | `IStationIoClient` 의 ROS 구현 — `io_service` 쓰기 · `io_resp` 이미지 |
| `src/gripper_node.{hpp,cpp}` · `src/node_params.cpp` | `LifecycleNode` + 액션 서버 + 주기 tick |
| `src/sim_station_node.cpp` | SIL 스테이션 — `remote_io_ros` 자리에 플랜트를 세워 로봇 없이 폐루프 |
| `test/gripper_ros_core_test.cpp` · `core/CMakeLists.txt` | ROS-free 부분의 plain CMake 회귀 |

## 조회로 뒤집힌 전제 2건

- **`remote_io_ros` 는 이미 있다.** 워킹트리에 안 보여 «미구현» 으로 볼 뻔했으나
  `git log --all` → `origin/main` 에 존재. 계약(`io_service`·`io_resp`·비트 인덱스 워드×16+비트)이
  `IStationIoClient` 와 같아 변환 계층이 필요 없었다.
- **알람 그룹 비트 대응이 추측과 달랐다.** legacy `checkAlarmGroup()`(amr04 `gripper_node.cpp:1115-1141`)
  실제는 B=0x2 · C=0x4 · D=0x8 · **E=0x0**. E 가 전 비트 0 이라 «0 = 알람 없음» 이 성립하지 않아
  알람 활성 여부를 함께 받는 형태로 고쳤다.

## 설정 보완

`gripper_stack.yaml` 에 **`signal_map.do_bit_count: 96` · `di_bit_count: 80`** 을 신설했다.
`SignalMap::validate()` 가 요구하는데 키가 없어 `configure` 가 실패했다 — lifecycle 게이트가
실제로 작동함을 확인한 사례이기도 하다. 값의 근거는 `remote_io_ros` 계약(DI 5워드 · DO 6워드).

## 검증

| 항목 | 결과 |
|---|---|
| 빌드 | 경고 0 |
| 코어 시험 | 전 시나리오 통과(rclcpp 없이) |
| **뮤테이션** | **8 뮤턴트 · 살아남음 0 · red 39단언** |
| lifecycle | 키 누락 시 `configure` 실패 → 보완 후 `configure`·`activate` 성공 |
| 거절 경로 | stale · 미등록 프로파일 · `COMMAND_STEP` · 필드 조합 위반 4종 실측 |
| **SIL 폐루프** | 냉시동 release 완주 — `PRECHECK → ORIGINATING → WAIT_SETON → STEP_SET → DRIVING → VERIFY → DONE`, `result_code=0` |
| 인터록 | 매거진 미감지 grip 거절 실측 |

첫 뮤테이션에서 **2 뮤턴트가 살아남았다** — 누락 키를 0 으로 채워도, 인터록 문자열 오타를 `kNone`
으로 관대 처리해도 시험이 통과했다. 둘 다 `validate()` 가 «대신» 막아 준 것이라 적재기 자신의
계약은 검증되지 않고 있었다. 사유 문자열이 그 키를 짚는지까지 단언하도록 고쳐 0 으로 만들었다.

## 잔여

- **grip 완주 SIL 미시험**(debt-093) — 플랜트가 매거진 감지를 «파지 성립» 으로 모형화해 실측(존재
  감지)과 어긋난다. 순환이 생겨 grip 경로를 폐루프로 못 돈다.
- `COMMAND_STEP` 미수락(debt-094) — 키스위치 입력이 신호맵에 없다.
- 코봇 브리지(`cobot_bridge.enabled: false`) — 실기 확인 후 별도 작업.
- HIL — 리모트 `~/LGIT_C6_MoMa` 에서 별도 수행.
