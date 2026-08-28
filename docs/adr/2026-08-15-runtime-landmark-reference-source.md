# ADR 2026-08-15 — Runtime 변환 기준점을 save_landmark_pose 산출물에서 자동 로드

- 날짜: 2026-08-15 (KST, Korea Standard Time)
- 관련: 사용자 지시(2026-08-15) "드로어 찍고 저장 => 최근 파일 알아서 불러와서 계산 못함?", "매번 자동 ㄱㄱ. 여러번 할거야", [ADR 2026-08-15 save_landmark_pose Job 신설](2026-08-15-save-landmark-pose-job.md)
- 대상: `tools/convert_to_runtime.py` · `tm_task_manager/job_executor.py`(`_exec_generate_runtime` 배선) · `test/test_runtime_landmark_reference.py`(신설)

## Status

**Accepted — 2026-08-15 (실기 미검증).** 사용자 승인 2026-08-15 "매번 자동 ㄱㄱ".

## Context

마스터 레시피를 Landmark 기준 상대좌표 실행본으로 바꾸려면 기준점 `T_landmark` 가 필요하다. 기존 소스는 둘뿐이었다(`convert_to_runtime.py` 기존 `convert_to_relative`).

1. **마스터의 `reference.tm_jig_landmark`** — `main_window._update_recipe_reference` 가 GUI 저장 시에만 갱신한다. 그런데 `job_executor.tm_landmark_pose` 가 비면 `coordinate_system_manager` 의 값으로 **조용히 폴백한다**(`main_window.py:745-751`). 이번 작업 중 실제로 이 경로를 타서, `pallet0_drawer_cali.yaml` 에 드로어 마커와 무관한 좌표(= `config/positions.yaml` 의 `coordinate_definitions.jig_landmark`, 여섯 값 일치)가 기록됐다. 그 값으로 변환하면 4점이 전부 엉뚱한 곳으로 간다.
2. **`data/jig_mark/**/*.yaml`** (`find_latest_jig_plate_file`) — 무관한 최신 파일이 잡힐 수 있는 폴백.

두 소스 모두 **측정과 기준점이 같은 실행에서 나왔다는 보장이 없다.** 게다가 1번은 작업자가 스캔 직후에 저장 버튼을 눌러야 해서, "정지 없이 돌아야 한다"는 운용 요구와 충돌한다.

한편 [save_landmark_pose Job](2026-08-15-save-landmark-pose-job.md) 이 신설되어, 레시피 실행 중 `scan_tm_landmark` 직후에 기준 Landmark 6자유도가 `data/landmark_pose/` 에 파일로 남는다. 이 파일은 정의상 **측정과 같은 실행에서 나온 값**이다.

캘리브레이션을 팔레트 6대 × 드로어 여러 개에 반복할 예정이라(사용자: "여러번 할거야"), 매 회 수작업 계산·YAML 편집은 성립하지 않는다.

## Decision

### 1. 기준점 소스에 `landmark_pose` 를 추가하되, 기존 우선순위는 건드리지 않는다

탐색 순서: **마스터 `reference`** → **최신 `data/landmark_pose/*.yaml`** → **최신 `data/jig_mark/**/*.yaml`**.

`landmark_pose` 를 맨 앞이 아니라 `reference` **뒤**에 넣는다. 앞에 두면 `tm_landmark_test4.yaml`·`gripper_test_jig.yaml` 등 `reference` 로 동작 중인 기존 마스터의 기준점이 말없이 바뀐다. 기존 레시피 동작 변화 0 이 우선이다.

우리 마스터(`pallet0_drawer_cali.yaml`)는 `reference` 블록을 제거했으므로 자연히 2번을 탄다. (스캔 없이 GUI 저장하면 폴백으로 다시 생길 수 있음 — 레시피 헤더에 명시.)

### 2. `find_latest_landmark_pose_file()` 은 기존 `find_latest_jig_plate_file()` 과 같은 규약

`data/landmark_pose/**/*.yaml` 중 mtime 최대. 폴더 부재·빈 폴더면 `None`. 새 규약을 만들지 않는다.

### 3. CLI 와 `generate_runtime` Job 양쪽에 배선

`main()` 과 `_exec_generate_runtime` 모두 `find_latest_landmark_pose_file()` 을 호출해 넘긴다. 한쪽만 배선하면 경로에 따라 결과가 달라진다.

### 4. 불완전한 파일은 조용히 통과시키지 않는다

`landmark` 키에 x/y/z/rx/ry/rz 가 모두 있지 않으면 경고 후 `None` — 다음 소스로 넘어가고, 어느 소스도 없으면 변환 실패(`False`)와 함께 **세 소스를 모두 안내**한다. 기존 실패 메시지는 `reference` 만 안내해 실제 해법을 가리지 못했다.

