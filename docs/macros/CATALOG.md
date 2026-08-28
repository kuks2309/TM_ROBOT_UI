# Macro Catalog

> 이 문서는 `scripts/generate_macro_catalog.py` 가 매크로 레지스트리에서 생성한다.
> **직접 수정하지 말 것** — 매크로를 고친 뒤 스크립트를 다시 돌린다.

매크로는 재사용 가능한 함수이고, Job 은 매크로를 포함해 호출하는 단위다.
설계 근거: [ADR 2026-08-11 매크로 계층](../adr/2026-08-11-macro-layer.md)

## 읽는 법

- **requires** — 실행 전 충족돼야 하는 것. `config:` 접두는 외부 선행조건(설정·학습 데이터)이고, 그 외는 앞선 매크로가 칠판에 남긴 산출물이다.
- **produces** — 이 매크로가 칠판에 남기는 것. 뒤따르는 매크로가 `requires` 로 받는다.

## 매크로 (8개)

### `pallet_capture_marker`

비고정식 팔레트의 위치 마커를 측정해 칠판과 파일에 남긴다. 실행 시점에 이 마커를 다시 찍어 팔레트가 어디로 옮겨졌는지 알아낸다.

- 카테고리: `Calibration`
- requires: 없음
- produces: `position_marker_pose`, `marker_view_tcp`

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `repeat_count` | int | `10` | min 1, max 30 | 반복 측정 횟수 |
| `outlier_method` | choice | `'3sigma'` | none/iqr/3sigma | Outlier 제거 방법 |
| `wait_after_command` | int | `0` | - | 스캔 명령 후 대기 (ms) |

### `pallet_capture_teach`

지금 로봇이 서 있는 자세를 평면 좌표계 상대값으로 환산해 티칭 슬롯에 담는다. 절대좌표가 아니라 상대값이라 팔레트를 옮겨도 재사용된다.

- 카테고리: `Calibration`
- requires: `plate_pose`
- produces: `teach_poses`

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `slot` | choice | `'pick'` | approach/pick/place | 이 자세를 담을 슬롯 |

### `pallet_center_approach`

측정한 평면의 중심 위 standoff 높이로, 팔레트에 정렬해 이동한다. 공구 면이 평면과 평행해지고(기울기 추종) 공구 회전이 팔레트 긴 변에 맞는다.

- 카테고리: `Calibration`
- requires: `plate_pose`
- produces: `approach_pose`

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `standoff_mm` | float | `150.0` | min 1.0 | 평면에서 띄울 거리 (mm) |
| `rz_mode` | choice | `'plane'` | plane/keep | plane=팔레트 긴 변에 회전 정렬(기본) · keep=현재 공구 회전 유지. 기울기는 두 경우 모두 평면을 따른다 |
| `velocity` | float | `20.0` | min 1.0, max 100.0 | 이동 속도 (%) |

### `pallet_emit_recipes`

측정한 평면과 티칭 자세로 픽앤플레이스 레시피를 발행한다. 고정식은 절대좌표, 비고정식은 마커 기준 상대좌표로 낸다.

- 카테고리: `Calibration`
- requires: `plate_pose`, `teach_poses`
- produces: `recipe_paths`

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `pallet_name` | str | `''` | - | 팔레트 이름 — 레시피 파일명이 된다 |
| `mount` | choice | `'fixed'` | fixed/floating | fixed=고정식 · floating=비고정식(위치 마커 기준) |
| `pitch_x` | float | `0.0` | - | 마커 가로 간격 (mm) |
| `pitch_y` | float | `0.0` | - | 마커 세로 간격 (mm) |
| `trim_x` | float | `0.0` | - | 마지막 지점 X 보정 (mm) |
| `trim_y` | float | `0.0` | - | 마지막 지점 Y 보정 (mm) |
| `operator` | str | `''` | - | 작업자 이름 |
| `overwrite` | bool | `False` | - | 같은 이름의 레시피가 있으면 덮어쓴다 |

