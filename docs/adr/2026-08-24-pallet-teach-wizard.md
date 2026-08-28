# ADR 2026-08-24 — 팔레트 티칭 마법사 (한 탭 버튼 워크플로우)

- Status: Accepted
- Date: 2026-08-24 (KST)
- Deciders: 사용자 승인 (탭 위치 = MK2 데스크탑 PyQt · 측정 정밀도 = 기존 MK2 방식)

## Context

팔레트를 새로 등록하려면 지금까지 사람이 (a) `pallet0_cali.yaml` 을 복사해 마커 간격
오프셋을 손으로 고치고, (b) 측정 후 좌표를 눈으로 읽어, (c) `_pick.yaml`·`_place.yaml`
을 손으로 써야 했다. 팔레트가 6개(`pallet0`~`pallet5`)로 늘면서 이 수작업이 반복
비용이자 오기 위험이 됐다.

목표는 **한 탭에서 버튼만 눌러** 다음이 끝나는 것이다:

1. 고정식/비고정식 선택 + 마커 간격 입력
2. (비고정식) 위치 마커 촬영·저장
3. 1사분면 마커로 조그 → 4점 측정 승인
4. 자동 4점 측정 → 평면 중심 위로 자동 이동
5. 조그로 상세 티칭 (박스가 가드에 닿지 않고 면에 안착하는 자세)
6. 이름 입력 → 픽앤플레이스 레시피 자동 생성

## Decision

### D1. 오케스트레이터를 새로 만들지 않고 **매크로 계층**에 등록한다

`macros/base.py` 가 이미 칠판(blackboard)·선행조건 검사·정적 순서 검증을 제공한다
(ADR 2026-08-11). `run_macro` 는 `blackboard_requires` 미충족 시 실행 **전에** 막고,
`validate_sequence` 는 Job 정의 시점에 순서 오류를 잡는다. 별도 마법사 서비스를
만들면 이 셋을 재구현하게 되므로 매크로 6개로 나눈다.

    pallet_capture_marker    → position_marker_pose, marker_view_tcp  (비고정식만)
    pallet_scan_4corners     → plate_pose, plate_marks, scan_start_tcp   ┐ 둘 중 하나
    pallet_load_measurements → plate_pose, plate_marks, measurement_sources ┘
    pallet_center_approach   → approach_pose      (requires plate_pose)
    pallet_capture_teach     → teach_poses        (requires plate_pose)
    pallet_emit_recipes      → recipe_paths       (requires plate_pose, teach_poses)

`plate_pose` 를 만드는 매크로가 둘이고 뒤 단계는 그것만 요구하므로, 실측 경로와
파일 경로가 **뒤 단계를 공유**한다 — 분기는 칠판이 흡수한다.

### D2. 좌표 계산은 **기존 헬퍼를 재사용**한다 (신규 수학 0줄)

`tools/jig_plane_calculator.py` 와 `tools/landmark_frame.py` 에 필요한 변환이 전부 있다:

| 필요 | 재사용 함수 |
| --- | --- |
| 평면 중심 위 standoff 자세 | `tcp_pose_for_plane_normal` |
| 티칭 TCP → 평면 상대 | `pose_in_plane_frame` |
| 티칭 TCP → 마커 상대 | `pose_in_landmark_frame` |
| 4점 → 평면 pose | `JigPlaneCalculator.load_from_dicts` + `to_dict` |

### D3. 레시피는 **절대좌표로 박지 않고** 기존 상대이동 잡을 쓴다

| 마운트 | 픽/플레이스 잡 | 기준 프레임 |
| --- | --- | --- |
| 고정식 | `move_to_plane_pose` | 4점으로 만든 평면 (중심·법선) |
| 비고정식 | `move_to_landmark_pose` (`frame_mode: rz_only`) | 위치 마커 1점 |

절대 TCP 를 박으면 팔레트가 1mm 만 움직여도 무효가 된다. `rz_only` 를 쓰는 이유는
스키마 설명대로 마커 rx/ry 측정 산포가 레버암에서 증폭되지 않기 때문이다.

발행물:

    고정식   <name>_cali.yaml · <name>_pick.yaml · <name>_place.yaml
    비고정식 <name>_marker_scan.yaml · <name>_pick.yaml · <name>_place.yaml

