# Hand-Eye Calibration 서브시스템 구축 계획서 (ADR 겸)

- 작성일: 2026-07-08 (KST)
- 대상 코드 버전: workspace `3663f7dc` (main)
- 상태: **계획(Design/ADR) — 구현 미착수**
- 목적: AR 태그 모션 4개 스텁(`move_to_ar_offset`/`align_to_ar_tag`/`move_to_ar_center`/`wait_for_detection`)을 "방식 B(PC가 좌표 계산 후 ROS2 명령)"로 제대로 구현하기 위한 **전제 서브시스템**(camera→base extrinsic) 구축.
- 관련: docs/code_review/TM_Task_Manager_unimplemented/2026-07-08.md, docs/web_gui/connection-design-2026-07-08.md

---

## 1. 배경 / 문제

카메라가 준 태그 위치는 **카메라 프레임(`camera_link`)**, 로봇 명령은 **base 프레임**이 필요하다. 둘을 잇는 hand-eye 변환이 없어 4개 잡이 스텁(`return True # 임시`)으로 방치됨. 지금 그대로 `set_positions`를 연결하면 카메라 좌표를 base로 착각해 **오이동(충돌 위험)**.

## 2. 현황 (실측 근거)

| 요소 | 현황 | 근거(file:line) |
| --- | --- | --- |
| 카메라 | TM 내장 카메라 이미지 `/techman_image` 구독 | aruco_detector.cpp:13,47 |
| 장착 방식 | 플랜지 장착 = **eye-in-hand (사용자 확정 2026-07-08 — 카메라가 손목에 부착)** | techman_image = 엔드이펙터 카메라 |
| AR 포즈 발행 | `aruco/pose` (PoseStamped, `camera_link` 프레임) | aruco_detector.cpp:14,52-53 |
| Intrinsic 캘리브 | 체스보드 → ROS2 `calibration/save_calibration` | camera_calibration_service.py:58 |
| **Extrinsic(hand-eye)** | **없음** (`calibrateHandEye`/`solvePnP` 0건, 저장파일 0건) | grep 확인 |
| handeye_test_manager | 반복 **오차 통계만**(캘리브 아님) | handeye_test_manager.py:415-478 |
| handeye_analyzer.py | 정밀도 CSV **시각화 GUI**(캘리브 아님) | scripts/handeye_analyzer.py |
| 로봇 TCP 포즈 소스 | `tool_pose` → `current_tcp_pose` [x,y,z,rx,ry,rz] | main_window.py:132,185 |
| AR 포즈 저장 결함 | `detected_ar_pose`에 x,y,z만(자세 소실) | job_executor.py:893 |

## 3. 이론 (eye-in-hand 기준)

`cv2.calibrateHandEye(R_gripper2base, t_gripper2base, R_target2cam, t_target2cam)` → **X = cam2gripper**(카메라가 플랜지에 붙은 상대 자세) 산출.

런타임 변환 체인:
```
target_base = T_gripper2base(현재 TCP) · X(cam2gripper) · target_cam(aruco/pose)
```
- `T_gripper2base` = 명령 시점 `current_tcp_pose`로 매 호출 계산.
- `X` = 캘리브레이션으로 1회 산출·저장.
- `target_cam` = `aruco/pose`(위치+자세).

## 4. 데이터 수집 절차

1. 캘리브 타깃(체스보드 또는 ArUco board) 고정.
2. 로봇을 서로 다른 자세 **N≥12~15개**로 이동(자세 다양성 확보 — 회전축 골고루).
3. 각 자세에서 기록: (a) `current_tcp_pose`(gripper2base), (b) `solvePnP`로 target2cam.
4. `calibrateHandEye`로 X 산출. 방법 비교(TSAI/PARK/HORAUD) 후 재투영 오차 최소 선택.

## 5. 신규/변경 컴포넌트 (구조안)

| # | 구성요소 | 유형 | 역할 |
| --- | --- | --- | --- |
| 1 | `services/hand_eye_calibration_service.py` | 신규 | 자세 수집·`calibrateHandEye`·X 저장/로드 |
| 2 | `config/hand_eye.yaml` | 신규 | X(4x4 또는 R,t) + 메타(날짜·오차·방법) |
| 3 | `tabs/handeye_test_tab.py` | 변경 | 캘리브 수집·실행 UI 추가(테스트와 별개 섹션) |
| 4 | `services/coordinate_transformer.py` | 확장 | `ar_cam_to_base(tcp, X, ar_pose)` 변환 함수 |
| 5 | `job_executor.py` scan_ar_tag | 변경 | `detected_ar_pose`에 자세(quaternion→euler) 저장 |
| 6 | `job_executor.py` 4개 `_exec` | 재작성 | §4 X 로드 → 변환 → `set_positions`(패턴: `_exec_align_tm_landmark`) |

