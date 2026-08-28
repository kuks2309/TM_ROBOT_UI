# ADR: 팔레트 평면 인식 및 법선 수직 정렬 (align_to_plane_normal / measure_plane_distance)

- 날짜: 2026-07-27 (KST, Korea Standard Time)
- 관련: [worklog 2026-07-27](../worklog/2026-07-27.md), [hand-eye 계획서](../planning/hand-eye-calibration-plan-2026-07-08.md), [ADR hand-eye](2026-07-10-hand-eye-calibration.md), 사용자 지시(2026-07-27 13:22) "팔레트의 TM(Techman) Landmark 4개로 평면 인식 + 평면과 수직으로 엔드이펙터 정렬 + 평면과의 거리 인지"
- 대상: `JobExecutor` 신규 Job 2종 + `jig_plane_calculator` 순수함수 3개 + 웹 브리지 Landmark 실행 경로 개방

## Status

**Proposed (제안 — 사용자 승인 대기).** 승인 전 코드 미작성.

확정된 선행 결정 (사용자, 2026-07-27):
- **검출 경로 = 하이브리드** — TMflow 가 TM Landmark 를 검출해 base 프레임 6-DoF(Degrees of Freedom) 를 반환하고, PC(Personal Computer) 가 평면 계산·수직 정렬·거리 제어를 담당. PC 측 camera calibration · hand-eye 는 본 과제 범위 밖.
- **웹 GUI(Graphical User Interface) 활용** — 기존 웹 브리지·프론트를 재사용하되 Landmark 실행 경로를 개방한다.

## Context

### 요구 (3항)

1. 팔레트에 부착한 TM Landmark **4개**로 팔레트 **평면 인식**
2. 엔드이펙터가 그 **평면과 수직**(평면 법선과 Tool Z축 일치)이 되게 정렬
3. 평면과의 **거리 인지**

### 경로 결정 근거 (1차 소스)

TM Landmark 는 TM 독자 마커(두께 0.2 cm, 5×5 cm 정사각형 알루미늄 판)이며, 흑백 경계선 + 중앙 그래픽 피처를 TMflow 가 인식해 **흑백 경계선 중앙에 6 자유도(X, Y, Z, RX, RY, RZ) 베이스 시스템**을 생성한다 — [TMvision v2.18 문서버전 1.00 (KR), §TM Landmark, page 15](../Software_TMvision_2.18_1.00_KR.pdf). ✓

따라서 ArUco 전용인 자체 검출기([aruco_detector.cpp:15](../../src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp) `DICT_4X4_50`)로는 TM Landmark 를 검출할 수 없고, PC 자체 비전 경로는 마커 교체를 전제해야 한다 → 미채택.

같은 매뉴얼이 TM Landmark 의 **권장 용도를 본 과제와 동일하게** 규정한다 — [TMvision v2.18 문서버전 1.00 (KR), §TM Landmark, page 16](../Software_TMvision_2.18_1.00_KR.pdf): ✓

> "TM Landmark 는 6 개의 자유도로 베이스 시스템을 생성하며 **RX, RY 및 Z 방향**에 있는 데이터는 EIH(Eye-In-Hand) 2D 비전을 통해 정확하게 획득하기 쉽지 않습니다(즉, **카메라 평면이 개체와 평행한지 여부, 카메라 평면과 개체 사이의 거리**). TM Landmark 는 이러한 축을 따라 2D 비전의 위치 지정 능력을 향상시킬 수 있습니다."

동시에 매뉴얼은 정확도 한계를 명시한다 — [TMvision v2.18 문서버전 1.00 (KR), §TM Landmark, page 15](../Software_TMvision_2.18_1.00_KR.pdf): ✓

