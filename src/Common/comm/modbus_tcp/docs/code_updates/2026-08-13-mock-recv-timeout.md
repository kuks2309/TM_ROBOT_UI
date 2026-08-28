# 2026-08-13 — mock 서버 recv 타임아웃 (debt-023 상환)

## 무엇을

| 파일 | 변경 |
|---|---|
| `test/mock_gl9089_server.hpp` | `setRecvTimeout(std::chrono::milliseconds)` 신설(기본 2000ms) · `serveOnce` 가 accept 한 client fd 에 `SO_RCVTIMEO` 적용 · `<chrono>` include 와 `recv_timeout_` 멤버 추가 |
| `test/mock_gl9089_server_test.cpp` | 신설 — 요청 수 불일치 회귀 1종 + 정상 교환 유지 1종 |
| `CMakeLists.txt` | 테스트 목록에 `mock_gl9089_server_test` 등록 |
| `docs/code_review/mock_gl9089_server/2026-08-13.md` | 신설 — 픽스처 함수표(심볼 10 + 회귀 3), 전역변수 없음, 소비처, 결함·처방 |

## 왜

debt-023: `recvRequest` 의 `::recv` 에 상한이 없어, 핸들러가 기대한 요청 수(`serveBank(fd, n, …)`)보다
클라이언트가 적게 보내면 블로킹 recv 가 영구 대기하고 `join()` 이 hang 된다 — CI 는 타임아웃으로 죽고
clean-fail 이 아니다. 부채 상환계획이 **`remote_io_sim`(M2) 착수 시 mock 재사용 전 정비**를 요구했고,
M2 착수 지시(2026-08-13)에 따라 선행 조건으로 처리했다.

`serveBank` 는 이미 `req.size() < 12` 에서 return 하므로, recv 가 풀리기만 하면 클린 종료된다.
따라서 처방은 수락 fd 의 수신 상한 하나로 충분하다.

## 검증

- **red**: 타임아웃을 60초로 되돌린 사본으로 회귀 케이스 실행 → **5초 상한 내 미종료(rc=124)** — hang 재현
- **green**: 원본 200ms 로 **0.21초 통과**
- 전체 `ctest` **4/4 통과** (`mbap_client_test` · `mbap_client_fault_test` · `mbap_link_state_tsan_test` · `mock_gl9089_server_test`)

## 잔여

1. **PIO 사본 미적용** — `Sensors/PIO/pio_hal/test/mock_gl9089_server.hpp` 는 네임스페이스만 다른 복제본이며 같은 결함이 남아 있다. `pio_hal` 테스트·PIO SIL 이 그 사본을 쓴다. 사본 통합 여부는 별도 판단.
2. **`remote_io_hal` 측 검증 보류** — `remote_io_hal/CMakeLists.txt:62` 의 `MODBUS_TCP_TEST_INC` 가 소문자 `common/...` 를 가리키는데 작업 트리 실제 경로는 `Common/...` 이라 해석되지 않는다(대소문자 개명 진행 중 상태). 개명 소유자 확인 후 경로 정정 필요.
