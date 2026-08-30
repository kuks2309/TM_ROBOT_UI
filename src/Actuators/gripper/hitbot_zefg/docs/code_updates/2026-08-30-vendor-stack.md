# 2026-08-30 — hitbot_zefg 벤더 스택 마감 (ADR-005 단계④, Task 1~4)

- 계획: [docs/superpowers/plans/2026-08-29-hitbot-zefg-stack.md](../../../../../../docs/superpowers/plans/2026-08-29-hitbot-zefg-stack.md) · 원장: `.superpowers/sdd/2026-08-29-hitbot-zefg-stack/progress.md` (Ruling 1~10)
- Spec: [ADR-005](../../../docs/adr/ADR-005-multi-vendor-restructure.md) D1(벤더 폴더)·D3(회사별 hal/motion/sim)·D5(profile→위치·속도·전류는 config 소유)·D6 단계④(검증 = sim SIL 전 시나리오)
- 실측 정본: [HIL 2026-08-29 Z-EFG-C35 H0](../../../docs/hil/2026-08-29-zefg-c35-h0.md) — 영점 매핑(표시 0mm=실물 열림·35mm=닫힘)·H2 실사용값·§H0 재수행·§백드라이브
- 모듈 함수표(권위본): [../function_table.md](../function_table.md) · 루트 집계: [../../../docs/functions-index.md](../../../docs/functions-index.md)

## 산출물 — 3패키지 (hal · sim · motion)

| 패키지 | 커밋 | 내용 |
|---|---|---|
| `hal/` | `a047d89` (+리뷰 주석 보완 `7ee14cd`) | `zefg_registers.hpp` 레지스터 계약 상수(전 항목 매뉴얼 p5/실측 인용) + `ZefgHal`(RtuClient 위 어댑터 — IEEE754 상위워드 우선 float 변환[실측 0x420C0000=35.0]·RtuError→HalError 고정 매핑·`lastExceptionCode()`[Ruling 7 승인]) + 테스트 8종 + `tools/zefg_hal_h0_smoke.cpp`(읽기 전용 H0 도구, Task 4 계획분 조기 인출) |
| `sim/` | `fd3c8d9` (+골격 환원 fix `6b0cf4f`) | `ZefgPlant` 결정론 플랜트(MockSlaveLink 내장 + 명령 관찰 데코레이터, 래치 상태 유지 시맨틱스[실측 근거]) + 테스트 7종. fix wave: `hitbot_zefg/sim/` 독립 패키지 환원 + 단일마스터 게이트 정밀화 — 면제 = `(hal|sim)/`+`motion/test/` 만(Ruling 8) |
| `motion/` | `decfc32` (+리뷰 Minor fix `2da382f`) | `ZefgSequencer` FSM(tick 기반·시계 주입·hal 호출 ≤1회/tick·**status_grace 신선도 게이트**) + 테스트 10종(ZefgPlant+RtuClient+ZefgHal 실조립) |

의존 방향(게이트 강제): `hitbot_zefg/{hal,motion,sim} ──▶ {gripper_common, Common/comm/modbus_rtu}` —
mock/실기 모두 **같은 RtuClient·ZefgHal 코드**를 지난다(단계③ 검증 사슬 승계). `gripper_ros` 조립 연결은 본 계획 밖(후속).

## 총검증 실수치 (Task 4 Step 3 · hal/motion gtest 수는 최종 fix wave `aa3e063` 클린 재빌드 기준, 2026-08-30 본 PC)

