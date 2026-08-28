# ADR 2026-08-16 — gripper_ros 조립층: LifecycleNode + 액션 서버 + 스테이션 클라이언트

## Status

Proposed

## Context

M0~M3 로 ROS-free 코어가 섰다 — 포트 계약(`gripper_hal`) · 원격 IO(Input/Output) 어댑터(`gripper_hal/impl`) ·
시퀀스 FSM(Finite State Machine, `gripper_motion`) · 플랜트 모형(`gripper_sim`). 남은 것은 **조립**이다.

M1 은 `IStationIoClient` 라는 심(seam)만 남겨 두고 rclcpp 를 배제했다. 그 심을 구현해 주입하는 것이
조립층의 첫 책임이고, 두 번째는 `GripperCommand.action` 을 FSM 에 태우는 것이다.

전제 사실(조회 결과):

- **`remote_io_ros` 는 `origin/main` 에 이미 있다** — `io_service`(`tc_msgs/srv/Io`) · `io_resp`
  (`tc_msgs/msg/Io`, 20ms) · `io_alarms` 를 legacy `tc_io` 파리티로 제공한다.
  (`LGIT-C6-MOMA/src/IOs/Remote_IO_Station/remote_io_ros/docs/functions.md`)
- 비트 인덱스 규약이 양쪽에서 같다 — **워드×16 + 비트, LSB-first**. `io_di` 80비트(DI 5워드) ·
  `io_do` 96비트(DO 6워드). `IStationIoClient::BitCommand` 의 규약과 일치하므로 변환이 필요 없다.
- `Io.srv` = `int32[] indices, int32[] states` → `bool received, int32[] indices_resp, int32[] states_resp`.
  `WriteAck` 의 `received`·`echo_*` 가 이 응답과 1:1 이다.
- 개발 PC 에 ROS 2 Humble 이 있다.

## Decision

### D1. 스테이션 접근은 `io_service`/`io_resp` 클라이언트 하나로 한다

`RosStationIoClient` 가 `IStationIoClient` 를 구현한다 — `write_bits` 는 `io_service` 동기 호출,
`image()` 는 `io_resp` 구독이 채운 최신 이미지의 사본, `link_up()` 은 이미지 수신 신선도.

그리퍼는 Modbus 를 열지 않는다(ADR-008 Q7 단일 쓰기 마스터, `⟦CI:gripper-io-single-master⟧`).
게이트의 «`gripper_ros` 만 예외» 규칙은 **rclcpp 결선**에 대한 것이지 소켓·Modbus 에 대한 허가가 아니다.

### D2. 노드는 `rclcpp_lifecycle::LifecycleNode`

`configure` 에서 설정을 읽고 검증한다 — 검증 실패는 **`configure` 실패**이며 활성화되지 않는다.
`activate` 에서 액션 서버와 주기 타이머를 연다. 이 경계 덕분에 «미검증 설정으로 구동» 이 구조적으로 불가능하다.

### D3. 판정 로직은 ROS-free 번역 단위에 둔다

`config_loader`(파라미터 값 → `MotionConfig`·`SignalMap` + 검증)와 `result_map`(`MotionResult` ·
`MotionState` → 액션 `RESULT_*`·`PHASE_*`)은 rclcpp 를 모른다. 둘 다 plain CMake 로 단위 시험한다.
노드에 남는 것은 결선뿐이다 — 시험할 수 없는 코드를 최소화한다.

### D4. 한 번에 한 목표만 받는다

FSM 이 진행 중이면 `request()` 가 `kBusy` 를 돌려주므로, 액션 서버는 그 목표를 **거절**한다(큐잉하지 않는다).
그리퍼는 물리 장치 하나이고 큐는 «언제 움직일지 모르는 명령» 을 만든다.

취소 요청은 `GripperFsm::abort()` — 출력을 복귀시키고 `RESULT_CANCELED` 로 마감한다.
복귀가 실패하면 `RESULT_ABORT_FAILED`(정지 미보장)로 구분한다.

### D5. `COMMAND_STEP`(정비용 직접 스텝)은 **거절**한다

액션 IDL(Interface Definition Language)은 이 명령을 정의하면서 «`maintenance.allow_direct_step` 이 true
이고 키스위치가 MANUAL 일 때만» 이라는 조건을 달았다. 그런데 **`SignalMap` 에 키스위치 입력이 없다** —
legacy 는 DI 9(`0 = MANUAL`)를 채터링 카운팅과 함께 읽지만 우리 신호맵에는 그 비트가 없다.

조건을 확인할 수단이 없으므로 «조건이 충족됐다고 가정하고 수락» 하지 않는다.
`RESULT_INVALID_REQUEST` 로 거절하고, 사유를 `message` 에 남긴다.
키스위치 입력이 신호맵에 추가되면 그때 별도 ADR 로 연다.

### D6. 결과 코드는 손실 없이 매핑한다

`MotionResult` 19종 → 액션 `RESULT_*` 15종은 단사(injective)가 아니다. 매핑표를 `result_map` 에
명시하고, 액션의 `message` 필드에 원래 `MotionResult` 이름을 문자열로 실어 정보를 잃지 않게 한다.
기계 분기는 `result_code`, 진단은 `message` — IDL 의 선언과 같다.

`alarm_raw_bits`·`alarm_group` 은 피드백 스냅샷의 OUT0~5 에서 채운다(legacy `gripper_node.cpp:1119-1138`
4비트 그룹 판정 파리티).

## Consequences

**얻는 것**

- 실기에서 우리 코드로 직접 개폐한다 — 손으로 시퀀스를 만들 필요가 없어진다.
- 설정 검증이 lifecycle 경계에 붙어 미검증 설정이 활성화되지 못한다.
- 조립층에서 시험 가능한 부분(설정·매핑)이 rclcpp 밖에 있어 로봇 없이 회귀가 돈다.

**치르는 것**

- `remote_io_ros` 가 떠 있어야 그리퍼가 움직인다(단일 마스터의 대가). 그 노드가 죽으면
  `link_up()`=false → 스냅샷 stale → FSM 이 `kStaleFeedback` 으로 끊는다. 조용히 멈추지는 않는다.
- `io_service` 동기 호출이 액션 실행 스레드를 잠깐 막는다. 콜백 그룹을 분리해 타이머·구독이
  굶지 않게 한다.
- `COMMAND_STEP` 은 당분간 쓸 수 없다(D5). 정비용 임의 스텝이 필요하면 키스위치 입력 추가가 선행이다.

**부채**

- `require_manual_key` 미구현(D5) — 키스위치 비트가 신호맵에 없다. `debt` 등록 대상.

## Rollback

가역이다. `gripper_ros` 는 신규 패키지이며 기존 자산을 고치지 않는다 —
패키지를 빌드에서 빼면 M0~M3 코어는 그대로 남는다. 실기 배포 전이라 되돌릴 현장 상태가 없다.

**Rollback**: `colcon build --packages-skip gripper_ros` (또는 패키지 디렉터리 제거). 영속 상태·스키마 변경 없음.
