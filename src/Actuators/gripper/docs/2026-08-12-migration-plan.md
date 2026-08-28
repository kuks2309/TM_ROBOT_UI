# gripper 마이그레이션 계획 (SSOT)

- **작성**: 2026-08-12 · **대상**: legacy `tc_gripper`(4호기 Tx) → MOMA `Actuators/gripper`
- **계약 상태의 권위는 ADR** — [ADR-008](../../../../docs/adr/ADR-008-gripper-stack-and-robot-gripping-structure.md) (Proposed, 사용자 승인 5건 반영)
- **legacy 실측 정본**: [docs/analysis/gripper_tx_wiring_and_drive_2026-08-12.md](../../../../../docs/analysis/gripper_tx_wiring_and_drive_2026-08-12.md)
- **1차 소스**: [references/smc/](../../../../../references/smc/README.md) · [3,4호기 전기 도면](../../../../../references/lgit/electrical/LGIT_COBOT_AMR_3,4호기.pdf)
- **용어**: HAL(Hardware Abstraction Layer), SIL(Software In the Loop), HIL(Hardware In the Loop), DL(Deviation Ledger), MGZ(Magazine), DI/DO(Digital Input/Output), IDL(Interface Definition Language)

## 1. 범위와 경계

| 소유 | 위치 |
|---|---|
| 그리퍼 신호·시퀀스·타이밍·안전 | 본 스택 |
| 원격 IO 물리 접근(Modbus TCP) | `IOs/Remote_IO_Station` — **`remote_io_ros` 노드가 스테이션 단일 쓰기 마스터**, 소비자는 서비스 경유(사용자 결정 2026-08-12) |
| 파지 응용(매거진 접근·재시도·팔 조합) | `Skills/Robot_Gripping` |
| 스텝별 속도·압력 값 | SMC 컨트롤러 스텝 테이블 (**우리 자산 아님**) |

## 2. 마일스톤

| 단계 | 산출물 | 게이트 | 상태 |
|---|---|---|---|
| **M0 계약 동결** | `gripper_hal` 헤더 4종 · `GripperCommand.action` · `gripper_stack.yaml` 스키마 · 본 계획서 · 인벤토리 표 | 헤더 syntax·format 통과 + 계약 의미 검증 + 외부 리뷰(never-self-approve) | **작성 완료 · 외부 리뷰 1라운드 반영 · 승격 대기**(Q5·Q6 결정 후) |
| M1 코어 구현 | `impl/` 3포트(**ROS-free 심 `IStationIoClient` 위의 어댑터**) + 신호맵 + 단위 테스트 | 단위 PASS · `⟦CI:gripper-io-single-master⟧` | **구현 완료 + 외부 리뷰 2라운드 반영 (2026-08-13)** — 단위 20종 ✅ · ctest 3/3(게이트 포함) · 빌드 경고 0. 1차 8건 중 7건 · 2차 20건 중 Blocking 5 전건 포함 11건 반영(유예 3건은 debt-074~076). 잔여: rclcpp 결선(M4) |
| M2 시퀀스 FSM | `gripper_motion` 전이표 + 인터록 정책 | 전이표 테스트 · DL 4건 반영 확인 | **구현 + 외부 리뷰 1라운드 반영 (2026-08-16)** — 시나리오 25종 ✅ · 경고 0 · **red 12종**(Blocking 8 + High 2 + SIL). 규칙 R1~R13 고정. 잔여: Medium/Low 잔여·재리뷰 |
| M3 SIL | `gripper_sim` 플랜트(LECP6 병렬 I/O 모형) + 결함주입 | 시나리오 회귀 PASS | **구현 + 리뷰 반영 (2026-08-16)** — S1~S7 ✅ · 경고 0 · **red: 원점복귀 무력화 시 14단언 실패 + 플랜트 알람**. 이미지 seq 공유로 same_image 규약 정합. 잔여: 재리뷰 |
| M4 조립·HIL | `gripper_ros` LifecycleNode + 액션 서버 + 코봇 브리지 | H0~H3 순차 통과 | **SIL 구현 완료 (2026-08-16)** — 경고 0 · 코어 시험 통과 · **뮤테이션 8종 살아남음 0(red 39단언)** · lifecycle 검증 게이트 실측 · 액션 거절 4경로 실측 · **SIL 폐루프 냉시동 release 완주**(PRECHECK→ORIGINATING→WAIT_SETON→STEP_SET→DRIVING→VERIFY→DONE). 잔여: grip 완주 SIL(debt-093 플랜트 충실도) · COMMAND_STEP(debt-094) · 코봇 브리지 · **HIL** |

## 3. 파리티 기준선 (legacy 관측 동작)

