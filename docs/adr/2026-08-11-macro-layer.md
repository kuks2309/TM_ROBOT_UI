# ADR 2026-08-11 — 매크로 계층 도입 (재사용 함수 + Job 이 매크로를 포함)

- 날짜: 2026-08-11 (KST, Korea Standard Time)
- 관련: 사용자 지시(2026-08-11) "job 과 매크로는 다름 … job은 마크로를 포함해야 함", "마크로는 재사용가능한 함수 같은것", [ADR 2026-08-10 기준점 확인](2026-08-10-reference-point-check.md)
- 대상: `tm_task_manager/macros/` 신설 + `JobExecutor` 디스패치 + `RecipeManager.JOB_TYPES` 스키마 확장

## Status

**Accepted — 2026-08-11 (실기 미검증).** 사용자 승인 2026-08-11. 1단계(레지스트리 + 매크로 2개 + 복합 Job 예시 1개) 범위만 해당한다.

## Context

### 요구

매크로는 **재사용 가능한 함수**이고, Job 은 그 매크로들을 **포함해 호출하는 단위**다. 각 매크로의 기능을 읽어서 사용할 수 있어야 한다.

### 현재 구조와 그 한계 (실측)

`JOB_TYPES` 31개 항목이 곧 최소 실행 단위이고, `JobExecutor._exec_*` 핸들러가 1:1로 대응한다. 핸들러들이 참조하는 공유 상태를 세어 보면(핸들러 구간 `self.*` 참조 횟수):

```
_log 249 │ ros_node 82 │ vision_manager 33
detected_ar_pose 16 · detected_landmark_pose 15 · detected_plate_pose 8
tm_transform_matrix 5 · jig_landmark_results 4 · last_reference_result 2
_move_to_position 7 · _transform_relative_to_absolute 7 · scan_landmark_averaged 3
```

**합성은 이미 암묵적으로 일어나고 있다** — `scan_tm_landmark` 가 `detected_landmark_pose` 를 남기면 `align_tm_landmark` 가 그것을 읽는다. 즉 공유 칠판(blackboard)을 통한 매크로 합성이 이미 동작 중이다.

빠진 것은 세 가지다:

1. **계약 선언 부재** — 어떤 재사용 단위가 무엇을 요구하고 무엇을 남기는지 코드를 읽어야만 안다
2. **합성 경로 부재** — 하나의 Job 이 여러 재사용 단위를 부를 방법이 없다
3. **가독 형태 부재** — 매크로 목록·파라미터·선후관계를 읽을 산출물이 없다

### 제약

기존 31개 Job 은 실기에서 동작 중이다(이번 세션에서 `scan_tm_landmark` 실행을 실측 확인). 일괄 전환은 검증 부담이 크고 되돌리기 어렵다.

## Decision

### 1. 매크로 계약

```python
def macro_fn(ctx: MacroContext, **params) -> MacroResult
```

- **`MacroContext`** — 위 실측 목록을 그대로 반영한 단일 진입점. 장비 핸들(`ros_node`·`vision_manager`·서비스) + 공용 helper(`move_to_position`·`scan_landmark_averaged`) + 로그 + 콜백 + 칠판. `JobExecutor` 를 감싸므로 매크로는 executor 내부 구조를 모르고, executor 는 매크로 구현을 모른다.
- **`MacroResult`** — `ok` / `message` / `data`. 현재 핸들러가 `bool` 만 반환해 실패 사유가 로그에만 남는 문제를 해소한다.

### 2. 레지스트리에 `requires` / `produces` 를 넣는다

```python
MacroSpec(name, summary, category, params, fn, requires, produces)
```

이 두 필드가 "읽어서 사용 가능"의 실질이다. 없으면 카탈로그는 이름 나열에 그친다. 표기 규약:

- `produces` / `requires` 의 평범한 이름 = **칠판 키** (같은 실행 안에서 앞선 매크로가 남긴 것) → 정적 검사 대상
- `config:` 접두 = **외부 선행조건** (예: `config:taught_origin` — 학습된 원점이 `positions.yaml` 에 있어야 함) → 정적 검사 제외, 매크로가 런타임에 스스로 확인

### 3. Job 이 매크로 시퀀스를 포함한다

`JOB_TYPES` 항목에 `macros` 키를 추가한다. 이 키가 있으면 디스패치가 매크로 경로를 타고, 없으면 기존 `_exec_*` 경로를 그대로 탄다.

