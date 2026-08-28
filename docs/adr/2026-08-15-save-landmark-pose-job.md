# ADR 2026-08-15 — Landmark 좌표 저장 Job 신설 (save_landmark_pose)

- 날짜: 2026-08-15 (KST, Korea Standard Time)
- 관련: 사용자 지시(2026-08-15) "정지없이 돌아야 하기에 레시피 안에서 저장 바람", "어차피 모든 마커값 x y z rx ry rz 저장해야함", "드로어마커 저장 태스크 따로 하나 만드슈"
- 대상: `tm_task_manager/recipe_manager.py`(JOB_TYPES 1항목) · `tm_task_manager/job_executor.py`(분기 1줄 + 함수 2개) · `test/test_landmark_pose_save.py`(신설)

## Status

**Accepted — 2026-08-15 (실기 미검증).** 사용자 승인 2026-08-15: Job 신설 지시("따로 하나 만드슈") + 저장 위치 정책 선택("별도 폴더").

## Context

드로어 마커 1점을 기준으로 팔레트 칼리브레이션 마크 4점을 상대좌표로 순회 측정하는 레시피를 구성 중이다. 이때 **기준으로 쓴 드로어 마커 값 자체가 어디에도 파일로 남지 않는다.**

- `_exec_scan_tm_landmark` 는 결과를 `self.tm_landmark_pose` 에 넣고 끝난다(`job_executor.py:1555`).
- `coordinate_system_manager.set_single_landmark_scan` 은 메모리 `_definitions` 만 갱신한다(`coordinate_system_manager.py:161-166`). 파일 기록은 별도 `save_to_config()` 호출이 필요한데 스캔 경로에서 부르지 않는다.
- `_execute_job` 이 분기하는 34개 Job 을 AST 로 전수 검사한 결과, 좌표를 파일에 쓰는 Job 은 `calculate_plate_pose`(→`_save_plate_pose`) 하나뿐이다. `save_pose` 는 이름과 달리 `self.saved_poses[key] = tcp` 딕셔너리 대입이며(`job_executor.py:1983`) 레시피 실행이 끝나면 사라진다.
- `_save_plate_pose` 는 `jig1~4` 만 기록한다(`job_executor.py:1847-1854`). 기준 Landmark 자리가 없다.

GUI 저장(`main_window._update_recipe_reference`)으로 남기는 경로는 있으나 **작업을 멈춰야** 하고, `tm_landmark_pose` 가 비면 `coordinate_system_manager` 의 옛 값으로 조용히 폴백한다(`main_window.py:745-751`) — 실제로 이 폴백 때문에 레시피에 무관한 기준점(`positions.yaml` 의 `jig_landmark`)이 기록된 사례가 이번 작업 중 발생했다.

## Decision

### 1. 기존 저장물 확장이 아니라 Job 신설

`_save_plate_pose` 에 `reference_landmark` 키를 얹는 안을 먼저 제시했으나, 사용자가 별도 Task 를 지시했다. 별도 Job 이 나은 실질 근거도 있다 — `calculate_plate_pose` 없이 Landmark 만 재는 레시피에서도 저장할 수 있고, Jig 4점 측정과 기준점 기록의 실패 조건이 분리된다.

### 2. `landmarks` 딕셔너리에 5번째 항목을 넣지 않는다

`_save_plate_pose` 의 `landmarks` 는 `enumerate(landmarks, start=1)` 로 `jig1~4` 를 만들고(`job_executor.py:1853`), 소비자 `average_landmarks_from_files` 가 `jig1~4` 를 요구한다(`job_executor.py:1785`). 5번째를 넣으면 `load_plate_pose` 경로가 깨진다.

### 3. 파일명 규칙은 재사용, 저장 폴더는 분리

파일명은 기존 `_plate_pose_file_name`(`job_executor.py:1809-1820`)을 그대로 호출한다 — `<레시피명>_<캡션>_<저장시각>.yaml`. 규칙을 새로 만들지 않는다.

저장 폴더는 `plate_pose_calc` 와 분리한다(사용자 선택). 같은 폴더에 두면 `load_plate_pose` 의 `file_prefix` 검색이 이 파일까지 집어 skip 로그를 남긴다(크래시는 아니나 노이즈).

### 4. 실패는 조용히 넘기지 않는다

`calculate_plate_pose` 는 `save_path` 가 비면 "저장하지 않음"이 정상 동작이지만, 본 Job 은 **저장이 유일한 목적**이므로 공란은 오류로 보고 `False` 를 돌려준다. 스캔 전 실행·좌표 키 누락도 마찬가지다. 설정 실수가 조용히 통과하면 생산 운전에서 기준점 없는 측정본만 쌓인다.