## 6. 공개표면 / ADR 필드 (coding.md §3)

- **비가역 변경 여부**: 낮음 — 신규 config/서비스 추가 중심. 4개 `_exec` 재작성은 현재 무동작 스텁이라 회귀 위험 작음.
- **Rollback Plan**: `hand_eye.yaml` 미존재/로드 실패 시 4개 잡은 §7 안전가드(`return False`+로그)로 폴백. X 적용 전/후 동작 분기.
- **신뢰경계**: 캘리브 결과가 로봇 물리 이동을 좌우 → §9 검증 게이트 **필수**(미검증 X로 실동작 금지).
- **의존성**: OpenCV(`cv2.aruco`, `calibrateHandEye`) — 이미 사용 중(aruco 4.8 포팅됨). 신규 추가 없음.

## 7. 안전 가드 (구축 전/중 공통, 즉시 적용 가능)

4개 스텁의 `return True # 임시` → `return False` + "미구현/미검증" 로그. 캘리브 완료·검증 전까지 실이동 차단. (사용자가 별도로 "안전 최소 수정"만 원하면 이 항목만 단독 적용 가능.)

## 8. 작업 분해 (WBS)

1. (S) 안전 가드 적용 — §7.
2. (M) `hand_eye_calibration_service` — 수집·solve·save/load + 단위 테스트.
3. (M) UI 수집 플로우 — handeye_test_tab 확장.
4. (S) `coordinate_transformer` 변환 함수 + 단위 테스트(합성 데이터로 왕복 검증).
5. (S) scan_ar_tag 자세 저장 수정.
6. (M) 4개 `_exec` 재작성 — `_exec_align_tm_landmark` 패턴 재사용.
7. (M) §9 검증.

## 9. 검증 계획 (never-self-approve)

- **재투영 오차**: 캘리브 후 각 자세 재투영 RMS < 목표(예: 1~2 px).
- **실공간 오차**: 알려진 위치의 태그로 이동 → 실제 도달 위치 편차 측정(기존 `precision_test_manager` 재사용). 목표 오차 확정 필요.
- **eye-in-hand 가정 검증**: 카메라가 플랜지 고정인지 물리 확인(고정 카메라면 eye-to-hand 공식으로 전환).
- 최종 verdict 는 저자 self-approve 금지 — 별도 리뷰 패스.

## 10. 미결 질문 (2026-07-08 사용자 확정)

1. **카메라 장착**: ✅ eye-in-hand(손목 부착) 확정 → 본 계획의 `calibrateHandEye`(cam2gripper) 공식 유지.
2. **캘리브 타깃**: ✅ 기존 체스보드 재사용 (신규 ArUco board 불요) — `camera_calibration_service`의 체스보드 검출 재활용.
3. **허용 오차 목표**: 🔶→ 사용자 선택 **±0.5mm 이하**(2026-07-10). 단 §11상 eye-in-hand + 단일 마커 비전 단독으로는 **도전적**(±0.1~0.5mm는 정밀조립 영역, 힘제어 병행 권장). → **구축 후 실측**해 미달 시 다중마커/거리단축/힘제어로 개선.
4. **X 저장 포맷/위치**: ✅ `config/hand_eye.yaml` 유지.
5. **임의 포즈 촬영(hand-eye 수집 전제)**: ✅ **가능 확인**(2026-07-10, §12) — `Vision_DoJob()` 무이동판 + TMflow 잡 "Start at Initial Position 해제".

## 11. 이동 오차 기준 가이드 (목표 오차 산정용)

"오차 몇 mm가 적당한가"는 **작업이 요구하는 정밀도**에서 역산한다. 총 오차 예산(error budget)은 다음 합이다:

```
총 오차 = intrinsic 오차 + hand-eye(X) 오차 + 로봇 반복정밀도 + 태그 검출 오차 + 캘리브 타깃 오차
```

- TM(Techman) 협동로봇 **반복정밀도(repeatability)**는 사양상 ±0.02~0.1 mm 수준이라, 실전 오차의 지배 항은 보통 **hand-eye + 태그 검출**이다.
- eye-in-hand + 단일 마커는 통상 **±1~3 mm / ±0.5~2°** 대에 수렴(카메라 해상도·마커 크기·거리 의존). 이보다 정밀하려면 마커 크기↑, 거리↓, 다중 마커(board), 조명 개선이 필요.

**작업별 허용 오차 기준표(권장 목표):**

