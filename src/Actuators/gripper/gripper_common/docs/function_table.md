# gripper_common 함수표 (모듈 로컬 원본 — coding SOP §2/§6 이중 기록)

갱신: 2026-08-29 (Task 4 — `magazine_port.hpp` 를 `gripper_hal` 에서 이관, ADR-005 D3. 직전: Task 3 — 벤더 무관 공용 타입 신설)
루트 집계 반영은 Task 5 담당(`../../docs/functions-index.md`).

> 전역 변수: **없음** (전 상태는 구조체 소유)
> 출처: `smc_lecp6/hal/include/gripper_hal/types.hpp` 의 벤더 무관부를 자구 그대로 이동.
> 네임스페이스는 이동 후에도 `gripper::hal` 유지(소비 코드 무수정).

## 공개 표면

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
| `IMagazineDetectPort::read` | magazine_port.hpp:15 | — | `Result<MagazineSnapshot>` | MGZ 2점 스냅샷(극성 적용) — 로봇측 DI 라 벤더 무관(ADR-005 D3) |
| `IMagazineDetectPort::health` | magazine_port.hpp:17 | — | `Health` | 링크·에러 카운터 |

## 검증 자산

| 심볼 | 위치 | 기능 |
|---|---|---|
| `main` | test/common_contract_check.cpp | `Result<void>`/`Result<T>` ok/err 의미·`kNone`→`kProtocol` 승격, `MagazineSnapshot` 헬퍼(fresh=false 전면 미검출), `Health` 기본값 검증 + `IMagazineDetectPort` 공개 표면 static_assert(추상 인터페이스·`read()`→`Result<MagazineSnapshot>`·`health()`→`Health`) |

## 소유 경계

SMC 전용부(`kStepMin`/`kStepMax`·`ControlLine`·`FeedbackSignal`·`FeedbackSnapshot`·`get`·`step_echo`·
`alarm_state`·`emergency_stop_state`·`is_ready_for_drive`·`is_ready_for_origin`·`same_image`)는
`smc_lecp6/hal/include/gripper_hal/types.hpp` 에 잔류 — 본 표에 포함하지 않는다(중복 방지).
