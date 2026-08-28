# 2026-08-13 — M1 원격 IO 백엔드 구현 (`gripper_hal/impl`)

M0 계약 헤더 3종의 첫 구현. 스테이션 접근은 `remote_io_ros` 노드 경유이며, 그리퍼는 그 서비스의 클라이언트다.

## 설계 변경 — 주입 대상이 `IRemoteIoStationPort` 가 아니다

M0 함수표의 M1 예정 행은 "`IRemoteIoStationPort` 주입(공유)" 이었다. 그대로 하면 두 문제가 생긴다.

1. 스테이션 포트를 그리퍼가 직접 잡으면 쓰기 마스터가 둘이 된다 — ADR-008 Q7 이 닫은 결정과 충돌.
2. 서비스 클라이언트를 이 계층에 두면 rclcpp 가 들어와 ROS-free 규율이 깨진다.

그래서 **ROS-free 심 `IStationIoClient`**(write_bits / image / link_up)를 두고, 포트 3종은 그 위에서만 동작한다.
rclcpp 결선(`io_service` 클라이언트 · `io_resp` 구독)은 M4 조립층이 이 인터페이스를 구현해 주입한다.
계약 헤더(`command_port.hpp`·`feedback_port.hpp`·`magazine_port.hpp`)는 **한 줄도 바뀌지 않았다**.

## 오류 등급 결정

| 상황 | 등급 | 근거 |
|---|---|---|
| 스텝·라인 범위 밖 | `kOutOfRange` (송신 0회) | `command_port.hpp:17,20` |
| 링크 down | `kNotReady` | 송신 전 차단 |
| 응답 없음 | `kIndeterminate` | 적용 여부 불명 |
| `received=false` | `kIndeterminate` | `remote_io_node.cpp:252-300` 이 **요청 검증 거부와 쓰기 실패를 같은 값**으로 돌려줘 "적용 안 됨" 을 단정할 수 없다 |
| echo 불일치 | `kProtocol` | 응답이 요청 계약 위반 |

피드백·매거진의 stale 은 오류가 아니라 `fresh=false` 스냅샷이다(계약 문면 그대로). 이미지가 신호 인덱스를
담지 못하는 경우만 `kProtocol` 이다 — 설정과 실제 레이아웃이 어긋난 상태이므로 조용히 지나가면 안 된다.

## 산출물

| 자산 | 내용 |
|---|---|
| `impl/include/gripper_hal_impl/` | `station_io_client.hpp` · `signal_map.hpp` · `remote_io_{command,feedback,magazine}_port.hpp` |
| `impl/src/` | `signal_map.cpp` · `remote_io_{command,feedback,magazine}_port.cpp` |
| `gripper_hal/CMakeLists.txt` | 계약 커널 + impl 정적 라이브러리 + 테스트 2종(plain CMake, 외부 의존 0) |
| `test/remote_io_ports_test.cpp` | 단위 12종 |
| `checks/gripper-io-single-master.sh` | `⟦CI:gripper-io-single-master⟧` |

## 검증

- 빌드: `cmake -S gripper_hal -B build && cmake --build build` — **경고 0**
- 시험: `ctest` **2/2** (`gripper_hal_contract_check`, `gripper_hal_remote_io_ports_test`)
- 게이트 red 시연 2종 — `remote_io_station_port.hpp` include 주입 → rc=1 / ROS-free 계층에 `rclcpp` include 주입 → rc=1.
  둘 다 제거 후 rc=0 복귀 확인.

## 외부 리뷰 1라운드 (Codex, never-self-approve) — 2026-08-13

