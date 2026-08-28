# 2026-08-12 — 주석 정책 적용 + HOME 인터록 신설

## 무엇을

**1) 주석 축소 (코드 4파일 + 테스트 + config)**

| 파일 | 걷어낸 것 | 남긴 것 |
|---|---|---|
| `gripper_hal/include/gripper_hal/types.hpp` | 규율 (a)~(f) 블록, 1차 소스 인용 6줄, legacy `file:line` 인용, 리뷰 반영 설명 | 파일 목적 1줄 + 심볼별 기능·단위·극성 1줄 |
| `command_port.hpp` | 규율 4줄 + 원자성 계약 서술 6줄 | 구현체 의무 2줄 + 메서드별 1줄 |
| `feedback_port.hpp` · `magazine_port.hpp` | 규율·근거 서술 | 인터페이스 1줄 + 메서드 1줄 |
| `test/contract_check.cpp` | 검증 의도 서사 | 검증 항목 1줄씩 |
| `gripper_ros/config/gripper_stack.yaml` | legacy 경위·결정 이력 주석 | 정책 값·단위·구분 설명 |

시그니처 변경 0건. 줄 번호가 밀려 함수표 앵커 55개를 재동기화했다(드리프트 0 확인).

**2) HOME 인터록 신설**

`interlock.auto_mode.home` · `interlock.manual_mode.home` = `forbid_any`.
`manual_override.applies_to` 에 `home` 추가(기본 꺼짐 · MANUAL 키 필수 · 감사 로그).

## 왜

**주석**: 사용자 지시 — "불필요한 주석은 제거, 주석은 반드시 함수의 기능만, 이력은 별도 파일에". 근거·경위는
`docs/functions.md`(1차 소스 절) · `docs/2026-08-12-migration-plan.md` · ADR-008 · 본 `code_updates/` 가 담는다.
코드는 "무엇을 하는가"만 말한다.

**HOME 인터록**: 매거진을 문 채 홈 자세로 가면 낙하 위험이 있다. legacy 는 이 의도를 로그로만 남기고
(`"Magazine sensor is detected -> Reject Gripper Home"`) 알람 발행을 주석 처리한 뒤 실제로는 통과시켰다
(`gripper_node.cpp:1074-1087`). 사용자 결정(2026-08-12 "1 home interlock 필요")으로 규칙화했다.
정비 복구(문 채 빼내기)는 `manual_override` 로만 열린다.

## 검증

- `contract_check` ALL PASS (일반 · `-DNDEBUG -O2`)
- 헤더 4종 `-fsyntax-only -Wall -Wextra` 통과 · `clang-format --dry-run -Werror` 통과
- `gripper_stack.yaml` 파싱 OK — `auto.home=forbid_any` · `manual.home=forbid_any` · `override.applies_to=[grip, home]`
- 함수표 앵커 55개 전수 대조 — 드리프트 0