## Alternatives

- **`landmark_pose` 를 1순위로** — 우리 레시피엔 편하나 기존 마스터의 기준점이 말없이 바뀐다. 기각.
- **`_update_recipe_reference` 의 폴백 제거** — 근본 원인(옛 값 폴백)을 없애지만 그 폴백에 의존하는 기존 흐름을 모른 채 건드리는 것이고, 여전히 "저장 버튼을 누르러 정지" 문제가 남는다. 기각.
- **`generate_runtime` 을 레시피 Job 으로 넣어 매 실행 자동 변환** — 변환기가 그 Job 을 런타임 파일에 복사하는데 `_exec_generate_runtime` 이 `_runtime` 파일명을 거부하므로(`job_executor.py:2292-2294`) 런타임 실행이 멈춘다. 기각. 변환은 CLI 1회.
- **파일명 타임스탬프로 최신 판정** — mtime 이 기존 함수와 같은 규약이고 파일명 형식 변경에 취약하지 않다. mtime 유지.

## Consequences

**이득**

- 스캔 → 저장 → 변환이 사람 손 없이 이어진다. 팔레트마다 반복해도 절차가 같다
- 기준점이 측정과 같은 실행에서 나온 값임이 구조적으로 보장된다
- 기준점 부재 시 실패 메시지가 실제 해법 3가지를 안내한다

**비용 · 동작 변화**

- `data/landmark_pose/` 는 최신 1개만 쓰이므로 오래된 파일이 쌓인다. 정리 정책은 두지 않았다
- **여러 드로어를 연달아 측정하면 "최신 1개"가 의도한 드로어가 아닐 수 있다.** 드로어별로 측정 직후 변환하거나, CLI 3번째 인자로 파일을 명시할 것
- 기존 마스터(`reference` 보유)는 동작 변화 없음 — 테스트로 고정

**남는 위험**

- `RecipeConverter.__init__` 시그니처가 늘었다. 키워드 기본값이라 기존 호출부는 무영향이나, 위치인자 3개로 부르는 외부 코드가 있다면 깨진다(저장소 내에는 없음).

## 신규 함수표

| 함수 | 가시성 | 인자 | 반환 | 역할 |
| --- | --- | --- | --- | --- |
| `find_latest_landmark_pose_file` | 모듈 공개 | 없음 | `Optional[str]` | `data/landmark_pose` 최신 YAML 경로 |
| `RecipeConverter.load_landmark_pose` | 공개 메서드 | 없음 | `Optional[Dict]` | 파일 → `{X,Y,Z,Rx,Ry,Rz}` |

| 변경 | 내용 |
| --- | --- |
| `RecipeConverter.__init__` | `landmark_pose_file: Optional[str] = None` 추가 |
| `RecipeConverter.convert_to_relative` | 기준점 탐색에 2순위 삽입, 실패 메시지 3소스 안내 |
| `main()` · `_exec_generate_runtime` | 최신 파일 조회·전달 |

## 검증

`test/test_runtime_landmark_reference.py` 10건 — 기준점 채택·4점 relative 변환·왕복 복원·시스템 회전 시 4점 강체 회전·마크 간 거리 보존·**시스템 통째 회전 시 상대좌표 불변**·마스터 reference 우선순위 유지·기준점 전무 시 실패·불완전 파일 거부·`find_latest` mtime 선택 및 부재 처리.

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/ -q
1 failed, 503 passed
```

유일한 실패 `test_recipe_manager.py::test_manager_get_job_types_by_category` 는 본 변경 이전부터 실패한다(`scan_ar_tag` 의 category 는 HEAD 에서도 `'AR Tag'`, 단언은 `'Vision'` 기대). 본 변경과 무관.

최종 verdict 는 저자가 찍지 않는다 — 리뷰 필요.

## Rollback

가역. 되돌리는 절차:

1. `convert_to_runtime.py` 의 `find_latest_landmark_pose_file` · `RecipeConverter.load_landmark_pose` 삭제
2. `RecipeConverter.__init__` 의 `landmark_pose_file` 인자와 `self.landmark_pose_file` 삭제
3. `convert_to_relative` 의 2순위 블록 삭제, 실패 메시지 원복
4. `main()` · `_exec_generate_runtime` 의 조회·전달 삭제
5. `test/test_runtime_landmark_reference.py` 삭제

되돌리면 `pallet0_drawer_cali.yaml` 은 `reference` 블록이 없어 변환이 실패한다(조용한 오동작 아님). 그때는 스캔 직후 GUI 저장으로 `reference` 를 채우거나 CLI 3번째 인자로 jig_plate 파일을 명시해야 한다.
