# gripper — 그리퍼 구동 스택 (LGIT-C6-MOMA)

> **현재 상태: M0 계약 작성 완료(동결 승격은 외부 리뷰 후).** 구현체·노드는 아직 없다. 이 README 가 **어디에 무엇이 들어가는지**의 SSOT 다.
> 빈 디렉터리는 "여기에 무엇이 온다"는 예약이지 구현이 아니다 — 착각 방지를 위해 스텁 코드를 두지 않았다(Docking_Control 선례).

- **용어**: HAL(Hardware Abstraction Layer), ADR(Architecture Decision Record), SSOT(Single Source of Truth), DL(Deviation Ledger), SIL(Software In the Loop), HIL(Hardware In the Loop), DI/DO(Digital Input/Output), MGZ(Magazine), BOM(Bill of Materials), NC(Normally Closed), AMR(Autonomous Mobile Robot), IDL(Interface Definition Language). 단자명(`IN0~IN5`·`SETUP`·`HOLD`·`DRIVE`·`RESET`·`SVON`·`LOCK_OFF` 등)은 도면 표기 리터럴이다.
- **결정 기록**: [../../../docs/adr/ADR-008-gripper-stack-and-robot-gripping-structure.md](../../../docs/adr/ADR-008-gripper-stack-and-robot-gripping-structure.md) (Proposed)
- **회사별 재배치 결정**: [docs/adr/ADR-005-multi-vendor-restructure.md](docs/adr/ADR-005-multi-vendor-restructure.md) (Accepted 2026-08-28) — SMC 스택은 `smc_lecp6/`, 공용은 `gripper_common/`(단계②), HITBOT `hitbot_zefg/`·SCHUNK `schunk_egu/` 는 후속 단계
- **조사 정본**: [../../../../docs/analysis/gripper_tx_wiring_and_drive_2026-08-12.md](../../../../docs/analysis/gripper_tx_wiring_and_drive_2026-08-12.md) — 배선 8페이지 실물 열람 + legacy `tc_gripper` 전수 + 실기 로그 실측 (2026-08-12)
- **참조 아키텍처**: [../../../docs/architecture/2026-07-24-hal-reference-and-roadmap.md](../../../docs/architecture/2026-07-24-hal-reference-and-roadmap.md) §1.1-1.2(계층·경계), §4(그리퍼 = 단일 계약 + 백엔드 2종)

## 구조

| 경로 | 역할 | 빌드 | 상태 |
|---|---|---|---|
| `smc_lecp6/hal/` | 포트 계약 3종 + 백엔드. **신호 이름·극성 규약의 소유자**(물리 비트 인덱스는 config 소유) | plain CMake | ✅ **M0 — 계약 헤더 4종 + 의미 검증 통과**(승격은 외부 리뷰 후) |
| `smc_lecp6/hal/include/gripper_hal/` | `types.hpp` · `command_port.hpp` · `feedback_port.hpp` · `magazine_port.hpp` | — | ✅ 작성 |
| `smc_lecp6/hal/impl/` | **Tx(4호기) 백엔드** — ROS-free 심 `IStationIoClient` 위의 어댑터(스테이션 직접 접근 없음) | — | ✅ **M1 — 포트 3종 + 신호맵, 단위 12종 통과** |
| `smc_lecp6/motion/` | 순수 시퀀스 FSM — 알람리셋 → 서보ON → **원점복귀** → 스텝 → BUSY 감시 → 완료판정 + 인터록 (ROS-free) | plain CMake | ✅ **M2 — 전이표 + 시나리오 15종 통과** |
| `gripper_ros/` | 얇은 조립 — LifecycleNode + `GripperCommand.action` + config 로드 | ament | 액션 IDL·config 스키마만 작성(노드는 M4) |
| `gripper_ros/config/` | `gripper_stack.yaml` — 프로파일→스텝 표·신호 비트맵·코봇 브리지·타임아웃·인터록 | — | ✅ M0 스키마 |
| `smc_lecp6/sim/` | LECP6 병렬 I/O 플랜트 + 포트 어댑터 + SIL 하니스 | plain CMake | ✅ **M3 — S1~S7 통과** |
| `checks/` | `⟦CI⟧` 게이트 — ros-free · no-blocking · io-single-master · vendor-sealed · contract-freeze | — | `gripper-io-single-master.sh` ✅ (나머지는 해당 계층 착수 시) |
| `docs/` | [migration-plan(SSOT)](docs/2026-08-12-migration-plan.md) · [인벤토리](docs/code_review/gripper_hal/2026-08-12.md) · [함수표 집계](docs/functions-index.md) · 수정 이력 | — | ✅ 작성 |