고정식이라도 저장된 측정 파일로 평면을 만든 경우에는 cali 를 빼고 2개만 낸다 (→ D6-1).

### D4. 탭 UI 는 **코드로 만들고 `addTab()` 으로 붙인다** (기존 탭과 다름)

다른 탭은 `ui/*.ui` 를 `uic.loadUi` 로 읽어 `main_window.ui` 의 placeholder 에 붙는다.
이 탭만 코드로 위젯을 만들어 `tabWidget_main.addTab()` 한다 — `main_window.ui` 는 Qt
Designer 생성 XML 이라 손으로 패치하면 다른 탭까지 깨질 위험이 있고, 마법사는 위젯이
단순해 코드로 충분하다. **의도된 예외이며, 위젯이 복잡해지면 `.ui` 로 옮긴다.**

### D5. 마법사는 **자기 칠판을 소유**한다

`JobExecutor.macro_blackboard` 를 쓰면 사용자가 마법사 도중 다른 레시피를 돌리는 순간
`run_from()` 이 칠판을 비워 측정 결과가 사라진다. 탭이 dict 를 들고
`MacroContext(executor, blackboard)` 로 주입한다.

### D6-1. 저장된 측정 파일로 4점 측정을 **대체하는 경로**를 둔다 (2026-08-24 추가)

같은 팔레트를 이미 여러 번 측정해 뒀다면(`data/plate_pose_calc/<pallet>/*.yaml`)
6분짜리 재측정을 반복할 이유가 없다. `pallet_load_measurements` 가 파일을 골라
**outlier 제거 후 평균**내 `plate_pose` 를 만들고, 그 뒤 단계(중심 접근 → 티칭 →
발행)는 실측 경로와 완전히 같다. 로봇을 움직이지 않는다.

outlier 제거에 `average_landmarks_from_files` 를 쓰지 **않는다** — 그 함수는 단순
평균이라 한 번 튄 측정이 그대로 중심을 끌고 간다. 대신 꼭짓점마다
`LandmarkAnalyzer` 를 물려 스캔 반복에 쓰는 것과 **같은 규칙**(iqr·3sigma)을 파일
간에도 적용한다.

파일 고르기는 **네이티브 파일 창**(`QFileDialog.getOpenFileNames`)으로 한다 —
드래그·Shift·Ctrl 다중 선택이 공짜로 따라오고 사용자가 이미 아는 조작이다. 파일명
접두어 입력칸은 두지 않는다(사용자 지시 2026-08-24). 매크로의 `file_prefix` 파라미터는
레시피·프로그램 호출용으로 남긴다.

이 경로에는 실측 시작 자세가 없으므로 고정식이라도 `_cali.yaml` 을 **발행하지
않는다**(발행물 2개). 그 파일들을 만든 cali 레시피가 이미 있다는 뜻이고, 없는
자세를 지어내면 그 레시피가 엉뚱한 곳으로 간다.

### D5-1. 중심 접근은 **팔레트에 정렬**한다 (기본 `rz_mode='plane'`, 2026-08-24 지시)

`tcp_pose_for_plane_normal` 은 공구 Z 를 항상 `-법선` 으로 놓으므로 **기울기는
`rz_mode` 와 무관하게** 평면을 따른다 — 공구 면이 팔레트 면과 평행해진다
(실측: 공구 Z ↔ 법선 각차 1.2e-06°, 사실상 0). `rz_mode` 가 정하는 것은 **법선축
둘레의 회전**뿐이다.

기본값을 `keep`(현재 공구 회전 유지) → **`plane`(팔레트 긴 변 정렬)** 으로 바꾼다.
티칭 시작 자세가 팔레트에 맞춰져 있어야 조그가 적게 든다.

실측 대조 (pallet0 13개 평균, 평면 Rz 89.576 · 기울기 0.270°):

| rz_mode | Rx | Ry | Rz | 공구Z↔법선 |
| --- | --- | --- | --- | --- |
| keep | 179.739 | 0.066 | −90.000 | 0.0000° |
| plane | 179.936 | −0.262 | **179.576** | 0.0000° |

