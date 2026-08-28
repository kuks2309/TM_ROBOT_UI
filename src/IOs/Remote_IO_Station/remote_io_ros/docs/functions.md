# remote_io_ros 함수표 (모듈 로컬 원본 — coding SOP §6 이중 기록)

M4 산출물. legacy `tc_io` 공개 계약(`io_resp`/`io_service`/`io_alarms`)을 유지하는 **얇은 조립층**.
Modbus 접근·RMW·read-back·watchdog 은 전부 `remote_io_hal` 소유이고 본 패키지는 갖지 않는다.

## 공개 표면 — ROS 계약 (legacy 파리티, 근거 M0 인벤토리 §3)

| 이름 | 타입 | 방향 | QoS | 주기 |
|------|------|------|-----|------|
| `io_resp` | `tc_msgs/msg/Io` | pub | depth 10 | **20ms**, **읽기 성공 시에만** |
| `io_alarms` | `tc_msgs/msg/AmrAlarm` | pub | depth 10 | 에러 지속 중 매 틱 반복 · 재연결 시 해제(0) 1회 |
| `io_service` | `tc_msgs/srv/Io` | srv | — | 요청 시 |

`io_di` 80비트(DI 5워드) · `io_do` 96비트(DO 6워드), 인덱스 = 워드×16 + 비트(LSB-first).

## 함수표

| # | 심볼 | 입력 | 출력 | 기능 | 위치 | 상태 |
|---|------|------|------|------|------|------|
| 1 | `AlarmCode` | — | — | legacy 알람 코드 4종(0·1101·1102·1103). **1110(IO_CAN_FAIL)은 만들지 않는다** — legacy 도 정의만 있고 미사용(사도 상수 이식 금지) | io_contract.hpp | M4 ✅ |
| 2 | `expandBits(words, bit_count)` | 워드 벡터·비트 수 | vector<int32_t> | 워드→비트 배열 전개(LSB-first). 워드가 모자라면 나머지 0 — 쓰레기 값 금지 | io_contract.cpp | M4 ✅ |
| 3 | `buildInitialImage(on_bits, do_word_count)` | ON 인덱스 목록·워드 수 | vector<uint16_t> | 기동 초기 출력 이미지. **ON 목록은 config 소유**(legacy 는 8비트를 코드에 박아 뒀다). 범위 밖이 하나라도 있으면 **빈 벡터** — 조용한 무시 금지 | io_contract.cpp | M4 ✅ |
| 4 | `checkWriteRequest(indices, states, do_word_count)` | 서비스 요청 | {ok, reason} | 길이 불일치·범위 밖·비 0/1 거부. legacy 는 길이 불일치를 검사하지 않았다 | io_contract.cpp | M4 ✅ |
| 5 | `decideAlarm(current, reconnected)` | 현재 코드·재연결 여부 | {publish, code} | 에러 지속 중 매 틱 반복 발행, 재연결 시 해제(0) 1회 — legacy 관측 동작 재현 | io_contract.cpp | M4 ✅ |
| 6 | `RemoteIoNode::tick` | — | void | 20ms 주기. 읽기 실패 시 **발행하지 않고** 알람만 낸다 | remote_io_node.cpp | M4 ✅ |
| 7 | `RemoteIoNode::applyInitialImage` | — | void | 링크 (재)확립 시 1회 적용. 범위 밖 설정이면 적용하지 않고 ERROR 로 알린다. **`apply_initial_image` 가 true 일 때만 호출**(기본 false) | remote_io_node.cpp | M4 ✅ |
| 8 | `RemoteIoNode::handleWrite` | srv Req/Res | void | 검증 → `writeBits` 최대 3회(간격 100ms) → echo. 요청 결함은 알람 대상 아님(호출자 오류) | remote_io_node.cpp | M4 ✅ |
| 9 | `RemoteIoNode::publishAlarmIfNeeded` | 재연결 여부 | void | `decideAlarm` 결과대로 발행. `AmrAlarm.state` 는 legacy 처럼 세트하지 않는다 | remote_io_node.cpp | M4 ✅ |

## 전역 변수

없음. 주소·워드수·주기·재시도·초기 ON 목록 **전부 파라미터**(기본값은 `io.info` 실측값).

**`apply_initial_image`(bool, 기본 `false`)** — 링크 확립만으로 출력을 바꾸지 않는다. DO 는 실제 장치를 구동하므로 기본은 **읽기 전용 기동**이고, 운용 전환(cutover S4)에서만 true 로 올린다. false 일 때 출력은 장치 잔존값 그대로이며 그 사실을 기동 로그에 남긴다.

