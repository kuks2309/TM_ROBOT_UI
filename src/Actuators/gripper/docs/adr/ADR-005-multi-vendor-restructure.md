# ADR-005 — 회사별 그리퍼 스택 재배치 + 공용 Modbus RTU 통신 계층

- **Status**: Accepted — 2026-08-28 (사용자 승인 완료 / 구현 미착수)
- **결정자**: 사용자 (세션 6055e03f, 2026-08-28)
- **관련**: ADR-001(gripper-ros 조립) · 구(舊) ADR-008 "단일 계약 + 백엔드 2종" — 본 저장소에 파일 부재(이관 누락 ⚠, 아래 Context)

## Context

- **요구 1**: 그리퍼를 회사(제조사)별로 장착할 수 있도록 폴더 구조 재구성 (사용자, 2026-08-28).
- **요구 2**: HAL 통신 구조는 `src/Common/comm` 에 공용으로 배치 (사용자, 2026-08-28).
- **신규 장착 대상**: HITBOT(Huiling-tech Robotic Co., Ltd.) **Z-EFG-C35** 전동 그리퍼 — **신규 호기/장비**에 장착, 제어 채널은 **RS485 Modbus RTU** (사용자 확정 2026-08-28. I/O 모드는 채택하지 않음).
- **Z-EFG-C35 1차 source** ✓ — [references/hitbot/z-efg-c35/](../../../../../references/hitbot/z-efg-c35/) 로 정규화 보관(원본 루트 → 표준 경로 이동, 2026-08-28):
  - RTU 프로토콜: function code 0x03/0x06/0x10, 기본 115200 8N1, ID 1 ✓ [Z-EFG-C35 Product Manual V20240120, page 4](../../../../../references/hitbot/z-efg-c35/Z-EFG-C35%20Brochure_V20240120.pdf)
  - 레지스터 맵: 0x0000 초기화 · 0x0002 파지 위치(float, 0~35mm) · 0x0004 속도(float, 1~100mm/s) · 0x0006 전류(float, 0.1~0.5A) · 0x0040 초기화 상태(5=완료) · 0x0041 파지 상태(0 In place/1 Moving/2 Clamping/3 Dropping) · 0x0042/0x0044/0x0046 위치·속도·전류 피드백 · 0x0080~0x0090 파라미터(ID·baud·초기화 방향·저장 등) ✓ [동 매뉴얼, page 5](../../../../../references/hitbot/z-efg-c35/Z-EFG-C35%20Brochure_V20240120.pdf)
  - 기계 사양: 스트로크 35mm · 파지력 15~50N · DC24V ✓ [동 매뉴얼, page 2](../../../../../references/hitbot/z-efg-c35/Z-EFG-C35%20Brochure_V20240120.pdf)
- **결정 배경 — 현행 "공용 계약"은 사실상 SMC 전용이다** ✓: [command_port.hpp:18-24](../../smc_lecp6/hal/include/gripper_hal/command_port.hpp) 는 `write_step(IN0~IN5 6bit)`·`write_line(SETUP/HOLD/DRIVE/RESET/SVON)`·`clear_step_and_drive()` — SMC LECP6 병렬 IO 형상 그대로다. HITBOT 는 위치·속도·전류를 레지스터에 직접 쓰는 방식이라 이 포트 계약을 구현할 수 없다. 회사 간 진짜 공용은 **profile 공개 API(`grip`/`release`/`home`) + `GripperCommand.action` + config 스키마**이고, 포트 계약·시퀀스 FSM·sim 플랜트는 회사별 자산이다.
- 구 ADR-008 은 "그리퍼 = 단일 계약 + 백엔드 2종(impl/rtu_schunk 예약)"을 결정했으나(README 인용 기준 ⓦ — 원문 파일이 본 저장소에 이관되지 않아 직접 대조 불가 ⚠), 위 발견으로 **포트 계약 공유 전제가 성립하지 않는다.** 본 ADR 이 그 결정을 대체한다(supersede 표기는 원문 이관 후 수행).
- 기존 검증 자산: gripper_hal M0~M1(단위 12종) · gripper_motion M2(시나리오 15종) · gripper_sim M3(S1~S7) 통과 상태 ⓦ(README 기준). gripper_ros 노드(M4)는 미착수 — **지금이 재배치 비용 최소 시점**이다.

## Decision

**D1. 회사별 스택 재배치 (승인안 B)** — 회사 추가 = 폴더 1개:

```
src/Common/comm/
  modbus_tcp/                # 기존 무이동 (Crevis remote IO 용 MBAP 클라이언트)
  modbus_rtu/                # 신규 — RS485 Modbus RTU 마스터 (ROS-free, modbus_tcp 패키지 패턴 답습)

src/Actuators/gripper/
  gripper_common/            # 공용: Result/Health 등 공용 타입 · profile 정의 · magazine_port (로봇측 DI, 회사 무관)
  smc_lecp6/                 # 기존 자산 이관 — 코드 무수정, 경로만 이동 (Tx 4호기)
    hal/    ← gripper_hal/   (SMC 포트 계약 + impl/remote_io)
    motion/ ← gripper_motion/ (step 시퀀스 FSM)
    sim/    ← gripper_sim/   (LECP6 플랜트)
  hitbot_zefg/               # 신규 — Z-EFG-C35 스택 (신규 호기)
    hal/                     # RTU 레지스터 계약 + modbus_rtu 위 어댑터
    motion/                  # 초기화 확인 → profile 파라미터 기록 → 상태 폴링 시퀀서
    sim/                     # RTU 슬레이브 레지스터 맵 플랜트
  schunk_egu/                # 예약 — README 표기만, 빈 스텁 없음 (Rx 1·2호기, 기존 원칙 유지)
  gripper_ros/               # 공용 조립 — config `vendor:` 필드로 회사 스택 선택
  checks/  docs/  tools/
```