> "landmark 위치 지정의 정확도는 식별 및 배열 용도로 충분하지 않습니다. 원칙적으로 TM Landmark 는 베이스 시스템을 생성한 후 사용자가 로봇을 개별 지점으로 바로 이동하거나 모션을 실행하도록 설계되지 않았습니다. 대신 이는 로봇을 유효한 시각 지점으로 인도하는 **배열 툴**입니다."

⇒ 본 과제의 산출물은 **개략 정렬·접근용**으로 성격을 못박고, 최종 정밀 작업은 별도 수단(2D 비전 기능, 힘제어)에 위임한다. 목표 오차는 §미결 질문 1 로 남긴다.

### 기존 자산 (동작 확인됨)

| 요소 | 위치 | 상태 |
|---|---|---|
| Landmark 4개 스캔 Job `scan_tm_landmark_jig`(jig 1~4 → `g_robot_command` 4~7) | [job_executor.py:1801](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py), [vision_manager.py:363](../../src/TM_Robot_Task_Manager/tm_task_manager/services/vision_manager.py) · [:491](../../src/TM_Robot_Task_Manager/tm_task_manager/services/vision_manager.py) | 동작 (PyQt5 앱) |
| 평면 pose 계산 Job `calculate_plate_pose` | [job_executor.py:1872](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py) | 동작 |
| 4점 → 평면 중심·ZYX Euler 산출 `JigPlaneCalculator.calculate_plane_pose` (Z축 = X×Y 외적 = 법선) | [jig_plane_calculator.py:141-199](../../src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plane_calculator.py) | 동작 |
| 자세유지 직선 이동(구간 분해·하강 감속) | [job_executor.py:900](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py) · [:868](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py) | 실기 검증 완료(2026-07-27) |
| LINE_T 전송 `_move_to_position_line` | [job_executor.py:457](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py) | 동작 |

### 현 격차 (실측)

1. **평면 pose 가 모션으로 이어지지 않음** — `detected_plate_pose` 는 [job_executor.py:1909](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py) 에서 대입될 뿐 **읽는 곳 0곳**(grep: 정의 78행 + 대입 1909행뿐). 요구 2·3 을 수행하는 코드가 없다.
2. **웹 브리지에서 Landmark 실행 불가 (2건)**
   - `SEQUENCE_WHITELIST` 6종에 Landmark 계열 전무 → 실행 시 `"v1 미지원 잡"` 거부 ([bridge_node.py:35-42](../../src/tm_web_bridge/tm_web_bridge/bridge_node.py) · [:249-255](../../src/tm_web_bridge/tm_web_bridge/bridge_node.py))
   - `BridgeJobExecutor(ros_node=self)` 로만 생성 → `vision_manager=None` ([bridge_node.py:87](../../src/tm_web_bridge/tm_web_bridge/bridge_node.py), 시그니처 [job_executor.py:50](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py)). 스캔 Job 두 개가 첫 줄에서 `if not self.vision_manager: return False` ([job_executor.py:1728](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py) · [:1819](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py))
   - 브리지에 `GlobalVariableScript` 인스턴스 없음 (grep 0건) — VisionManager 의 전제
   - **PyQt5 는 장애물이 아님**: 브리지가 이미 `RobotMotionService()`·`TeachingService()` 두 QObject 서비스를 헤드리스로 인스턴스화해 운영 중 ([bridge_node.py:61-62](../../src/tm_web_bridge/tm_web_bridge/bridge_node.py))

### 중복 조사 (coding SOP §2)

**재사용 (신규 작성 안 함)**

