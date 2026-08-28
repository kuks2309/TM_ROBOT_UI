# 2026-08-16 — M2 시퀀스 FSM 구현 (`gripper_motion`)

M1 은 «비트를 원자적으로 쓴다» 까지만 책임진다. **순서 규칙**을 아는 계층이 없어 2026-08-15 실기에서
원점복귀를 건너뛴 시퀀스로 step 구동이 4회 연속 실패했다(mistake `2026-08-16-004`). 이번 M2 가 그 계층이다.

## 전이표에 고정한 실기 규칙

| # | 규칙 | 구현 | 근거 |
|---|---|---|---|
| R1 | **알람 이력이 있으면 `SETON`=1 이어도 원점복귀를 다시 한다** | `needsHoming()` 이 `alarm_seen_` 를 최우선 판정(`gripper_fsm.cpp:70`) | legacy `returnToOrigin()`(amr04 gripper_node.cpp:362-465) · HIL §5-6 |
| R2 | grip 완료는 `INP` 단독 금지 — **매거진 감지**로 판정 | `verifyComplete()` 가 프로파일별로 갈림(`gripper_fsm.cpp:127`) | HIL §5-1 (무부하 grip 40회 중 6회 `INP`=0인데 정상 종료) |
| R3 | 유효 프로파일 3종뿐 | `validate()` 스텝 범위·중복 검사(`fsm_types.cpp:15`) + `request()` 재확인 | HIL §5-6 (step4 는 BUSY 미상승·즉시 알람) |
| R4 | 알람 복구는 IN·DRIVE 0 → RESET → 복귀 대기 | `kResettingAlarm` 상태 | legacy `resetAlarmGripper()` |
| R5 | grip `require_both` · home `forbid_any` — **모드 무관** | `checkInterlock()` + `validate()` 가 완화 설정 자체를 거부 | ADR-008 Q6 · HIL §5-5 |

## 설계

- **블로킹 없음** — 모든 대기는 `tick()` 안의 시각 비교다. 주기는 호출자(M4 노드)가 소유한다.
- **시계 주입** — 타임아웃 경로를 실시간 대기 없이 시험한다.
- **거부는 송신 0회** — 프로파일·인터록 판정을 `request()` 에서 끝낸다.
- **모든 실패 경로가 출력을 복귀시킨다** — `fail()`·`abort()` 가 `clear_step_and_drive()` 를 호출한다.
- **미검증 설정으로는 구동하지 않는다** — `validate()` 실패 시 전 `request()` 거부.

## 검증

- 빌드 경고 0 · 시나리오 **15종 전부 통과**
- **red 시연 4종**: R1 되돌림 → 2단언 실패 / R2 → 2 / R5 → 5 / 실패 시 출력복귀 제거 → 1. 복구 시 전량 통과
- R1 red 는 **2026-08-15 실기 실패의 재현**이다 — 이제 코드가 그 경로를 막는다

## 잔여

- 외부 리뷰(never-self-approve)
- M3 `gripper_sim` — LECP6 병렬 I/O 플랜트로 이 FSM 을 SIL 회귀
- M4 `gripper_ros` — 액션 서버·config 로더·`IStationIoClient` ROS 구현
