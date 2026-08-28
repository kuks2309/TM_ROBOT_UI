# 2026-08-13 — GL-9089 에뮬레이터 공용 승격

## 무엇을

| 이전 | 이후 |
|---|---|
| `Sensors/PIO/pio_sim/sil/sil_gl9089_server.hpp` · `namespace pio::sim::sil` · `class SilGl9089Server` | `Comm/modbus_tcp/sim/gl9089_server.hpp` · `namespace comm::modbus_tcp::sim` · `class Gl9089Server` |

- 파일 **이동 1건**(`git mv`) — 사본 0. 기능 변경 없음.
- 프레임 헬퍼 의존을 PIO 사본(`pio::hal::modbus::test`)에서 **공용 `comm::modbus_tcp::test`** 로 전환(파일 상대 include).
- 사용처 정정: `pio_sim/sil/sil_orchestrator.hpp` + SIL 테스트 3종(`watchdog`·`golden_parity`·`comm_robustness`).
- 빌드 배선: `pio_sim/sil/CMakeLists.txt` 에 `COMM_MODBUS_TCP_SIM_INC` 추가.
- 파일 머리 주석을 "무엇을 제공하는가"로 재작성(이력 서술 제거).

## 왜

`remote_io_sim`(M2)이 같은 스테이션(GL-9089)의 에뮬레이터를 필요로 한다. 그대로 두면 선택지가 둘뿐이었다 —
사본을 뜨거나(debt-023 재현), `IOs → Sensors/PIO` 역방향 의존을 만들거나. 둘 다 debt-022 가 남긴 교훈에 어긋난다:
**둘 이상이 쓸 자산은 서브시스템 안에 두지 않고 공용 위치에 한 벌만**(사용자 확인 2026-08-13).

"나중에 승격"을 택하지 않은 이유도 같다 — debt-022 가 정확히 그 경로였고, 옮길 시점엔 이미 중복이 확정돼 있었다.

## 검증

| 항목 | 결과 |
|---|---|
| 패키지 빌드 (plain CMake, ROS-free) | `modbus_tcp` · `pio_hal` · `pio_e23` · `pio_sim` 전부 OK |
| PIO SIL 회귀 | `golden_parity` · `watchdog` · `comm_robustness` · `fault_matrix` · `load_determinism` **5/5 통과** |

`watchdog`·`fault_matrix` 통과가 핵심 — 승격 후에도 워치독 발동·결함 주입 경로가 동작한다는 뜻이고, M2 가 요구하는 기능이 그대로 살아 있음을 보인다.

## 잔여

- `pio_hal` 자체 테스트는 아직 PIO 사본 mock(`pio_hal/test/mock_gl9089_server.hpp`)을 쓴다 — debt-023 잔여, PIO 세션 소관.
  이번 승격으로 **SIL 경로는 이미 공용 mock 을 쓰므로** 그 세션의 작업 범위가 그만큼 줄었다.