| 필요 기능 | 기존 구현 | 위치 |
|---|---|---|
| 4점 → 평면 중심·자세 | `JigPlaneCalculator.calculate_plane_pose` | jig_plane_calculator.py:141 |
| 회전행렬 → ZYX Euler | `JigPlaneCalculator._rotation_matrix_to_euler_zyx` | jig_plane_calculator.py:201 |
| Euler → 회전행렬 | `CoordinateTransformer.euler_to_rotation_matrix` | coordinate_transformer.py:41 |
| 4×4 변환행렬 생성·pose 추출 | `_create_transform_matrix` / `_extract_pose` | job_executor.py:314 · :339 |
| 마크 간 거리행렬(무결성 검사용) | `JigPlaneCalculator.calculate_distance_matrix` | jig_plane_calculator.py:294 |
| LINE_T 전송 | `_move_to_position_line` | job_executor.py:457 |
| 자세유지 구간 분해 · 하강 감속 | `_build_pose_keep_segments` / `_build_descent_segments` | job_executor.py:900 · :868 |
| 자세 편차 로깅 | `_log_orientation_deviation` | job_executor.py:946 |
| 속도 % → 서비스 물리단위 | `CoordinateTransformer.velocity_percent_to_service` | coordinate_transformer.py:25 |

**중복 후보 — 사용 안 함 (사유 명시)**

- `JigPlateValidator.calculate_center`([jig_plate_validator.py:385](../../src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plate_validator.py)) 는 `JigPlaneCalculator` 의 중심 계산과 기능이 겹치나, 해당 파일은 matplotlib · PyQt5 GUI 도구라 Job 실행 경로에 부적합. **평면 계산 SSOT(Single Source of Truth) 는 `JigPlaneCalculator` 로 유지**한다. (중복 자체는 기존 상태 — 본 ADR 로 새로 만들지 않을 뿐. 통합 여부는 `debt` 등록 대상 → §미결 질문 3)
- `JigPlateValidator.check_plane_parallelism`([:274](../../src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plate_validator.py)) 은 Ry 값 비교만 하는 GUI 검사라 법선 각도 검증에 재사용 불가.

**신규 필요 (활성 코드 0건 확인)**

- 점 → 평면 **부호 있는 수직 거리**: grep 0건
- 평면 **법선 → TCP(Tool Center Point) 목표 자세** 변환: 0건. (`_exec_align_to_ar_tag`([job_executor.py:1385-1435](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py))에 `target_rx = 180.0 + ar_rx` 형태의 근사가 있으나 **미동작 스텁**(`return True # 임시`)이고 수학적으로도 일반 법선에 대해 성립하지 않음 → 참조만, 재사용 안 함.)
- 4 Landmark 배치 무결성 게이트: 0건 (validator 는 GUI 전용)

## Decision

**신규 Job 2종 + 순수함수 3개 추가. 기존 Job·기존 로직 무수정.** 웹 브리지는 Landmark 실행 경로 개방(추가만).

### 원리

```
[1] scan_tm_landmark_jig ×4   (기존)  → jig_landmark_results[1..4]  (base 프레임 6-DoF)
[2] calculate_plate_pose      (기존)  → detected_plate_pose {x,y,z,rx,ry,rz}
[3] align_to_plane_normal     (신규)  → 평면 법선 n 산출 → Tool Z가 -n 을 향하는 자세로 정렬
                                       → 자세 유지한 채 평면 중심 위 standoff 거리로 이동
[4] measure_plane_distance    (신규)  → 현재 TCP → 평면 부호거리 계산·로깅 (로봇 무동작)
```

평면 법선 n 은 `detected_plate_pose` 의 ZYX Euler 를 회전행렬로 되돌린 **3번째 열**이다 — `JigPlaneCalculator` 가 Z축을 X×Y 외적으로 잡았으므로([jig_plane_calculator.py:172](../../src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plane_calculator.py)) 정의상 평면 법선이다.

### 신규 순수함수 3개 — `tools/jig_plane_calculator.py` 에 모듈 레벨 추가

평면 기하 SSOT 를 한 파일로 유지하기 위해 신규 파일을 만들지 않는다(같은 단위 규약: 위치 mm, 각도 deg, ZYX Euler). 파일명이 `jig_` 이지만 **팔레트를 포함한 일반 평면**에 적용됨을 docstring 에 명시한다.

