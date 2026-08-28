# ADR(Architecture Decision Record) 2026-08-20 — BUSY 상승 래치 (`drive_hold` 보다 짧은 펄스)

- 날짜: 2026-08-20 (KST, Korea Standard Time)
- 관련: [ADR-002](ADR-002-already-at-target-completion.md)(본 ADR 이 supersede) · [ADR-003 성격의 우회 경로는 `originInterlock` 주석 참조](../../smc_lecp6/motion/src/gripper_fsm.cpp)
- 대상: `gripper_motion/include/gripper_motion/gripper_fsm.hpp`(멤버 1개) · `gripper_motion/src/gripper_fsm.cpp`(`enter()`·`kWaitingBusyRise`) · `gripper_motion/test/gripper_fsm_test.cpp`

## Status

**Accepted — 구현 완료 · 단위 검증 통과 · 실기 미검증.** 사용자 승인 2026-08-20("해봐... 복구 가능하게만 해").

## Context

### 증상

MK4 에서 **이미 열린 상태로 `release`** 를 걸면 3초 뒤 `BusyRiseTimeout`(result_code=8) 으로 실패했다.
`grip` 도 이미 닫힌 상태에서 같은 실패를 냈다. 레시피의 첫 잡이 "집기 전 그리퍼 열기" 라 실행이 시작조차 못 했다.

### 실측 (MK4 2026-08-20, `/io_resp` 50Hz 관측)

```
   t(s)  | OUT스텝 | BUSY | INP | SETON | ALARM(neg)
   0.30  |    2    |  0   |  1  |   1   |     1      ← 명령 전(이미 열림)
   1.75  |    0    |  1   |  1  |   1   |     1      ← 명령 직후 BUSY 상승, 스텝 반향은 0 으로 떨어짐
   1.81  |    0    |  0   |  1  |   1   |     1      ← 60ms 만에 BUSY 하강
   4.77  |    2    |  0   |  1  |   1   |     1      ← 동작 완료, 스텝 반향 복귀
```

두 가지가 확정됐다:

1. **컨트롤러는 이미 목표 위치여도 명령을 정상 수행하고 BUSY 를 낸다.** 동작 완료 후 스텝 반향이 2 로 돌아온다.
2. **그 BUSY 펄스는 60ms 로 짧다.** 이동 거리가 0 에 가깝기 때문이다.

### 원인

`kWaitingBusyRise` 가 BUSY 를 **레벨**로만 판정했다:

```cpp
if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kBusy))
{
    if (!expired(config_.drive_hold))  // drive_hold_ms: 100
    {
        break;                          // 유지시간 미충족 — 아무것도 하지 않고 다음 tick 으로
    }
    ...DRIVE=0 → kWaitingBusyFall
}
if (expired(config_.busy_rise_timeout)) return fail(kBusyRiseTimeout);
```

| 시각 | BUSY | FSM(Finite State Machine) 동작 |
|---|---|---|
| 0~60ms | 1 | `drive_hold`(100ms) 미충족 → `break` |
| 60ms~ | 0 | **분기 조건이 거짓** — 다시는 들어갈 수 없다 |
| 3000ms | 0 | `kBusyRiseTimeout` |

`tick_period_ms` 는 20ms(`node_params.cpp:81`)라 신호를 **놓친 것이 아니다. 보고도 처리하지 못했다.**
`drive_hold` 가 BUSY 펄스보다 길면 구조적으로 항상 실패한다.

이동 거리가 큰 명령(닫힘→열림)은 BUSY 가 100ms 넘게 유지되므로 드러나지 않았다.
**"이미 그 위치일 때만" 재현되는 결함**이었다.

## Decision

BUSY 상승을 **단계 안에서 래치**한다. 레벨이 내려가도 "봤다" 는 사실은 남는다.

```cpp
if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kBusy))
{
    busy_seen_ = true;
}
if (busy_seen_)
{
    if (!expired(config_.drive_hold)) break;   // 유지시간은 그대로 채운다(legacy 파리티)
    write_line(ControlLine::kDrive, false);
    enter(MotionState::kWaitingBusyFall);
    break;
}
```

- `busy_seen_` 은 `enter()` 에서 리셋된다 — `phase_wrote_` 와 같은 수명(단계 단위).
- `drive_hold` 의 목적(DRIVE 최소 유지)은 변하지 않는다. **판정 근거만 레벨 → 엣지로 바꾼다.**
- `busy_rise_timeout` 은 그대로다. BUSY 를 **한 번도** 못 보면 여전히 실패한다 — DL-GR01(Deviation Ledger, 의도적 이탈 기록)의 "명령 미수신 오판 제거" 취지가 유지된다.

## Consequences

**긍정**

- 이미 목표 위치인 `release`·`grip` 이 정상 완료된다. 레시피가 그리퍼 초기 상태에 의존하지 않아도 된다.
- 짧은 행정 전반(미세 이동)에서 같은 실패가 사라진다.
- `kWaitingBusyFall` 이후 경로는 그대로라 완료 검증(`verifyComplete`)은 종전과 동일하게 적용된다.

**부정 · 위험**

- BUSY 가 **채터링**(짧은 노이즈)으로 한 번 튀면 래치가 서서 진행할 수 있다. 다만 그 뒤 `kWaitingBusyFall` →
  `kVerifying` 이 실제 완료를 검증하므로(release 는 `INP`, grip 은 매거진 감지) 잘못된 성공으로 끝나지는 않는다.
- ADR-002 가 도입한 `step_echo` 도달 판정은 이제 이 문제의 해법이 아니다(중복 방어층으로만 남음).

**검증** (never-self-approve — 최종 verdict 는 저자가 찍지 않는다)

- 신규 테스트: 20ms tick × 3 = **60ms 동안만 BUSY 를 올린 뒤 내림** → `kDone` · `kOk` 도달, `drive_level == 0`
- 기존 FSM 시나리오 전건 회귀 **ALL PASS (0 fail)**
- MK4 에서 `gripper_hal`·`gripper_motion`·`gripper_ros` **3패키지 함께 빌드**
  (ADR-002 때 `gripper_ros` 재링크를 빠뜨려 실기에 반영되지 않았던 전례가 있다 — 정적 라이브러리 `.a` 이므로 반드시 함께 빌드한다)
- **실기 확인 미수행** — 열린 상태 release / 닫힌 상태 grip / 정상 이동 회귀

## Rollback

가역이다.

1. **소스 복원** — 원격 MK4 에 변경 직전 백업이 있다:
   `~/backup_gripper_before_busylatch_20260820.tgz` (`src/Actuators/gripper` 전체, 134,846 bytes)
   ```bash
   cd ~/Projects/jjh/tm-robot-4/src/Actuators && tar xzf ~/backup_gripper_before_busylatch_20260820.tgz
   ```
2. **부분 되돌림**(백업 없이) — `kWaitingBusyRise` 의 `if (busy_seen_)` 를 원래 조건
   `if (snapshot.fresh && hal::get(snapshot, FeedbackSignal::kBusy))` 로 되돌리고,
   `busy_seen_` 멤버와 `enter()` 의 리셋 한 줄을 제거한다.
3. **재빌드·재기동**
   ```bash
   colcon build --packages-select gripper_hal gripper_motion gripper_ros
   # 이후 gripper_node 재기동 (실행 중인 프로세스는 옛 바이너리를 유지한다)
   ```

설정 파일(`gripper_stack.yaml`)은 건드리지 않았으므로 파라미터 호환성 문제가 없다.
되돌리면 "이미 목표 위치에서 `BusyRiseTimeout`" 증상이 그대로 복귀한다.