| 작업 유형 | 허용 오차(위치) | 근거 |
| --- | --- | --- |
| 개략 접근(pre-grasp, 넓은 그리퍼) | ±5~10 mm | 그리퍼 개폐 여유가 흡수 |
| 일반 pick & place(트레이/지그 안착) | ±1~3 mm | 지그 챔퍼(모따기)가 최종 정렬 흡수 |
| 정밀 조립·삽입(커넥터/핀) | ±0.1~0.5 mm | 유격 자체가 작음 — 비전 단독 부족, 힘제어 병행 |
| 검사·촬영 위치잡기 | ±1~5 mm | 화각 안에 들어오면 충분 |

**권장 설정 절차**: (1) 목표 작업을 정한다 → (2) 위 표에서 목표 오차 선택 → (3) 캘리브 후 §9 실공간 측정으로 **달성 오차 < 목표**인지 확인 → (4) 미달 시 마커 크기/거리/다중마커로 개선. 이 시스템의 현재 AR 잡(`move_to_ar_offset`/`align_to_ar_tag`)은 "개략 접근~일반 pick&place"용이므로 **1차 목표 ±1~3 mm**를 제안한다(정밀 조립은 별도 힘제어 트랙).

---

**다음**: 위 §10 확인 후 WBS §8 순서로 착수. 착수 시 각 단계는 coding.md 절차(사전조사→구현→검증→이중기록) 준수.

---

## 12. 진행 업데이트 (2026-07-10)

### ✅ Intrinsic 캘리브레이션 완료 (전제 ①)
- 커스텀 노드 `camera_calibration_node`(9×6 예시→ 실보드 **6×8**, 사각형 **25mm**)로 15뷰 수집 → `run_calibration`.
- **재투영 오차 0.4575 px**(목표 1~2px 대비 우수). 저장: `src/Vision/ROS2/tm_camera_calibration/calibration_data/20260710_161025/calibration_result.yaml` (camera_matrix + dist_coeffs). solvePnP 전제 확보.
- 부수 수정: config `save_path` 리터럴 `~` 버그 정식 수정(issues_and_fixes 2026-07-10).

### ✅ 블로커 해결 — "임의 포즈 촬영" 가능 확인 (매뉴얼 1차 인용)
hand-eye는 로봇을 서로 다른 자세로 옮기며 각 자세에서 **현재 포즈 그대로 촬영**해야 하는데, 기존 `Vision_DoJob_PTP()`는 초기 위치로 이동해버려 불가했다. 매뉴얼 확인 결과:
- [TMscript v2.18 Rev1.0, §13.26 Vision_DoJob(), p.351-352](../Programming-Language-TMscript_2.18_Rev1.0_EN.pdf): "Execute ... **but not the ones with initial positions. Must create vision jobs without checking Start at Initial Position.**" (초기위치 잡이면 False 반환)
- `Vision_DoJob()` = **무이동(현재 위치 촬영)**, `Vision_DoJob_PTP()`(p.353)/`Vision_DoJob_Line()`(p.354) = 초기위치 이동 후 촬영.
- **원인 규명**: 과거 무이동판 이미지 미전송은 `TM_IMG_Send` 잡이 "Start at Initial Position" 체크됨 → False 반환이었음.
- **해결책**: TMflow에서 "Start at Initial Position **해제**"(기존 `TM_IMG_Send` overwrite) → `Vision_DoJob("TM_IMG_Send")` 이 현재 포즈에서 촬영·전송.
- **✅ 트랙 B 실측 완료(2026-07-10 17:09)**: `/send_script` 로 `Vision_DoJob("TM_IMG_Send")` 전송 → `ok=True`, `:6189` 에 `[169.254.122.16] -> Post(DET)` 수신. **촬영 전후 TCP 포즈 동일**(`[-904.21,-58.44,190.81,-179.42,0.46,8.48]`, moving False) = **무이동 확정**. → hand-eye 수집(임의 포즈에서 TCP+이미지 쌍) 실현 가능 확인.

### 🔶 마커 전략 (미결)
- 현재 검출기: **DICT_4X4_50 · 단일 마커 · solvePnP**(`aruco_detector.cpp:15,115`) — 보드/ChArUco 미지원.
- ±0.5mm 목표엔 단일 마커 부족 → **estimatePoseBoard/ChArUco 확장(코드 작업)** 또는 마커 크게/거리 단축 필요. hand-eye 구축 시 확정.

### 다음 순서
1. (사용자) TMflow "Start at Initial Position 해제" 잡 생성 → (나) `Vision_DoJob()` 실측(입회).
2. 마커 전략 결정(단일 유지 vs 보드 확장).
3. WBS §8 순서로 hand-eye 코드 구축.