| 함수 | 시그니처 | 역할 |
|---|---|---|
| `plane_normal_from_pose` | `(pose: Dict) -> np.ndarray` | 평면 pose → 단위 법선 벡터 (회전행렬 3번째 열) |
| `signed_point_to_plane_distance` | `(point: Tuple[float,float,float], plane_pose: Dict) -> float` | 점 → 평면 부호 거리 (mm). 양수 = 법선 방향 쪽 |
| `tcp_pose_for_plane_normal` | `(plane_pose: Dict, standoff_mm: float, rz_mode: str, current_tcp: List[float]) -> Dict` | 평면 중심에서 법선 방향으로 `standoff_mm` 떨어진 지점 + Tool Z가 평면을 향하는 자세 |

`tcp_pose_for_plane_normal` 의 자세 산출:
- Tool Z축 = **-n**(평면을 바라봄)
- 평면 내 회전(Rz)은 자유도가 남으므로 `rz_mode` 로 결정
  - `keep`(기본) — 현재 TCP 의 Rz 를 최대한 보존(불필요한 손목 회전 방지)
  - `plane` — 평면 좌표계 X축을 따름(`plane_pose.rz` 사용)
- 산출된 회전행렬 → `JigPlaneCalculator._rotation_matrix_to_euler_zyx` **재사용**으로 (Rx, Ry, Rz) 반환

### 신규 Job A — `align_to_plane_normal` ("평면 수직 정렬")

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `standoff_mm` | 150.0 | 평면 중심에서 법선 방향으로 떨어질 거리 (mm, 양수 필수) |
| `rz_mode` | `keep` | 평면 내 회전 처리 (`keep` / `plane`) |
| `velocity` | 10.0 | 이동 속도 (%) |
| `max_tilt_deg` | 30.0 | 법선이 base −Z 축에서 벗어난 각도 상한. 초과 시 **거부**(스캔 오류 방어) |
| `decel_zone_mm` | 40.0 | 접근 감속 구간 (기존 `pose_keep` 과 동일 의미, 0 = 없음) |
| `decel_velocity` | 10.0 | 감속 구간 속도 (%) |

**모션 2단계** (기존 검증된 패턴 재사용):
1. **제자리 자세 정렬** — 현재 XYZ 고정, 자세만 목표로. `_move_to_position_line`(LINE_T) 사용. PTP(Point To Point) 를 쓰지 않는 이유는 관절보간이 경로 중간 TCP 위치를 흔들기 때문(2026-07-27 ADR §Context 1 과 동일 근거).
2. **자세 유지 접근** — `_build_pose_keep_segments` + `_build_descent_segments` 재사용으로 standoff 지점까지 이동. ①에서 자세가 이미 정렬됐으므로 lock 자세가 곧 목표 자세다.

### 신규 Job B — `measure_plane_distance` ("평면 거리 측정")

- 파라미터 없음. **로봇 무동작**.
- 현재 TCP 위치 → `signed_point_to_plane_distance` → 로그 + `self.measured_plane_distance` 에 저장.
- 법선과 Tool Z축의 사이각도 함께 로깅(수직 정렬 품질 확인용).

### 웹 브리지 개방 (3건, 추가만)

| # | 파일 | 변경 |
|---|---|---|
| 1 | `bridge_node.py` | `GlobalVariableScript(self)` + `VisionManager(gv_manager=…, ros_node=self)` 생성 후 `BridgeJobExecutor(ros_node=self, vision_manager=…)` 로 주입 (PyQt5 QObject 는 기존 2개 서비스와 동일 패턴) |
| 2 | `bridge_node.py` | `SEQUENCE_WHITELIST` 에 `scan_tm_landmark_jig`, `calculate_plate_pose`, `align_to_plane_normal`, `measure_plane_distance` 추가. 속도 30% clamp 는 기존 generic 로직이 자동 적용 |
| 3 | `TaskEditor.tsx` | `taskTree` 에 신규 2종 추가(Landmark 카테고리). 파라미터 편집 UI 는 `/tasks/schema` → `RecipeManager.JOB_TYPES` 로 자동 생성되므로 별도 작업 없음 |

