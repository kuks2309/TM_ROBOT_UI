# ADR 2026-08-10 — 로봇 기준점 확인 매크로 (verify_reference_point)

- 날짜: 2026-08-10 (KST, Korea Standard Time)
- 관련: 사용자 지시(2026-08-10) "기준점 확인 마크로 생성 — 미리 알고있는 로봇 바디의 TM mark로 이동해서 로봇이 항상 그 위치에서 3차원 tm mark 좌표가 맞는지 확인. 다를경우 알람. 학습과 허용범위 등을 gui에 넣어야함. 시나리오 첫번째 또는 마지막, 옵션으로 반드시 하도록 선택 가능"
- 대상: `ReferenceCheckService` 신규 + `JobExecutor` 신규 Job 1종 + `RecipeManager.JOB_TYPES` 2건 + 좌표계 탭 GUI(Graphical User Interface)
- 인벤토리 근거: [code_review 2026-07-07](../code_review/TM_Robot_ros2_ws/2026-07-07.md) 함수표 #4c·#17·#23·#29, 전역변수표 G6

## Status

**Accepted — 2026-08-10 (실기 미검증).** 사용자 승인 2026-08-10, 설계 4개 결정 사항 확정.

로봇·TMflow 연결이 필요한 실기 검증은 미수행이며, 본 ADR은 단위 테스트 통과까지만 근거로 삼는다.

## Context

### 요구 (4항)

1. 미리 학습해 둔 로봇 바디 기준 TM(Techman) Landmark 위치로 이동해, 그 자세에서 마크의 3차원 좌표가 학습값과 일치하는지 확인한다.
2. 불일치 시 알람 — 로봇 교정(calibration)이 필요하다는 신호.
3. 학습(teaching)과 허용범위(tolerance) 설정을 GUI에 넣는다.
4. 시나리오(Recipe)의 첫 번째 또는 마지막에 배치하며, "반드시 실행"을 옵션으로 선택할 수 있어야 한다.

### 측정 원리와 그로부터 오는 제약 (설계의 핵심 제약)

TMflow 가 반환하는 `g_TM_Landmark` 는 **로봇 베이스 프레임 기준 6-DoF(Degrees of Freedom)** 이며, 값은 사실상

```
T_base_mark = T_base_tcp × T_tcp_cam × T_cam_mark
```

로 합성된다. 즉 측정값에는 **로봇 기구학(kinematics) 오차가 그대로 실려 들어온다** — 이것이 본 기능이 로봇 교정 필요 여부를 판단할 수 있는 근거인 동시에, 다음 제약을 낳는다:

> 학습 시와 **다른 TCP(Tool Center Point) 자세**에서 측정하면 편차가 자세 차이에 오염되어 판정이 무의미해진다.

따라서 기준값은 `landmark` 단독이 아니라 **`(tcp_pose, landmark)` 쌍**으로 저장하고, 확인 시 그 TCP 자세로 복귀한 뒤 측정한다. 이 제약이 아래 Decision 4의 직접 근거다.

TM Landmark 자체의 정확도 한계(배열 툴이며 정밀 위치지정용이 아님)는 [ADR 2026-07-27 팔레트 평면 정렬](2026-07-27-pallet-plane-align.md)에 인용된 TMvision 매뉴얼 근거를 그대로 승계한다. 본 기능은 절대 정밀도가 아니라 **동일 조건 반복 측정의 재현성 변화**를 보는 것이므로 그 한계와 모순되지 않는다.

### 기존 자산 (재사용 — 신규 작성 회피)

| 자산 | 위치 | 본 과제에서의 역할 |
|---|---|---|
| Landmark 스캔 (`g_robot_command=2` → `g_TM_Landmark`) | 함수표 #9 `VisionManager.execute_tm_landmark_scan`/`execute_tm_landmark_read` | 그대로 호출 |
| 반복측정·outlier 제거·평균 | 함수표 #23 `LandmarkAnalyzer` | 그대로 호출 |
| YAML 설정 영속화 | 함수표 #17 `ConfigManager.get`/`set` | 학습값·허용범위 저장 |
| Job 파라미터 GUI 자동 생성 | `TaskEditTab._display_task_params` (JOB_TYPES 스키마 기반) | 신규 Job 파라미터 UI 자동 확보 |
| Job 타입 카탈로그 단일 진실원 | 전역변수표 G6 `RecipeManager.JOB_TYPES` | 신규 Job 등록 지점 |

### 중복 후보 검토 (coding.md §2)

