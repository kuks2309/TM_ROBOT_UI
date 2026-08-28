# 2026-08-13 — `Common/comm` → `Comm` 이관 (ADR-009)

## 무엇을

| 이동 전 | 이동 후 | 파일 |
|---|---|---|
| `src/Common/comm/can/{can_hal, canopen_stack, checks, docs}` | `src/Comm/CAN/` | 8 |
| `src/Common/comm/modbus_rtu` | `src/Comm/modbus_rtu` | 16 |
| `src/Common/comm/modbus_tcp` | `src/Comm/modbus_tcp` | 16 |

`src/Common/comm` 디렉터리 제거. `src/Common/tc_msgs` 는 유지.

참조 갱신 **37파일** — 코드 6곳(`remote_io_hal/CMakeLists.txt` 2행 · `can_hal/CMakeLists.txt` · `can_hal.hpp` · `can-no-ros.sh` · `test_steer_home_sync.py`) + 문서 31곳.
이관 트리 내부 상대 링크 2건은 깊이가 한 단계 얕아져 `../` 를 하나씩 줄였다(해석 실패 → 재해석 확인 방식으로 자동 정정, 미해결 0).

## 왜

사용자 지시(2026-08-13) — CAN 자산이 `Common/comm/can` 과 `Comm/CAN` 두 곳으로 갈라져 있었고, 통신 공용 패키지의 소유 폴더를 `Comm` 으로 단일화한다. 결정 근거·구조는 ADR-009.

## 검증

| 항목 | 결과 |
|---|---|
| `modbus_tcp` 단독 빌드·테스트 (새 위치) | ctest **4/4 통과** |
| `remote_io_hal` 빌드·테스트 | ctest **6/6 통과** — 이관 전에는 mock 경로 미해석으로 **빌드 불가**였다 |
| 게이트 스크립트 4종 | `can-hal-single-owner` · `can-no-ros` · `modbus-tcp-ros-free` · `modbus-tcp-tsan` 전부 PASS |
| 잔여 `common/comm` 참조 | **0건** (md·txt·cmake·hpp·cpp·py·sh 전수 grep) |

**부수 발견**: `can-hal-single-owner.sh` 는 이관 전 `SEARCH_ROOT` 가 `src/src`(미존재)로 계산돼 **0파일 스캔 후 PASS** 하는 헛통과 상태였다. 이관으로 `src` 를 올바로 가리키게 되어 이제 **196개 `.cpp` 를 실제로 스캔**한다.

## 잔여

- git 은 소문자 `src/common/...` 삭제 + `src/Comm/...` 추가로 본다 — 커밋 시 rename 인식 여부 확인 필요.
- `Sensors/PIO/pio_hal/test/mock_gl9089_server.hpp`(네임스페이스만 다른 사본)는 이번 이관 대상이 아니며 debt-023 의 recv 타임아웃도 미적용 상태다.