### 안전 가드

- `detected_plate_pose` 부재 시 거부 (`calculate_plate_pose` 선행 강제)
- 4 Landmark **배치 무결성 게이트**: `calculate_distance_matrix` 의 대각선 2쌍(`d_1_4`, `d_2_3`) 차이가 임계 초과면 거부 — 마크 순서 오배치·오검출 방어
- **법선 기울기 상한** `max_tilt_deg` 초과 시 거부
- 좌표계가 `RobotBase` 가 아니면 거부 (기존 `pose_keep_move_to_point` 와 동일 규칙)
- `standoff_mm <= 0` 거부 (평면 안쪽으로 파고드는 명령 차단)
- 실패 시 **PTP 폴백 없이 즉시 중단** (폴백하면 정렬이 깨짐)
- 기본 속도 10%, 실모션은 사용자 입회·저속 원칙(2026-07-08 과속 사고 규칙) 유지

### 설계 결정 세부 / 미채택

- **`align_tm_landmark`(기존) 확장 안 함** — 그것은 단일 Landmark 자세만 맞추는 Job([job_executor.py:1469](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py))이라 4점 평면과 의미가 다르다. 기존 레시피 회귀를 피해 신규 Job 으로 분리.
- **`LandmarkAlignService`(TMflow Vision Base + ChangeBase) 사용 안 함** — 단일 Landmark 의 Vision Base 기준이라 4점 평면에 적용 불가([tm_landmark_align_service.py:192-234](../../src/TM_Robot_Task_Manager/tm_task_manager/services/tm_landmark_align_service.py)). 좌표계 전환 부작용도 회피.
- **스리-TM 랜드마크(TMflow 내장, 3개·3~6배 정확) 미채택** — 사용자 요구가 4개이고, 채택 시 작업 주체가 TMflow 설정으로 옮겨간다. 정밀도 미달 시 대안으로 재검토(→ §미결 질문 1).
- **거리 측정을 Job A 에 합치지 않음** — "인지"(측정·표시)와 "정렬 이동"은 안전 성격이 달라 분리. 측정 Job 은 무동작이라 모션 게이트 없이도 안전하게 반복 호출 가능.
- **camera calibration · hand-eye 미포함** — 하이브리드 경로에서는 TMflow 가 base 프레임 좌표를 주므로 원리상 불필요. 단 `aruco_params.yaml` 의 placeholder intrinsic 불일치는 별건으로 남는다(→ §미결 질문 4).

## Consequences

**긍정**

- 요구 3항이 기존 자산 위에서 연결된다 — 신규 코드는 순수함수 3개 + Job 2개로 국한.
- 순수함수 3개는 로봇 없이 합성 데이터로 단위 테스트 가능(법선·거리·목표자세 왕복 검증).
- 웹 브리지 개방으로 **Landmark 계열 기존 Job 5종도 함께 웹에서 실행 가능**해진다(부수 이득).
- 기존 Job 무수정 → 기존 레시피 동작 불변.

**부정·비용**

- **TM 내장 보정 정확도에 종속**되며 우리가 검증할 수 없다. 매뉴얼이 "개별 지점 이동용으로 설계되지 않았다"고 명시하므로([TMvision v2.18 문서버전 1.00 (KR), §TM Landmark, page 15](../Software_TMvision_2.18_1.00_KR.pdf)) 정밀 작업에는 후속 수단이 필요하다.
- 브리지가 VisionManager·GlobalVariableScript 를 갖게 되어 **브리지 ↔ tm_task_manager 결합이 늘어난다**(현재 3서비스 → 5).
- 브리지에서 Landmark 스캔이 가능해지면 **TMflow 글로벌 변수 채널을 웹에서 건드릴 수 있게 된다** — 신뢰경계 확대. 화이트리스트 외 잡 차단은 유지되나, 스캔 자체가 로봇 비전 잡을 구동한다는 점은 새 노출면이다.
- 구간 경계 정지(blend 0)로 사이클 타임 증가(기존 `pose_keep_move_to_point` 와 동일 특성).

