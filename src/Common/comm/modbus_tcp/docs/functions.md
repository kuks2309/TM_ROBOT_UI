# modbus_tcp 함수표 (모듈 로컬 원본 — coding SOP §6 이중 기록)

갱신: 2026-07-31 (ADR-000: pio_hal 에서 승격 이관 — 로직 비트 동일, namespace·타입 자립·atomic link_up_ 만 변경).
소비자: pio_hal `ModbusSignalPort`(TcpError→PortError 매핑 소유) · rio_hal(예정, ADR-001 개정).

## 공개 표면 (계약 — 변경 시 ADR)

| # | 심볼 | 입력 | 출력 | 기능 | 위치 | 상태 |
|---|------|------|------|------|------|------|
| 1 | `Result<T>::ok/err/has_value/value/error` | T 또는 TcpError | Result | 접근자 가드형 결과 타입([[nodiscard]]) — pio_hal 규약 승계 | tcp_types.hpp | ✅ |
| 2 | `MbapClient::connect/close` | — | Result<void> / void | Modbus TCP(MBAP) 연결 수명주기 — RAII fd(#5b), non-blocking connect+poll로 유계, 지수 백오프 | src/mbap_client.cpp | ✅ (이관) |
| 3 | `MbapClient::isLinkUp` | — | bool | 링크 상태 관측 — **유일한 교차 스레드 API**(std::atomic, debt-014 ① — ⟦CI:modbus-tcp-tsan⟧) | mbap_client.hpp | ✅ (신규 계약) |
| 4 | `MbapClient::readHoldingRegisters` | start_addr, quantity | Result<vector<uint16_t>> | FC3 — quantity>125 사전거부(#6c), TID/PID/UID 대조·재동기(#6b), ByteCount 교차검증(#6d) | src/mbap_client.cpp | ✅ (이관) |
| 5 | `MbapClient::writeSingleRegister` | addr, value | Result<void> | FC6 — 요청 에코 검증(GL-9089 후행 4B 여분 허용, HIL 2026-07-24). 예외응답(FC\|0x80)→TcpError 매핑, FC 지역변수 재사용(#4a) | src/mbap_client.cpp | ✅ (이관) |

## 전역 변수

없음 — 전 상태는 클래스 멤버. 네임스페이스 상수: `kMaxReadQuantity(125)` · `kDefaultModbusPort(502)`
(매뉴얼 인용 주석 동반 — mbap_client.hpp 참조).

## 구현 노트

- 구현 범위: FC3·FC6 만(수정안 #4(d)). 장치 레지스터 의미(GL-9089 워치독 0x1020 등)는 본 계층 금지 —
  소비자 HAL impl 소유(modbus_rtu 와 동일 규율).
- 동시성 계약: 변이 호출은 단일 소유 스레드 전용, `isLinkUp()` 만 교차 스레드 관측 허용.
  전용 통신 스레드·stop-token·join(#5(e)(f)(g))은 조립층(pio_ros M4·rio_ros) 책임 — 헤더 계약 명시.
- 게이트: `checks/modbus-tcp-ros-free.sh` ⟦CI:modbus-tcp-ros-free⟧(rclcpp·tc_msgs·pio_hal include 차단) ·
  `checks/modbus-tcp-tsan.sh` ⟦CI:modbus-tcp-tsan⟧ — TSan data race 0 (red→green 시연:
  비원자 bool 로 되돌리면 race 검출 FAIL 확인, 2026-07-31). 스크립트는 Linux 6.8 ASLR 비호환 회피로
  `setarch -R` 사용(실측: kernel 6.8.0-124).
- 테스트: `mbap_client_test`(전송 happy/주요결함, 이관) · `mbap_client_fault_test`(예외코드 전수·백오프·
  에코 불일치 — pio_hal faultpath 에서 계층 분리 이관) · `mbap_link_state_tsan_test`(동시성 계약).
  mock 픽스처 `test/mock_gl9089_server.hpp` 는 pio_hal 포트 테스트·PIO SIL 이 include 경로로 재사용.