의존 방향 (게이트로 강제 예정):

```
gripper_ros ──▶ smc_lecp6/motion ──▶ smc_lecp6/hal ──▶ [impl/remote_io 어댑터] ──▶ remote_io_ros 서비스 ──▶ 스테이션
smc_lecp6/sim ──▶ {smc_lecp6/motion, smc_lecp6/hal}          # ROS-free
```

**자체 Modbus 클라이언트 금지** — 원격 IO 스테이션의 유일 쓰기 마스터는 `remote_io_ros` 노드다(사용자 결정 2026-08-12, ADR-008 Q7). 그리퍼는 그 서비스의 클라이언트일 뿐이다
([ADR-001 개정](../../Sensors/PIO/docs/adr/ADR-001-moma-io-ownership.md)). `smc_lecp6/hal/impl/remote_io/` 밖에서
소켓·modbus 심볼이 보이면 `⟦CI:gripper-io-single-master⟧` 로 실패시킨다.

## 대상 하드웨어 (4호기 Tx — 1차 source: 도면 실물 열람 ✓)

| 구성 | 모델 | 근거 |
|---|---|---|
| 그리퍼 | **SMC LEHF40K2-40-R3C6173** (`169GR1`) | 3,4호기 도면 p.4 BOM 항목 19 · p.55 |
| 컨트롤러 | `169SD6` — **SMC LECP6 계열(스텝데이터 입력형) 확정** (CN5 26핀 배치가 매뉴얼과 완전 일치). **NPN/PNP 변형·부번 `C6173` 은 미확정 ⚠** — 실물 라벨 확인 필요 | p.55 + [SMC LECP6 OM (LEC-OM00608), page 26-28](../../../../references/smc/controllers/SMC_LECP6_OperationManual_E.pdf) |
| MGZ 감지 | **OMRON E2E-X9C212 2M ×2** (NC) — `169PX15`/`169PX16` | p.4 BOM 항목 38 · p.55 |
| 명령 채널 | Crevis **GT-226F** SLOT#11 DO `0x1050~0x105B` (12점) | p.72 |
| 피드백 채널 | Crevis **GT-12DF** SLOT#5 DI `0x0040~0x004C` (13점) | p.66 |
| MGZ 채널 | Crevis GT-12DF SLOT#2 DI `0x0018`·`0x0019` | p.63 |
| 비상정지 | 컨트롤러 `EMG` 단자 ← 안전릴레이 `OS2` **직결** — 소프트웨어 경유 아님 | p.55 |

Rx(1,2호기)는 **SCHUNK EGU 60-EI-M-B / Modbus RTU** 로 백엔드만 다르다 — 계약은 공유하고 `impl/rtu_schunk/` 를 예약한다(ADR-008 D2, Q4).

## 신호 ↔ 코드 인덱스 ↔ Modbus (이식 기준표)

신호 **이름**은 `smc_lecp6/hal/include/gripper_hal/types.hpp`, **비트 인덱스**는 `gripper_ros/config/gripper_stack.yaml` 이 소유한다(코드 하드코딩 금지). 상세·근거는 조사 정본 §2.5.

| 신호 | 도면 주소 | legacy 인덱스 | Modbus 홀딩 레지스터·비트 |
|---|---|---|---|
| `IN0~IN5` (스텝 6bit) | `0x1050~0x1055` | 80~85 | 2053 / bit 0~5 |
| `SETUP`·`HOLD`·`DRIVE`·`RESET`·`SVON` | `0x1056~0x105A` | 86~90 | 2053 / bit 6~10 |
| `LOCK_OFF` | `0x105B` | 91 | 2053 / bit 11 |
| `OUT0~OUT5` | `0x0040~0x0045` | 64~69 | 4 / bit 0~5 |
| `BUSY`·`AREA`·`SETON`·`INP`·`SVRE`·`ESTOP`·`ALARM` | `0x0046~0x004C` | 70~76 | 4 / bit 6~12 |
| MGZ 감지 #1·#2 | `0x0018`·`0x0019` | 24·25 | 1 / bit 8·9 |