**미검증 (실기 대기)**

- **법선 부호 방향** — `JigPlaneCalculator` 의 Z축(X×Y)이 팔레트 위쪽인지 아래쪽인지는 마크 배치 순서에 의존한다([jig_plane_calculator.py:7-10](../../src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plane_calculator.py) 규약: Mark1 좌하 / 2 좌상 / 3 우하 / 4 우상). **부호가 반대면 로봇이 팔레트 쪽으로 접근한다** → 실기 전 무동작 로그로 부호 확정이 **필수 게이트**.
- 실제 정렬 오차·거리 오차 수치
- 팔레트 위 4개 Landmark 의 TMflow 비전 잡(`g_robot_command` 4~7) 설정 여부 — 로봇 측 작업

## Rollback

**가역 (영속 상태·스키마 마이그레이션 없음).** 되돌림 = 추가분 삭제:

1. `job_executor.py` — `_exec_align_to_plane_normal` · `_exec_measure_plane_distance` · `_execute_job` 분기 2줄 · 상태변수 `measured_plane_distance` 삭제
2. `jig_plane_calculator.py` — 모듈 함수 3개 삭제 (기존 클래스 무수정이므로 클래스는 영향 없음)
3. `recipe_manager.py` — `JOB_TYPES` 항목 2개 삭제
4. `tabs/task_edit_tab.py` — 단독 실행 분기·래퍼 삭제
5. `bridge_node.py` — whitelist 4줄 + VisionManager/GlobalVariableScript 생성·주입 삭제 (삭제하면 `vision_manager=None` 인 현재 상태로 복귀)
6. `TaskEditor.tsx` — `taskTree` 2줄 삭제
7. 신규 테스트 파일 삭제

**안전 폴백**: `detected_plate_pose` 미존재 · 무결성 게이트 실패 · 기울기 상한 초과 중 하나라도 걸리면 Job 은 `return False` + 사유 로그로 **실이동을 하지 않는다**. 즉 캘리브/스캔이 안 된 상태에서 코드만 있어도 로봇은 움직이지 않는다.

**주의**: 되돌리기 전 이 Job 을 사용한 레시피 YAML 이 있으면 해당 Job 은 "알 수 없는 Job 타입"으로 실패한다(레시피 편집 필요). 레시피 파일 자체는 손상되지 않는다.

## Verification (never-self-approve)

- **단위 테스트(로봇 무동작)** — 순수함수 3개: 합성 평면(수평·기울어진 평면)에 대해 법선·거리 해석해 일치, `tcp_pose_for_plane_normal` 결과를 다시 법선으로 환산했을 때 왕복 일치, `rz_mode` 두 모드 동작, 거부 조건 5가지, Job 라우팅.
- **무동작 실기 게이트 (실모션 전 필수)** — 팔레트에 Landmark 4개 부착 → `scan_tm_landmark_jig` ×4 → `calculate_plate_pose` → `measure_plane_distance` 로 **법선 부호·거리 부호를 로그로만 확인**. 여기서 부호가 기대와 다르면 코드 수정 후 재확인. **이 게이트 통과 전 Job A 실행 금지.**
- **실기 정렬 검증** — 사용자 입회·저속(5~10%)·standoff 충분히 크게. 정렬 후 `measure_plane_distance` 의 사이각이 0 에 수렴하는지, 거리가 `standoff_mm` 과 일치하는지 실측.
- **전체 회귀** — `pytest test/` 기존 통과 수 유지(현재 기준선: 65 passed / 1 failed — 실패 1건은 `scan_ar_tag` 카테고리 기대값 불일치로 본 변경과 무관한 기존 실패), `colcon build --packages-select tm_task_manager tm_web_bridge` 성공, `npx tsc -b` 0 errors(프론트 변경 시).
- **checks** — `banned-pattern.sh`, `adr-fields.sh` 통과.
- 최종 verdict 는 저자 self-approve 금지 — 별도 리뷰 패스(`code_review` 또는 사람).