**D2. 공용 통신 계층** — `src/Common/comm/modbus_rtu/`: `IRtuClient` = `read_holding(0x03)` / `write_single(0x06)` / `write_multiple(0x10)` + CRC16 + 타임아웃·재시도. 시리얼 설정(device·baud·parity)은 config 소유. sim 에 레지스터 맵 주입식 RTU 슬레이브 mock 포함(각 회사 sim 이 재사용). 그리퍼 전용 심볼 금지 — 범용 RTU 마스터만.

**D3. 공용/회사별 경계** — 공용: `GripperCommand.action` · profile 공개 API · config 스키마 · 공용 타입 · MGZ 매거진 포트 · `gripper_ros` 조립. 회사별: 포트 계약 헤더 · 백엔드 어댑터 · 시퀀스 FSM · sim 플랜트. 상위 소비자(`Skills/Robot_Gripping`)는 회사 교체에도 무수정.

**D4. 단일 마스터 원칙 확장** — Crevis TCP: 유일 쓰기 마스터 = `remote_io_ros`(기존 유지). RS485 버스: **유일 마스터 = 해당 그리퍼 노드의 RTU 클라이언트 인스턴스**. `checks/gripper-io-single-master.sh` 의 modbus 심볼 허용 범위를 `src/Common/comm/*` + 각 회사 `hal/` 로 갱신한다.

**D5. profile→파라미터 매핑은 config 소유** — SMC: profile→step 번호(기존). HITBOT: profile→(위치mm·속도mm/s·전류A) 3튜플. 코드 하드코딩 금지(기존 원칙 승계). HITBOT 는 SMC 의 "스텝 편집 장비 부재" 봉인 제약이 없다 — 파지력·속도가 config 로 조정 가능해진다.

**D6. 이행 4단계** (각 단계 완료 후 다음 진입):

| 단계 | 내용 | 검증 |
|---|---|---|
| ① | `git mv` 순수 이동 + 빌드 경로 갱신만(include 경로·네임스페이스 무수정) | 기존 SIL 전 시나리오(12종·15종·S1~S7) 재실행 무손상 |
| ② | 공용 타입 분리 → `gripper_common` | 동일 SIL 재실행 |
| ③ | `modbus_rtu` 신규 | 단위(프레이밍·CRC·타임아웃) + mock 슬레이브 SIL |
| ④ | `hitbot_zefg` 스택 신규 | sim 기반 SIL(정상·낙하·타임아웃·미초기화 시나리오) — HIL 은 별도 승인 |

## Alternatives (기각)

- **A안 — 기존 4패키지 유지 + 신규 회사만 증분 추가**: 이동 비용 0 이나, `gripper_hal`·`gripper_motion` 이 SMC 전용임이 이름에 드러나지 않는 비대칭 구조가 영구화된다. 기각.
- **C안 — 계층 유지 + 계층 내부 회사 분리**(`gripper_hal/impl/<회사>/` 등): 한 회사 자산이 hal·motion·sim 3곳에 산개해 "회사별 장착" 요구와 어긋난다. 포트 계약 자체가 회사별이라 impl 분리만으로는 부족하다. 기각.

## Consequences

- **이득**: 회사 추가 = 폴더 1개(hal/motion/sim 동일 골격); 구조가 계약 실체와 일치; RTU 마스터 공용화로 SCHUNK(EGU, Modbus RTU) 착수 시 재사용; HITBOT 는 파지력·속도 config 조정 가능(SMC 봉인 제약 없음).
- **비용**: 경로 이동에 따른 CMake·README·문서 링크·checks 경로 갱신 + SIL 재검증 1회; README 구조표 전면 개정.
- **남는 위험·부채**:
  - 구 ADR-008 원문 부재로 supersede 절차 불완전 ⚠ — 원문 이관 시 본 ADR 과 대조 필요. README 의 ADR-008·조사 정본·SMC 매뉴얼 링크가 dangling(이관 누락) — `references/smc/` 재확보 필요.
  - RS485 물리 경로(USB-RS485 컨버터·포트 장치명) 미정 ⚠ — Open Question.
  - Z-EFG-C35 근거 문서가 브로슈어(Product Manual 요약본) 1종뿐 — 상세 User Manual 확보 전 레지스터 맵 외 동작 단정 금지(추정 금지 원칙).

## Rollback

- 단계 ①·②(이동·분리): 가역 — 해당 커밋 `git revert`(이동 역방향 `git mv` 포함) + SIL 재실행으로 원상 확인.
- 단계 ③·④(신규 패키지): 가역 — `gripper_ros` 조립 연결 전까지 소비자 0 이므로 디렉터리 삭제 커밋으로 원복. 조립 연결 후에는 config `vendor:` 를 `smc_lecp6` 로 되돌리면 런타임 원복.

## Open Questions

1. 신규 호기 명칭·번호 (config 네이밍에 필요)
2. RS485 물리 경로 — USB-RS485 컨버터 모델·장치명(`/dev/ttyUSB*`), 케이블 배선(브로슈어 page 4 배선 주의사항 4항 준수)
3. SCHUNK EGU 스택 착수 시점