**주의 — legacy 주석의 코봇 매핑은 틀렸다**: `io_board_data.h:73` 은 `0x003D` 를 `COBOT : DO 03` 이라 적었으나
도면 p.53 배선은 **코봇 `DO4`**(p.65 표기 `COBOT INPUT4`)다. 출력측도 `0x103D` ↔ 코봇 `DI1`.
**legacy 는 정상 동작하므로 틀린 것은 주석이며**(사용자 판단 2026-08-12), 정정은 이 스택의 `gripper_stack.yaml` `cobot_bridge` 주석에 도면 단자명으로 반영했다 — legacy 소스는 무수정 보존.

## 명령 모델 — 프로파일 선택 (압력·속도를 어떻게 다루는가)

배선된 명령 채널은 **스텝 6bit + SETUP/HOLD/DRIVE/RESET/SVON** 이 전부이고 **아날로그·시리얼은 0** 이다(도면 p.55 단자 전수 ✓).
따라서 런타임 자유도는 **스텝 번호(1~63)** 하나다.

- 공개 API 는 **프로파일 이름**을 받는다 — `grip` / `release` / `home` (+ 확장 슬롯).
- 프로파일→스텝 매핑은 `gripper_ros/config/gripper_stack.yaml`. legacy 파리티 기본값: `grip=1 · release=2 · home=3` ✓.
- **각 스텝의 속도·추력(압력) 값은 컨트롤러 스텝 데이터 테이블 소관**이며 우리 API 로 쓰지 않는다 — 배선상 전달 경로가 없다.

### 스텝 데이터의 실체 (1차 소스 확인 완료 2026-08-12)

[SMC LECP6 Operation Manual (LEC-OM00608), page 32](../../../../references/smc/controllers/SMC_LECP6_OperationManual_E.pdf) — 스텝 **64개 × 12항목**:

| 항목 | 의미 | 우리 관심 |
|---|---|---|
| `Move` | Absolute / Relative | — |
| **`Speed`** (mm/s) | 목표 위치까지 이동 속도 | **"속도 조정" = 이 값** |
| `Position` (mm) | 목표 위치 | 그립/릴리즈 폭 |
| `Accel`·`Decel` (mm/s²) | 가감속 | — |
| **`PushingF`** (%) | **0 = 위치결정 동작 / 1~100 = 밀어붙임(최대 추력 대비 %)** | **"압력 조정" = 이 값** |
| `TriggerLV` (%) | INP ON 판정 추력 임계 | 파지 성공 판정 |
| `PushingSp` (mm/s) | 밀어붙임 구간 속도 | 파지 속도 |
| `MovingF` (%) | 이동 중 추력 | — |
| `Area1`·`Area2` (mm) | `AREA` 출력 구간 | 미사용(legacy) |
| `In pos` (mm) | INP 판정 폭 | — |

**편집 경로** — [동 매뉴얼 page 9 §2.3 · page 17-18 §4.3](../../../../references/smc/controllers/SMC_LECP6_OperationManual_E.pdf): 컨트롤러 **CN4 시리얼 I/O 커넥터**에
①티칭박스 `LEC-T1-3EG□` 또는 ②컨트롤러 세팅킷 **`LEC-W2`**(세팅 소프트웨어 + 통신케이블 + 변환유닛 + USB 케이블)를 물려 쓴다.
**CN4 는 AMR 배선에 없다**(도면 p.55 단자 전수 ✓) → 스텝 편집은 **사람이 하는 정비 작업**이지 런타임 경로가 아니다.

**레거시에도 편집 경로는 없다** ✓ — 실기 홈 전체 grep 결과 스텝 테이블을 읽거나 쓰는 코드·툴·파일 0건.
즉 **현재 step 1/2/3 에 실제로 설정된 Speed·PushingF 값은 저장소·로봇 어디에도 기록이 없다**(⚠, ADR-008 Q2-b).