지적 8건 중 7건 반영, 1건은 근거를 달아 수용(설계 변경 없음). Gemini 는 일일 무료 쿼터 소진으로 실행 실패 — 리뷰어 1인.

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| 1 | **High** — 링크 down 이어도 age 가 한계 내면 `fresh=true` | 타당 | `fresh = link_up && age 한계 내`. 링크가 끊기면 이미지가 갱신될 수 없으므로 현재 상태를 대표하지 않는다(types.hpp:155). `remote_io_feedback_port.cpp:44-46` · `remote_io_magazine_port.cpp:42-44` |
| 2 | **High** — 신호맵이 IN0~IN5 의 동일 워드 여부를 검증하지 않음 | 타당 | `validate()` 에 원자성 요건 추가 — step 6비트 + DRIVE 가 같은 워드가 아니면 거부. `signal_map.cpp:75-89` |
| 3 | **High** — echo 검사가 `received` 보다 먼저라 미확정이 `kProtocol` 로 강등 | 타당 | 판정 순서 교체 — 미확정이 우선. `remote_io_command_port.cpp:103-112` |
| 4 | **Medium** — 클라이언트 비소유 참조의 수명 위험 | 타당(선례 일치) | `shared_ptr` 공유 소유로 전환 + 널 가드(`kNotReady`). drawer_hal 이 이미 `shared_ptr<IRtuClient>` 다 |
| 5 | **Medium** — 에뮬레이터/GTest 부재 시 SIL 이 조용히 빠짐 | 부분 타당 | 에뮬레이터 부재는 트리 결손이므로 `FATAL_ERROR` 로 승격. GTest 부재는 환경 제약이라 경고 유지. `remote_io_hal/CMakeLists.txt:96-98` |
| 6 | **Medium** — S2 의 `doWord` 단언이 공허(FIN 은 DO 를 지우지 않음) | 타당 | DO 워드 `writeCount` 증가로 재기록을 관측. `wire_watchdog_sil_test.cpp:60-70` |
| 7 | **Medium** — 게이트가 ctest 에 미등록 | 타당 | `add_test(gripper_io_single_master)` 등록 — ctest 3/3 |
| 8 | **Low** — 게이트 검사 확장자에 `.c`·`.cxx`·`.py` 누락 | 타당 | 확장자 9종으로 확대 |

**반영 검증(red 시연)**: 1·2·3 을 동시에 되돌리면 대응 단언 **7개**가 실패하고(링크 4 · 워드 2 · 판정순서 1), 복구 시 전량 통과.

## 외부 리뷰 2라운드 (code-reviewer, 실측 프로브 동반) — 2026-08-13

지적 20건(Blocking 5 · High 3 · Medium 6 · Low 6). **Blocking 5 + High 1 + Medium 3 + Low 2 반영**, 범위가 큰 3건은 부채 등록.
1라운드 반영이 **불완전**했던 항목을 잡아냈다 — `validate()` 를 만들어 두고 호출자가 시험뿐이었다.

| # | 지적 | 조치 |
|---|---|---|
| B-1 | **`validate()` 가 포트 생성 경로에서 강제되지 않아** 워드가 갈린 맵으로 `write_step` 이 «성공» 반환 | 세 포트가 생성 시 검증 → 실패면 **전 호출 송신 0회 `kNotReady`**(`map_valid()` 노출). red: 강제 제거 시 4단언 실패 |
| B-2 | 비트 인덱스 상한 검사 부재 — 인덱스 5000 이 그대로 송신 | `SignalMap` 에 `do_bit_count`·`di_bit_count`(레이아웃 주입, 0 은 거부) + `validate()` 상한 검사 |
| B-3 | S4 가 **발동 0회여도 통과**(공허 단언) | 억제 확인 전에 `ASSERT_GT(fireCount,0)`·재무장 1회를 선행 고정 + `(void)read()` → `ASSERT_TRUE`. red: 리뷰어 변이(advance 제거) 재현 시 `:110` 실패 |
| B-4 | GTest 부재 시 SIL 통째로 조용히 누락, 구성은 초록 | `REMOTE_IO_REQUIRE_SIL`(기본 ON) — 부재 시 구성 실패. 실측 rc=1 |
| B-5 | 게이트 우회 4종(대소문자·소켓 경로·화이트리스트 고정·스캔 0건) | `grep -riEn` · 소켓 패턴 확대(`netdb.h`·`sys/un.h`·`asio`·`::socket(`) · ROS 예외를 **`gripper_ros` 만 제외**로 반전 · 스캔 하한 미달 시 fail. **4종 전부 rc=1 확인** |
| H-1 | 결함 매트릭스가 등급 대조를 안 함, F3 주석과 실제(kTimeout) 불일치 | F1=`kOutOfRange`·F3=`kTimeout`·F4=`kNotConnected` 를 `EXPECT_EQ` 로 고정, F3 주석 정정 |
| M-1 | F2 대조가 전부 0 인 벡터끼리 | `setEquipmentInputs({0xA55A,…})` 로 비대칭 패턴 주입 후 대조 |
| M-3 | 매거진만 원시값을 `==` 로 비교(피드백은 `!=0`) | 0/1 정규화 후 극성 대조로 통일 |
| M-4 | 이미지 미수신인데 `health()` 가 «나이 0ms·정상» | 미수신 경로에서 `snapshot_age` 를 stale 한계 초과로 |
| M-6 · L-3 | `feedback_stale_limit` 출처 주석 오류 · 하니스 "가상시계 하나" 주석이 사실 아님 | 주석 정정(백오프·타임아웃은 실 clock) |