- `JigPlateValidator.check_*` (함수표 #29) — 허용범위 합/불 판정이라는 점은 유사하나, 대상이 지그 플레이트 **4점 기하**(변 길이차·대각선차·평행도)이고 `tools/jig_plate_validator.py` 는 PyQt5·matplotlib 를 import 하는 GUI 겸용 독립 스크립트다. 서비스 계층에서 import 하면 무거운 UI 의존이 딸려온다 → **재사용하지 않고 별도 dataclass 로 분리**. 판정 결과 구조(항목·측정값·임계값·통과여부)의 *형태*만 차용.
- `CoordinateSystemManager` (함수표 #10) — 좌표계 저장이라는 점은 유사하나 `SUPPORTED_SYSTEMS` 화이트리스트(robot_base/jig_landmark/jig_plate) 기반 **좌표계 정의** 전용이며, 허용범위·합불 판정은 다른 책임이다 → 클래스는 분리하되 **저장 파일(`config/positions.yaml`)은 공유**.
- `JobExecutor._exec_scan_tm_landmark` 와 `_exec_scan_tm_landmark_jig` 는 반복스캔·outlier·평균 로직이 **이미 2벌 복제**되어 있다(함수표 #4c 군집). 세 벌째를 만들지 않기 위해 공통 helper 로 추출하고 기존 2개 Job 도 그 helper 를 호출하도록 치환한다.

## Decision

### 1. 알람 = 팝업 + 실행 즉시 중단

허용범위 초과 시 `JobExecutor` 는 `on_reference_alarm` 콜백을 발화하고 `False` 를 반환한다. 기존 Job 실패 경로가 그대로 `ExecutionState.ERROR` 로 전이시켜 레시피를 멈춘다. `MainWindow` 가 콜백을 받아 `QMessageBox` 경고창을 띄운다.

`JobExecutor` 는 UI 를 직접 조작하지 않는다(CLAUDE.md 아키텍처 원칙 — Service→UI 는 콜백/시그널).

**함수표 #4c 의 High 결함(스텁 4곳이 `return True # 임시` 로 실패를 성공 보고)을 답습하지 않는다** — 미학습·스캔 실패·판정 실패는 모두 `False` 를 반환한다.

### 2. "반드시 실행" 강제는 Recipe 단위

`recipe_info` Job 에 `reference_check` 파라미터(`none`/`first`/`last`/`both`, 기본 `none`)를 추가한다. `RunMonitorTab._on_run` 진입 시 배치를 검사하고, 위반이면 **실행을 거부하고 안내창**을 띄운다.

자동 삽입하지 않는다 — 레시피 파일에 없는 Job 이 실행되면 저장된 시나리오와 실제 실행 이력이 어긋나 사후 추적이 불가능해진다.

### 3. 판정은 6축 개별 비교

`|측정 - 기준|` 을 X/Y/Z 는 mm, Rx/Ry/Rz 는 deg 단위로 **축별로** 임계값과 비교한다. 3D 거리 단일값을 쓰지 않는 이유는 어느 축이 틀어졌는지가 교정 방향 판단의 실질 정보이기 때문이다. 회전 편차는 ±180° 경계를 넘는 wrap-around 를 정규화해 계산한다.

### 4. 확인 Job 은 학습된 TCP 자세로 이동 후 측정

Context 의 측정 원리 제약에 따른 결정. `move_to_reference` 파라미터(기본 `True`)로 이동 생략도 가능하게 두되 기본값은 이동이다.

### 5. 허용범위·기준값은 `config/positions.yaml` 단일 출처

Job 파라미터에 허용범위를 넣지 않는다. 기준점 확인은 로봇 하드웨어 상태 점검이므로 레시피마다 다른 기준을 쓸 이유가 없고, 두 곳에 값이 있으면 어느 쪽이 적용됐는지 사후 추적이 불가능해진다.

```yaml
reference_check:
  learned_at: '2026-08-10T17:30:00'
  tcp_pose:    {x, y, z, rx, ry, rz}   # 학습 시 로봇 TCP 자세 (RobotBase 기준, mm/deg)
  landmark:    {x, y, z, rx, ry, rz}   # 그 자세에서 측정된 TM mark 좌표 (RobotBase 기준, mm/deg)
  measure:     {repeat_count, outlier_method}
  learned_std: {x, y, z, rx, ry, rz}   # 학습 시 산포 — 허용범위 타당성 참고값
  tolerance:   {xyz: 1.0, rpy: 0.5}    # mm / deg, 각 축 개별
```

`learned_std` 를 남기는 이유: 허용범위를 학습 산포보다 작게 잡으면 정상 상태에서도 알람이 뜬다. GUI 가 산포를 보여줘 설정 근거로 쓴다.

### 6. 신규 공개 함수 (함수표 갱신 대상)

| 함수 | 입력 | 출력 | 기능 |
|---|---|---|---|
| `ReferenceCheckService.has_reference` | — | bool | 학습 여부 |
| `ReferenceCheckService.load_reference` | — | dict\|None | 학습값 로드 |
| `ReferenceCheckService.save_reference` | tcp_pose, landmark, measure, std | bool | 학습값 저장 |
| `ReferenceCheckService.get_tolerance`/`set_tolerance` | xyz, rpy | dict/bool | 허용범위 R/W |
| `ReferenceCheckService.evaluate` | measured dict | ReferenceCheckResult | 6축 개별 판정 |
| `JobExecutor._scan_landmark_averaged` | repeat, outlier, wait | (pose, std)\|None | 반복스캔 공통 helper (중복 3벌화 방지) |
| `JobExecutor._exec_verify_reference_point` | Job | bool | 기준점 확인 Job |
| `RunMonitorTab._validate_reference_check_placement` | Recipe | (bool, str) | 필수 배치 검사 |

전역 가변 상태는 추가하지 않는다. 모든 상태는 `ConfigManager` 경유 파일 + 인스턴스 속성이다.

## Alternatives

- **3D 거리 단일 임계값** — 설정은 가장 단순하나 축별 원인 분석이 불가능해 기각(Decision 3).
- **전역 설정으로 필수 실행 강제** — 레시피별 예외를 둘 수 없어 기각(Decision 2).
- **위반 시 확인 Job 자동 삽입** — 저장 파일과 실행 이력이 어긋나 기각(Decision 2).
- **`CoordinateSystemManager` 확장** — 좌표계 정의와 합불 판정의 책임 혼재로 기각(Context 중복 후보 검토).

## Consequences

**이득**

- 로봇 기구학 드리프트·카메라 이동·마크 변위를 시나리오 실행 전후에 자동 검출한다.
- 반복스캔 로직 3벌화를 막고 기존 2벌을 1벌로 수렴시킨다(함수표 #4c 중복 일부 해소).
- Job 파라미터 GUI 가 스키마에서 자동 생성되므로 UI 배선 부담이 파라미터 쪽에는 없다.

**비용**

- `config/positions.yaml` 에 최상위 키 `reference_check` 가 추가된다 — 기존 키를 건드리지 않는 순수 추가.
- `ui/main_window.ui` 에 위젯 그룹 1개가 추가된다.
- 기존 `_exec_scan_tm_landmark`/`_exec_scan_tm_landmark_jig` 2개 Job 이 helper 호출로 치환된다 — **동작 동일성은 회귀 테스트로 확인해야 하며, 무증거 "동일합니다" 주장은 금지**(CLAUDE.md 핵심원칙 4).

**남는 위험**

- 실기 미검증. 허용범위 기본값(XYZ 1.0 mm / RPY 0.5 deg)은 [jig_plate_validator.py:106-110](../../src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plate_validator.py) 의 기존 임계값에서 가져온 **잠정값**이며, 실제 값은 현장에서 `learned_std` 를 보고 정해야 한다.
- 마크가 로봇 베이스에 대해 물리적으로 움직인 경우와 로봇 기구학이 틀어진 경우를 본 기능만으로는 구분할 수 없다. 알람은 "교정 필요 여부 점검"의 트리거이지 원인 판정이 아니다.
- `JobExecutor` 는 Qt 메인 스레드에서 동기 실행되므로(함수표 §B-3, Medium 결함) 이동+반복스캔 동안 UI 가 멈춘다 — 기존 Landmark Job 과 동일한 성질이며 본 과제로 악화되지도 개선되지도 않는다.

## Rollback

가역. 되돌리는 절차:

1. `RecipeManager.JOB_TYPES` 에서 `verify_reference_point` 항목과 `recipe_info.params.reference_check` 제거
2. `JobExecutor` 의 dispatch 분기·`_exec_verify_reference_point`·`on_reference_alarm` 제거, `_scan_landmark_averaged` 호출부 2곳을 원래 인라인 로직으로 되돌림(git revert 로 충분)
3. `RunMonitorTab._validate_reference_check_placement` 호출 제거
4. `services/reference_check_service.py` 및 `services/__init__.py` export 삭제
5. `ui/main_window.ui` 의 `groupBox_referenceCheck` 및 `SettingsTab` 핸들러 삭제
6. `config/positions.yaml` 의 `reference_check:` 키 삭제 — 다른 키와 독립이므로 제거만으로 원상복구되며, 기존 레시피 파일은 영향 없음(신규 Job 을 쓰지 않는 레시피는 무변경)

되돌린 뒤에도 이미 저장된 레시피에 `verify_reference_point` Job 이 남아 있으면 `_execute_job` 의 `else` 분기가 "알 수 없는 Job 타입" 을 로그하고 `False` 를 반환한다 — 조용한 오동작이 아니라 명시적 실패다.
