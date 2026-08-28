# ADR: Hand-Eye Calibration 서브시스템 구조

- 날짜: 2026-07-10 (KST)
- 관련: [계획서](../planning/hand-eye-calibration-plan-2026-07-08.md), [worklog 2026-07-10](../worklog/2026-07-10.md)
- 대상: eye-in-hand(손목 카메라) 카메라→base extrinsic X(cam2gripper) 산출·적용

## Status

**Proposed (제안 — 사용자 컨펌 대기)**. 승인 시 구현 착수, 승인 전 코드 미작성.

## Context

- **왜**: 카메라가 주는 태그 위치는 `camera_link` 프레임, 로봇 명령은 base 프레임. 둘을 잇는 hand-eye 변환 X가 없어 AR 잡 6개가 스텁(`job_executor.py:850/869/925/1154/1206/1238`). 그대로 연결하면 카메라 좌표를 base로 착각해 오이동(충돌 위험).
- **전제(모두 충족, 2026-07-10)**:
  - Intrinsic 완료(재투영 0.46px, `calibration_result.yaml`) → solvePnP 준비
  - 임의 포즈 무이동 촬영 검증 완료(`Vision_DoJob("TM_IMG_Send")`, TCP 불변) → 자세별 (TCP+이미지) 수집 가능
  - TCP 포즈 소스 `/robot/status.current_tcp_pose`
  - 체스보드(6×8, 25mm) 재사용 타깃
- **현 결함**: `detected_ar_pose`(job_executor.py:56,893)가 x/y/z만 저장 → 자세(회전) 소실. hand-eye 변환엔 자세 필요.
- **중복 없음**: `calibrateHandEye`/`hand_eye` 0건(신규). `coordinate_transformer`에 `euler_to_rotation_matrix`/`quaternion_to_euler` 재사용 가능.

## Decision

### 이론 (eye-in-hand)
```
X = cam2gripper = cv2.calibrateHandEye(R/t_gripper2base[N], R/t_target2cam[N])
런타임: target_base = T_gripper2base(현재 TCP) · X · target_cam(aruco/pose)
```

### 구성요소 (신규/변경)
| # | 구성요소 | 유형 | 위치 | 역할 |
|---|---|---|---|---|
| 1 | `hand_eye_calibration` 모듈 | 신규 | **결정A 참조** | 자세별 (gripper2base, target2cam) 수집·`calibrateHandEye`·저장/로드 |
| 2 | `config/hand_eye.yaml` | 신규 | `tm_task_manager/config/` | X(4×4 또는 R,t) + 메타(날짜·방법·재투영·N) |
| 3 | 수집 플로우(UI/엔드포인트) | 신규 | 결정A | jog→무이동촬영→검출→solvePnP→쌍저장 반복 + solve |
| 4 | `coordinate_transformer.ar_cam_to_base(tcp, X, ar_pose)` | 변경(확장) | `services/coordinate_transformer.py` | 런타임 카메라→base 변환(순수함수, 단위테스트) |
| 5 | `detected_ar_pose` 자세 저장 | 변경 | `job_executor.py:893` | quaternion→euler 로 자세 포함 저장(기존 `quaternion_to_euler` 재사용) |
| 6 | AR 잡 4개 `_exec` 재작성 | 변경 | `job_executor.py` | X 로드→변환→`set_positions`(패턴: `_exec_align_tm_landmark`) |

### 데이터 흐름 (수집)
```
[자세 N마다] (웹 GUI) jog 로 로봇 이동
   → Vision_DoJob("TM_IMG_Send") 무이동 촬영 → /techman_image
   → cv2 체스보드 검출 + solvePnP(intrinsic=calibration_result.yaml) → target2cam
   → /robot/status.current_tcp_pose → gripper2base
   → 쌍 (gripper2base, target2cam) 누적
[N≥12~15] → cv2.calibrateHandEye(방법 TSAI/PARK/HORAUD 비교, 재투영 최소 선택) → X → hand_eye.yaml
```