**부채 등록(범위가 커 유예)**: `debt-074` 쓰기 경로 결함주입 부재(부분 적용 미검증) · `debt-075` WDV-2 가 에뮬레이터 카운터 리셋 모형에 의존 · `debt-076` `WriteAck::received` 의 read-back 의미 미명문화.

**미반영 + 사유**: M-2·H-2·H-3 → 위 부채. M-5(동작 중 스텝 변경 방어)는 HAL 계약이 금하지 않고 FSM(M2) 소관이라 보류. L-1(맵 사본 드리프트)·L-2(TEST_INC 보호)·L-5·L-6 은 M4 로더 작성 시 함께 처리.

## 외부 리뷰 3라운드 (code-reviewer, 실기 안전 관점) — 2026-08-13

판정 REQUEST CHANGES — Blocking 1 · High 3 · Medium 3 · Low 6. **저비용 6건 반영, 안전 설계 3건은 부채 등록.**

| # | 지적 | 조치 |
|---|---|---|
| H-1 | **echo 레벨 검증이 시험으로 전혀 보호되지 않음** — 레벨 비교절을 삭제해도 전건 통과(리뷰어 뮤테이션 실증) | Fake 에 `echo_flip_level` 추가 + DRIVE=0 요청에 1 을 되돌리는 응답을 `kProtocol` 로 잡는 시나리오. red: 비교절 삭제 시 3단언 실패 |
| M-1 | **F2 가 결함 주입을 하지 않음(공허)** — 2차 반영 치환에서 `injectPartialFrameOnce()` 가 삭제됐다 | 주입 복구. red: 재조립 무력화 시 `:44` 실패. **내 회귀이므로 mistake 2026-08-13-005 기록** |
| M-2 | 게이트가 빌드 그래프 우회를 못 잡음(`CMakeLists.txt`·`package.xml` 무검사) | 빌드 파일 스캔 추가. red: CMake 의존·package.xml depend 주입 각각 rc=1 |
| M-3 | 명령 포트 `health()` 가 `snapshot_age` 미대입 — M-4 가 닫으려던 «0ms 정상» 오독이 잔존 | 시계 주입 + 세 포트 동일 규약 |
| L-1 | 맵 무효 사유에 따라 `kOutOfRange` 가 반환됨(설정 오류가 «범위 밖 인자» 로 위장) | `map_valid_` 확인을 인덱스 조회보다 앞으로 |
| L-3 · L-6 | 매거진에 널 클라이언트 시험 없음 · 게이트 하한이 env 로 무력화 | 시나리오 추가 · 하한 상수화(red: env=0 시도 rc=1) |

**부채 등록(안전 설계 — 사용자 결정 필요)**: `debt-077` 재연결·워치독 복구 시 DRIVE 자동 재기록(무인 물리 재구동) ·
`debt-078` DRIVE 선 채 스텝 변경 무방비(2차 M-5 를 앵커 없이 유예한 것도 함께 교정) · `debt-079` 미러 미시드 첫 쓰기가 워드 전체를 0 으로 덮음.

**`debt-077` 은 실기 상시 운전 전 필수 해결**이다. 단, watchdog 미구성 상태에서는 재적용 경로가 비활성이라
**단발 펄스 시험(짧은 DRIVE + 즉시 clear)** 은 관리 가능하다.

## 잔여

- 4차 리뷰는 debt-077~079 처리 후 — M4 착수 시 조립층 포함 재리뷰
- rclcpp 결선 구현체와 config → `SignalMap` 로더 — M4 `gripper_ros`
- M0 계약 동결 승격은 ADR-008 Q1·Q5 결정에 걸려 있다(본 구현은 헤더를 바꾸지 않으므로 승격 판단과 독립)
