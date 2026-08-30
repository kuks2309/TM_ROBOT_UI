# gripper 스택 함수표 **집계** (coding SOP §2/§6 이중 기록)

갱신: 2026-08-30 (ADR-005 단계④ 마감 — HITBOT `hitbot_zefg/{hal,motion,sim}` 벤더 스택 행 추가. 직전: 2026-08-29 단계①·② — SMC 스택 `smc_lecp6/{hal,motion,sim}` 재배치 + `gripper_common` 신설·`magazine_port` 이관)

> **본 문서는 집계본이다.** 각 패키지의 **모듈 로컬 원본**이 권위이며, 변경 시 두 곳을 함께 갱신한다
> (자매 선례: `Actuators/drawer/docs/functions-index.md`, `Sensors/PIO/docs/functions-index.md`).
>
> | 패키지 | 모듈 로컬 원본 | 상태 |
> |---|---|---|
> | gripper_common | [../gripper_common/docs/function_table.md](../gripper_common/docs/function_table.md) | 단계② 신설 — 공용 타입·MGZ 포트 |
> | gripper_hal | [../smc_lecp6/hal/docs/functions.md](../smc_lecp6/hal/docs/functions.md) | M0 계약 + **M1 impl 구현** |
> | gripper_motion | (M2 예정) | 비어 있음 |
> | gripper_ros | (M4 예정 — 단 `GripperCommand.action`·config 스키마는 M0) | 계약만 |
> | gripper_sim | (M3 예정) | 비어 있음 |
> | hitbot_zefg | [../hitbot_zefg/docs/function_table.md](../hitbot_zefg/docs/function_table.md) | ✅ 단계④ — hal(레지스터 계약+`ZefgHal`)·sim(`ZefgPlant`)·motion(`ZefgSequencer`)+H0 도구, 심볼 #1~#108 실측 앵커 |
>
> 전역 변수: **없음** (전 상태는 클래스/구조체 소유 — conventions 전역 규율)

## gripper_common (공용 계약)

갱신: 2026-08-29 (ADR-005 단계②-1·②-2 — 벤더 무관 공용 타입 신설 + `magazine_port` 이관, 소비자 include 실측 4파일 치환)

요약(원본 [../gripper_common/docs/function_table.md](../gripper_common/docs/function_table.md) 의 "공개 표면" 표를 그대로 집계 — 앵커·행 내용 추정 없음):

| 함수/타입 | 위치(파일:줄) | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `TimePoint` | types.hpp:13 | — | `using` (steady_clock::time_point) | 시각 별칭 |
| `Duration` | types.hpp:14 | — | `using` (milliseconds) | 기간 별칭 |
| `HalError` | types.hpp:18-29 | — | enum class | HAL 공통 오류 등급 9종(`kIndeterminate` 포함) |
| `Result<T>` | types.hpp:33-78 | `T` 또는 `HalError` | `Result<T>` | 접근자 가드형 결과(`[[nodiscard]]`), `err(kNone)` 은 `kProtocol` 로 승격 |
| `Result<void>` | types.hpp:81-111 | `HalError` | `Result<void>` | 값 없는 연산용 특수화, 승격 규약 동일 |
| `SignalState` | types.hpp:113-118 | — | enum class | `kUnknown`/`kInactive`/`kActive` — stale 을 정상/이상으로 만들지 않는 3상태 |
| `MagazineSnapshot` | types.hpp:120-127 | — | struct | `detected_1`·`detected_2`·`fresh`·`seq`·`stamp` |
| `both_detected` | types.hpp:129-132 | `MagazineSnapshot` | bool | `fresh=false` 는 무조건 false |
| `any_detected` | types.hpp:134-137 | `MagazineSnapshot` | bool | `fresh=false` 는 무조건 false |
| `Health` | types.hpp:139-146 | — | struct | `link_up`·`snapshot_age`·`error_count`·`last_seq`·`last_error` |
| `IMagazineDetectPort::read` | magazine_port.hpp:15 | — | `Result<MagazineSnapshot>` | MGZ 2점 스냅샷(극성 적용) — 로봇측 DI 라 벤더 무관(ADR-005 D3). gripper_hal 에서 이관(2026-08-29) |
| `IMagazineDetectPort::health` | magazine_port.hpp:17 | — | `Health` | 링크·에러 카운터 |

