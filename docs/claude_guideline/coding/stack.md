# 언어·스택 구체 규칙 (Stack Conventions)

> **본 파일은 지시용.** coding.md §4 가 위임하는 **언어·프레임워크·도구별 구체 선택**. self-contained — 본문 외 의존 0.

언어 무관 원칙은 `conventions.md`, 본 파일은 "이 프로젝트는 어느 언어/도구로 무엇을 쓴다"는 **구체 선택**을 고정한다.

## 1. 코드 포맷터 — 선택은 여기, 강제는 도구

포맷은 글 규칙이 아니라 **포맷터 도구**로 강제한다. 프로젝트는 언어별 포맷터를 **선택**하고 설정 파일로 고정하며, 준수는 `checks/format.sh`(`⟦CI:format⟧`)가 기계 검사한다.

| 언어 | 포맷터 | 설정 파일 | 예시 선택 |
| --- | --- | --- | --- |
| C/C++ | `clang-format` | `.clang-format` | **Microsoft** / Google / LLVM |
| Python | `black` (+`isort`) | `pyproject.toml` | black 기본 |
| JavaScript/TypeScript | `prettier` | `.prettierrc` | prettier 기본 |
| 공통(들여쓰기·줄끝·인코딩) | EditorConfig | `.editorconfig` | LF·UTF-8·스페이스 |

- **선택은 프로젝트 1회 결정 후 고정**(드리프트 금지). 스타일 변경은 ADR(Architecture Decision Record, 설계 결정 기록) + 전체 재포맷 1커밋.
- **C 계열 기본 중괄호: Allman** — 프로젝트가 아직 스타일을 선택하지 않았다면 `if`/`for`/`while`/`switch`/함수 정의의 여는 중괄호 `{` 는 다음 줄 단독(Allman)을 기본으로 하고, 그 선택을 `.clang-format` 으로 고정한다 (`BasedOnStyle: Microsoft` 가 Allman 중괄호 포함, 최소 지정은 `BreakBeforeBraces: Allman`).
- **미선택 시 자동 고정 + 전량 검사** — C 계열 코드가 있는 프로젝트에 `.clang-format` 이 없으면 **즉시 기본 파일을 생성해 고정한다**(번들 `install.sh` 가 설치 시 자동 수행, 기존 파일은 절대 덮어쓰지 않음; 설치 후 작업 중 발견해도 동일하게 즉시 생성). 검사 범위는 신규 코드만이 아니라 **기존 C 계열 코드 전체**다 — `checks/format.sh` 가 전량 검사하며, 위반 잔존분의 일괄 재포맷 시점(1커밋)은 사용자가 결정한다.

  ```c
  for (...)
  {
      ...
  }

  if (...)
  {
      ...
  }
  ```

- 포맷터·설정이 없으면 `format.sh` 는 검사 생략(강제력 0) — 그 환경은 포맷 강제 없음을 정직히 인정.

예) C++ 프로젝트가 Microsoft 스타일을 쓰려면 루트에 `.clang-format` 한 줄:

```yaml
# .clang-format
BasedOnStyle: Microsoft
```

## 2. 언어·런타임 (프로젝트별 작성)

| 자리 | 언어·표준 | 빌드·패키지 도구 |
| --- | --- | --- |
| 주 구현 | (예: C++17) | (예: colcon / CMake) |
| 보조·스크립트 | (예: Python 3.10) | (예: uv / pip) |

**채우기 전까지 적용되는 것** — 빈 칸은 "자유" 가 아니라 **매번 다르게 고르는 자리**다. 그 발산은 조용히 쌓인다(설치본 8곳 실측 2026-11-01, 8/8 미작성). §1 이 포맷터 미선택을 기본값으로 메우듯 본 절도 메운다:

1. **도메인 규칙이 그 자리를 못박았으면 도메인이 우선한다** — `domains/` 의 규칙은 해당 도메인에서 본 절보다 구체적이다. 본 절을 채울 때도 도메인과 어긋나게 쓰지 않는다.
2. 도메인이 말하지 않으면 **저장소 실측을 따른다** — 이미 가장 많이 쓰인 언어·표준이 그 프로젝트의 사실상 선택이다. 새 언어·런타임을 들이는 것은 coding.md §3 사전승인(ADR) 대상이며, 그때 본 표를 함께 채운다.

```bash
# 실측 — 무엇이 이미 쓰이고 있나 (상위 5)
git ls-files | sed -n 's/.*\.\([A-Za-z0-9_]\+\)$/\1/p' | sort | uniq -c | sort -rn | head -5
```

## 3. 프레임워크·UI (프로젝트별 작성)

| 자리 | 선택 | 생성·갱신 규칙 |
| --- | --- | --- |
| UI 프레임워크 | (하나만 적는다) | (예: 디자이너 산출물은 손으로 고치지 않는다) |
| 그 외 프레임워크 | | |

- **UI 는 하나로 고정한다** — 둘 이상이 섞이면 위젯 관습·시그널 규약·배포 의존이 갈라져 재사용이 끊긴다. 새 UI 프레임워크를 들이는 것은 ADR 대상이다. 이미 섞여 있다면 통합 시점은 사용자가 정한다.
- 채우기 전까지는 §2 와 같다 — 도메인이 못박았으면 도메인, 아니면 실측(이미 쓰이는 UI).
- UI 스택의 생성·갱신 규칙이 한 줄을 넘기면 `domains/` 로 뺀다.