| 항목 | 결과 |
|---|---|
| hitbot hal 패키지 ctest | **4/4 PASS** — `hitbot_zefg_hal_test` gtest **8/8** + modbus_rtu 3 엔트리 동거(아래) |
| hitbot sim 패키지 ctest | **1/1 PASS** — `hitbot_zefg_plant_test` gtest **7/7** |
| hitbot motion 패키지 ctest | **1/1 PASS** — `hitbot_zefg_sequencer_test` gtest **10/10** |
| modbus_rtu 회귀 | **26/26** — `rtu_frame_test` 9 + `rtu_client_test` 12 + `serial_port_test` 5, 전부 PASS |
| 기존 gripper SIL 회귀 | gripper_common ctest **1/1** · smc_lecp6/hal ctest **3/3** · smc_lecp6/motion ctest **1/1** · smc_lecp6/sim ctest **1/1** — 전부 PASS(베이스라인 무손상) |
| `checks/gripper-io-single-master.sh` | `✅ gripper-io-single-master: 직접 접근 0건 (검사 대상 52 파일)` rc=0 |
| `checks/modbus-rtu-ros-free.sh` | `✅ modbus-rtu-ros-free: rclcpp·tc_msgs·pio_hal include 0 (검사 대상 13 파일)` rc=0 |
| colcon(tc_msgs+gripper_ros) | `Summary: 2 packages finished [25.3s]` rc=0 |

## 실기 H0 (Ruling 10 — 기존 기록 인용, 재수행 없음)

계획 Task 4 Step 4 의 스모크 도구 신설(`zefg_snapshot_smoke.cpp`)은 **불요 판정**(원장 Ruling 10) —
`tools/zefg_hal_h0_smoke.cpp` 가 이미 존재하고 2026-08-30 11:00 nx-orin-1 실기 수행 완료:

```
init=Completed clamp=Dropping position=0.000mm speed=1.000mm/s current=-0.094A exception=0x00
health: link_up=1 error_count=0 last_error=0
```

SerialPortLink→RtuClient→ZefgHal 전체 C++ 체인의 실기 8워드 스냅샷 판독 성공 — position 0.000mm=실물
완전 열림(영점 정본 정합). 원문·해석(speed fb 1.0mm/s ⚠ 포함): [HIL 정본 §H0 재수행](../../../docs/hil/2026-08-29-zefg-c35-h0.md).

## profile 매핑 지침 (ADR-005 D5 — 값은 config 소유, gripper_ros 연결 시 결선)

| profile | 값 | 근거 |
|---|---|---|
| `release` | **0.0mm** | 표시 0mm=**실물 완전 열림** — [HIL 정본 §영점 매핑 실측](../../../docs/hil/2026-08-29-zefg-c35-h0.md)(매뉴얼 p6 예제와 반대, 실측이 정본. 0x0082 설정 변경 시 재실측) |
| `grip` | **대상물 치수 − 여유** (config 소유) | 기본값 확정은 gripper_ros 연결 시. 참조 가능 실측: SDC 파지 **16.56mm**(task-manager `sdc_gripper_close` 기본값, 커밋 `3de4922`) |
| 속도 기본 | **20mm/s** | H2 실측 사용값(35mm 편도 2.5~2.7s 완주·상태 전이 정상) |
| 전류 기본 | **0.3A** | H2 실측 사용값. §백드라이브 실측: 전류 제한이 곧 유지력·순응 강도 조정 파라미터(0.1~0.5A ↔ 파지력 15~50N[매뉴얼 p2]) |

## status_grace{300} 신선도 게이트 (SeqConfig — 브리프 승인 확장)

장치는 Dropping/Clamping 상태를 다음 모션 반영 전까지 래치한다 — [HIL 정본 §백드라이브·힘 순응 실측](../../../docs/hil/2026-08-29-zefg-c35-h0.md)
부수 발견(python `zefg_serial.move_to` 가 직전 래치 Dropping 을 첫 폴링에 읽고 오탐 실패)이 근거.
`ZefgSequencer` 의 kWaitMotion 폴링은 **Moving 관측 후 또는 목표 write 후 status_grace(기본 300ms) 경과
후에만** Clamping/Dropping 을 판정한다(InPlace+위치 대조는 예외 — 무이동 명령 즉시 성공 보존). python
선례 `zefg_serial.py` 의 `STATUS_GRACE_S` 와 동일 시맨틱스. 테스트 ⑧(래치 함정 재start) + 변이
프로브(`fresh=true` 강제 시 FAILED 실증)로 load-bearing 확인.

## 한계 (⚠ · 후속)