**`watchdog.timeout_ms`(int, 기본 `0` = 비활성) · `watchdog.master_fault_action`(bool, 기본 false)** —
마스터 두절 시 커플러가 출력을 안전 상태로 떨어뜨리는 장치 보호. 링크 확립 후 **1회 구성**하고
성공분은 포트가 재연결 시 자동 재무장한다. **값 자체는 현장 안전 정책이라 사용자 소유** — 코드는
기본값을 고르지 않는다. 비활성일 때는 그 사실을 **경고 로그로 드러낸다**(보이지 않는 미보호 금지).

## DL — legacy 대비 개선 이탈 (파리티 아님, 의도적)

| # | legacy 동작 | 본 구현 | 사유 |
|---|---|---|---|
| DL-1 | `getIoOut` lock 과 `writeToOutRegs` lock 이 분리돼 read→write 사이 비원자 구간 존재(인벤토리 §4) | 포트가 **로컬 미러 기반 RMW**, 스테이션 단일 writer | 이중 마스터·경합 원천 제거(ADR-001 개정 Decision 1) |
| DL-2 | 전용 스레드가 `while(true)` 4초 주기 재연결(cpp:211-243) | 유계 백오프(MbapClient) + 노드 수명 소유, 무한 스레드 없음 | legacy §6-1 결함 차단 |
| DL-3 | 읽기 실패해도 직전 값을 계속 발행 | **발행하지 않는다** | stale 을 신선한 값으로 위장 금지(§6-5) |
| DL-4 | 서비스 요청 길이 불일치 미검사 | 거부 | 인덱스 초과 접근 위험 제거 |
| DL-5 | 초기 ON 8비트를 코드에 하드코딩(cpp:170-178) | 파라미터 `initial_on_bits` | 호기별 차이를 코드 수정 없이 수용 |
| DL-6 | `IO_WRITING_FAIL`(1102)에 해제 경로가 없어 재연결 전까지 20ms 마다 영구 반복 | **쓰기 성공 시 해제** | 알람이 사실을 반영하지 않으면 상위가 무시하게 된다. 래칭 필요 시 상위가 소유 |
| DL-7 | 미연결에도 서비스가 즉시 `received=false` (재시도 없음) | 동일 — **미연결이면 재시도하지 않는다** | legacy 파리티 복원. 직전 구현은 미연결에도 3회 재시도해 틱을 200ms 막았다 |
| DL-8 | 단일 인스턴스 강제 없음 | **추상 유닉스 소켓 락** — 중복 기동은 스스로 종료 | 쓰기 마스터 0/1 을 프로세스 수준에서 강제(ADR-003). 토픽 수신 판정은 소유권의 대리 지표라 오판한다 |

## 게이트

- 실기 검증(2026-08-11 07:4x): 워치독 비활성 **경고 출력 확인** · 초기값 **1회 적용** ·
  단일 인스턴스 락 **중복 기동 rc=1 거부** · `io_service` `received=True` · DO `…4400` 불변 ·
  `io_resp` **50.1Hz 발행자 1개**
- ⚠ **락의 한계(실측)**: 락 도입 **이전에 뜬 인스턴스**는 락을 잡지 않으므로 막히지 않는다.
  재빌드 후에는 `exe` 가 `(deleted)` 로 바뀐 옛 프로세스를 **명시 회수**해야 한다
  (실측: 3.8시간 된 옛 인스턴스가 살아 있어 발행율이 100Hz 로 관측됐다).
- 계약 파리티 단위: `remote_io_ros_io_contract_test` **15/15** ✅ (전개 4 · 초기값 3 · 요청검증 4 · 알람 4)
- 빌드 경고 **0** (`-Wall -Wextra -Wpedantic` + `-Werror=` 3종)
- **M4 게이트 미통과** — 실 스테이션 HIL(쓰기 포함)이 남았다. 계획 §5-1 상 쓰기 HIL 은
  **사용자 승인 후**이며, 현재 스테이션에는 legacy `tc_io` 가 운영 마스터로 붙어 있을 수 있어
  **동시 쓰기 마스터 2개를 만들지 않도록 전환 절차가 선행**돼야 한다.
- 외부 리뷰: **미실시** — verdict 는 저자가 찍지 않는다(never-self-approve).
