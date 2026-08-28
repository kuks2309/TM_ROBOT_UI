# ADR 2026-08-15 — 마커 좌표계 이동 Task 신설 (move_to_landmark_pose)

- 날짜: 2026-08-15 (KST, Korea Standard Time)
- 관련: 사용자 지시(2026-08-15) "마커의 x,y,z,rz 보고 그 좌표계 기준으로 알아서 상대좌표로 하는거", "마커 측정 자체는 그렇게 정밀할 필요 없는게 1번, 이거 일단 되야, 드로어 줍게에도 쓸수있는게 2번", "rx ry 도 포함해서 하는놈도. 얘는 박스 옮기는 용", "하나 만들고... rx ry 토글이면 될듯", [ADR 2026-08-15 save_landmark_pose Job 신설](2026-08-15-save-landmark-pose-job.md)
- 대상: `tm_task_manager/tools/landmark_frame.py`(신설) · `recipe_manager.py`(JOB_TYPES 1항목) · `job_executor.py`(분기 + 함수 3개) · `tabs/task_edit_tab.py`(티칭 분기) · `test/test_landmark_frame.py`(신설) · `config/recipes/pallet0_drawer_cali.yaml`

## Status

**Accepted — 2026-08-15 (실기 미검증).** 사용자 승인 2026-08-15 "ㄱㄱ".

## Context

### 1. `coordinate_mode: relative` 는 사용자에게 보이지 않고 티칭으로 깨진다

랜드마크 기준 이동 수단이 `move_to_point` + `coordinate_mode: relative` 뿐이었다. 그런데 이 키는 **YAML 전용**이다 — `tabs/*.py`·`main_window.py` 전체에 읽거나 쓰는 코드가 0건이라 Task 편집기에 표시되지 않는다.

그 결과 실제 사고가 났다. `_on_teach_position`('현재위치 입력')이 `coordinate_mode` 를 보지 않고 현재 TCP **절대값**을 `params.X/Y/Z` 에 덮어쓰는데(`task_edit_tab.py:520-550`) 플래그는 `relative` 로 남는다. 저장된 레시피의 Job 6 이 `X: 127.18 / coordinate_mode: relative` 인 혼합 상태가 되었고, 실행하면 절대좌표가 한 번 더 변환돼 엉뚱한 곳으로 간다.

### 2. 마커 자세 전체를 프레임에 쓰면 측정 산포가 증폭된다

드로어 마커 22회 실측 산포와, 그것이 250mm 레버암에서 만드는 위치 오차:

| 축 | 표준편차 | 범위 | 250mm 에서의 위치 오차(범위 기준) |
| --- | --- | --- | --- |
| x | 1.576 mm | 3.157 mm | — |
| y | 0.247 mm | 0.723 mm | — |
| z | 0.078 mm | 0.220 mm | — |
| rx | 0.055° | 0.197° | 0.86 mm |
| ry | 0.042° | 0.129° | 0.56 mm |
| rz | 0.264° | 0.602° | 2.63 mm |

마크를 카메라 시야에 넣는 것이 목적인 이동은 평면 기울기를 따라갈 이유가 없다. rx/ry 를 프레임에 넣으면 1.4mm 가 공짜로 딸려 들어온다.

같은 11회 데이터를 두 프레임으로 역산한 티칭점 산포가 이를 확인한다:

| 프레임 | x | y | z |
| --- | --- | --- | --- |
| 마커 자세 전체 | ±0.118 | ±0.162 | ±0.140 mm |
| **Rz 만** | **±0.015** | **±0.003** | **±0.010 mm** |

### 3. 그러나 박스 이송에는 rx/ry 가 필요하다

공구가 대상 면을 마주봐야 하는 이동에서는 마커 자세를 따라가야 한다(사용자 지시).

### 4. `move_to_plane_pose` 로는 대체 불가

평면 좌표계 이동은 `detected_plate_pose` 를 요구한다(`job_executor.py`). 그 평면을 만드는 것이 캘리브레이션 레시피 자체이므로 순환이다. 마커 1 점만으로 서는 좌표계가 별도로 필요하다.

## Decision

### 1. Task 하나 + 프레임 모드 토글

`move_to_landmark_pose` 하나를 만들고 `frame_mode` 로 회전 정의를 고른다 — `rz_only`(기본) / `full`. Task 를 둘로 나누면 구현·테스트·문서가 갈라지고 사용자가 매번 고르는 부담만 는다. `align_to_plane_normal` 의 `rz_mode` 와 같은 패턴이다.