| 항목 | 값 | 근거 |
|---|---|---|
| 스텝 | grip=1 · release=2 · home=3 | `gripper_config.json` 실기 실측 |
| 스텝 → 비트 | `(step >> i) & 1`, IN0=LSB | `gripper_node.cpp:696-699` |
| 그립 시퀀스 | 인터록 → BUSY 확인 → IN 세팅 → 200ms → DRIVE=1 → BUSY↑(3s) → DRIVE=0 → BUSY↓(10s) → INP(1s) → 코봇 통지 | `gripper_node.cpp:668-800` |
| 원점복귀 | SVRE 확인 → SETUP 0 → 1s → SETUP 1 → BUSY↑(2s) → BUSY↓(10s) → SETON(2s) → INP(1s) | `gripper_node.cpp:407-448` |
| 알람 극성 | ALARM=1 정상 (negative-true) | `gripper_node.cpp:1367-1375` + LECP6 OM page 28 |
| 알람 그룹 | OUT0~OUT3 4비트 → B/C/D/E | `gripper_node.cpp:1119-1138` |
| 실측 소요 | GUI RELEASE 전체 1.507초 | 실기 로그 `~/tcon/log/20260805/LOG_SEQ` |

## 4. 의도적 이탈 (DL)

| DL | 이탈 | legacy | 사유 |
|---|---|---|---|
| DL-GR01 | BUSY 상승 확인을 전 명령 필수 | release/home 은 주석 처리 후 고정 200ms sleep | 명령 미수신을 완료로 오판하는 경로 제거 |
| DL-GR02 | 인터록 명령×모드 표 + **MANUAL grip 인터록** + **HOME forbid_any** | MANUAL 통째 우회 · HOME 은 의도만 있고 통과 | 사람이 누르는 경로가 무방비였고, 문 채 홈 이동은 낙하 위험(사용자 결정 2026-08-12) |
| DL-GR03 | 실패는 항상 결과 코드로 종결 | 알람 발행 다수 주석 | 조용한 실패 제거 |
| DL-GR04 | 진행 중 상태 명령별 분리 | HOME 도 `GRIPPING` | 소비자 오독 제거 |

## 5. 게이트 (`checks/`)

| id | 검사 |
|---|---|
| `gripper-ros-free` | `gripper_hal`·`gripper_motion`·`gripper_sim` 에서 `rclcpp` 등장 시 실패 |
| `gripper-io-single-master` | `gripper_hal/impl/remote_io/` 밖에서 소켓·modbus 심볼 등장 시 실패 |
| `gripper-vendor-sealed` | SMC/SCHUNK 고유 명칭이 `impl/`·`gripper_sim/` 밖 등장 시 실패(주석 인용 허용) |
| `gripper-no-blocking` | 콜백 스코프에 `sleep_for`·`spin_until_future_complete` 등장 시 실패 |
| `gripper-contract-freeze` | 동결 헤더 해시 대조 — 변경 시 ADR 갱신 요구 |

## 6. HIL 진입 (낙하·협착 위험)

H0 읽기 전용 관측 → H1 서보/알람만 → H2 무부하 동작 → H3 적재 동작. SIL 회귀 통과 없이 H1 이후 금지.
실기는 리모트 `~/LGIT_C6_MoMa`. 티칭박스를 물린 정비 중이면 `ESTOP` 유입은 고장이 아니라 정비 상태다.

## 7. 미결

| # | 내용 | 소관 |
|---|---|---|
| 1 | 포트 3종 시그니처 동결 승격 — 외부 리뷰 필요 | ADR-008 Q1 |
| 2 | 컨트롤러 라벨 확인(LECP6N/P·부번 `C6173`) | ADR-008 Q2-a |
| 3 | 스텝 실값 읽기 — 티칭박스·세팅킷 미보유로 **불가**, 확장 봉인 유지 | ADR-008 Q2-b |
| 4 | 코봇 팔 시퀀스 소유자 | ADR-008 Q3 (보류, 형태는 액션+lifecycle 고정) |
| 5 | Rx(SCHUNK) 백엔드 착수 시점 — 병렬 I/O 형 계약과 시리얼 필드버스의 형태 차이 재검토 | ADR-008 Q4 |
| 6 | **명령 중재** — 코봇 브리지 ↔ ROS 액션 동시 지시 시 상호 배제 규약 부재 (M2 전 결정) | ADR-008 Q5 |
| ~~7~~ | ~~MANUAL 모드 인터록~~ → **해소**: grip 은 모드 무관 require_both, 우회는 manual_override 전용 | ADR-008 Q6 |
| ~~8~~ | ~~배포 토폴로지~~ → **해소**: `remote_io_ros` 노드가 스테이션 소유, 그리퍼는 **서비스 클라이언트 어댑터**. 계약 변경 없음 | ADR-008 Q7 |