## 이식성 (다른 TM 로봇으로 옮길 때) — 사용자 질의 2026-07-27 14:1x

### 캘리브레이션 재수행 여부

- **내장 EIH 카메라는 생산(공장) 보정 상태** — "카메라의 기본 해상도는 5M 픽셀이며 생산 보정 픽셀도 동일합니다. 고정 지점과 Landmark 에서 5M 픽셀 위치 지정이 지원됩니다" ([TMvision v2.18 문서버전 1.00 (KR), 표 3 참고, page 20](../Software_TMvision_2.18_1.00_KR.pdf)) ⇒ 로봇을 바꿔도 **사용자 카메라 보정 불요**. ✓
- 대조: 외부(ETH) 카메라는 고유 매개변수 보정이 명시적으로 필수 ([같은 문서, page 97](../Software_TMvision_2.18_1.00_KR.pdf)) — 본 경로는 내장 EIH 라 해당 없음. ✓
- 작업 공간 보정은 "**고정 지점 비전 작업에 대해**" 작업 공간을 생성하는 절차 ([같은 문서, page 21](../Software_TMvision_2.18_1.00_KR.pdf)). 랜드마크 위치 설정 고유 파라미터(표 7, [page 32](../Software_TMvision_2.18_1.00_KR.pdf))에 작업 공간 항목 없음. ✓
- ⚠ **미확인**: page 31 이 랜드마크 잡의 Motion/Camera 파라미터를 "3.2.1 고정된 지점 참조"로 위임하는데 그 표에 "작업 공간 설정" 항목이 있다. 매뉴얼이 랜드마크에 대해 "작업 공간 불필요"를 명시하지 않았다 → **TMflow 화면 실물 확인 필요**(현장 확인으로 즉시 판정 가능).

### 프로젝트 전송