`operator` 공란은 경고 후 `null` 저장 — `calculate_plate_pose` 와 같은 규약을 따른다.

## Alternatives

- **`_save_plate_pose` 에 `reference_landmark` 키 추가** — 파일 1개로 끝나고 변경도 한 줄이다. 사용자가 별도 Task 를 지시해 기각. 다만 "한 번의 측정 = 파일 1개" 를 원하면 재검토 여지 있음.
- **`save_pose` 를 파일 저장으로 확장** — 이름은 맞지만 `move_to_saved_pose` 가 세션 내 메모리를 전제로 동작한다. 의미를 바꾸면 기존 레시피가 영향받는다. 기각.
- **`scan_tm_landmark` 가 스캔 직후 자동 저장** — Job 추가가 없어 간단하나, 저장이 필요 없는 레시피에서도 파일이 쌓이고 경로 파라미터를 스캔 Job 에 얹어야 한다. 관심사 분리 위반. 기각.
- **`coordinate_system_manager.save_to_config()` 호출** — `positions.yaml` 의 단일 슬롯을 덮어쓰는 구조라 측정 이력이 남지 않는다. 기각.

## Consequences

**이득**

- 레시피가 정지 없이 한 번 돌 때마다 드로어 마커 + Jig 4점, 총 5마커가 전부 6자유도로 파일에 남는다
- GUI 저장 시 옛 값으로 폴백하는 함정을 우회한다
- 기준점 기록이 `calculate_plate_pose` 성공 여부와 독립이다

**비용 · 동작 변화**

- 측정 1회당 파일이 2개(plate_pose 1 + landmark 1)로 늘어난다
- Task 편집 UI 의 Landmark 카테고리에 항목이 하나 추가된다
- **기존 레시피는 영향 없다** — 새 Job 을 쓰지 않는 한 동작이 바뀌지 않는다

**남는 위험**

- `tm_landmark_pose` 는 `scan_tm_landmark` 만 채운다. `find_landmark` 는 `detected_landmark_pose` 만 갱신하므로(`job_executor.py:1438`, `:1456`), `find_landmark` 단독 실행 뒤 본 Job 을 부르면 직전 `scan_tm_landmark` 값이 저장된다. 레시피에서 `scan_tm_landmark` 직후에 두는 것을 전제한다.

## 신규 함수표

| 함수 | 가시성 | 인자 | 반환 | 역할 |
| --- | --- | --- | --- | --- |
| `JobExecutor._exec_save_landmark_pose` | 내부(디스패치 진입점) | `job: Job` | `bool` | 전제조건 검사 후 저장 위임 |
| `JobExecutor._save_landmark_pose` | 내부 | `save_dir: str, pose: Dict, job: Job, operator: str` | `bool` | YAML 기록 |

| 클래스 상수 | 값 | 역할 |
| --- | --- | --- |
| `JobExecutor.LANDMARK_POSE_KEYS` | `('x','y','z','rx','ry','rz')` | 검증·직렬화 키 목록 단일 정의 |

## 검증

`test/test_landmark_pose_save.py` 9건 — 등록·디스패치·6자유도 저장·파일명 규칙·3자리 반올림·스캔 전 실패·`save_path` 공란 실패·좌표 누락 실패·`operator` 공란·레시피 미로드·기존 `_save_plate_pose` 산출물 무변경.

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/ -q
1 failed, 493 passed
```

유일한 실패 `test_recipe_manager.py::test_manager_get_job_types_by_category` 는 **본 변경 이전부터 실패**한다. `scan_ar_tag in categories['Vision']` 을 단언하는데 `scan_ar_tag` 의 category 는 HEAD 에서도 `'AR Tag'` 다(AST 로 HEAD 판과 작업본을 대조해 양쪽 모두 단언 불성립 확인). 본 변경은 `Landmark` 카테고리에 항목 1개를 더할 뿐이다.

최종 verdict 는 저자가 찍지 않는다 — 리뷰 필요.

## Rollback

가역. 되돌리는 절차:

1. `recipe_manager.py` 의 `JOB_TYPES['save_landmark_pose']` 항목 삭제
2. `job_executor.py` 의 `_execute_job` 내 `save_landmark_pose` 분기 2줄 삭제
3. `job_executor.py` 의 `LANDMARK_POSE_KEYS` · `_exec_save_landmark_pose` · `_save_landmark_pose` 삭제
4. `test/test_landmark_pose_save.py` 삭제

되돌린 뒤 레시피에 `save_landmark_pose` Job 이 남아 있으면 `_execute_job` 이 "알 수 없는 Job 타입" 을 로그하고 `False` 를 돌려 실행이 멈춘다 — 조용한 오동작이 아니다. 되돌리기 전에 해당 Job 을 레시피에서 먼저 지울 것.