`plane` 의 Rz 179.576 = 평면 Rz 89.576 + 90 (평면 Y축 = 긴 변 정렬). Rx/Ry 가 180/0
에서 벗어난 것이 기울기 0.270° 를 따라간 결과다. 화면에서 `keep` 도 고를 수 있다.

### D6-2. 측정 정밀도는 **기존 MK2 방식**을 유지한다 (사용자 결정)

`scan_tm_landmark_jig` 10회 + 3sigma — `pallet0`~`pallet5` 가 이미 쓰는 검증된 경로다.
KJW 워크스페이스의 근접 스캔(각도 잡음 9배 개선)은 이식 비용이 커 이번 범위에서 뺀다.

## Consequences

**좋아지는 것**

- 팔레트 등록이 수작업 YAML 편집에서 버튼 6번으로 바뀐다
- 티칭이 평면/마커 상대값이라 팔레트를 옮겨도 재측정만 하면 재사용된다
- 매크로 레지스트리가 2개 → 8개로 늘어 레시피에서도 조합할 수 있다
- 이미 측정해 둔 팔레트는 재측정 없이 티칭만 다시 할 수 있다 (6분 → 즉시)

**감수하는 것**

- 탭 UI 가 `.ui` 파일 규약에서 벗어난다 (D4 — 의도된 예외)
- `pitch_x`/`pitch_y`(마커 간격) 를 사람이 입력해야 한다. 1사분면에서 나머지 3점까지의
  거리를 모르면 순회할 수 없고, MK2 에는 KJW 의 `plan_pallet_corners` 가 없다
- 4점 측정 중 UI 는 작업 스레드로 넘기지만 로봇 이동 자체는 취소 지점이 잡 경계뿐이다

**Rollback Plan**

되돌림은 파일 삭제 + 앵커 2곳 원복으로 끝난다 (영속 스키마 변경 없음):

1. `tm_task_manager/macros/pallet_teach.py`, `services/pallet_recipe_generator.py`,
   `tabs/pallet_teach_tab.py`, `test/test_pallet_teach.py` 삭제
2. `macros/__init__.py`, `tabs/__init__.py`, `main_window.py` 를 같은 폴더의
   `*.bak_before_pallet_teach` 로 복원
3. `python3 scripts/generate_macro_catalog.py` 재실행
4. 이미 발행된 `config/recipes/<name>/` 은 **그대로 둔다** — 일반 레시피라 본 기능
   없이도 실행된다

## 검증 (2026-08-24)

- 신규 테스트 `test/test_pallet_teach.py` — **37 passed** (탭 배선 offscreen 4건 + 정렬 5건 포함)
- 전체 회귀 — **762 passed, 1 failed**
- 실제 저장 데이터 대조: `data/plate_pose_calc/pallet0` 13개 평균 → 중심
  X817.652 Y215.032 (개별 파일의 `plate_pose.x: 817.691` 과 정합), `pallet4` 10개도 동일 확인
- 그 1건(`test_recipe_manager.py::test_manager_get_job_types_by_category`, `scan_ar_tag`
  카테고리)은 **본 변경 이전부터 실패**한다. 본 ADR 의 import 를 끄고 단독 실행해도
  동일하게 실패함을 확인했다 — 별도 결함으로 `docs/debt/registry.md` 소관
- 최종 verdict 는 저자가 찍지 않는다 (coding SOP §5 never-self-approve) — 실기 동작
  확인과 리뷰 승인은 별도 lane 이 렌더한다

## 미검증 (실기 필요)

본 변경은 **로봇 없이** 검증했다. 다음은 실기에서 확인해야 한다:

- 4점 순회 이동이 팔레트·가드와 간섭하지 않는지
- `move_to_plane_pose` 의 `max_radius_mm` 자동 산출값이 실제 티칭 지점을 거부하지 않는지
- 비고정식에서 `max_age_min: 30` 이 현장 운용 리듬에 맞는지
- 파일 경로로 만든 평면이 실측 평면과 실제로 같은 결과를 내는지 (팔레트를 옮긴 뒤의
  옛 측정이 섞이면 조용히 틀린다 — 목록이 최신순인 이유)