- "빌드 날짜, 마지막 업데이트 날짜, 마지막 실행 날짜는 프로젝트 **가져오기/내보내기를 따라 다른 로봇에 전송됩니다**" ([TMflow v2.18 문서버전 1.02 (KR), §실행 설정, page 63](../Software-Manual-TMflow_SW2.18_Rev1.02_KR.pdf)) ✓
- 전송 대상에 `Projects\` · `GlobalVariable.zip` · `TCP.zip` · `EthSlave\` 포함, 경로 `TMROBOT\TM_Export\{RobotID}\` ([표 12, page 108](../Software-Manual-TMflow_SW2.18_Rev1.02_KR.pdf)) ✓ — 본 워크스페이스 [TM_Export/CC2432022_CA2432022/](../../TM_Export/CC2432022_CA2432022/) 가 정확히 이 구조(`Projects/ROS2_COM1.zip`, `GlobalVariable.zip`)
- ⚠ **제약**: "가져온 백업 파일은 압축되고 암호화됩니다 / 가져오는 동안 **컴퓨터 ID 및 로봇 ID 를 확인**합니다" ([같은 표 12 참고, page 108](../Software-Manual-TMflow_SW2.18_Rev1.02_KR.pdf)). 실측으로도 `unzip` 이 표준 ZIP 으로 열지 못함 → **타 로봇 임포트가 ID 검사에 걸리는지 실기 확인 필요**.

### 본 설계의 이식 결합점

- PC 측 로봇 종속 상수는 **IP 하나뿐**. Landmark 결과를 글로벌 변수로 읽는 구조라 로봇 교체에 중립.
- **단 `jig_number → g_robot_command = 3 + N` 규약**([job_executor.py:1826](../../src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py))이 TMflow 프로젝트 쪽 비전 잡 배치와 짝을 이룬다 → 이식 시 **PC 코드와 TMflow 프로젝트를 함께** 옮겨야 한다. 이 결합은 기존 구조에서 상속된 것으로 본 ADR 이 새로 만들지 않는다.

### 범위 경계 — "Landmark 로 물체 인식 후 pick & place" 는 절반

매뉴얼이 축 담당을 나눈다 ([TMvision v2.18 문서버전 1.00 (KR), §TM Landmark, page 16](../Software_TMvision_2.18_1.00_KR.pdf)): ✓

| 담당 | 축 |
|---|---|
| TM Landmark | RX, RY, Z (평면 평행 + 거리) |
| TMvision 2D 기능 | X, Y, RZ (물체 실제 위치) |

> "TM Landmark 가 X, Y 및 RZ 방향을 획득할 수 있음에도 불구하고 ... 데이터를 위치 지정에 대해 직접적으로 사용하지 않는 것이 좋습니다 ... 그런 다음 사용자가 후속 2D 비전 작업에 대한 기본으로 이 배치를 사용하며 TMvision 2D 기능을 통해 X, Y 및 RZ 의 남은 축 방향을 배열할 수 있습니다."

⇒ 본 ADR 의 산출물은 **앞 절반(Landmark: 평면 정렬 + 거리)** 이다. Pick & place 까지 가려면 뒷 절반(2D 비전 물체 인식)이 **별도 트랙**으로 필요하며, 이식 시에도 양쪽을 함께 옮겨야 동일 작업이 성립한다. 앞 절반은 팔레트·로봇이 바뀌어도 재사용되는 공통 기반이다.

## 미결 질문 (사용자 확인 필요)

1. **목표 오차** — 매뉴얼이 TM Landmark 를 "배열 툴"로 규정하므로(page 15) 정밀 조립급은 기대하기 어렵다. 1차 목표를 어디로 잡을지 (참고: [계획서 §11 기준표](../planning/hand-eye-calibration-plan-2026-07-08.md) — 개략 접근 ±5~10 mm / 일반 pick&place ±1~3 mm). 미달 시 스리-TM 랜드마크 전환을 재검토.
2. **standoff 기본값 150 mm** 이 팔레트 작업 거리로 적절한지. 매뉴얼은 "카메라와 Landmark 거리가 짧을수록 정확도가 높다"고 하며 근접 재촬영(예: 10 cm)을 권장한다 — [TMvision v2.18 문서버전 1.00 (KR), §TM Landmark 참고, page 17](../Software_TMvision_2.18_1.00_KR.pdf). ✓
3. **`JigPlateValidator` ↔ `JigPlaneCalculator` 중심계산 중복**을 `debt` 에 등록할지(본 ADR 범위 밖, 식별만).
4. **`aruco_params.yaml` placeholder intrinsic 불일치**(615/320/240 vs 실측 2677/1240/1003)를 별건으로 처리할지 — 본 경로에서는 미사용이나 방치 시 향후 함정.

## WBS (Work Breakdown Structure) — 승인 후 착수 순서

1. (S) `jig_plane_calculator.py` 순수함수 3개 + 단위 테스트 — 로봇 불필요
2. (S) `recipe_manager.py` `JOB_TYPES` 2종 스키마
3. (M) `job_executor.py` `_exec` 2종 + 안전 가드 + `_execute_job` 분기 + 단위 테스트
4. (S) `tabs/task_edit_tab.py` 단독 실행 분기
5. (S) `bridge_node.py` VisionManager 주입 + whitelist
6. (S) `TaskEditor.tsx` taskTree
7. (M) 무동작 실기 게이트(법선 부호 확정) → 사용자 입회 실기 검증

각 단계는 coding SOP 절차(사전조사 → 구현 → 검증 → 이중기록)를 따른다.