### 2. 파라미터는 `move_to_plane_pose` 형태를 그대로 따른다

`offset_x/y/z/rx/ry/rz` + `velocity` + `max_radius_mm` + `decel_*`. 새 규약을 만들지 않는다. 전부 파라미터이므로 편집기에 그대로 보인다 — §1 의 "안 보인다" 가 구조적으로 해소된다.

`offset_z` 에 양수 제약을 두지 않았다. 평면 좌표계와 달리 마커 좌표계의 Z 는 "평면 위쪽"이 아니라 단순한 축이며, 실제 접근점이 마커보다 아래(-24 ~ -29mm)에 있다.

### 3. 티칭은 역산으로만 채운다

`_teach_landmark_frame_offset` 이 현재 TCP 를 `pose_in_landmark_frame` 으로 되돌려 `offset_*` 칸에 넣는다. `align_to_plane_normal` 의 `_teach_plane_align_offset` 과 같은 방식이다. **절대 좌표가 상대 칸에 들어가는 §1 의 사고가 구조적으로 불가능해진다.**

### 4. 변환은 별도 모듈로 분리

`tools/landmark_frame.py` 에 `pose_from_landmark_frame` / `pose_in_landmark_frame` / `landmark_frame_rotation` 을 둔다. 회전·오일러(ZYX) 규약은 `jig_plane_calculator` 의 `_rotation_matrix_from_pose` · `_rotation_matrix_to_euler_zyx` 를 재사용한다 — 규약을 두 벌 만들지 않는다.

## Alternatives

- **`coordinate_mode` 를 UI 에 노출하고 티칭이 이를 인식하게 수정** — 근본 원인은 고치지만 `move_to_point` 한 Task 가 절대/상대 두 의미를 겸하는 구조가 남는다. 파라미터 이름이 여전히 `X/Y/Z`(절대처럼 보임)이라 오독 위험도 남는다. 기각.
- **`ChangeBase("vision_TM_Landmark_detection")` 로 로봇에 실제 임시 베이스 생성** — 사용자가 처음 떠올린 방식이고 `LandmarkAlignService` 에 함수도 있다. 그러나 이를 부르는 Job 타입이 없고, `move_to_point`·`go_home`·`move_to_plane_pose` 가 모두 `current_base != RobotBase` 면 거부한다. 그 가드들을 전부 손대야 해서 범위가 크다. 결과가 동일하므로 소프트웨어 환산 채택.
- **Task 를 rz_only 용·full 용 둘로 분리** — 사용자가 "하나 만들고 rx ry 토글" 로 명시. 기각.
- **`move_linear` 체인 유지** — 원본 `palletN_cali` 방식이고 TPP 가 공구 좌표계임도 실측 확인했다. 다만 마크→마크 체인이라 오차가 누적되고, 첫 점 자세가 고정이면 회전 추종이 깨진다. 4점 전부 마커 기준 절대 오프셋이 더 견고하다.

## Consequences

**이득**

- 마커 1 점만으로 서는 좌표계가 생겨 캘리브레이션·드로어 줍기에 같은 Task 를 쓴다
- `rz_only` 로 마커 rx/ry 산포(1.4mm 상당)가 결과에서 빠진다
- 모든 값이 파라미터라 편집기에 보이고, 티칭이 역산이라 깨질 수 없다
- 4점이 각각 마커 기준 절대 오프셋이라 순회 중 오차가 누적되지 않는다

**비용 · 동작 변화**

- Task 편집 UI 의 Landmark 카테고리에 항목이 하나 는다
- `pallet0_drawer_cali.yaml` 이 `move_to_point`+`coordinate_mode` / `move_linear` 조합에서 이 Task 4개로 바뀌었다. 기존 다른 레시피는 영향 없다
- `frame_mode: full` 은 마커 rx/ry 를 그대로 받으므로 위 산포가 되살아난다 — 면 추종이 필요한 경우에만 쓸 것

**남는 위험**

- 마커가 시야에서 크게 벗어나면 `scan_tm_landmark` 가 실패하고 이 Task 는 전제부터 성립하지 않는다. 앞단에 `find_landmark` 를 두는 것은 레시피 작성자 몫이다
- `max_radius_mm` 기본값 0(무제한)이다. 오프셋 오타가 먼 곳으로 보내는 것을 막으려면 레시피에서 명시해야 한다(본 레시피는 600 지정)