### `pallet_load_measurements`

이미 저장된 측정 파일 여러 개를 골라 outlier 제거 후 평균내 평면을 만든다. 로봇을 움직이지 않으므로 4점 측정을 건너뛰고 바로 티칭으로 갈 수 있다.

- 카테고리: `Calibration`
- requires: 없음
- produces: `plate_pose`, `plate_marks`, `measurement_sources`

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `source_path` | dirpath | `'data/plate_pose_calc'` | - | 측정 파일 폴더 (상대경로는 패키지 루트 기준) |
| `file_prefix` | str | `''` | - | 파일명 접두어 (비우면 폴더 전체) |
| `max_files` | int | `5` | min 0, max 100 | 최신 파일 몇 개를 쓸지 (0=전부). file_paths 를 주면 무시 |
| `outlier_method` | choice | `'iqr'` | none/iqr/3sigma | 파일 간 outlier 제거 방법 |
| `file_paths` | list | `None` | - | 쓸 파일을 직접 지정 (화면에서 고른 목록). 주면 source_path 검색을 건너뛴다 |

### `pallet_scan_4corners`

1사분면 마커에서 시작해 마커 간격만큼 이동하며 꼭짓점 4개를 측정하고 평면(plate) pose 를 계산한다. 시작 자세는 사용자가 조그로 맞춰 둔 것을 쓴다.

- 카테고리: `Calibration`
- requires: 없음
- produces: `plate_pose`, `plate_marks`, `scan_start_tcp`

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `pitch_x` | float | `0.0` | min 0.0 | 마커 가로 간격 (mm) — 팔레트 고유값 |
| `pitch_y` | float | `0.0` | min 0.0 | 마커 세로 간격 (mm) — 팔레트 고유값 |
| `trim_x` | float | `0.0` | - | 마지막 지점 X 보정 (mm) — 마커 부착 편차 흡수 |
| `trim_y` | float | `0.0` | - | 마지막 지점 Y 보정 (mm) — 마커 부착 편차 흡수 |
| `velocity` | float | `25.0` | min 1.0, max 100.0 | 꼭짓점 사이 이동 속도 (%) |
| `repeat_count` | int | `10` | min 1, max 30 | 지점당 반복 측정 횟수 |
| `outlier_method` | choice | `'3sigma'` | none/iqr/3sigma | Outlier 제거 방법 |
| `wait_after_command` | int | `0` | - | 스캔 명령 후 대기 (ms) |

### `vision_origin_check`

학습된 TCP 자세로 복귀해 랜드마크를 재측정하고 6축 편차를 판정한다. 허용범위를 벗어나면 알람 콜백을 발화하고 실패로 끝난다.

- 카테고리: `Calibration`
- requires: `config:taught_origin`
- produces: `origin_check_result`

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `move_to_reference` | bool | `True` | - | 학습된 TCP 자세로 이동 후 측정 |
| `velocity` | float | `20.0` | - | 기준 위치 이동 속도 (%) |
| `repeat_count` | int | `5` | min 1, max 20 | 반복 측정 횟수 |
| `outlier_method` | choice | `'iqr'` | none/iqr/3sigma | Outlier 제거 방법 |
| `wait_after_command` | int | `100` | - | 명령 후 대기 시간 (ms) |

### `wait`

정해진 시간만큼 대기한다. 실행 정지 요청이 오면 즉시 중단한다.

- 카테고리: `Control`
- requires: 없음
- produces: 없음

| 파라미터 | 타입 | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `duration` | int | `1000` | min 0 | 대기 시간 (ms) |

## 매크로를 포함한 Job (3개)

| Job 타입 | 표시명 | 포함 매크로 |
| --- | --- | --- |
| `settled_origin_check` | Settled Origin Check | `wait` → `vision_origin_check` |
| `vision_origin_check` | Vision Origin Check | `vision_origin_check` |
| `wait` | 대기 | `wait` |
