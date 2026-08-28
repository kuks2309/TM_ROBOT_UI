# ADR-000: MBAP 클라이언트의 pio_hal → Comm/modbus_tcp 승격

- **Status**: Accepted (사용자 승인 — 2026-07-30 "Comm/modbus/ 승격+debt-014 연동 정산 ←승인" + 2026-07-31 "진행" + 폴더명 `modbus_tcp` 선택)
- **Date**: 2026-07-31
- **관련**: [debt-022](../../../../../../../docs/debt/registry.md) · [ADR-001 개정(IOs HAL 단일 마스터)](../../../../../Sensors/PIO/docs/adr/ADR-001-moma-io-ownership.md) · debt-014 ①

## Context

- 참조 아키텍처 §1.4 는 물리·프로토콜 계층을 `Comm/` 소관으로 규정하나, MBAP(Modbus Application Protocol, Modbus TCP 프레이밍) 클라이언트가 `pio_hal/src/modbus/` 내부에 위치했다.
- ADR-001 개정(2026-07-30)으로 신설되는 `IOs/Remote_IO_Station/rio_hal` 이 동일 스테이션(Crevis GL-9089)용 Modbus TCP 클라이언트를 필요로 하므로 방치 시 중복 구현이 확정적이었다.
- 형제 패키지 `Comm/modbus_rtu`(namespace `comm::modbus_rtu`, drawer ADR-DR004 동결)가 이미 존재 — 명명 대칭.

## Decision

1. **파일 이관**: `mbap_client.{hpp,cpp}` + 테스트(`mbap_client_test.cpp`·`mock_gl9089_server.hpp`)를 `Comm/modbus_tcp/` 로 이동. namespace `pio::hal::modbus` → **`comm::modbus_tcp`**, 테스트 픽스처는 `comm::modbus_tcp::test`.
2. **타입 자립**: `tcp_types.hpp` 신설(`TcpError`·`Result<T>`·`Duration`·`TimePoint`) — common 계층이 pio_hal 에 역의존하지 않도록 `pio_hal/types.hpp` 의존 제거. `TcpError` 는 MbapClient 가 실제 방출하는 6종 + kNone 만 정의(1:1 매핑 가능 부분집합).
3. **pio_hal 경계 어댑터**: `ModbusSignalPort` 가 `TcpError → PortError` 1:1 매핑을 소유. `pio_hal/modbus/mbap_client.hpp` 는 삭제하고, `modbus_signal_port.hpp` 에 하위호환 별칭(`pio::hal::modbus::MbapClient/MbapClientConfig = comm::modbus_tcp::…`)을 두어 SIL 등 기존 소비자의 표기 파급을 최소화한다.
4. **debt-014 ① 동시 정산**: `link_up_` 을 `std::atomic<bool>` 로(교차 스레드 `isLinkUp()` 관측 허용), 헤더에 "#5(e)(f)(g)(전용 통신 스레드·stop-token+join)는 조립층 책임" 계약 명시, **TSan 게이트** `checks/modbus-tcp-tsan.sh`(⟦CI:modbus-tcp-tsan⟧) 신설 — 관측 스레드+소유 스레드 동시 구동 테스트를 ThreadSanitizer 로 검증.
5. **빌드 통합**: `modbus_tcp` 는 독립 plain CMake 프로젝트(install export `modbus_tcp::impl`). `pio_hal` 은 `PIO_HAL_WITH_MODBUS=ON` 일 때 `find_package(modbus_tcp CONFIG)` 우선, 미설치 시 소스트리 `add_subdirectory` 폴백. `pio_hal` 을 find_package 로 소비하는 하위(SIL 등)는 `find_package(modbus_tcp)` 를 **pio_hal 보다 먼저** 호출해야 한다.

## Consequences

- rio_hal(M1)은 `modbus_tcp::impl` 을 직접 소비 — MBAP 재구현 금지(debt-022 상환 목적).
- FC3/FC6 한정 범위·락스텝 단일요청·SIGPIPE 국소 처리 등 기존 검증 계약은 **비트 동일 이관**(파리티) — 기능 변경은 atomic link_up_ 뿐.
- ADR-004(옵션 타깃)는 유지 — `PIO_HAL_WITH_MODBUS=OFF` 기본 빌드는 modbus_tcp 를 요구하지 않는다(역이식 무영향).
- pio_hal 함수표에서 MbapClient 3행은 modbus_tcp `docs/functions.md` 로 이동(이중기록 갱신).

## Rollback Plan

이관 커밋 revert 로 파일 원위치 + 소비자 `find_package(modbus_tcp)` 1줄 제거. 동작 변경이 atomic link_up_ 뿐이므로 revert 시 기능 회귀 없음(파리티 테스트가 보증).