```python
'vision_origin_check': {'macros': [{'use': 'vision_origin_check'}], 'params': {...}},
'settled_origin_check': {'macros': [{'use': 'wait', 'bind': {'duration': 'settle_ms'}},
                                    {'use': 'vision_origin_check'}], 'params': {...}},
```

`bind` 는 Job 파라미터명 → 매크로 파라미터명 매핑이다. 이름이 같으면 생략한다.

### 4. 마이그레이션은 점진적으로 — 빅뱅 금지

| 단계 | 내용 |
|---|---|
| **1 (본 ADR)** | 레지스트리·컨텍스트 도입 + `vision_origin_check`·`wait` 2개 전환 + 복합 Job `settled_origin_check` 1개 + 카탈로그 생성기 |
| 2 | 신규 매크로는 전부 매크로 방식으로 작성 |
| 3 | 기존 핸들러는 필요할 때만 건별 이관 |

전환한 2개는 **구현을 매크로로 옮기고 기존 핸들러는 삭제**한다(위임 껍데기를 남기면 구현이 2벌이 된다). 나머지 29개는 한 줄도 건드리지 않는다.

### 5. 칠판 수명 = 레시피 실행 1회

`JobExecutor` 가 보유하고 `run_from()` 에서 초기화한다. Job 경계를 넘어 유지되므로 기존 `detected_*` 공유 방식과 동일한 합성이 가능하다.

### 6. 카탈로그는 레지스트리에서 생성한다

`scripts/generate_macro_catalog.py` → `docs/macros/CATALOG.md`(사람용) + `docs/macros/macros.json`(도구용). 손으로 쓰지 않는다 — 손으로 쓰면 반드시 낡는다.

## Alternatives

- **매크로 = 저장된 Job 하위 시퀀스(서브루틴 파일)** — 티칭 펜던트식 매크로 개념. 코드 변경이 거의 없으나 "재사용 가능한 함수"라는 요구(파라미터·반환값·계약)를 만족하지 못해 기각.
- **31개 일괄 전환** — 일관성은 최고이나 실기 동작 중인 경로를 한 번에 흔든다. 검증 비용과 롤백 난이도로 기각.
- **`requires`/`produces` 생략** — 구현은 간단해지나 카탈로그가 이름 나열로 전락해 본 과제의 목적을 잃는다. 기각.

## Consequences

**이득**

- 재사용 단위가 이름·파라미터·선후관계를 갖는 1급 개념이 된다
- 하나의 Job 이 여러 매크로를 조합할 수 있다
- `MacroResult` 로 실패 사유가 구조화되어 상위에서 분기 가능해진다
- 카탈로그가 레지스트리에서 파생되므로 낡지 않는다

**비용**

- `JOB_TYPES` 스키마에 선택 키(`macros`)가 하나 늘어난다
- 매크로와 기존 핸들러 두 방식이 당분간 공존한다 — 3단계 완료까지 유지되는 과도기 부채. `debt` 로 등록한다.

**남는 위험**

- `MacroContext` 가 `JobExecutor` 내부(`_move_to_position`·`_stop_requested` 등 비공개 멤버)에 의존한다. executor 리팩터링 시 함께 깨진다 — 어댑터 한 곳에 모아 두어 수정 지점을 1곳으로 좁혔다.
- 칠판 키는 문자열이라 오타를 정적 검사로 못 잡는다. `validate_sequence()` 가 Job 정의 시점의 미충족 `requires` 만 잡는다.

## Rollback

가역. 되돌리는 절차:

1. `JOB_TYPES` 에서 `macros` 키와 `settled_origin_check` 항목 제거
2. `JobExecutor._execute_job` 의 매크로 분기와 `_run_macro_sequence` 제거
3. `macros/` 의 `vision_origin_check`·`wait` 구현을 `_exec_vision_origin_check`·`_exec_wait` 핸들러로 되돌림(git revert 로 충분)
4. `tm_task_manager/macros/` 패키지와 `docs/macros/` 삭제

되돌린 뒤 저장된 레시피에 `settled_origin_check` 가 남아 있으면 `_execute_job` 의 `else` 분기가 "알 수 없는 Job 타입"을 로그하고 `False` 를 반환한다 — 조용한 오동작이 아니라 명시적 실패다.
