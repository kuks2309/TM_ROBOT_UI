# gripper 스택 함수표 **집계** (coding SOP §2/§6 이중 기록)

갱신: 2026-08-13 (**M1 원격 IO 백엔드** — gripper_hal/impl 구현·단위 12종·게이트 red 시연. 직전: 2026-08-12 M0)

> **본 문서는 집계본이다.** 각 패키지의 **모듈 로컬 원본**이 권위이며, 변경 시 두 곳을 함께 갱신한다
> (자매 선례: `Actuators/drawer/docs/functions-index.md`, `Sensors/PIO/docs/functions-index.md`).
>
> | 패키지 | 모듈 로컬 원본 | 상태 |
> |---|---|---|
> | gripper_hal | [../gripper_hal/docs/functions.md](../gripper_hal/docs/functions.md) | M0 계약 + **M1 impl 구현** |
> | gripper_motion | (M2 예정) | 비어 있음 |
> | gripper_ros | (M4 예정 — 단 `GripperCommand.action`·config 스키마는 M0) | 계약만 |
> | gripper_sim | (M3 예정) | 비어 있음 |
>
> 전역 변수: **없음** (전 상태는 클래스/구조체 소유 — conventions 전역 규율)

## gripper_hal (계약)

| 함수/타입 | 정의 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| `IGripperCommandPort::write_step` | command_port.hpp | uint8_t(1~63) | Result<void> | IN0~IN5 원자 6bit 쓰기. 개별 비트 조작 경로 없음 |
| `IGripperCommandPort::write_line` | command_port.hpp | ControlLine, bool | Result<void> | SETUP/HOLD/DRIVE/RESET/SVON/LOCK_RELEASE |
| `IGripperCommandPort::clear_step_and_drive` | command_port.hpp | — | Result<void> | legacy `initGripperInNum` 파리티 |
| `IGripperFeedbackPort::read` | feedback_port.hpp | — | Result<FeedbackSnapshot> | 13신호 원자 스냅샷, stale 은 fresh=false |
| `IMagazineDetectPort::read` | magazine_port.hpp | — | Result<MagazineSnapshot> | MGZ 2점(극성 적용) |
| `alarm_state` / `emergency_stop_state` | types.hpp | FeedbackSnapshot | SignalState | **negative-true 극성** 적용 + stale 은 `kUnknown` |
| `is_ready_for_drive` / `is_ready_for_origin` | types.hpp | FeedbackSnapshot | bool | 착수 조건 판정(DRIVE 는 SETON 요구, SETUP 은 미요구) |
| `Result<T>` / `HalError` / `ControlLine` / `FeedbackSignal` | types.hpp | — | — | 계약 커널 |

## gripper_hal/impl (M1 — 원격 IO 백엔드)

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
| 신호 **이름**·극성 규약 | `gripper_hal/types.hpp` | 계약 커널 |
| 물리 **비트 인덱스** | `gripper_ros/config/gripper_stack.yaml` | 하드코딩 금지(drawer D03 선례) |
| Modbus TCP 물리 접근 | `IOs/Remote_IO_Station` | 스테이션 단일 쓰기 마스터(ADR-001) |
| 스텝의 속도·추력 값 | **SMC 컨트롤러 스텝 테이블**(우리 소유 아님) | ADR-008 C2-1 |
