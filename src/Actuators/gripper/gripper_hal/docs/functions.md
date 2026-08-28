# gripper_hal 함수표 (모듈 로컬 원본 — coding SOP §2/§6 이중 기록)

갱신: 2026-08-13 (**M1 원격 IO 백엔드 + 외부 리뷰 3라운드 반영**. 직전: 2026-08-12 M0 계약 동결 초안, ADR-008)
루트 집계: [../../docs/functions-index.md](../../docs/functions-index.md)

> 전역 변수: **없음** (전 상태는 클래스/구조체 소유 — conventions 전역 규율)
> 계층 규율: 무-ROS(`⟦CI:gripper-ros-free⟧`) · 벤더 심볼은 `impl/` 에만(`⟦CI:gripper-vendor-sealed⟧`) ·
> 물리 접근은 `Remote_IO_Station` 단일 마스터 경유(`⟦CI:gripper-io-single-master⟧`)
> **소유 경계**: 신호 **이름·극성 규약**은 본 헤더 소유 / 물리 **비트 인덱스**는 config 소유(drawer D03 선례)

## 공개 표면 (계약 — 변경 시 ADR + 재동결)

| # | 심볼 | 입력 | 출력 | 기능 | 위치 | 상태 |
|---|------|------|------|------|------|------|
| 1 | `Result<T>` / `Result<void>` | T 또는 `HalError` | Result | 접근자 가드형 결과 타입(`[[nodiscard]]`) — 실패 은닉 금지(remote_io·drawer 선례 승계) | types.hpp:31·77 | M0 |
| 2 | `HalError` | — | enum | `kNone`/`kNotReady`/`kTimeout`/`kOutOfRange`/`kProtocol`/`kStaleData`/`kBusy`/`kRejected`/**`kIndeterminate`**(쓰기 일부 적용·확정 불가 — 재시도 전 상태 재확인) | types.hpp:16 | M0 |
| 3 | `ControlLine` | — | enum | `kSetup`·`kHold`·`kDrive`·`kReset`·`kServoOn`·`kLockRelease` — **스텝 비트(IN0~5)는 여기 없다**(개별 조작 차단, `write_step` 만이 경로) | types.hpp:115 | M0 |
| 4 | `FeedbackSignal` | — | enum | `kOut0~kOut5`·`kBusy`·`kArea`·`kSetOn`·`kInPosition`·`kServoReady`·`kEmergencyStop`·`kAlarm` — LECP6 CN5 B1~B13 대응 | types.hpp:127 | M0 |
| 5 | `kStepMin` / `kStepMax` | — | constexpr uint8_t | 1 / 63 — 스텝 번호 유효 범위(LECP6 6bit, step 0 = 미지정) | types.hpp:110·111 | M0 |
| 6 | `FeedbackSnapshot` | — | struct | `bits`(FeedbackSignal 인덱스 LSB-first)·`fresh`·**`seq`**·`stamp` — `fresh=false` 로 판정 금지, `stamp` 은 수신 시각 고정·`seq` 는 입력 이미지 단조 번호 | types.hpp:156 | M0 |
| 7 | `get(snapshot, signal)` | 스냅샷, 신호 | bool | 원시 레벨 조회(극성 미적용) | types.hpp:168 | M0 |
| 8 | `alarm_state(snapshot)` / `emergency_stop_state(snapshot)` | 스냅샷 | SignalState | **negative-true 극성 적용 + stale=kUnknown** 판정 — `ALARM`/`ESTOP` 는 정상 시 ON (근거: LECP6 OM page 28 각주 \*2). 원시 0/1 을 그대로 해석하는 실수 차단 | types.hpp:175·185 | M0 |
| 9 | `is_ready_for_drive(snapshot)` | 스냅샷 | bool | `BUSY=0` 且 `SVRE=1` 且 **`SETON=1`** 且 알람·ESTOP 없음 — 원점 미확립 DRIVE 는 무동작(매뉴얼 page 38 §8.1) | types.hpp:195 | M0 |
| 9-1 | `is_ready_for_origin(snapshot)` | 스냅샷 | bool | 원점복귀(SETUP) 착수 판정 — SETON 은 요구하지 않음(확립하러 가는 동작) | types.hpp:203 | M0 |
| 8-1 | `SignalState` | — | enum | `kUnknown`/`kInactive`/`kActive` — **stale 에서 정상/이상을 만들지 않기 위한 3상태** | types.hpp:146 | M0 |
| 10 | `MagazineSnapshot` | — | struct | `detected_1`·`detected_2`·`fresh`·**`seq`**·`stamp` — **극성 적용 완료값**(센서 NC, 감지=0 → `detected=true`) | types.hpp:210 | M0 |
| 10-2 | `both_detected(snapshot)` / `any_detected(snapshot)` | 매거진 스냅샷 | bool | 인터록 판정 헬퍼 — `fresh=false` 는 둘 다 false(판정 불가를 통과로 만들지 않음) | types.hpp:220·226 | M0 |
| 10-1 | `same_image(feedback, magazine)` | 스냅샷 2 | bool | 두 스냅샷이 **같은 입력 이미지(seq)** 에서 왔는지 — 다르면 조합 인터록 판정 금지 | types.hpp:232 | M0 |
| 11 | `Health` | — | struct | `link_up`·`snapshot_age`·`error_count`·`last_seq`·`last_error` | types.hpp:237 | M0 |
| 12 | `IGripperCommandPort::write_step` | `uint8_t step` | Result<void> | IN0~IN5 **원자 배치 쓰기**(6bit). 범위 밖은 송신 없이 `kOutOfRange` | command_port.hpp:18 | M0 |
| 13 | `IGripperCommandPort::write_line` | `ControlLine`, `bool` | Result<void> | SETUP/HOLD/DRIVE/RESET/SVON/LOCK_RELEASE 단일 라인 구동 | command_port.hpp:21 | M0 |
| 14 | `IGripperCommandPort::clear_step_and_drive` | — | Result<void> | IN0~5=0 + DRIVE=0 원자 복귀 (legacy `initGripperInNum` 파리티) | command_port.hpp:24 | M0 |
| 15 | `IGripperCommandPort::health` | — | Health | 링크·에러 카운터 | command_port.hpp:26 | M0 |
| 16 | `IGripperFeedbackPort::read` | — | Result<FeedbackSnapshot> | 13신호 원자 스냅샷. 수신 이력 없음/stale 은 `fresh=false` | feedback_port.hpp:16 | M0 |
| 17 | `IGripperFeedbackPort::health` | — | Health | | feedback_port.hpp:18 | M0 |
| 18 | `IMagazineDetectPort::read` | — | Result<MagazineSnapshot> | MGZ 2점 스냅샷(극성 적용). Rx 백엔드는 null 구현 | magazine_port.hpp:17 | M0 |
| 19 | `IMagazineDetectPort::health` | — | Health | | magazine_port.hpp:19 | M0 |

## 검증 자산

| 심볼 | 위치 | 기능 |
|---|---|---|
| `bit` / `main` | contract_check.cpp:22·27 | 계약 의미 실행 검증 — negative-true 극성 3상태(`alarm_state`·`emergency_stop_state`, stale=kUnknown) · `is_ready_for_drive` 6조건 / `is_ready_for_origin` · `same_image` seq 대조 · 매거진 인터록 헬퍼 · `Result` 규약(`err(kNone)` 승격, 미검사 `value()` 는 `std::bad_optional_access`, rvalue 는 값 반환) · 스텝→비트 파리티 63개. **`-DNDEBUG -O2` 빌드에서도 동일 통과** |

## 구현 (M1 — `impl/`, 원격 IO 백엔드)

주입 대상은 `IRemoteIoStationPort` 가 아니라 **ROS-free 심 `IStationIoClient`** 다. 스테이션 포트를 직접 잡으면
그리퍼가 두 번째 쓰기 마스터가 되고(ADR-008 Q7 위반), 서비스 클라이언트는 rclcpp 를 끌고 들어와 ROS-free 계층이 깨진다.
ROS 결선은 조립층(M4)이 이 인터페이스를 구현해 주입한다.

| # | 심볼 | 입력 | 출력 | 기능 | 위치 | 상태 |
|---|------|------|------|------|------|------|
| 20 | `impl::BitCommand` / `StationImage` / `WriteAck` | — | struct | 심의 자료형 — 절대 비트 인덱스·입력 이미지(seq·stamp·valid)·쓰기 응답(transport_ok·received·echo) | station_io_client.hpp:17·25·36 | M1 ✅ |
| 21 | `IStationIoClient::write_bits` / `image` / `link_up` | — | — | 스테이션 창구 3종. 같은 워드 비트는 스테이션이 단일 RMW 로 커밋 | station_io_client.hpp:50·53·55 | M1 ✅ |
| 22 | `impl::SignalMap` | — | struct | 스텝 6·제어 6·피드백 13·매거진 2 의 절대 비트 인덱스 + 감지 레벨 + **이미지 크기(do/di_bit_count)** + stale 한계. 기본값 없음(config 소유) | signal_map.hpp:19·29 | M1 ✅ |
| 23 | `SignalMap::control_index` / `step_index` / `feedback_index` | enum·비트 | int32_t | 이름 → 인덱스. 범위 밖·미매핑은 `kUnmapped(-1)` | signal_map.hpp:36·43·49 | M1 ✅ |
| 24 | `impl::validate(map)` | SignalMap | `MapCheck{ok,reason}` | 미매핑·중복·감지 레벨·비양수 stale 거부 + **이미지 범위 상한** + **step 6비트와 DRIVE 의 동일 워드 요건**(단일 RMW 보장) | signal_map.cpp:28·96 | M1 ✅ |
| 25 | `RemoteIoCommandPort::write_step` | uint8_t | Result<void> | 범위 밖은 **송신 0회** `kOutOfRange`, 유효하면 IN0~IN5 6비트를 한 요청으로 | remote_io_command_port.cpp:34 | M1 ✅ |
| 25-1 | `RemoteIo*Port::map_valid` | — | bool | 생성 시 `validate()` 결과. **거짓이면 전 호출을 송신 0회로 거부**(`kNotReady`) — 미검증 맵은 원자성·범위 보장이 없다 | remote_io_command_port.hpp:26 · remote_io_feedback_port.hpp:25 · remote_io_magazine_port.hpp:25 | M1 ✅ |
| 26 | `RemoteIoCommandPort::write_line` | ControlLine·bool | Result<void> | 라인 1비트. `kCount`·미매핑은 송신 0회 `kOutOfRange` | remote_io_command_port.cpp:59 | M1 ✅ |
| 27 | `RemoteIoCommandPort::clear_step_and_drive` | — | Result<void> | IN0~IN5 + DRIVE 7비트를 한 요청에 0 으로 | remote_io_command_port.cpp:69 | M1 ✅ |
| 28 | (내부) `RemoteIoCommandPort::commit` | vector\<BitCommand\> | Result<void> | 공통 송신·판정 — 링크 down/클라이언트 없음 `kNotReady` / 미응답·`received=false` `kIndeterminate` / echo 불일치 `kProtocol`. **미확정이 프로토콜 위반보다 우선** | remote_io_command_port.cpp:91 | M1 ✅ |
| 29 | `RemoteIoFeedbackPort::read` | — | Result<FeedbackSnapshot> | 13신호 원시 적재. 수신 이력 없음·stale·**링크 down** 은 `fresh=false` 스냅샷(오류 아님), 이미지 결손은 `kProtocol` | remote_io_feedback_port.cpp:14 | M1 ✅ |
| 30 | `RemoteIoMagazinePort::read` | — | Result<MagazineSnapshot> | 2점을 **0/1 로 정규화 후**(피드백의 `!=0` 규약과 동일) 극성 적용. 링크 down 은 `fresh=false`. seq 는 이미지 번호라 `same_image` 가 성립 | remote_io_magazine_port.cpp:14 | M1 ✅ |
| 31 | `RemoteIo*Port::health` | — | Health | link_up·snapshot_age·error_count·last_seq·last_error. **세 포트 동일 규약** — 이미지 미수신이면 age 를 stale 한계 초과로(«0ms 정상» 오독 차단) | remote_io_command_port.cpp:125 · remote_io_feedback_port.cpp:64 · remote_io_magazine_port.cpp:64 | M1 ✅ |

### 오류 등급 (본 계층이 고정)

`received=false` 를 `kIndeterminate` 로 두는 이유: `remote_io_node.cpp:252-300` 은 **요청 검증 거부와 쓰기 실패를
같은 값**으로 돌려주므로 "적용되지 않았다" 를 단정할 수 없다. 재시도 전 상태 재확인이 호출자 의무다.

### 검증

| 자산 | 위치 | 결과 |
|---|---|---|
| 단위 시험 23종 | remote_io_ports_test.cpp:118 | 스텝 전개·범위 거부(송신 0)·라인·복귀·오류 등급 4종·stale·극성·seq 일치 + **링크 down 강등·워드 분산 거부·미확정 우선·널 클라이언트·미검증 맵 전면 거부·이미지 범위 상한·health 오독 차단·**echo 레벨 왜곡·매거진 널 클라이언트**** ✅ |
| `⟦CI:gripper-io-single-master⟧` | ../../checks/gripper-io-single-master.sh | ✅ 직접 접근 0건. **ctest 등록됨**(`gripper_io_single_master`). red 시연 2종(스테이션 include·rclcpp include) 모두 rc=1 |
| 리뷰 반영 red 시연 | 2026-08-13 | 1라운드 3수정 되돌림 → 7단언 실패 · 2라운드 맵검증 강제 되돌림 → 4단언 실패 · 게이트 우회 5종(대소문자·소켓·신규 패키지·스캔 0건 포함) 전부 rc=1 |

## 예정 (M3)

| 심볼 | 위치 | 비고 |
|---|---|---|
| `make_sim_*` 3종 | `gripper_sim/` | LECP6 병렬 I/O 플랜트 |

## 소비처 (역참조)

- `gripper_motion` — 시퀀스 FSM 이 `FeedbackSnapshot`·`MagazineSnapshot` 소비, `ControlLine`/`write_step` 방출
- `gripper_ros` — 노드가 포트 3종을 소유·조립, `GripperCommand.action` 서버 + 코봇 IO 브리지
- `gripper_sim` — 본 인터페이스 3종을 구현

## 1차 소스 (계약 근거)

- LECP6 CN5 단자 정의: [SMC LECP6 Operation Manual (LEC-OM00608) page 26-28](../../../../../../references/smc/controllers/SMC_LECP6_OperationManual_E.pdf)
- 스텝 데이터 12항목·64개: 동 page 32 · 배선: [3,4호기 도면 p.55·p.63·p.66·p.72](../../../../../../references/lgit/electrical/LGIT_COBOT_AMR_3,4호기.pdf)
- legacy 파리티 근거: [docs/analysis/gripper_tx_wiring_and_drive_2026-08-12.md](../../../../../../docs/analysis/gripper_tx_wiring_and_drive_2026-08-12.md)