### 결정 A — 수집 오케스트레이션 위치 (✅ **확정 2026-07-10: A1 브리지**)
- **A1(권장): tm_web_bridge**. 웹 GUI가 현재 활성 인터페이스이고 브리지에 send_script·motion·status·/techman_image 구독이 이미 있음. 신규 엔드포인트 `POST /handeye/capture_pair`·`/handeye/solve`·`GET /handeye/status` + 웹 UI 섹션. solvePnP·calibrateHandEye는 브리지 내 Python cv2(이미 가용).
- A2: tm_task_manager Qt 앱(계획서 원안, `tabs/handeye_test_tab.py`). Qt 앱을 별도로 띄워야 함.
- **런타임 변환(#4,#5,#6)은 어느 경우든 tm_task_manager/job_executor 소관**(AR 잡이 거기 있음). `hand_eye.yaml`을 두 쪽이 공유.

### 결정 B — solvePnP 검출 재사용 (✅ **확정 2026-07-10: B1 Python cv2**)
- **B1(권장): 수집 모듈 내 Python cv2 자체 검출**(체스보드 detect + solvePnP). 자기완결, C++ 노드 무변경.
- B2: `camera_calibration_node`(C++)에 `get_chessboard_pose` 서비스 추가로 재사용. 검출 일원화되나 C++ 변경·rebuild.

## Consequences

**장점**: AR 잡 6개 실동작화(비전 가이드 pick&place/정렬), 카메라 3D 인식을 로봇 모션으로 연결. 순수함수 변환(#4)은 단위테스트로 왕복 검증 가능.

**단점/위험**:
- **신뢰경계**: 캘리브 결과 X가 로봇 물리 이동을 좌우 → 미검증 X로 실동작 금지(§Verification 게이트 필수).
- **정밀도 한계**: 단일 마커+eye-in-hand 통상 ±1~3mm. 사용자 목표 **±0.5mm는 도전적** → 구축 후 실측, 미달 시 다중마커(ChArUco/estimatePoseBoard, 검출기 확장=추가 코드)·거리단축·힘제어.
- **결합 증가**: 수집(브리지)과 런타임(tm_task_manager)이 `hand_eye.yaml`로 결합 → 포맷·경로 SSOT 1곳 고정.

**연기(deferred)**: 마커 보드 확장(±0.5mm용), 힘제어 병행.

## Rollback

- **가역성: 높음** — #1,#2,#3은 신규 추가(삭제로 원복). #4는 신규 순수함수(호출 안 하면 무영향).
- **안전 폴백**: `hand_eye.yaml` 미존재/로드 실패 시 AR 잡 4개는 **`return False` + "미검증/미보정" 로그**(현재 스텁과 동일하게 실이동 차단). X 적용 전/후 동작 분기(feature-gate).
- **회귀 위험 작음**: #6 대상 4개 `_exec`는 현재 무동작 스텁이라 되돌릴 로직 없음.
- **원복 절차**: hand_eye.yaml 삭제 → 자동으로 폴백(실이동 차단). 코드 원복은 신규 파일 삭제 + #4/#5/#6 커밋 revert.

## Alternatives

- **TMflow 내장 Eye-In-Hand 마법사**(BT02 매뉴얼): 로봇 자체 캘리브. 커스텀 파이프라인 대신 로봇 종속. 현재 방식(PC 좌표계산)과 통합 불명 → 보류, 필요시 별도 검토.
- **단일 마커 유지 vs 보드 확장**: ±0.5mm 목표엔 보드 확장 유력하나 검출기 코드 변경 동반 → 구축 후 실측으로 결정.

## Verification (never-self-approve)

- **재투영 오차**: 캘리브 후 각 자세 재투영 RMS < 목표(1~2px).
- **실공간 오차**: 알려진 위치 태그로 이동 → 도달 편차 측정(`precision_test_manager` 재사용). 목표 ±0.5mm 대비.
- **왕복 단위테스트**: `ar_cam_to_base` 합성 데이터로 역변환 일치.
- 최종 verdict는 저자 self-approve 금지 — 별도 리뷰 패스(`code_review`/사람).

## WBS (구현 순서, coding.md 절차 준수)

1. (S) 안전 가드 — 4개 스텁 `return True # 임시` → `return False`+로그 (즉시 적용 가능).
2. (M) `hand_eye_calibration` 수집 모듈(결정A/B 반영) + solvePnP + calibrateHandEye + save/load + 단위테스트.
3. (M) 수집 UI/엔드포인트.
4. (S) `coordinate_transformer.ar_cam_to_base` + 단위테스트(왕복).
5. (S) `detected_ar_pose` 자세 저장 수정(#5).
6. (M) AR 잡 4개 `_exec` 재작성(#6).
7. (M) §Verification.

## 사용자 확인 (2026-07-10)

1. **결정 A** — ✅ **A1 브리지(웹 GUI)** 확정.
2. **결정 B** — ✅ **B1 Python cv2 자체** 확정.
3. `hand_eye.yaml` 위치 — 잠정 `tm_task_manager/config/`(내일 최종 확인).
4. 착수 범위 — 🔶 **내일 결정**(오늘은 ADR 검토만). 후보: WBS 전체 vs 우선 1~2단계(안전가드+수집).

> 다음 세션: 위 4번(범위) 확정 후 coding.md 절차로 착수. A1/B1은 확정이므로 재논의 불요.
