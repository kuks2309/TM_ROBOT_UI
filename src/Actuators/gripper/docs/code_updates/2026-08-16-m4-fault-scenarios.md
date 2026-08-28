# SIL 고장 시나리오 — 취소가 «정지» 를 뜻하지 않던 문제 (2026-08-16)

## 왜 만들었나

그때까지의 SIL 은 정상 경로만 봤다. 실기에서 무는 것은 대개 고장 경로다 — 스테이션이 응답하지
않거나, 쓰기를 확정하지 않거나, 링크가 끊기거나, 운전자가 도중에 취소하는 경우.

`sim_station_node` 에 고장 주입을 넣고(`fault.write_mode`·`fault.link_down`), 액션 서버를 실제로
두드리는 시나리오 러너(`test/sil_scenarios.py`)를 붙였다.

## 무엇이 나왔나

**취소가 «멈췄다» 를 뜻하지 않았다.** 취소 직후 다음 명령이 `NotReadyForDrive` 로 거절됐다 —
`BUSY` 가 아직 서 있었다. `DRIVE` 는 트리거라 내려도 컨트롤러는 목표까지 계속 간다(R10 이 그렇게
쓰라고 한 신호다). 그런데 액션 계약은 `RESULT_CANCELED` 를 «취소 요청으로 정상 중단(**정지 확인
완료**)» 이라고 못박고 있다. 우리는 확인하지 않고 그렇게 보고했다.

legacy 는 `HOLD` 를 **상태 보고에만** 쓰고 인가하지 않는다(`gripper_node.cpp:1338`). 감속정지를
새로 도입하려면 매뉴얼 인용과 실기 확인이 필요하므로, **측정 가능한 것만으로** 고쳤다 —
`BUSY` 하강을 확인한 뒤에 취소를 보고한다(R25).

## 고친 것

- `MotionState::kAborting` 신설. `abort()` 는 스텝·`DRIVE` 를 내리고 이 상태로 간다.
  `BUSY` 하강을 보면 출력 복귀 후 `kAborted`, `busy_fall_timeout` 을 넘기면 `kStopUnconfirmed`.
- `MotionResult::kStopUnconfirmed` → 액션 `RESULT_ABORT_FAILED`(«장치 정지 미보장»)로 매핑.
- `GripperFsm::finalizeStop()` — lifecycle 비활성화처럼 기다릴 수 없는 종료 경로용 즉시 마감.
  결과는 `kStopUnconfirmed` 다. 확인한 척하지 않는다.
- 노드 `on_deactivate` 는 `abort()` → `tick()` 1회 → `finalizeStop()`. 전이를 막지 않으면서
  결과 등급은 정직하게 남긴다.

## 스스로 만든 결함 1건

`abort()` 를 `kAborting` 으로 바꾸자 **비활성화가 FSM 을 그 상태에 가뒀다** — 타이머를 껐으니
아무도 전진시키지 않고, 이후 모든 요청이 `kBusy` 로 거절됐다. 시나리오 S-G 가 잡았다.
`finalizeStop()` 이 그 구멍을 닫는다.

## 시험 자체의 결함 2건

첫 실행에서 S-F(취소)·S-G(비활성화)가 **매거진 없이 grip 을 보내** 인터록에서 거절당했고,
단언이 `code != 0` 이라 «PASS» 가 났다 — 취소 경로를 아예 타지 않은 채로. 안착을 선행시키고
`CANCELED` 를 정확히 요구하도록 고쳤다.

코어 시험의 «`MotionResult` 전 값» 순회도 **손으로 나열한 배열**이라 새로 추가한
`kStopUnconfirmed` 가 조용히 빠졌다. 열거 범위 순회로 바꿨다(마지막에 값이 붙는 경우는
`result_map` 의 switch 가 `-Werror=switch` 로 먼저 잡는다).

## 검증

| 항목 | 결과 |
|---|---|
| 빌드 | 경고 0 |
| 단위 | hal 3/3 · motion 1/1 · sim 1/1 · ros_core 1/1 |
| **SIL 시나리오** | **26 단언 전부 통과** — 정상 사이클 · 고장 4종 · 취소 · 비활성화 · 연속운전 15회 |
| 게이트 | `gripper-io-single-master` 38파일 |

고장 4종의 관측: 쓰기 미확정·무응답·echo 불일치는 전부 `ABORT_FAILED`(사유 `IoError`)로,
링크 두절은 접수 단계에서 `stale` 로 거절된다. 조용히 성공하는 경로가 없다.

## 잔여

- `HOLD` 로 **실제 감속정지** — 매뉴얼(LEC-OM00608) 인용과 실기 확인이 선행이다. 지금은
  «정지를 확인한 뒤 보고» 까지만 한다(정지를 앞당기지는 않는다).

---

## 실기 계측 보강 (2026-08-16 HIL)

첫 실기 구동에서 실패가 났는데 **노드 로그에 아무것도 남지 않았다** — 실패 사유가 액션 결과로만
가고 로그에는 없었다. 사후 진단이 불가능한 구조였다.

- `finishGoal` 이 실패 시 사유·단계·복귀실패·경과를 `WARN` 으로 남긴다.
- `RosStationIoClient` 가 마지막 쓰기 실패 사유를 보관한다(`service_not_ready`·`call_timeout(…)`·
  `station_not_received(…)`·`echo_size(…)`), 노드가 `kIoError` 일 때 함께 출력한다.

이 계측이 붙은 뒤 재현 시도에서 «시퀀스 실패 0건 · 유일한 경고는 액션 응답 전송 타임아웃» 이
드러나, 앞선 실패가 장치가 아니라 **시험 하니스의 이중 노드**였음을 가릴 수 있었다.
기록: `docs/hil/2026-08-16-m4-first-drive.md`