상세(검증 자산·소유 경계)는 모듈 로컬 원본 참조.

## gripper_hal (계약)

| 함수/타입 | 정의 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `IGripperCommandPort::write_step` | command_port.hpp | uint8_t(1~63) | Result<void> | IN0~IN5 원자 6bit 쓰기. 개별 비트 조작 경로 없음 |
| `IGripperCommandPort::write_line` | command_port.hpp | ControlLine, bool | Result<void> | SETUP/HOLD/DRIVE/RESET/SVON/LOCK_RELEASE |
| `IGripperCommandPort::clear_step_and_drive` | command_port.hpp | — | Result<void> | legacy `initGripperInNum` 파리티 |
| `IGripperFeedbackPort::read` | feedback_port.hpp | — | Result<FeedbackSnapshot> | 13신호 원자 스냅샷, stale 은 fresh=false |
| `IMagazineDetectPort::read` | magazine_port.hpp | — | Result<MagazineSnapshot> | gripper_common 으로 이관(2026-08-29) |
| `alarm_state` / `emergency_stop_state` | types.hpp | FeedbackSnapshot | SignalState | **negative-true 극성** 적용 + stale 은 `kUnknown` |
| `is_ready_for_drive` / `is_ready_for_origin` | types.hpp | FeedbackSnapshot | bool | 착수 조건 판정(DRIVE 는 SETON 요구, SETUP 은 미요구) |
| `ControlLine` / `FeedbackSignal` | types.hpp | — | — | SMC 전용 계약 커널 |

## smc_lecp6/hal/impl (M1 — 원격 IO 백엔드)

| 함수/타입 | 정의 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `IStationIoClient` | station_io_client.hpp | — | — | **ROS-free 심** — 스테이션 창구(write_bits·image·link_up). rclcpp 결선은 M4 조립층이 구현·주입 |
| `SignalMap` / `validate` | signal_map.{hpp,cpp} | — | MapCheck | 이름 → 절대 비트 인덱스. 기본값 없음(config 소유), 미매핑·중복·비양수 stale 거부 |
| `RemoteIoCommandPort` | remote_io_command_port.{hpp,cpp} | 클라이언트·맵 | IGripperCommandPort | 스텝 6비트 원자 송신, 범위 밖은 송신 0회 |
| `RemoteIoFeedbackPort` | remote_io_feedback_port.{hpp,cpp} | 클라이언트·맵·시계 | IGripperFeedbackPort | stale 은 오류가 아니라 `fresh=false` |
| `RemoteIoMagazinePort` | remote_io_magazine_port.{hpp,cpp} | 클라이언트·맵·시계 | IMagazineDetectPort | 극성 적용, seq 는 이미지 번호(`same_image` 성립) |

## gripper_ros (M0 계약분만)

| 자산 | 정의 | 비고 |
|---|---|---|
| `GripperCommand.action` | action/ | `COMMAND_PROFILE`/`COMMAND_ORIGIN`/`COMMAND_RESET` + result_code |
| `gripper_stack.yaml` | config/ | 프로파일 3종(봉인 정책) · 신호 비트맵 · 코봇 브리지 · 타임아웃 · 인터록 정책 |

## 소유 경계 (중복 방지)

| 대상 | 소유자 | 근거 |
|---|---|---|
| 신호 **이름**·극성 규약 | `smc_lecp6/hal/include/gripper_hal/types.hpp` | 계약 커널 |
| 물리 **비트 인덱스** | `gripper_ros/config/gripper_stack.yaml` | 하드코딩 금지(drawer D03 선례) |
| Modbus TCP 물리 접근 | `IOs/Remote_IO_Station` | 스테이션 단일 쓰기 마스터(ADR-001) |
| 스텝의 속도·추력 값 | **SMC 컨트롤러 스텝 테이블**(우리 소유 아님) | ADR-008 C2-1 |
| 공용 타입·MGZ 포트 | `gripper_common/include/gripper_common/` | ADR-005 D3 |