절차 규율: 신규 프로파일이 필요하면 **정비 절차로 컨트롤러에 스텝을 등록한 뒤** config 에 이름을 추가한다 — 순서를 뒤집지 않는다.

### 현재 방침 — 3스텝 고정, 확장 봉인 (2026-08-12 확정)

**티칭박스·세팅킷 모두 현장에 없다**(사용자 확인 2026-08-12). CN4 는 RS485 준거이나 통신 프로토콜·레지스터맵이 매뉴얼에 공개돼 있지 않아
자체 제작 리더는 근거가 없다(⚠, LECP6 OM 전수 검색 0건). 따라서:

- 이식은 **현행 3스텝(grip=1 / release=2 / home=3) 파리티**로 진행한다. 이미 실기에서 동작이 검증된 값이다 ✓.
- **프로파일 확장(step 4~63)은 봉인** — config 스키마에 슬롯만 열어 두고 값은 넣지 않는다.
- 압력·속도 조정이 실제로 필요해지면 **먼저** ①장비 제작사(T-ROBOTICS)/SMC 대리점에 커미셔닝 스텝 데이터 백업 요청, 또는 ②`LEC-W2`/`LEC-T1` 확보 중 하나를 해소한다.
- 이 제약은 **장비 보유 문제이지 설계 문제가 아니다** — M0~M4 진행을 막지 않는다.
- legacy 에 `hard_grip_step_num_ = 4` 가 선언만 되고 미사용으로 남아 있다 ✓ — 다중 프로파일 의도의 흔적.

## legacy 대비 의도적 이탈 (DL — Deviation Ledger)

파리티(P1)가 기본이며 아래 4건만 의도적으로 다르게 간다. 근거·legacy 위치는 ADR-008 §C3·D4.

| DL | 이탈 |
|---|---|
| DL-GR01 | BUSY 상승 확인을 **전 명령에서 필수화** (legacy 는 release/home 에서 주석 처리 후 고정 200ms sleep) |
| DL-GR02 | 인터록 **명령×모드 정책 표** + **MANUAL grip 인터록**(legacy 는 MANUAL 우회) + **HOME `forbid_any`**(legacy 는 의도만 있고 통과). 정비 우회는 `interlock.manual_override` 기본 꺼짐·MANUAL 키 필수·감사 로그 |
| DL-GR03 | 실패를 **항상 결과 코드로 종결** (legacy 는 알람 발행 다수 주석) |
| DL-GR04 | 진행 중 상태를 **명령별로 분리** (legacy 는 HOME 도 `GRIPPING`) |

## HIL 진입 규율 (낙하·협착 위험)

실기는 리모트 `~/LGIT_C6_MoMa` 고정(루트 CLAUDE.md). SIL 회귀 통과 없이 H1 이후 진입 금지.

| 단계 | 내용 | 쓰기 |
|---|---|---|
| H0 | 신호 관측 — DI 13점 + MGZ 2점 스냅샷·극성 실측 | 없음(읽기 전용) |
| H1 | 서보/알람 경로 — `SVON`·`RESET` 만 | 최소 |
| H2 | 무부하 동작 — 매거진 없는 상태 home/release/grip | 있음 |
| H3 | 적재 동작 — 매거진 장착 | 있음 |

## 여기 없는 것

| 자산 | 위치 | 이유 |
|---|---|---|
| Crevis 스테이션 소유·Modbus TCP 물리 접근 | [`../../IOs/Remote_IO_Station`](../../IOs/Remote_IO_Station) | 스테이션 단일 쓰기 마스터 |
| 매거진 접근·정렬, 파지 재시도, 코봇 팔 시퀀스 조합 | [`../../Skills/Robot_Gripping`](../../Skills/Robot_Gripping) | 장치가 아니라 **응용** |
| Baumer OM30 거리센서(Rx 전용, 그리퍼와 버스 공유) | `Sensors/` 독립 HAL (사용자 결정 2026-08-02) | 센서 장치 |
