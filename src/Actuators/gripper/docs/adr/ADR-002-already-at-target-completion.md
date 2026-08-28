# ADR(Architecture Decision Record) 2026-08-19 — 이미 목표 위치일 때의 완료 판정 (DL-GR01 개정)

- 날짜: 2026-08-19 (KST, Korea Standard Time)
- 관련: [ADR-001 gripper_ros 조립층](ADR-001-gripper-ros-assembly.md) · [마이그레이션 계획 DL-GR01](../2026-08-12-migration-plan.md)
- 대상: `gripper_hal/include/gripper_hal/types.hpp`(헬퍼 추가) · `gripper_motion/src/gripper_fsm.cpp`(`kWaitingBusyRise` 분기) · `gripper_motion/test/gripper_fsm_test.cpp`

## Status

**Superseded by ADR-004 (2026-08-20) — 전제가 실측으로 반증됐다.**

본 ADR 은 *"이미 목표 위치면 컨트롤러가 이동하지 않아 BUSY 가 오르지 않는다"* 를 전제로 삼았다.
2026-08-20 MK4 실기에서 `/io_resp` 를 50Hz 로 관측한 결과 **그 전제가 틀렸다**:

```
t=0.30  OUT=2  BUSY=0  INP=1     ← 명령 전(이미 열림)
t=1.75  OUT=0  BUSY=1  INP=1     ← 명령 직후 BUSY 가 실제로 상승
t=1.81  OUT=0  BUSY=0  INP=1     ← 60ms 만에 하강
t=4.77  OUT=2  BUSY=0  INP=1     ← 동작 완료, 스텝 반향 복귀
```

컨트롤러는 이미 목표 위치여도 **명령을 정상 수행하고 BUSY 를 낸다**. 실패 원인은
`drive_hold`(100ms)가 BUSY 펄스(60ms)보다 길어 **상승을 보고도 처리하지 못한 것**이었다(→ ADR-004).

본 ADR 이 도입한 `step_echo` 헬퍼와 `kWaitingBusyRise` 의 도달 판정 분기는 **코드에 남아 있으나**,
ADR-004 의 래치 수정으로 정상 경로가 복구되었으므로 **더 이상 이 문제의 해법이 아니다**.
남겨 둔 이유는 «이미 목표 위치 + BUSY 미상승» 이 실제로 발생할 경우의 방어층이기 때문이며,
제거해도 기능 손실은 없다. 제거 시 `types.hpp` 의 `step_echo` 와 해당 분기·테스트 ①~⑤ 를 함께 지운다.

## Context

### 관측된 실패 (MK4, 2026-08-19 22:15)

```
[22:15:55] [SMC 그리퍼] release 명령 전송
[22:15:58] [SMC 그리퍼] release 실패 result_code=8 msg=BusyRiseTimeout
[22:15:58] ✗ Job 실패: SMC 그리퍼 놓기
```

**그리퍼가 이미 열려 있는 상태에서 release 를 걸었다.** 55초→58초, 정확히 3초는
`timeouts.busy_rise_ms: 3000`(`gripper_ros/config/gripper_stack.yaml:86`)과 일치한다.

사용자 실측으로 대비가 확인됐다 — **그리퍼가 닫힌 상태에서 release 하면 성공**한다.
즉 컨트롤러는 명령을 받았으나, 이동할 거리가 없어 BUSY 를 올리지 않는다.

### 코드 경로

`kDriving` 에서 `DRIVE=1` 인가 후 `kWaitingBusyRise` 로 진입하고, 그 상태는 **BUSY 상승만** 기다린다.
`busy_rise_timeout` 이 만료되면 무조건 실패다 — `gripper_fsm.cpp:655-658`.

```cpp
if (expired(config_.busy_rise_timeout))
{
    return fail(MotionResult::kBusyRiseTimeout);
}
```

### 이것이 의도된 이탈이라는 사실

마이그레이션 계획의 **DL-GR01**(DL = Deviation Ledger, 의도적 이탈 기록) 이 바로 이 동작을 규정했다:

| DL | 이탈 | legacy | 사유 |
|---|---|---|---|
| DL-GR01 | BUSY 상승 확인을 전 명령 필수 | release/home 은 주석 처리 후 고정 200ms sleep | 명령 미수신을 완료로 오판하는 경로 제거 |

같은 사상이 원점복귀 경로 주석에도 있다 — *"SETON 래치만으로 완료로 보지 않는다 — 실제 이동(BUSY)이 없으면 실패다"*(`gripper_fsm.cpp:523`).

### 문제의 정확한 형태

DL-GR01 은 **"명령 미수신"** 을 잡으려 했는데, 실제로 구현된 판정은 **"이동 발생"** 이다.
이 둘은 "이미 목표 위치에 있음"이라는 정상 상태에서 갈라진다:

| 실제 상황 | 명령 수신 | 이동 발생 | 목표 상태 도달 | 현재 판정 | 옳은 판정 |
|---|---|---|---|---|---|
| 정상 구동 | ○ | ○ | ○ | 성공 | 성공 |
| 명령 미수신 | ✗ | ✗ | ✗(이전 위치) | 실패 | 실패 |
| **이미 목표 위치** | ○ | ✗ | **○** | **실패** | **성공** |

세 번째 행이 이번 사고다. 그리고 이 표가 해결의 열쇠다 —
**"이동했는가"가 아니라 "목표 상태에 있는가"를 물으면 세 경우가 모두 옳게 갈린다.**

## Decision

`kWaitingBusyRise` 의 타임아웃 분기에서, 즉시 실패하는 대신 **목표 상태 도달 여부를 확인**한다.

```
busy_rise_timeout 만료 && BUSY 미상승:
    INP 활성  &&  step_echo(snapshot) == stepOf(profile_)   →  kOk  (이미 도달)
    그 외                                                    →  kBusyRiseTimeout  (기존과 동일)
```

- `step_echo` — `gripper_hal` 에 신설할 헬퍼. 피드백 `kOut0`~`kOut5` 6비트를 정수로 읽는다(LSB=out0).
  현재 이 비트들은 **신호맵에 배선되어 있으나(`gripper_stack.yaml:47-52`, DI(Digital Input) 64~69, 도면 p.66) 읽는 코드가 없다.**
- `INP`(In Position, `kInPosition`) — "목표 위치 도달". 정지 완료를 보증한다.
- 알람 판정은 기존 그대로 우선한다(타임아웃 분기에 도달하기 전에 `kAlarmActive` 로 빠진다).

### DL-GR01 과의 관계 — 취지는 유지된다

명령을 받지 못했다면 컨트롤러는 **이전 스텝**을 반향하므로 `step_echo != 목표` 로 걸러진다.
즉 "명령 미수신을 완료로 오판"하는 경로는 여전히 닫혀 있다.
바뀌는 것은 판정 **근거**이지 판정의 **엄격함**이 아니다 — BUSY 하나 대신 `INP + step_echo` 두 신호를 요구한다.

DL-GR01 을 다음과 같이 개정한다:

> **BUSY 상승 확인을 전 명령 필수. 단 BUSY 미상승이라도 `INP` 활성이고 스텝 반향이 목표와 일치하면
> "이미 목표 위치"로 보아 완료로 처리한다.** legacy 의 무조건 200ms sleep 과 달리 두 신호로 상태를 확인한다.

### 실측 결과 (2026-08-19 22:41, MK4 실기 `/io_resp` 1샷)

**`OUT0~5` 가 실행 스텝 번호를 반향한다**는 전제가 2차 자료(코드 주석 `gripper_hal/types.hpp:126`,
설정 주석 `gripper_stack.yaml:12` 의 SMC LECP6 Operation Manual LEC-OM00608 p.26-28 인용)뿐이었으므로
1차 소스 부재 상태에서 **실기 측정으로 확인**했다. 매뉴얼 원본은 여전히 `references/` 에 없다.

| 그리퍼 상태 | OUT0~5 (스텝) | `in_position` | `busy` | `set_on` | `alarm`(neg) |
|---|---|---|---|---|---|
| 열림 (release) | **2** | **1** | 0 | 1 | 1 |
| 닫힘 (grip) | **0** | **0** | 0 | 1 | 1 |

- **release 는 전제대로다** — `profiles.release: 2` 와 일치하고 `INP` 가 선다.
- **grip 은 스텝 1 이 아니라 0 이고 `INP` 도 서지 않는다.** 파지는 물체를 밀어 잡는 동작이라
  목표 위치에 도달하지 못한 채 정지하므로 컨트롤러가 "도달한 스텝 없음"을 낸다.
  즉 **OUT 은 "지시된 스텝"이 아니라 "도달 완료한 스텝"의 반향**이다.
  - 이 측정은 **`grip` 명령으로 정상 닫힌 상태**에서 잰 값이다(사용자 확인 2026-08-19).
    수동으로 닫았거나 실패한 상태의 값이 아니므로, "정상 완료했는데도 도달 스텝이 없다"가 확정이다.
  - 따라서 **닫기는 컨트롤러 신호로 "이미 닫혀 있음"을 증명할 수 없다** —
    `OUT=0 · INP=0` 은 "이미 잡고 있음"과 "명령을 받지 못함"이 동일하게 나타난다.

### 그 결과 — 적용 범위는 release 로 좁혀진다 (의도된 한계)

판정식 `INP 활성 && step_echo == 목표 스텝` 은 신호 특성상 자동으로 갈린다:

| 프로파일 | 판정 성립 | 비고 |
|---|---|---|
| `release` | **성립** | 이번에 고치려는 실패가 여기서 난다 |
| `grip` | **불성립** (OUT=0, INP=0) | 기존대로 `kBusyRiseTimeout`. **사용자 결정(2026-08-19): 닫기는 완화하지 않는다** — 매거진 2점 감지로 대체 판정하는 안을 검토했으나, grip 인터록이 `require_both` 라 명령 전부터 참이어서 "명령 미수신"과 구분되지 않고 빈 그리퍼 진행을 낳는다. 실무 pick 흐름은 `열기 → 접근 → 닫기` 라 닫기가 이미 닫힌 상태로 불릴 일은 앞 열기가 생략·실패했을 때뿐이다 |
| `home` | 해당 없음 | FSM 의 별도 경로(`kHomingWaitBusyRise` + `origin_busy_rise_timeout`)라 본 변경 범위 밖 |

이 좁혀짐은 **안전 방향**이다. 파지 완료를 잘못 성공 처리할 경로가 구조적으로 존재하지 않는다 —
판정을 느슨하게 만드는 것이 아니라, 신호가 도달을 명시적으로 증명하는 경우에만 통과시킨다.

## Alternatives

| | 안 | 판정 |
|---|---|---|
| A | 레시피에서 선행 `release` 를 제거 | 임시방편. 그리퍼가 닫힌 채 시작하면 박스를 못 집는다. FSM(Finite State Machine) 의 빈틈은 그대로 남아 다른 레시피에서 재발한다 |
| B | **본 결정** — `INP` + 스텝 반향으로 "이미 도달" 판정 | 채택 |
| C | `busy_rise_ms` 증가 | **무의미**. 이동하지 않으므로 아무리 기다려도 BUSY 는 오르지 않는다 |
| D | FSM 이 마지막 성공 스텝을 내부 기억 | 전원 재기동·수동 조작·티칭박스 개입 후 실제 위치와 어긋난다. 하드웨어 신호보다 신뢰도가 낮다 |

## Consequences

**긍정**

- "이미 목표 위치" 정상 상태가 실패로 종결되지 않는다. 레시피가 그리퍼 초기 상태에 의존하지 않아도 된다.
- 배선만 되어 있고 쓰이지 않던 `OUT0~5` 가 처음으로 상태 판정에 활용된다.
- 판정 근거가 신호 1개(BUSY)에서 2개(`INP` + 스텝 반향)로 늘어 오판 여지가 줄어든다.

**부정 · 위험**

- **`OUT` 반향 전제는 실측으로 확인됐다**(§Decision 실측 결과). 다만 1차 소스(LECP6 매뉴얼)는 여전히 부재이며,
  측정은 release/grip 두 상태뿐이다. 컨트롤러 스텝 테이블이 바뀌면 재확인이 필요하다.
- **`grip` 은 본 경로로 구제되지 않는다** — "이미 잡은 상태에서 재-grip" 은 계속 `kBusyRiseTimeout` 이다.
  실무 레시피는 열기→집기 순서라 드물지만 한계로 남는다.
- 알람 발생 시 `OUT0~3` 이 알람 그룹으로 전환된다면 스텝 반향과 값이 겹칠 수 있다.
  다만 알람 판정이 타임아웃 분기보다 **먼저** 실행되므로 그 경로로는 도달하지 않는다. 테스트로 고정한다.
- `gripper_motion` 은 ROS-free 코어이므로 `⟦CI:gripper-ros-free⟧` 게이트를 계속 만족해야 한다(rclcpp 미사용).

**검증 요건** (never-self-approve — 최종 verdict 는 저자가 찍지 않는다)

- 단위 테스트 4종 이상: ① 이미 도달(INP 활성 + 스텝 일치) → `kOk` ② 스텝 불일치 → `kBusyRiseTimeout`
  ③ INP 비활성 → `kBusyRiseTimeout` ④ 알람 동시 → `kAlarmActive` 우선
  ⑤ grip 실측 신호(OUT=0, INP=0) 재현 → `kBusyRiseTimeout`(회귀 고정)
- 기존 FSM 시나리오 회귀 전건 PASS
- MK4 실기: **열린 상태 release 성공**(현재 실패하는 케이스) · 닫힌 상태 release 성공(회귀 없음) · grip 정상 동작 유지

## Rollback

가역이다. 되돌리는 방법은 두 가지다.

1. **코드 되돌림** — `kWaitingBusyRise` 타임아웃 분기를 `return fail(MotionResult::kBusyRiseTimeout);`
   한 줄로 복원하고 `step_echo` 헬퍼를 제거한다. 신호맵·설정은 건드리지 않았으므로 다른 변경은 없다.
2. **재빌드** — MK4 에서 `colcon build --packages-select gripper_hal gripper_motion gripper_ros` 후
   `gripper_node` 재기동. 설정 파일(`gripper_stack.yaml`) 변경이 없으므로 파라미터 호환성 문제가 없다.

되돌린 뒤에는 본 ADR 이전 상태 — 즉 "이미 목표 위치"에서 `BusyRiseTimeout` 이 나는 상태로 복귀한다.
그 경우의 회피책은 §Alternatives 의 A(레시피에서 선행 release 제거)다.