- `SeqConfig.init_timeout{5000ms}` ⚠ **실측 미보유** — 실기는 전원 인가 자동 초기화만 관찰(0x0040=5 시작). HIL 로 보정 예약.
- `kPlantInitTicks=5` ⚠ 동일 — 결정론 sim 계약값이지 실측 아님.
- **gripper_ros 미연결** — LifecycleNode 조립·config 로드·profile 매핑 결선은 본 계획 밖(후속 단계).
- debt 관련성: [debt-023](../../../../../../docs/debt/debt-023.md)(RtuClient kFrameShort 도달 불가 진단성 격차)·[debt-024](../../../../../../docs/debt/debt-024.md)(SerialPortLink 오류 경로 강건성 3건)은 본 스택의 실기 하부 경로(SerialPortLink→RtuClient) 그대로에 적용되며, 상환 계획이 "단계④ HIL 확대 전 경화 커밋"으로 예약돼 있다.

## 최종 리뷰 fix wave (`aa3e063`) — 단계④ 최종 교차 리뷰 Ruling 11 반영

Task 4 총검증 후 최종 교차 리뷰(Critical 0·Important 8·Minor 6)의 일괄 fix wave — 17파일(+246/−122). 요지:

- **SeqOutcome 공개 계약 확장** — `kObstructed`·`kRejected` 추가(승인 확장). **gripper_ros result_map 결선 시 두 값의 매핑이 필요하다.**
- **kClamped 성공 조건 정밀화** — 닫힘 방향(목표 > 모션 시작 위치, `motion_start_position_mm_` 캡처)이면서 목표 미달일 때만 kSucceeded(kClamped). 그 외 fresh Clamping 은 kFailed(kObstructed) — HIL §백드라이브 근거(실기 Clamping 은 외력 소멸 시 복귀 가능한 과도 상태). writeTargets 의 kOutOfRange/kRejected 는 kFailed(kRejected)로 분리 보고. 테스트 ⑨(열기 방향 폐색)·⑩(범위 밖 무송신 거부) 추가 — motion **10/10**.
- **health().link_up 교정** — 성공 관측 1회 이상(`had_success_` 신설) && last_error ∉ {kTimeout, kNotReady}(케이블 분리=kTimeout 근거). 신규 테스트 1종 — hal **8/8**.
- **게이트 tools 2-tier 편입** — `--exclude-dir=tools` 폐지, 벤더 `tools/`·스택 최상위 `tools/` 를 modbus 매치만 면제하는 2-tier 검사로 편입. 음성 프로브 2종(sys/socket.h) rc=1 실증, 실트리 rc=0(52파일).
- **install 제거 확정** — hitbot 3패키지 install(TARGETS/EXPORT/DIRECTORY) 전부 제거, add_subdirectory 소비 전용(ADR-005 각주 갱신). h0 스모크 타깃은 `HITBOT_ZEFG_BUILD_TOOLS`(기본 OFF) 가드 — ON 컴파일 실증.
- **debt-026 등록** — 장치 계약 이중 정의(C++ 스택 ↔ python `zefg_serial.py` — 레지스터·범위·grace·tolerance·판정 규약) 동기화 의무.

검증(클린 재빌드): hal **8/8** · sim **7/7** · motion **10/10** GREEN(ctest 4/4·1/1·1/1, modbus_rtu 26 동반) · 게이트 2종 rc=0(52파일·13파일). 상세: `.superpowers/sdd/2026-08-29-hitbot-zefg-stack/task-3-report.md` §Final fix wave.

관찰(후속 인지 — 결함 아님):

- (N3) kClamped 의 목표 미달 판정은 **엄격 부등호** — 목표 정확 도달+Clamping 표본은 kObstructed 로 판정된다. 실사용 경로(grip 목표=대상물 치수−여유)에서는 안전하나, 실기 HIL 확대 시 확인 대상.
- (N4) kRejected 분리는 **write 경로 한정** — 폴링(readSnapshot) 경로의 슬레이브 예외는 kCommError 로 보고된다(소비자 결선 시 인지).