```bash
# 실측 — 무엇이 이미 import 되나 (상위에서 UI 툴킷을 고른다. 안 보이면 head 수를 늘린다)
git grep -hoE '^[ \t]*(import|from)[ \t]+[A-Za-z_][A-Za-z0-9_]*' -- '*.py' \
  | awk '{print $2}' | sort | uniq -c | sort -rn | head -30
```

> 두 명령은 git 저장소 안에서만 뜻이 있다 — 아니면 **조용히 비어 나온다.** 빈 결과를 "쓰는 것이 없다" 로 읽지 않는다. 특정 프레임워크 목록을 여기 박아 두지 않는 것은 의도다: 그 목록의 단일 근원은 해당 `domains/` 규칙이고, 여기 베껴 두면 한쪽만 바뀌어도 아무도 모른다.

## 4. 언어 결합 (Python ↔ C/C++) — 트리거 시

서로 다른 언어를 결합하면(예: Python 에서 C/C++ 호출) 경계에서 사고가 난다. 결합을 쓰면 본 절 활성, 안 쓰면 면제.

**결합 방법 선택** (1회 고정, 변경은 ADR):

| 방법 | 용도 |
| --- | --- |
| `ctypes` | 순수 C `.so`/`.dll` 런타임 호출, 빌드 단계 없음 |
| `cffi` | C 선언 기반 FFI(Foreign Function Interface, 외부 함수 인터페이스), ctypes 보다 안전 |
| **pybind11** | C++ ↔ Python (모던, 헤더 온리) |
| Cython | Python 유사 코드를 C 로 컴파일 |
| Python C API | CPython 직접(최저수준, 최후 수단) |

(ROS2 의 rclpy↔rclcpp 는 '결합'이 아니라 DDS(Data Distribution Service)로 분리 통신 — 본 절 비대상.)

**경계 규약** (체크리스트):

- [ ] **메모리 소유권**: 경계를 넘는 버퍼는 **소유자 단일 지정** + 생명주기 명시 (C 가 먼저 `free` → use-after-free 금지; Python 은 `Py_buffer` 참조로 GC(Garbage Collection) 보호).
- [ ] **GIL 해제**: 오래 도는 C 호출은 `Py_BEGIN_ALLOW_THREADS` 로 GIL(Global Interpreter Lock) 해제 → `domains/concurrency-coding.md`(concurrency aspect) 참조.
- [ ] **타입/시그니처**: `ctypes` 는 런타임만 체크 → 시그니처 불일치 = segfault. `argtypes`/`restype` 명시 + 경계 테스트.
- [ ] **에러 전파**: C 반환코드/`errno` ↔ Python exception 변환 규약 고정 (C 는 예외 못 던짐).
- [ ] **데이터 마샬링**: numpy ↔ C 버퍼는 buffer protocol(zero-copy), struct 정렬·패킹·엔디안 양쪽 일치.
- [ ] **빌드·ABI**: `.so` 빌드·링크·크로스컴파일을 `setup.py`/CMake/colcon 으로 일원화.

**공유 메모리 규약** (race 주 진원지): 같은 프로세스(Python↔C zero-copy)든 프로세스 간(`mmap`·POSIX shm·`multiprocessing.shared_memory`·ROS2 zero-copy)이든 —

> ★ **공유 가변 메모리는 단일 writer + 생명주기 소유자 명시. 다중 writer 면 동기화(lock/atomic).**
> → concurrency aspect + coding.md §6 **전역변수표 "누가 바꾸나" 칸**에 그 writer 를 기록한다.

**경계 = 공개표면**: 언어 경계는 공개 인터페이스라 coding.md **§3 사전승인 트리거**(공개 API) 대상 — 소유권·에러규약·빌드를 ADR 에 기록.

## 자체 점검

```bash
# 포맷터 설정 존재 여부 (선택했는지)
ls .clang-format .editorconfig pyproject.toml .prettierrc* 2>/dev/null || echo "(포맷터 미선택 — format 강제 없음)"
# 포맷 준수 검사
bash docs/claude_guideline/coding/checks/format.sh .
```

---

**VERSION**: 1.3.1 (1.3.0 + 독립 리뷰 반영 — §3 의 UI 실측 명령에 특정 프레임워크 목록을 박아 뒀던 것을 거뒀다(그 목록의 SSOT 는 `domains/` 이고 코어 마크다운에 베끼면 한쪽만 바뀌어도 모른다). 표 예시도 특정 프레임워크 대신 «하나만 적는다» 로. 두 실측 명령이 비-git 에서 조용히 비어 나온다는 사실 명시)

1.3.0 (1.2.0 + §2·§3 의 «(프로젝트별 작성)» 빈 칸을 채울 표 + **채우기 전까지의 기본값**(도메인 우선 → 저장소 실측)과 실측 명령으로 바꿨다. 빈 칸이 8/8 설치본에서 미작성으로 남아 선택이 매 작업마다 갈라지던 자리 — §1 의 포맷터 미선택 처리와 같은 꼴로 메운다)

1.2.0 (1.1.0 + 미선택 시 `.clang-format` 자동 고정(install.sh)·기존 C 계열 전량 검사 명시)