## 신규 함수표

| 함수 | 위치 | 인자 | 반환 | 역할 |
| --- | --- | --- | --- | --- |
| `landmark_frame_rotation` | `tools/landmark_frame.py` | `landmark, frame_mode` | `np.ndarray(3,3)` | 프레임 회전 행렬 |
| `pose_from_landmark_frame` | 〃 | `landmark, relative, frame_mode` | `Dict` | 상대 → 베이스 pose |
| `pose_in_landmark_frame` | 〃 | `landmark, pose, frame_mode` | `Dict` | 베이스 → 상대 (역변환) |
| `JobExecutor._landmark_frame_inputs` | `job_executor.py` | `params` | `(tuple\|None, str)` | 입력 검증 공통화 |
| `JobExecutor._exec_move_to_landmark_pose` | 〃 | `job` | `bool` | Job 실행 |
| `JobExecutor.estimate_landmark_frame_offset` | 〃 | `params` | `(Dict\|None, str)` | 티칭 역산 |
| `TaskEditTab._teach_landmark_frame_offset` | `tabs/task_edit_tab.py` | `job` | `None` | 역산 결과를 입력칸에 기입 |

| 상수 | 값 |
| --- | --- |
| `FRAME_MODE_RZ_ONLY` / `FRAME_MODE_FULL` / `FRAME_MODES` | `'rz_only'` / `'full'` / 두 값 튜플 |
| `JobExecutor.LANDMARK_FRAME_OFFSET_KEYS` | `('x','y','z','rx','ry','rz')` |

## 검증

`test/test_landmark_frame.py` 17건 — rz_only 가 마커 rx/ry 변화에 불변 / full 은 반대로 추종 / 두 모드 왕복 변환 / 오프셋 0 이 마커 위 / rz_only 회전이 순수 yaw / 잘못된 모드 예외 / 마커 회전 시 4점 강체 이동(거리 보존) / JOB_TYPES 등록 / 디스패치·목표 pose / 스캔 전 실패 / 잘못된 frame_mode 실패 / RobotBase 아닐 때 거부 / `max_radius_mm` 가드 및 0=무제한 / 티칭 역산 왕복 / 스캔 없이 티칭 시 보고.

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/ -q
1 failed, 535 passed
```

유일한 실패 `test_recipe_manager.py::test_manager_get_job_types_by_category` 는 본 변경 이전부터 실패한다(`scan_ar_tag` 의 category 가 HEAD 에서도 `'AR Tag'`, 단언은 `'Vision'` 기대). 본 변경과 무관.

레시피 검증(실측 11회 오프셋 적용): 접근점 간 거리 137.188 / 196.058 / 137.454 / 196.277 mm 로 마크 배치 실측과 일치. 마커를 X+150mm 이동·Rz+35° 회전시켜도 마크 간 거리 편차 0.000000000 mm, **마커 rx/ry 를 각 0.5° 흔들어도 목표점 이동 0.000 mm**.

최종 verdict 는 저자가 찍지 않는다 — 리뷰 필요.

## Rollback

가역. 되돌리는 절차:

1. `recipe_manager.py` 의 `JOB_TYPES['move_to_landmark_pose']` 삭제
2. `job_executor.py` 의 `move_to_landmark_pose` 분기 2줄, `LANDMARK_FRAME_OFFSET_KEYS`, `_landmark_frame_inputs`, `_exec_move_to_landmark_pose`, `estimate_landmark_frame_offset`, `landmark_frame` import 삭제
3. `tabs/task_edit_tab.py` 의 `_on_teach_position` 분기 3줄과 `_teach_landmark_frame_offset`, `LANDMARK_FRAME_OFFSET_KEYS` 삭제
4. `tools/landmark_frame.py` · `test/test_landmark_frame.py` 삭제
5. `config/recipes/pallet0_drawer_cali.yaml` 을 이전 방식으로 환원

되돌린 뒤 레시피에 `move_to_landmark_pose` 가 남아 있으면 `_execute_job` 이 "알 수 없는 Job 타입" 을 로그하고 `False` 를 돌려 실행이 멈춘다 — 조용한 오동작이 아니다. 5번을 먼저 처리할 것.
