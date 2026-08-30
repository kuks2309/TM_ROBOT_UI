# Issues and Fixes

---

## 2026-08-29

### [Fix] move_linear(Move_Line "TPP") 좌표계 오단정으로 실기 충돌 — sdc_marker_move(마커 frame 이동)로 대체

- **문제**: 팔래트 진입 레시피의 `move_linear` 실행에서 X·Y 이동이 기대(마커 표면 평행)와 다른 방향으로 나가 실기 충돌 사고(2026-08-29 16:38 사용자 보고). 로봇 에러·비상정지 없음 확인.
- **원인**: TM 스크립트 `Move_Line("TPP")` 의 좌표계 의미가 벤더 매뉴얼로 미검증 — 코드 docstring(`tm_robot_script_motion.py` "공구 좌표계 상대 직선 이동")만 근거로 안내·사용했고, 실기 거동은 그 주장과 불일치. 로컬에 TM Expression 매뉴얼 부재로 원문 대조 불가(이해 부채 debt-025, mistake `docs/claude-mistake/2026-08-29-003.md`).
- **해결**: 스크립트 의미에 무의존한 Job `sdc_marker_move` 신설 — 파라미터 (dx,dy,dz)를 마커 frame 기준으로 받아 목표 = 현 위치 + R_marker@(dx,dy,dz) 를 절대 좌표 LINE_T(정본 `_move_to_position_line`, MotionGuard 경유)로 이동, 자세 유지. X·Y=표면 평행·Z+=법선 방향이 좌표 변환으로 보장(테스트로 법선 성분 0 고정). 레시피 5번 스텝을 move_linear → sdc_marker_move(dz=+50, 10%)로 교체, move_linear 는 debt-025 해소 전까지 팔래트 레시피 사용 금지.
- **파일**: `tm_task_manager/job_executor.py`(`_exec_sdc_marker_move`), `tm_task_manager/recipe_manager.py`(JOB_TYPES 54종), `config/recipes/sdc_palette_entry.yaml`(스텝 교체), `test/test_sdc_marker_move.py`(신설 7건), `docs/debt/registry.md`(debt-025)
- **상태**: 코드·단위 검증 완료(sim, 2026-08-29 16:50 — 7건 PASS, 전체 회귀 915 passed). 실기 재검증 잔여(2026-08-29 기준 — 배포 후 저속 Step 실행 대기)

### [Fix] sdc_palette_tcp_align 법선 오차 2.52° — 오일러 근사식을 회전행렬 스냅으로 교체

- **문제**: `sdc_palette_tcp_align` 실기 실행 후 공구 Z축 ↔ 마커 법선 사이각 2.52° — 지그 진입 공차(~0.4°, 사용자 명시) 초과로 진입 불가. 명령 수행 자체는 목표 대비 0.10°로 정확(실기 실측) — 목표 "정의"의 결함.
- **원인**: 목표 자세를 오일러 성분 조작 `(-rx_m+o_rx, ry_m+o_ry, -rz_m+o_rz)` 으로 만드는 근사식(`job_executor.py` `_exec_sdc_palette_tcp_align`, 변경 전) — 부호반전은 마커가 축 정렬일 때만 정확하고, 마커 rx=-87.9(−90 에서 2.1° 이탈)의 이탈분이 법선 오차 2.44°로 새어 나옴(수치 재현 일치).
- **해결**: 근사식 자세의 Z축을 마커 법선에 정확히 일치시키는 최소 회전을 합성(스냅)해 회전행렬로 목표를 구성, 법선 주위 회전(카메라 -22° 보상)은 유지 — scipy Rotation('ZYX', 기존 `_create_transform_matrix` 와 동일 규약) 사용, 약 20줄 교체. 목표 법선각 2.44° → 0.0000°(수치 검증).
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py`(`_exec_sdc_palette_tcp_align` 목표 계산부), `test/test_sdc_palette_tcp_align.py`(법선 일치 0.01° 테스트 추가·기대값 갱신, 10건 PASS)
- **상태**: 완료 — ~~실기 재검증 잔여(2026-08-29 기준)~~ → 완료(실기, 2026-08-29 15:12): 재배포 후 사용자 재실행, 공구 Z축 ↔ 마커 법선 **0.033°** 실측(요구 0.4° 충족, 수정 전 2.52°). 단위 검증(sim, 2026-08-29 15:00 — 회귀 893 passed) 선행

### [Issue] 카메라 탭 이미지 캡처 불능 — tm_camera_bridge 미기동(복구) + TMflow External Detection URL 확인 대기

- **문제**: UI 캡처 버튼·직접 쓰기(g_robot_command=3) 모두 TMflow 쪽 촬영은 진행되나 UI 화면에 이미지가 오지 않음.
- **원인 1 (확정·복구 완료)**: orin(nx-orin-1) 스택 기동 시 tm_driver·task_manager_node 만 띄우고 **tm_camera_bridge(포트 6189) 를 빠뜨림**. 브리지는 TMflow External Detection HTTP POST 를 받아 `techman_image` 토픽으로 재발행하는 유일한 경로라, 없으면 캡처 명령이 성공해도 이미지가 UI 에 도달 불가(`/techman_image` 발행자 0, UI 로그 "수신 대기 시작" 후 타임아웃 실측). 부수: orin 에 flask·waitress·pip 자체가 없어 `python3 get-pip.py --user` 부트스트랩 후 워크스페이스 `vendor/pylibs` 에 설치(launch 파일의 vendor 경로 규약 준수, PYTHONNOUSERSITE 유지). 기동 후 6189 리슨·발행자 1 확인.
- **원인 2 (확정 — 참조 저장소 대조)**: kuks2309/TM_Robot_ros2_ws 워크로그(2026-07-07 §10·07-09)에 파이프라인이 기록됨 — 비전 잡 `TM_IMG_Send` 의 외부 감지 URL 이 **`169.254.183.100:6189/api/DET`(옛 ROS PC)** 로 설정되어 있고, 현 orin eth0 은 `169.254.183.1` 이라 이미지가 없는 주소로 전송됨. Ethernet Slave 일시정지 포함 UI 동일 순서 재시험에서도 브리지 HTTP 무수신으로 방증. 해결 선택지: ① orin 에 IP 별칭 추가 `sudo ip addr add 169.254.183.100/16 dev eth0`(TMflow 무수정, 재부팅 시 소멸 — netplan 영속화 별도) ② TMflow 에서 URL 을 169.254.183.1 로 수정.
- **후속 개선 후보(참조 저장소 검증본)**: 캡처 트리거를 `g_robot_command=3`+`ScriptExit()`(Listen 종료 위험) 대신 `Vision_DoJob_PTP("TM_IMG_Send",100,500)` 로 교체 — 참조 저장소 image_capture_service.py 에 구현·실기 PASS 기록 있음.
- **파일**: 코드 변경 없음(운영 절차). 재발 방지 — orin 기동 절차에 카메라 브리지 포함:
  `env PYTHONNOUSERSITE=1 PYTHONPATH=$WS/vendor/pylibs python3 $WS/src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py`
- **해결 (2026-08-29 13:25)**: 사용자가 orin 에서 `sudo ip addr add 169.254.183.100/32 dev eth0` 실행(옛 ROS PC 의 IP 를 orin 이 이어받음 — `/16` 은 기존 169.254.183.1/16 과 프리픽스 중복으로 RTNETLINK Invalid argument, `/32` 로 성공). 직후 캡처 실측: Ethernet Slave 일시정지 → g_robot_command=3 → **`/techman_image` 이미지 도착 확인** → 재개. TMflow 무수정으로 종결.
- **잔여**: ① IP 별칭은 재부팅 시 소멸 — netplan 영속화 필요(사용자 승인 대기) ② 캡처 트리거를 참조 저장소 검증본(`Vision_DoJob_PTP`)으로 교체할지 선택 대기
- **상태**: 해결 — UI Image Capture 버튼 정상 동작 사용자 확인(2026-08-29 13:28). 잔여 선택 2건(IP 별칭 netplan 영속화 / Vision_DoJob_PTP 트리거 교체)은 별도 지시 대기

---

### [Fix] 조그 x/y/z 가 베이스 축과 평행하게 움직이지 않음 — 공구 좌표계 조그를 베이스 좌표계로 교체

- **문제**: 공구가 기울어진 자세(rx 90°, ry -22°, rz -90°)에서 조그 x/y/z 버튼을 누르면 로봇이 베이스 축과 평행하지 않게 대각선으로 이동. 사용자 요구는 "robot base 기준으로 좌표축과 수평 이동".
- **원인**: `teaching_service.py` 의 `jog_tcp`(단발)·`jog_tcp_continuous`(연속) 둘 다 x/y/z 스텝을 공구 좌표계 증분(`tool_delta`, z 는 `-step` 부호 반전 포함)으로 만들고 `CoordinateTransformer.transform_tool_to_base`(coordinate_transformer.py:50) 로 현재 TCP 자세 회전을 곱해 보냈다 — 설계 자체가 공구 축 조그. 수직 하향 자세(rx≈180°)에서는 공구 축과 베이스 축이 부호만 다르고 일치해 결함이 보이지 않았고, 기울인 자세에서 드러났다. 로봇 활성 베이스 선택(`change_to_robot_base`/`change_to_vision_base`, 현재 robot_base)과 무관하게 공구 회전이 한 번 더 끼는 것이 핵심.
- **해결**: 두 메서드의 병진 분기에서 tool_delta + 회전변환을 제거하고 베이스 축 직접 증분(`target_pos[0..2] += step`)으로 교체(x+→+X, y+→+Y, z+→+Z). PTP_T 목표는 로봇의 현재 활성 베이스에서 해석되므로 조그는 선택된 베이스 축과 평행하게 움직인다. 회전 조그(rx/ry/rz)는 무변경. 사용자 승인(베이스 고정, 토글 없음) 후 구현.
- **부수 수정**: `test_robot_ip_probe.py::test_no_infinite_recursion` 이 실 config 디렉터리를 읽어 이번에 배치한 `config/robots/active.txt` 존재로 실패 → 빈 임시 디렉터리로 격리(전제: 아무 설정도 없음).
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/services/teaching_service.py`(`jog_tcp`·`jog_tcp_continuous` 병진 분기), `test/test_teaching_jog_base_frame.py`(신설 10건 — 기울인 자세에서 병진 조그가 단일 베이스 축만 변경·자세 불변 검증), `test/test_robot_ip_probe.py`(격리)
- **검증**: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/ -q` → **1 failed, 887 passed, 20 skipped**. 실패 1건 `test_recipe_manager.py::test_manager_get_job_types_by_category` 는 2026-08-15·08-17 항목에 기록된 선재 결함(본 건 무관). 실기 조그 검증은 orin 배포 후 사용자 확인 대기.
- **상태**: 완료(실기 확인 대기)

---

## 2026-08-18

### [Fix] 팔레트 순회 실패의 진짜 원인은 레시피 종류 차이 — 미사용·결함 레시피 13개 제거, 검증본 개명

- **문제**: "어제까지 되던 게 안 된다"며 `pick_place_all_pallets` 가 팔레트에서 179.57° 제자리 회전을 시도해 팔레트 가드에 충돌·정지. 좌표계(TCP) 틀어짐이 의심됐다.
- **원인 규명 경과 (오판 2회 포함)**:
  1. TCP 좌표계 가설 **기각** — 저장 캘리 6개가 2×3 격자로 일관(x 간격 267mm, y 217mm, Z 편차 1.26mm), 8/17 22:40 로그의 목표 좌표를 `pose_from_plane_frame` 로 재현해 `dx=0.000 dy=-0.002 dz=0.002mm` 일치, 로봇 도달오차 0.01~0.07mm.
  2. "오늘 코드 변경 탓" **기각** — `job_executor.py` 오늘 diff 의 삭제 라인이 총 5줄뿐이고 전부 스캔 로그·import 확장(모션 무관), 나머지는 순수 추가. `recipe_manager.py` 도 신규 job type 추가만.
  3. "빠짐 스텝을 없앴다" **기각(오판)** — `pick_place_all_pallets`(8/14 21:14)가 `drawer_to_pallet_pick_place`(8/15 21:53)보다 먼저 만들어졌다. 뺀 게 아니라 원래 없었다.
  4. "100회 성공한 게 이 레시피다" **기각(오판)** — 8/15 11:36~15:26 세션 로그(`~/.ros/log/python3_806213_*.log`, set_positions 2478건)를 분석하니 **75주기 × 47.9초 = 59.9분 무중단**이고 `Move_Line` 451건이 섞여 있다. `Move_Line` 은 `move_linear` 잡에서만 나오는데 `pick_place_all_pallets` 에는 그 잡이 0개다.
  5. **확정**: 100회 완주한 레시피는 **`pallet0_align_from_file`**(`load_plate_pose`×6 + `align_to_plane_normal`×6 + `move_linear`×6). 팔레트당 4모션(정렬 3 + Move_Line 1) × 6 = 주기당 24건으로 측정치 24.05 와 일치. 이 레시피는 **`move_to_saved_pose` 를 아예 쓰지 않고** 팔레트마다 `move_linear` 로 공구 −Z 150mm 후퇴 후 다음 팔레트로 간다. 그래서 그리퍼에 박스를 들고 100회를 돌아도 충돌이 없었다. 반면 `pick_place_all_pallets` 는 후퇴 없이 최저높이(offset_z=156.292)에서 `move_to_saved_pose` 를 불러 `_move_pose_keep` 의 "제자리 회전 먼저"를 팔레트 안에서 실행한다. 팔레트 짧은 변이 137.3mm 라 공구축에서 68.6mm 만 벗어나도 가드에 닿는다. **두 레시피는 애초에 다른 물건이고, 실패한 쪽은 완주 기록이 로그에 없다.**
- **해결**: 사용자 지시로 미사용·결함 레시피 제거 + 검증본 개명.
  - **삭제 13개** — 결함: `pick_place_all_pallets`(복귀 후퇴 누락 6곳), `pick_place_plane_demo`(동일 2곳 + `file_prefix: pallet0` 오염), `diag_speed_test`(접두어 오염). 미사용(8/10 이후 무수정·실행흔적 없음): `111`, `AI_test`, `gripper_test_jig`, `gripper_test_jig_runtime`, `jig-gripping`, `pallet_pickup_example`, `test`, `test_align`, `test_align1`, `팔레트 티칭1`(미완성 스텁).
  - **보존** — `tm_landmark_test4.yaml`·`tm_landmark_test4_runtime.yaml` 은 `tools/verify_recipe_manager.py`·`tools/test_job_executor_integration.py`·`tools/test_recipe_manager.py` 가 실제로 `load_recipe()` 하므로 삭제 대상에서 제외.
  - **개명** — `pallet0_align_from_file.yaml` → **`pallet_all_align_from_file.yaml`**(실제로 pallet0~5 순회). 내부 `name`·`description` 도 "팔레트 0~5" 로 정정.
  - **이식성** — 레시피 내 `/home/amap/.../TM_Robot_Task_Manager/` 절대경로 13곳(개명본 `source_path` 5곳 + cali 레시피 `save_path` 8곳)을 상대경로로 정규화. 상대경로는 `paths.PACKAGE_ROOT` 기준으로 풀리므로(`job_executor.py:1990-1991`) 로컬 동작은 불변.
  - `.recent_files.txt` 에서 삭제된 항목 제거.
- **파일**: `config/recipes/` 전반 (27개 → 14개), `config/recipes/.recent_files.txt`
- **검증**: 삭제 전 `config/recipes/` 전체를 `recipes_backup_20260818.tgz`(40개 항목)로 백업. `setup.py` 는 `glob('config/recipes/*.yaml')` 이라 파일 목록 하드코딩 없음 — 삭제 안전. 결함 감사 재실행 시 잔여 항목 0건(후퇴 누락·접두어 오염·절대경로·미등록 job type 전부 해소). 추적본 9개는 `git rm` 이라 HEAD 에서 복구 가능, 미추적 4개(`111`, `diag_speed_test`, `pick_place_plane_demo`, `팔레트 티칭1`)는 백업 tgz 에만 존재.
- **상태**: 완료 (실기 재실행 확인 필요)

### [Fix] pallet0 을 816mm 떨어진 허공에 놓음 — `file_prefix: pallet0` 이 드로어 캘리 파일까지 집어 평균

- **문제**: `pick_place_all_pallets.yaml`(팔레트→팔레트) 실행 시 pallet0 만 한참 엉뚱한 곳으로 감. 좌표계(TCP)가 틀어진 것으로 의심됐으나 아니었다. 드로어→팔레트 레시피는 정상.
- **원인**: `_resolve_plate_pose_files` 가 `pattern = f"{file_prefix}*.yaml"` 로 **와일드카드 접두어 매칭**을 하고 `sorted(..., reverse=True)` 로 **파일명 문자열 역순**(시각순 아님) 정렬한다 — `job_executor.py:1909-1910`. 레시피 파라미터가 `file_prefix: pallet0`, `average_count: 0`(=매칭 전부)이라 `data/plate_pose_calc` 의 세 종류가 모두 걸렸다:
  - `pallet0_cali_*` 11개 (8/14, 진짜 pallet0) · `pallet0_align_*` 2개 (8/14) · **`pallet0_drawer_cali_*` 19개 (8/15, 드로어)**
  - 32개 전부를 랜드마크 평균 → 평면중심 `(443.62, 514.96, -300.53, rz -56.37)` = pallet0(817, 215)과 드로어(175, 723)의 무의미한 중점. 목표가 `(446.3, 513.6)` 로 정상값 `(816.1, 217.6)` 에서 **수평 424mm** 벗어남.
  - **8/14 까지 정상이었던 이유**: 그때는 `pallet0*` 에 드로어 파일이 없었다. 8/15 19:00~21:48 드로어 캘리 작업으로 19개가 생기면서 오염 시작. 8/15 에 성공한 `drawer_to_pallet_pick_place.yaml` 은 접두어가 `pallet0_cali` 로 정확해 영향이 없었고, `pick_place_all_pallets.yaml` 은 그 뒤로 한 번도 실행되지 않아 오늘 처음 드러났다.
- **해결**: `pick_place_all_pallets.yaml` 의 `file_prefix: pallet0~5` → **`pallet0_cali ~ pallet5_cali`** (6줄). 코드 변경 없음.
- **파일**: `src/TM_Robot_Task_Manager/config/recipes/pick_place_all_pallets.yaml` (25, 62, 99, 136, 173, 210행)
- **검증**: 레시피의 6개 `load_plate_pose` 를 실제 파라미터로 재현한 결과 — 수정 전 pallet0 은 `{pallet0_drawer_cali:19, pallet0_cali:11, pallet0_align:2}` 32개 혼합 → 목표 `(446.3, 513.6)`. 수정 후 6개 전부 자기 `_cali` 파일만 선택(`pallet0_cali` 11개 등, **접두어 혼합 0건**), 목표가 각 팔레트 중심으로 복귀 — pallet0 `(816.1, 217.6)`, pallet1 `(549.1, 218.7)`, pallet2 `(814.7, -0.8)`, pallet3 `(547.6, 1.0)`, pallet4 `(813.9, -219.1)`, pallet5 `(546.9, -216.9)`. 실기 재실행은 미수행.
- **좌표계 무결성 확인(별도 검증)**: TCP 좌표계 틀어짐 가설은 기각됐다. ① 저장된 캘리 6개가 2×3 격자로 일관(x 간격 267mm, y 간격 217mm, Z 편차 1.26mm, Rz 편차 0.47°) ② 8/17 22:40 로그의 pallet1 목표를 `pose_from_plane_frame` 로 재현해 `dx=0.000 dy=-0.002 dz=0.002mm` 일치 ③ 로그상 모든 이동이 도달오차 0.01~0.07mm 로 완료. 즉 계산·로봇 모두 정상이고 **입력 파일 선택만 틀렸다**.
- **상태**: 완료 (실기 확인 필요)

### [Issue] 미해결 — `pick_place_all_pallets` 는 팔레트마다 179.5° 제자리 회전을 요구

- **문제**: 위 레시피는 팔레트마다 `move_to_plane_pose`(작업 자세 Rz≈-0.47) → `move_to_saved_pose`(시작 자세 Rz=180.00)를 반복한다. `_move_pose_keep` 이 **위치 고정 상태로 자세부터 맞추므로** Z=-169mm 깊은 곳에서 179.5° 제자리 회전이 발생하고 30초 타임아웃으로 실패한다(8/17 22:40:41 로그).
- **원인**: 작업 자세 Rz = plate Rz 89.541 + `offset_rz` -90.008 = **-0.47°**, 복귀 목표 Rz = 180.00° → 회전량 179.5°. `save_pose[start]` 는 레시피에 저장된 값이 아니라 **Run 누른 시점의 실측 TCP** 를 읽으므로(`_exec_save_pose`) 시작 위치에 따라 회전량이 달라진다.
- **후보 해결(미적용, 사용자 결정 대기)**: ① `offset_rz` -90.008 → +89.992 (2지 그리퍼면 물리적으로 동일 파지, 위치 불변 — `pose_from_plane_frame` 은 position 계산에 relative rz 를 쓰지 않음) ② 복귀 경로는 회전보다 Z 후퇴를 먼저 ③ 제자리 회전량 임계 초과 시 거부하는 가드
- **파일**: `tm_task_manager/job_executor.py`(`_move_pose_keep`), `config/recipes/pick_place_all_pallets.yaml`
- **상태**: 보류

---

## 2026-08-17

### [Issue] Z 10mm 조그가 대회전을 유발 + TCP 수신값 튐 — 원인 미확정, 명령/실측 pose 파일 로깅 신설

- **문제**: 그리퍼 장착 및 기능 추가(2026-08-15~17) 이후 (1) Z축 10mm 조그를 눌렀는데 로봇이 한 바퀴 도는 듯한 큰 회전을 시도, (2) 화면 TCP 수신값이 튐.
- **조사 결과 (원인 미확정)**:
  - **로그에 증거가 없다.** 오늘 세션 로그 `~/.ros/log/python3_1959660_1786959343839.log` 에 pose 값이 한 줄도 없다. 명령 흔적은 `[안전구역] 허용/미검사 set_positions` WARN 뿐(`1786965627.9~633.5` 구간 9건이 0.5~1.0초 간격 연속 — 조그 연타 흔적, 단 `로봇 연결 성공(1786965635.8)` 이전). GUI 로그는 `textEdit_log` 에만 쓰고 파일로 남기지 않는다(`main_window.py:1063-1069`). `launch.log` 는 종료 시 3개 노드가 SIGINT·SIGTERM 을 무시해 SIGKILL 된 것을 남겼다(GUI 스레드 블로킹 정황).
  - **조그 계산 경로는 오늘 변경되지 않았다** — `jog_service.py` 는 CommandGate 래퍼만 추가(계산 무변경), `teaching_service.py`·`coordinate_transformer.py`·`robot_motion_service.py` 는 git status 상 미변경. 즉 소프트웨어 회귀가 아니라 하드웨어/자세 조건 변화로 기존 결함이 드러난 쪽.
  - **후보 ① ±180° wrap·짐벌 (선례 있음)**: 본 문서 2026-07-13 항목에 "로봇 실측 Rx 가 `-179.9994` ↔ `180.0` 로 오가는 구간" 에서 무의미한 회전 명령이 발행된 실기 사례가 이미 있다. 남은 취약점 — `_quaternion_to_euler_deg`(`robot_motion_service.py:182-199`)가 `asin` 으로 ry 를 [-90,90] 에 강제하므로 ry≈±90 부근에서 같은 자세인데 rx/rz 가 요동, 조그는 그 값을 그대로 PTP_T 절대 목표로 복사(`teaching_service.py:71-95`), 완료 판정은 축별 2°(`robot_motion_service.py:130-142`)라 짐벌 근처에서 타임아웃.
  - **후보 ② 조그에 Base 좌표계 가드 없음**: `job_executor` 는 `current_base_name != 'RobotBase'` 면 이동을 거부하는데(`job_executor.py:578-582` 외 8곳) `JogService`/`teaching_service.jog_tcp` 에는 같은 검사가 없다. 랜드마크 정렬(`tm_landmark_align_service.py:28-32`)로 vision base 가 된 상태의 조그는 피드백/명령 좌표계가 어긋난다. Base 전환 자체가 TCP 표시값 점프를 만든다.
  - **후보 ③ 피드백 적체**: ROS 스핀이 GUI 스레드 QTimer 10ms + `spin_once(timeout_sec=0)`(`main_window.py:538-553`) 로 초당 최대 100 콜백인데 joint_states·tool_pose·feedback_states·techman_image(영구 구독)·IO 가 이를 나눠 쓴다. 모션 대기 중엔 `spin_once(0.1)+sleep(0.05)`(`main_window.py:344-357`)로 초당 ~20회까지 떨어져 큐(depth 10)가 넘치고, 모션 후 밀린 옛 pose 가 몰려 들어와 표시값이 튄다. 조그는 이 stale 값을 절대 목표의 기준으로 쓴다.
- **해결(이번 단계 — 진단 계측만, 원인 수정 아님)**: 사용자 선택으로 로깅 먼저. 모든 모션이 지나는 `TaskManagerNode._call_set_positions` 앞에 `_log_motion_command` 신설 — `[모션] <kind> base=<이름> vel=<속도> cur=[실측 TCP 6값] target=[목표 6값]` 을 ROS logger(파일로 남음)에 INFO 기록(PTP_J 는 6축 전부 deg 환산, 그 외는 mm/deg). 진단 로그가 모션을 막지 않도록 예외는 삼킨다. `JogService._log_intent` 는 `[조그]`/`[연속 조그] axis=z+ step=10.0mm vel=20%` 를 남겨 어느 버튼인지 짝지어 준다(노드에 `get_logger` 가 없으면 조용히 생략 — 테스트 fake 노드 호환).
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/main_window.py`(`_log_motion_command` 신설, `_call_set_positions` 에서 호출), `.../services/jog_service.py`(`_log_intent` 신설, `_jog`·`_jog_continuous` 에서 호출)
- **검증**: `python3 -m pytest test/ -q -p no:anyio` → **553 passed, 1 failed**. 실패 1건 `test_recipe_manager.py::test_manager_get_job_types_by_category` 는 본 변경을 stash 한 상태에서도 동일하게 실패함을 확인(선재 결함, 본 건 무관). 최초 구현에서 `test_command_gate.py` 3건이 fake 노드의 `get_logger` 부재로 실패 → `getattr` 가드로 수정 후 전건 통과.
- **상태**: 진행중 — 실기 재현 시 `[조그]`/`[모션]` 로그로 후보 ①②③ 판별. `base` 가 RobotBase 가 아니면 ②, `cur` 이 화면·실제와 어긋나면 ③, `cur`·`target` 의 자세가 같은 방향인데 로봇이 크게 돌면 ①.

---

## 2026-08-15

### [Fix] scan_tm_landmark 실패 원인을 구분할 수 없음 — 실패 로그를 원인별로 분리

- **문제**: 드로어 마커 `scan_tm_landmark` 10회가 전부 실패. 로그는 매 회차 `Landmark 인식 완료` 직후 `측정 N: 결과 읽기 실패 또는 미검출` 만 남기고 `[오류] 유효한 측정값 없음` 으로 종료. TMflow 검출 카메라 화면에서는 마커가 **약 70% 점수로 정상 검출**되고 있어 증상과 화면이 어긋났다.
- **원인**: 진단 불능이 1차 문제였다. `scan_landmark_averaged` 의 판정이 `if read_success and isinstance(result, dict) and result.get('detected', False)` 단일 조건이고(`job_executor.py:1516`, 변경 전) `else` 가 한 줄로 뭉쳐 있어, **서로 다른 실패 3가지**가 같은 문구로 찍혔다 — (1) `g_TM_Landmark` 읽기 실패, (2) 파싱/형식 오류, (3) 읽기·파싱은 정상인데 `g_tm_landmark_detect` 가 `true`/`=1` 이 아님. 또한 `Landmark 인식 완료` 는 검출 성공이 아니라 `g_robot_command` 가 3초 안에 0 으로 복귀했다는 뜻뿐이어서(`vision_manager.py:191-199`) 오해를 키웠다. 잘 도는 `scan_tm_landmark_jig` 는 `g_jig_landmark{n}_detect`/`g_Jig_Landmark{n}` 로 **변수 쌍이 완전히 다르므로**(`vision_manager.py:271-306`) 공통 통신·파서 문제일 가능성은 낮다.
- **해결**: `scan_landmark_averaged` 의 실패 분기를 4갈래로 분리 — `변수 읽기 실패 — <사유>` / `결과 형식 오류 — <값>` / `미검출 (<detect 변수명> 가 true/=1 아님) — 읽힌 좌표 X=…, Y=…, Z=…, Rz=…` / 성공. 미검출 시 **읽힌 좌표를 함께 출력**해, 값이 정상이면 원인이 detect 변수 하나로 좁혀지고 매 회차 같은 값이면 TM Flow 에 남은 옛 값임이 드러나게 했다. jig 경로는 자기 detect 변수명을 찍는다. 판정 조건 자체와 성공 경로 동작은 변경하지 않았다.
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py`(`scan_landmark_averaged`), `.../tools/landmark_parser.py`(`parse_tm_landmark` 실패 메시지에 원문 첨부, `_echo`/`RAW_ECHO_LIMIT` 신설), `.../test/test_scan_failure_logs.py`(신설 7건), `.../test/test_landmark_parser_echo.py`(신설 8건)
- **검증**: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test/ -q` → `1 failed, 518 passed`. 신규 15건 통과. 실패 1건 `test_recipe_manager.py::test_manager_get_job_types_by_category` 는 본 변경 이전부터 실패(`scan_ar_tag` 의 category 가 HEAD 에서도 `'AR Tag'`, 단언은 `'Vision'` 기대) — 본 건과 무관.
- **경과 1 (16:38)**: 재실행했으나 로그가 이전과 동일. 원인은 코드가 아니라 **프로세스가 옛 코드를 들고 있던 것** — 실행 중 프로세스 기동 시각 `Sat Aug 15 16:26:11`, 수정 시각 16:35 이후. 빌드는 정상이었다(`install/.../tm-task-manager.egg-link` → `build/tm_task_manager` → `src/.../tm_task_manager` 심볼릭 링크, `realpath` 로 설치본=소스 동일 파일 확인). Python 모듈은 프로세스 기동 시 1회 로드되므로 `colcon build` 없이 **GUI 재시작만으로 반영**된다.
- **경과 2 (17:00, 재시작 후)**: 분리된 로그가 원인을 지목 — 10회 전부 `변수 읽기 실패 — 파싱 실패 (중괄호 형식 아님)`. 즉 **detect 변수 문제가 아니고**, `g_TM_Landmark` 는 읽히지만 값이 `{x,y,z,rx,ry,rz}` 형식이 아니다(`landmark_parser.py:21-23`, 빈 값이면 `빈 값` 이 뜨므로 비어 있지도 않다). 앞서 세운 "비전 잡 최소 점수(70%) 미달로 fail 분기" 가설은 **기각**.
- **상태**: 진행중 — 다음 실행 로그의 `원문:` 이 실제 문자열을 보여준다. 같은 파서로 `g_Jig_Landmark{n}` 은 정상 파싱되므로(`vision_manager.py:304`) 파서·통신 공통 문제가 아니라 **`g_robot_command=2` 가 도는 TMflow 잡이 `g_TM_Landmark` 에 쓰는 값의 형식/타입 문제**로 좁혀진다. 수정은 TMflow 쪽이 정공법이며, 형식이 다른 것이 확인되면 파서 확장 여부를 그때 판단한다.

### [Fix] 직사각형 검증 알람이 실행 레시피에서도 작업을 멈춤 — load_plate_pose 는 경고 로그만 남기도록 변경

- **문제**: 캘리브레이션(마커 스캔 → 저장) 레시피에서만 떠야 할 "Plate 직사각형 검증 실패 — 작업자 확인 필요" 다이얼로그(Abort/Save)가, `load_plate_pose` → `align_to_plane_normal` → `move_linear` 로 구성된 **실행 레시피**에서 팔레트마다 떠 작업이 멈췄다. 실측 로그: `[11:27:02] Plate Pose 불러오기 완료 (10개 파일 평균)` 직후 `[알람] 직사각형 검증 실패`, 대각선 차 2.217mm (상한 1.500mm).
- **원인**: `_exec_load_plate_pose` 의 마지막 줄이 `return self._confirm_plate_rectangle(averaged, params)` 로 **차단형 가드**를 그대로 호출하고(`job_executor.py:1798`, 변경 전), `load_plate_pose.params.rect_guard_enabled` 기본값이 `True`(`recipe_manager.py:439-443`)여서 불러올 때마다 검증·질의가 발생했다. 저장 시에는 그 회차 1건을 검사하지만 불러오기는 **파일 N개의 랜드마크 평균**(`average_landmarks_from_files`, `job_executor.py:1769`)을 검사하므로, 개별 측정이 통과해도 평균은 상한을 넘을 수 있다.
- **해결**: (사용자 선택) `_confirm_plate_rectangle` 에 `blocking: bool = True` 인자 추가 — `False` 면 콜백을 호출하지 않고 `[경고] 직사각형 검증 실패` + 항목별 수치 + `[경고] 실행 단계이므로 중단하지 않고 계속합니다` 로그만 남기고 `True` 반환. `_exec_load_plate_pose` 는 `blocking=False` 로 호출. 계산·저장 경로(`_exec_calculate_plate_pose`)의 차단형 동작은 그대로 유지. `load_plate_pose.rect_guard_enabled` 설명도 실제 동작에 맞게 갱신.
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py`(`_confirm_plate_rectangle`, `_exec_load_plate_pose`), `.../recipe_manager.py`(`load_plate_pose.params.rect_guard_enabled` 설명), `.../test/test_load_plate_pose.py`(가드 테스트를 경고 전용으로 갱신)
- **검증**: `pytest test/` → **484 passed, 1 failed** (실패 1건은 `test_manager_get_job_types_by_category` 선재 결함, 본 변경 무관). 갱신한 `test_rect_guard_warns_but_does_not_block_on_load` 는 사다리꼴 실측 형상(pallet3)에서 Job 이 `True` 를 반환하고 `[경고] 직사각형 검증 실패` 로그가 남으며 `[알람]` 로그·작업자 질의가 **없음**을 확인. `test_plate_rect_guard.py` 16건(계산 경로 차단형)은 전부 PASS 로 기존 동작 유지 확인.
- **상태**: 완료 (GUI 실동작 확인은 재빌드·재기동 후 필요)

### [Bug] 스팸 클릭이 전부 기억됐다가 순서대로 실행됨 — 수동·조그 명령 단일 실행 게이트

- **문제**: 조그·수동 실행 버튼을 연타하면 누른 횟수만큼 로봇이 계속 움직인다. 멈추지 않아 위험.
- **원인**: 로봇 드라이버 큐가 아니라 **GUI 이벤트 큐 재진입**이다.
  1. `main_window._send_set_positions` 가 GUI 스레드에서 동기 블로킹으로 모션 완료까지 최대 30초 대기(`rclpy.spin_once` + `time.sleep(0.05)` 루프)
  2. `main_window._log` 가 매 줄마다 `QApplication.processEvents()` 호출 (main_window.py:1026)
  3. 대기 중 쌓인 클릭이 그 `processEvents()` 시점에 배달돼 핸들러가 재진입 실행됨
- **해결**: `CommandGate` 신설 — 실행 중이면 새 명령을 그 자리에서 버린다(첫 명령만 실행). `MainWindow` 가 1개를 보유하고 진입점이 공유한다.
  - 거부를 즉시 로그하면 로그 → `processEvents()` → 다음 대기 클릭 배달 → 거부 로그 … 로 재귀가 깊어지므로, **무시 건수만 세었다가 해제 시 한 줄**로 알린다
  - 적용 지점: `JogService.jog` / `JogService.jog_continuous` / `TaskEditTab._on_move_to_params`(모든 `_exec_*` 분기가 통과하는 단일 지점)
  - `try/finally` 해제 — 한 번 잠긴 채 남으면 이후 모든 수동 명령이 죽는다
- **동작 변화**: 조이스틱 연속 조그도 게이트에 걸린다. 스틱을 밀고 있어도 "이전 모션 완료 후 다음 명령"이 되어 반응이 끊기게 느껴질 수 있다(사용자 승인 완료).
- **파일**: `tm_task_manager/services/command_gate.py`(신규) · `services/jog_service.py` · `tabs/task_edit_tab.py` · `main_window.py`
- **상태**: 완료 (실기 미검증)

### [Bug] rz_mode='plane' 이 팔레트 짧은 변을 따라감 — 긴 변(평면 Y축) 기준으로 변경

- **문제**: 평면 수직 정렬을 `rz_mode: plane` 으로 실행하면 팔레트 긴 면에 박스 짧은 면이 맞는다.
- **원인**: `tcp_pose_for_plane_normal` 이 공구 X축을 **평면 X축**에 맞춘다(`jig_plane_calculator.py:401-407`, 변경 전). 평면 좌표계 정의상 X = 짧은 변, Y = 긴 변이다(`pose_in_plane_frame` docstring).
- **해결**: `rz_mode='plane'` 일 때 공구 X축의 원천을 평면 Y축으로 바꿨다 = **평면 법선축 기준 +90° 회전**. 법선축 기준이라 수직 정렬(공구 Z ∥ 법선)이 정확히 보존된다. euler `rz + 90` 은 베이스 Z축 회전이라 기운 평면에서 정렬이 깨지므로 쓰지 않았다.
  - `rz_mode='keep'` 의 투영 실패 fallback 은 기존대로 평면 X축 유지(keep 의미 보존)
- **동작 변화**: **저장된 레시피의 `rz_mode: plane` 실제 자세가 90° 바뀐다.** `config/recipes/pallet0_align*.yaml` 등은 실행 전 확인 필요(사용자 승인 완료).
- **파일**: `tm_task_manager/tools/jig_plane_calculator.py` · `recipe_manager.py`(설명 갱신) · `test/test_plane_geometry.py`
- **상태**: 완료 (실기 미검증)

### [Feature] 평면 수직 정렬에 그리퍼 오차(공구 좌표계 5축) + 오차 preset + 현재위치 자동 추산

- **문제**: 그리퍼 장착 오차를 반영할 통로가 없어 매번 조그로 보정해야 했다.
- **해결**:
  - `offset_x`, `offset_y`, `offset_rx`, `offset_ry`, `offset_rz` 파라미터 추가. **공구 좌표계** 기준(`apply_tool_offset`: 위치 `p + R@[dx,dy,0]`, 자세 `R@R_offset`)
  - **z 오차 축은 두지 않는다** — 수직 정렬의 법선 방향 거리는 `standoff_mm` 이 정하므로, z 오차를 두면 같은 양을 정하는 손잡이가 2개가 된다
  - **'현재위치 입력'** 이 오차를 역산한다(`tool_offset_from_poses` + `estimate_plane_align_tool_offset`). 손으로 맞춰 둔 자세와 오차 0 기준 목표의 차이가 곧 오차다. **항상 오차 0 기준으로 다시 재므로** 값이 겹쳐 쌓이지 않는다. 무시한 공구 Z 차이는 `standoff_mm` 으로 조정하라고 안내
  - **오차 preset** — `OffsetPresetService` 가 `config/plane_align_offsets.yaml` 을 읽고 쓴다. 파라미터 폼에 콤보 + 적용/저장/삭제 버튼을 동적 생성하므로 `.ui` 파일 수정 없음. UI 는 서비스만 호출(파일 I/O 직접 접근 금지)
- **부수 발견·수정**: `TaskEditTab._save_params_from_ui` 가 `offset_x/y/z` 를 **이름만 보고** 건너뛰어(dict 타입 `offset` 파라미터가 펼쳐진 경우를 위한 처리), float 로 선언된 offset 파라미터가 UI 에서 저장되지 않았다. 선언 타입 기준으로 판정하도록 고쳤다 — 기존 `move_to_plane_pose` 의 offset 도 이제 저장된다.
- **파일**: `tm_task_manager/tools/jig_plane_calculator.py` · `job_executor.py` · `recipe_manager.py` · `tabs/task_edit_tab.py` · `services/offset_preset_service.py`(신규) · `main_window.py`
- **상태**: 완료 (실기 미검증)

### 2026-08-15 검증

- 신규 테스트: `test_command_gate.py` 16건, `test_offset_preset.py` 14건, `test_plane_geometry.py` +8건, `test_plane_align_job.py` +9건
- 설계 근거: [ADR 2026-08-15](../adr/2026-08-15-manual-command-gate-and-tool-offset.md)

---

## 2026-08-14

### [Feature] load_plate_pose Job 추가 — 저장된 plate_pose 로 스캔 없이 평면 정렬

- **문제**: pallet0 의 1사분면 마커(Jig4)가 검출되지 않아(`g_jig_landmark4_detect=false`) `pallet0_align` 실행이 Job 3 에서 중단. 마커 재설치 전까지 `calculate_plate_pose` 를 돌릴 수 없고, `align_to_plane_normal` 은 `detected_plate_pose` 를 요구하는데 이 값은 `calculate_plate_pose` 실행 시에만 설정되므로(`job_executor.py:1641` 단일 경로) **이미 11회 측정해 둔 우수한 데이터가 있어도 쓸 방법이 없었다.**
- **원인**: 저장된 plate_pose YAML 을 실행기 상태로 되돌리는 경로 부재.
- **해결**: `load_plate_pose` Job 신설. 저장 파일을 읽어 스캔 없이 평면 정보를 복원한다.
  - **랜드마크 좌표를 평균한 뒤 `JigPlaneCalculator` 로 재계산** — 저장된 plate_pose 값을 그대로 쓰지 않으므로 pose 와 랜드마크의 정합이 보장된다
  - **`jig_landmark_results` 도 함께 복원** — `align_to_plane_normal` 의 대각선 배치 검증(`_check_landmark_diagonal_diff`)이 이 값을 읽으므로 누락 시 정렬이 실패한다
  - 불러온 배치에도 `_confirm_plate_rectangle` 동일 가드 적용
  - params: `source_path`(파일 또는 폴더) · `file_prefix` · `average_count`(0 이하면 전부) · 가드 임계 4종
- **주의**: **플레이트가 물리적으로 움직이지 않았을 때만 유효**하다. 마커를 재설치하면 위치가 달라지므로 저장 데이터는 폐기하고 재측정해야 한다.
- **파일**:
  - `tm_task_manager/job_executor.py` (`_exec_load_plate_pose`, `_resolve_plate_pose_files`, dispatch)
  - `tm_task_manager/recipe_manager.py` (`load_plate_pose` Job 타입 등록)
  - `config/recipes/pallet0_align_from_file.yaml` (신규 — 불러오기 + 정렬 2 Job)
  - `config/recipes/pallet0_align.yaml` (신규 — 측정 10 + 정렬, A 안용)
  - `test/test_load_plate_pose.py` (신규, 12건)
- **검증**: 신규 12건 PASS, 전체 회귀 414 passed / 1 failed(`test_recipe_manager::test_manager_get_job_types_by_category` — 변경 전에도 동일 실패, 무관). 실측 pallet0 11런으로 복원한 결과가 분석 평균과 소수 3자리까지 일치(X=817.645 Y=215.038 Z=-325.940 Rx=0.260 Ry=-0.067 Rz=89.576), 정렬 목표 X=818.323 Y=214.857 Z=-175.942.
- **상태**: 완료 (실기 정렬 실행은 마커 재설치 후 대기)

### [Feature] calculate_plate_pose 에 직사각형 검증 가드 추가 — 오차 초과 시 작업자 확인 요구

- **문제**: pallet3 의 4 Landmark 배치가 사다리꼴(짧은변 137.05 vs 133.81, 차 **3.24mm**)인데 아무 경고 없이 저장되었다. 정상 팔레트는 짧은변 차가 0.03~0.48mm 라 명백한 이상인데도 검출 수단이 없었다.
- **원인**: 기존 가드 `_check_landmark_diagonal_diff`(`job_executor.py:1717`)는 **대각선만** 검사한다. pallet3 대각선 차는 0.416mm(기본 상한 10.0mm)라 무사통과한다. 게다가 이 가드는 `align_to_plane_normal` Job 에서만 호출되고 `calculate_plate_pose` 경로에는 없었다. **변 길이 검사 부재**가 근본 원인.
- **해결**: `calculate_plate_pose` 계산 직후·**저장 전**에 직사각형 검증 가드를 삽입. 실패 시 안내 창을 띄우고 작업자가 [저장하고 계속] / [중단] 을 선택한다.
  - 검증 4항목은 기존 `JigPlateValidator.check_rectangle()` 재사용 — 대향변(수평/수직) 차, 대각선 차, 직각도
  - 임계 기본값(B 표준): 변 차 **1.0mm** / 대각 차 **1.5mm** / 직각도 **1.0°**, 레시피 파라미터로 조정 가능
  - `rect_guard_enabled` 로 on/off. UI 콜백 미등록 시 저장하지 않고 중단(fail-safe)
  - 아키텍처 준수 — 판정은 `tools`/`job_executor`, 다이얼로그는 `main_window`. job_executor 는 콜백 emit 만
- **파일**:
  - `tm_task_manager/tools/jig_plate_validator.py` (`load_from_dicts`, `get_side_lengths` 추가)
  - `tm_task_manager/job_executor.py` (`on_plate_rect_alarm` 콜백, `_confirm_plate_rectangle`, 가드 삽입)
  - `tm_task_manager/main_window.py` (`_on_plate_rect_alarm` 다이얼로그 + 콜백 연결)
  - `tm_task_manager/recipe_manager.py` (파라미터 4종 등록)
  - `test/test_plate_rect_guard.py` (신규, 16건)
- **검증**: 신규 테스트 16건 PASS, 전체 회귀 402 passed / 1 failed(`test_recipe_manager::test_manager_get_job_types_by_category` — 변경 전에도 동일 실패, 본 변경과 무관). 실측 70런 적용 결과 pallet3 10/10·pallet5 11/11·pallet1 1/11 발동, pallet0/2/4 는 0건.
- **상태**: 완료

### [Issue] plate_pose 측정 이상을 팔레트 하드웨어 탓으로 오귀속 — 스캔(카메라) 오차로 정정

- **문제**: `data/plate_pose_calc` 분석 보고에서 pallet3 의 사각형 짧은 변 3.24mm 불일치(jig4 Y 좌표 2.326mm 차이)를 "jig4 마커가 물리적으로 이동" 가설로 제시하고, 권고 1순위를 **팔레트 실물 점검**으로 지정했다. 같은 논리로 안장형 뒤틀림·자세각 위치 의존성도 "플레이트 제작 뒤틀림 vs 측정계 오차" 를 대등하게 놓았다.
- **원인**: 측정 조건이 동일한데 값이 달라진 경우의 귀속 순서를 어겼다. 같은 분석에서 이미 **검출기가 위치를 2.0417mm 격자 정수배로 잘못 읽는 현상 17건**과, 그 오차가 10회 반복 + 3sigma 평균을 전부 통과할 만큼 결정론적이라는 사실을 정량화해 둔 상태였다. 즉 측정계 오차 쪽에는 증거가 쌓여 있었고 물리적 이동 쪽에는 증거가 0건이었는데도 두 가설을 대등하게 제시했다.
- **해결**: 사용자 지적 2회를 거쳐 **재현성으로 분기하는 판정 기준**을 확정.
  - 1차 지적: "다 똑같이 쟀는데 값이 **튄거면** 그냥 스캔 값 에러입니다. 카메라가 측정한값. 팔레트 문제가 아니에요"
  - 2차 지적: "원인이 **일시적이면 스캔오차** 맞지만 **일정하면 팔레트나 하드웨어 문제** 맞아."
  > **측정값 귀속 원칙 — 재현성으로 분기 (확정판)**
  >
  > 측정 조건이 동일한데 값이 다를 때, **반복 측정의 산포**로 귀속을 나눈다.
  > - 편차가 런마다 다르고 재측정 시 사라진다(일시적·랜덤) → **스캔(카메라) 오차**. 실물 점검 권고 금지, 재측정으로 회피.
  > - 편차가 런마다 일정하고(산포 ≪ 편차) 재측정해도 남는다(계통) → **팔레트·하드웨어 문제**. 실물 점검 대상.
  >
  > 판정은 서술이 아니라 수치로 한다. `편차 / 반복산포` 비를 계산해 명시한다. 현상 서술과 귀속 결론이 이 표와 일치하는지 보고 전에 대조한다.
  - 11:15~11:21 격자 점프(런마다 8·16·40mm 랜덤, 재측정 시 소멸) → **스캔 오차** ✅
  - pallet3 사다리꼴 3.243mm (10런 std 0.0058mm, 편차/산포 = **540배**) → **팔레트/하드웨어 문제** — jig4 마커 실물 점검 대상
  - 안장형 뒤틀림 ±0.35~0.49mm (반복산포 0.003mm, **130배**) → **하드웨어 계통** (플레이트 뒤틀림 또는 로봇/카메라 기구 — 90° 회전 시험으로 분리)
  - 자세각 위치 의존 (Ry vs Y r=+0.957, Rz vs Y r=−0.964, 세션내 산포 0.001~0.013°) → **하드웨어/캘리브레이션 계통**
- **파일**: `docs/claude-mistake/2026-08-14-001.md`, `docs/claude-mistake/2026-08-14-002.md` (실수 기록 2건), 분석 대상 `src/TM_Robot_Task_Manager/data/plate_pose_calc/`
- **상태**: 완료

### [Fix] Plate Pose 저장본에 이력 추적 정보 부족 — 파일명 타임스탬프 + 측정 시각 + 작업자 기록 추가 (MK2 선적용)

- **문제**: 직전 개선(폴더 저장)에서 파일명이 `<레시피>_<캡션>.yaml` 고정이라 재실행 시 이전 결과가 덮어써지고, 저장본만 봐서는 **언제 측정했는지·누가 작업했는지** 알 수 없었다.
- **원인**: 파일명에 시각 요소 없음(`_plate_pose_file_name`), 저장 데이터에 저장 시각(`saved_at`)만 있고 각 Jig 의 측정 시각이 없음 — `_exec_scan_tm_landmark_jig` 가 `jig_landmark_results[n]` 에 좌표만 넣고 시각을 남기지 않았기 때문(`job_executor.py:1582`, 변경 전). 작업자 입력 수단도 없었음.
- **해결**: (사용자 승인 후) 3곳 변경 —
  - 파일명 `<레시피명>_<캡션>_<저장시각 YYYYMMDD_HHMMSS>.yaml` (매 실행 새 파일, 덮어쓰기 없음)
  - `_exec_scan_tm_landmark_jig` 가 스캔 결과에 `measured_at`(스캔 완료 시각) 을 기록 → 저장본의 jig1~4 **각 좌표마다** 측정 시각 동반. 값이 없으면 `null`. `JigPlaneCalculator.load_from_dicts` 는 x/y/z/rx/ry/rz 만 명시 참조(`jig_plane_calculator.py:76-80`)라 키 추가는 무해.
  - Task 파라미터 `operator`(str) 신설 — 저장본 최상단 `operator` 로 기록, 비면 `[경고] 작업자 이름이 비어 있습니다` 로그 후 `null` 로 저장(사용자 선택). `str` 타입은 기존 UI 의 기본 `QLineEdit` 분기로 렌더되어 UI 코드 추가 0.
  - 저장본에 `recipe`·`task_caption` 도 함께 기록.
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py`(`_exec_scan_tm_landmark_jig`, `_exec_calculate_plate_pose`, `_plate_pose_file_name`, `_save_plate_pose`), `.../recipe_manager.py`(`calculate_plate_pose.params.operator`), `.../test/test_plate_pose_save.py`
- **검증**: `pytest test/` → **386 passed, 1 failed** (실패 1건은 `test_manager_get_job_types_by_category` 선재 결함, 본 변경 무관). 신규 포함 `test_plate_pose_save.py` **11건 전부 PASS**. 실제 저장 실행 결과: 파일명 `pallet3_cali_pallet_plate_pose_calc_20260814_093040.yaml`, 내용에 `operator: 홍길동`, `recipe`, `task_caption`, `saved_at`, jig1~4 각각 `measured_at` 확인.
- **상태**: 완료 (MK4 이식은 사용자 실험 후 별도 승인 대기)

### [Fix] `calculate_plate_pose` 결과가 메모리에만 남아 재시작 시 소실 — Task 파라미터에 저장 경로 추가

- **문제**: `calculate_plate_pose` Task 가 계산한 Plate Pose 가 로그로만 출력되고(`Plate Pose 계산 완료: X=549.039 ...`) 어디에도 저장되지 않아 프로그램 재시작 시 사라짐.
- **원인**: `_exec_calculate_plate_pose` 가 결과를 인스턴스 변수 `self.detected_plate_pose` 에만 대입(`job_executor.py:1632`). 파일 기록 경로 없음 — `ConfigManager._save_config` 는 `positions.yaml` 전용, `CoordinateSystemManager.save_to_config` 는 coordinate_definitions 스키마 전용이라 임의 경로 저장에 재사용 불가.
- **해결**: Task 파라미터 `save_path`(신규 `dirpath` 타입 — **폴더** 지정) 추가. 폴더 지정 시 `<레시피 파일명>_<Task 캡션>.yaml` 로 `plate_pose` 6값 + `saved_at` + 입력 landmark 4점(jig1~4)을 기록. 상대 경로는 `paths.PACKAGE_ROOT` 기준 해석, 폴더 자동 생성, 저장 실패 시 로그 후 Job 실패(return False). 폴더가 비면 기존과 동일하게 메모리에만 유지.
  - 파일명: 레시피 미로드 시 캡션만, 캡션도 없으면 `<job type>_<job id>`. 경로 구분자 등 비허용 문자는 `_` 로 치환.
  - UI: Task 파라미터 패널에 `QLineEdit` + `폴더 선택...` 버튼(`QFileDialog.getExistingDirectory`) 행 렌더. 내부 `QLineEdit` 를 `param_widgets` 에 등록해 기존 파라미터 저장 로직(`_save_params_from_ui`)은 무수정.
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py`(`_exec_calculate_plate_pose`, 신규 `_save_plate_pose`·`_plate_pose_file_name`), `.../recipe_manager.py`(JOB_TYPES `calculate_plate_pose.params.save_path`), `.../tabs/task_edit_tab.py`(`dirpath` 위젯 분기, 신규 `_on_browse_dirpath`), 신규 테스트 `.../test/test_plate_pose_save.py`
- **검증**: `pytest test/` → **383 passed, 1 failed**. 실패 1건은 `test_recipe_manager.py::test_manager_get_job_types_by_category`(`scan_ar_tag` 카테고리) 로, 본 변경 stash 후 재실행에서도 동일 실패 — 선재 결함(본 변경 무관). 신규 `test_plate_pose_save.py` 8건 전부 PASS(레시피+캡션 파일명·폴백 파일명·문자 치환·상대 경로 해석·저장 실패 시 Job 실패·빈 경로 무저장·파라미터 정의 검증).
- **상태**: 완료

### [Fix] `ros2 launch` 가 `tm_task_manager` 를 못 찾음 — 워크스페이스 이름 변경으로 `--symlink-install` 심링크 962개 전멸

- **문제**: `./run` 실행 시 `Package 'tm_task_manager' not found` — 에러 메시지의 탐색 경로에는 `install/tm_task_manager` 가 정상적으로 들어 있는데도 패키지를 못 찾음. `ros2 node list` 도 빈 출력.
- **원인**: 워크스페이스 디렉토리가 `TM_Robot_ros2_ws` → `TM_Robot_MK2_ros2_ws` 로 **이름이 바뀌었고**(디렉토리 mtime 2026-08-13 16:41), `colcon build --symlink-install` 이 심링크를 **절대경로**로 박아둔 탓에 전부 끊겼다. 실측: `install/` 심링크 1008개 중 **962개가 broken**(전부 옛 이름 참조), `build/` 안에도 옛 경로 문자열 참조 1134개 파일. 결정적으로 ament 패키지 마커
  `install/tm_task_manager/share/ament_index/resource_index/packages/tm_task_manager` → `/home/amap/.../jjh/TM_Robot_ros2_ws/build/tm_task_manager/resource/tm_task_manager` 가 깨진 심링크라(`readlink -e` 실패) 패키지가 색인에서 사라졌다. `AMENT_PREFIX_PATH` 자체는 상대경로 기반이라 정상 소싱돼, "경로는 뒤졌는데 없다"는 형태로 에러가 났다. (옆 워크스페이스 `TM_Robot_MK4_ros2_ws` 는 제자리 빌드라 broken 0개 — 대조군)
- **해결**: (사용자 승인 후) 클린 재빌드 — `rm -rf build install log` 후 `colcon build --symlink-install`. 코드 수정 0줄.
  - **1차 시도 실패**: `custom_package` 가 `tm_msgs` 를 못 찾아 중단(6개 실패/중단, 15개 미처리). 아래 별도 entry 참조.
  - **2차 시도(2단계 빌드) 도 실패**: `--packages-up-to tm_msgs` 로 순서를 앞세워도 동일 실패. colcon 은 각 패키지 빌드 환경에 **package.xml 에 선언된 의존의 prefix 만** 넣으므로, 미선언 의존은 순서를 바꿔도 해결되지 않는다(문제는 순서가 아니라 환경 격리). — 최초 진단이 한 겹 얕았던 지점.
  - **3차 시도 성공**: `install/setup.bash` 를 **부모 셸에 먼저 소싱**한 상태로 `colcon build --symlink-install` → 워크스페이스 prefix 가 부모 환경으로 상속돼 `custom_package` 가 `tm_msgs` 를 찾음. **25개 패키지 전부 성공 (2min 19s)**.
- **파일**: 없음 (빌드 산출물만 재생성)
- **검증**: `find install/ -xtype l | wc -l` = **0**, 옛 이름 참조 심링크 **0**, `install/` 텍스트 내 옛 경로 **0**. 패키지 마커가 실경로 `src/TM_Robot_Task_Manager/resource/tm_task_manager` 로 해석됨. `ros2 pkg list` 에 `tm_task_manager`·`tm_web_bridge`·`tm_driver`·`tm_msgs`·`tm_description` 검출. `ros2 launch tm_task_manager task_manager.launch.py --show-args` 정상 출력(`robot_ip` 인자 노출). `./run check` 에서 패키지 미검출 에러 소멸.
- **상태**: 완료
- **재발 방지**: `--symlink-install` 워크스페이스는 **디렉토리 이름을 바꾸면 install/build 가 통째로 무효**가 된다. 이름 변경 시 `rm -rf build install log` + 재빌드를 함께 수행할 것.

### [Issue] `custom_package` 가 `tm_msgs` 의존을 package.xml 에 선언하지 않아 클린 빌드 불가 (부채 등록)

- **문제**: 클린 빌드 시 `custom_package` 가 `CMake Error ... Could not find a package configuration file provided by "tm_msgs"` 로 실패하고, 이후 `tm_task_manager` 를 포함한 다수 패키지가 연쇄 중단.
- **원인**: `src/Robot/tmrobot_official_packages/custom_package/CMakeLists.txt:29` 이 `find_package(tm_msgs REQUIRED)` 를 호출하지만 같은 패키지의 `package.xml` 에 `tm_msgs` 의존 선언이 **없다**(`techman_robot_msgs` 만 있음). colcon 은 package.xml 의 선언으로 빌드 순서와 **빌드 환경의 prefix 경로**를 모두 결정하므로, 미선언 의존은 클린 빌드에서 반드시 실패한다. 그동안 드러나지 않은 이유는 `tm_msgs` 가 이전 증분 빌드의 `install/` 에 남아 있었기 때문 — 즉 이 워크스페이스는 **클린 빌드가 불가능한 상태로 잠복**해 있었고, install 삭제로 노출됐다. (같은 파일의 `ament_index_cpp`·`tf2_geometry_msgs` 도 미선언이나 `/opt/ros/humble` 에 있어 무해)
- **해결**: 미적용 — 사용자가 **파일 무수정** 방침을 선택. 우회책으로 `install/setup.bash` 를 부모 셸에 소싱한 뒤 빌드하면 통과한다.
- **파일**: `src/Robot/tmrobot_official_packages/custom_package/package.xml` (미수정), `.../custom_package/CMakeLists.txt:29` (미수정)
- **상태**: 보류 (부채 `debt-004` 등록) — 근본 수정은 `package.xml` 에 `<depend>tm_msgs</depend>` 1줄 추가

### [Issue] 로봇 169.254.88.255 무응답 — LAN 물리 계층은 정상, 세그먼트에 응답 장비 0

- **문제**: `./run` 사전 점검에서 `✗ 로봇(169.254.88.255) 무응답`. 사용자는 LAN(Local Area Network) 연결 상태라고 확인.
- **원인**: 미확정 (PC(Personal Computer) 측 아님이 확인된 단계). 실측 증거 —
  - `eno1`: `Link detected: yes`, `Speed: 1000Mb/s`, `Duplex: Full`, IP `169.254.183.100/16` (기존 기록과 동일한 정상 구성)
  - `ping 169.254.88.255` 3/3 손실, `ip neigh` = `FAILED` (ARP 무응답)
  - 링크로컬 **/16 전체 65,534개 주소 ping 스윕 → 응답 0**, ARP 전부 FAILED/INCOMPLETE. IPv4 브로드캐스트(`ping -b 169.254.255.255`) 4/4 손실, IPv6 링크로컬 all-nodes 멀티캐스트(`ff02::1`) 무응답.
  - 단 `/proc/net/dev` 의 eno1 RX 는 계속 증가(10초에 13패킷, ~1.3pps) — 선에 뭔가 물려 트래픽은 오고 있으나 우리 주소 체계에 응답하지 않음.
  - GUI 기동 후 실측: `tm_driver`(pid 37667) 는 살아 있고 `/feedback_states` 를 66Hz 로 발행하나 내용은 `is_svr_connected: false`, `is_sct_connected: false`. `ss -tanp` 에서 TMSVR 소켓이 `SYN-SENT 169.254.183.100:44784 → 169.254.88.255:5891` 로 **고착**(로봇이 SYN 에 미응답). 명령 채널이 없어 로봇이 움직이지 않음.
  - 한계: `arp-scan`·`tcpdump` 는 sudo 암호가 필요해 미실행. 로봇이 링크로컬이 **아닌** 대역(예: 192.168.x 고정 IP)에 있다면 eno1(169.254.183.100/16 단독)로는 도달 불가라 이 스윕으로 검출되지 않는다.
- **해결**: PC 측 조치 없이 해소 — 로봇이 응답을 시작하자 `tm_driver` 의 `reconnect: true` 재접속 루프가 자동으로 TCP 를 수립했다. 해소 후 실측: ping 3/3 (0.2ms), ARP `169.254.88.255 lladdr 00:10:f3:b3:bf:b7 REACHABLE`(MAC(Media Access Control) 이 기록상 이 기체 `TM14S-M` 과 일치), 5890·5891 둘 다 `ESTAB`, `is_svr_connected/is_sct_connected` **true**, `robot_link: true`, `error_code: 0`. 로봇 모션 정상 동작 확인(사용자).
  - **로봇을 찾은 방법**: IP 대역 스윕이 아니라 **MAC OUI(Organizationally Unique Identifier) 지문**(`00:10:f3` = TM 제어박스)으로 `ip neigh` 전체를 훑어 검출. IP 기준 스윕은 로봇이 응답을 시작하기 전이라 전부 놓쳤다.
  - **기각된 가설 — 수동 모드**: `Operation_Mode=0`(수동)을 원인으로 지목했으나 **오진**. 연결 수립 후 동일한 `Operation_Mode=0` 상태에서 로봇이 정상적으로 움직였다. 수동 모드는 Listen 노드 외부 명령을 막지 않는다(속도 제한만 적용). 원인은 처음부터 끝까지 TCP 미수립 하나였다.
- **파일**: 없음
- **상태**: 완료 (로봇 측 요인으로 해소, PC 측 코드·설정 무변경)
- **교훈**: `is_svr_connected`/`is_sct_connected` 와 `ss -tanp` 의 소켓 상태(`SYN-SENT` vs `ESTAB`)가 로봇 연결 여부의 **1차 판정 근거**다. GUI 표시등과 `robot_link` 만 보면 오판한다.

### [Issue] GUI "연결됨" 표시가 실제 로봇 링크를 반영하지 않음 — 서비스 응답만 보고 켜짐

- **문제**: 로봇과 TCP 가 전혀 안 붙은 상태(`is_svr_connected: false`, 소켓 SYN-SENT)인데도 GUI 상태바가 `연결됨: 169.254.88.255` 로 표시됨. 사용자가 연결됐다고 판단하고 조작했으나 로봇이 움직이지 않아 원인 파악이 지연됐다.
- **원인**: `robot_connection.py:85-88` — `connect_tm` **서비스 응답의 `ok` 필드만** 보고 `ConnectionState.CONNECTED` 로 전이한다. 이 `ok` 는 tm_driver 가 재접속 요청을 접수했다는 뜻이지 TCP 수립 성공이 아니다. 실제 링크 상태인 `FeedbackState.is_svr_connected`/`is_sct_connected` 는 `main_window.py:222` 에서 수신만 하고 연결 표시에는 쓰이지 않는다(`job_executor.py:148` 은 `is_sct_connected` 를 실행 가드로 제대로 사용 중 — 즉 같은 저장소 안에서 판정 근거가 갈려 있다).
- **해결**: 미적용 (수정은 승인 필요). 방향: `ConnectionState.CONNECTED` 전이 조건에 `is_svr_connected` 를 포함하거나, 서비스 응답 단계를 `CONNECTING` 으로 두고 FeedbackState 수신 시 `CONNECTED` 로 확정.
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:85-88`, `src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:222`
- **상태**: 보류 (승인 대기)

---

## 2026-08-11

### [Fix] 이미지 캡처 트리거를 `g_robot_command=3` 으로 환원 — 2026-07-07 `Vision_DoJob_PTP` 방식 철회

- **문제**: Vision 탭 `Image Capture` 버튼 클릭 시 오류. 이미지가 오지 않고 15초 타임아웃. 추가로 캡처 시도 직후 TMSCT(5890) 제어 채널까지 끊김.
- **원인**: 캡처 트리거가 `Vision_DoJob_PTP("TM_IMG_Send", 100, 500)` 였음 — `image_capture_service.py:50` (구버전). 이는 2026-07-07 작업에서 당시 로봇 프로젝트("listen node DIO test")에 맞춰 `g_robot_command=3` 방식을 걷어내고 넣은 것인데, **그 판단 자체가 잘못**(사용자 확인). 현재 로봇 프로젝트는 전역변수 명령 규약을 쓰며 `TM_IMG_Send` 비전 잡이 없다. `send_script` 의 `ok=True` 는 스크립트 전달 성공일 뿐 잡 실행 성공이 아니라 오류가 드러나지 않았다. 로그 증거 `~/.ros/log/python3_206964_*.log:84-86` — `스크립트 전송 성공: Vision_DoJob_PTP(...)` 이후 이미지 수신 없음. 같은 저장소의 AI 캡처 경로(`job_executor.py:2166`)는 계속 `g_robot_command=3` 을 쓰고 있어 두 경로가 갈라져 있었다.
- **해결**: (사용자 승인 후) 캡처 트리거를 `g_robot_command=3` + `ScriptExit()` 로 환원, `job_executor.py:2164-2172` 와 동일 규약.
  - `image_capture_service.py`: 상수 `VISION_CAPTURE_COMMAND_VAR="g_robot_command"` / `VISION_CAPTURE_COMMAND=3` 신설(단일 근원), 전송부 16줄 → `_send()` 로 교체. `motion_gateway.send_vision_job` 안전 기록 래퍼는 유지. 7/7 잔재인 `VISION_CAPTURE_JOB_DEFAULT` 상수와 `get_vision_capture_job()` 함수(12줄) 삭제.
  - `tm_web_bridge/bridge_node.py`: 동일 실수가 남아 있던 `capture_vision`(구 :287)·`capture_still`(구 :310) 을 공용 `_trigger_capture_command()` 로 통합, 상수는 `image_capture_service` 에서 import(중복 정의 회피). `job_name` 인자는 API 호환 위해 유지하되 미사용.
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/services/image_capture_service.py`, `src/tm_web_bridge/tm_web_bridge/bridge_node.py`
- **검증**: `colcon build --packages-select tm_task_manager tm_web_bridge` 0 errors. `pytest test/` **375 passed, 1 failed** — 실패 1건은 `test_recipe_manager.py::test_manager_get_job_types_by_category` 로 본 변경과 무관한 기존 실패(해당 모듈 `git diff` 없음). GUI 재기동 후 버튼 클릭 로그 `~/.ros/log/python3_249860_*.log` — `Sending script: g_robot_command=3` / `변수 쓰기 성공: g_robot_command=3` 까지 정상 도달 확인.
- **상태**: PC 측 완료 — 이미지 수신은 **로봇 설정 대기**(코드 문제 아님).
  - 트리거 정상 동작 확인: Listen 노드 연결 상태에서 `g_robot_command=3` + `ScriptExit()` → `ok=True`, 이후 `ask_item` 으로 **값이 3 → 0 으로 리셋**됨 = `ROS2_COM5` 의 3번 분기가 실제 실행됨.
  - 그럼에도 이미지 미수신: 45초간 `ss -tan`(TIME_WAIT 포함) 감시에서 **6189 유입 0건**. 구 방식 `Vision_DoJob_PTP("TM_IMG_Send", 100, 500)` 도 동일하게 0건 — 트리거 종류와 무관.
  - PC 수신 경로는 정상: 로컬에서 `POST http://127.0.0.1:6189/api/DET` (multipart, `name="image"`) → HTTP 200 + `/techman_image` 발행 실측 PASS.
  - **근본 원인 — 로봇 교체**: 이미지가 되던 시점의 로봇은 `169.254.122.16`(MAC `00:10:f3:bf:3f:60`), 현재는 `169.254.88.255`(MAC `00:10:f3:b3:bf:b7`, `TM14S-M`) 로 **제어박스가 다른 기체**. 비전 잡 `TM_IMG_Send` 와 외부 감지 URL `http://169.254.183.100:6189/api/DET` 는 2026-07-07 에 **이전 로봇의 "listen node DIO test" 프로젝트**에 설정한 것이라 새 로봇에는 존재하지 않는다.
  - **남은 조치(로봇 측)**: `ROS2_COM5` 에 비전 노드(찾기→외부 감지, URL `http://169.254.183.100:6189/api/DET`) 추가 후 `g_robot_command==3` 분기가 그 노드를 거치도록 배치.
  - 참고: 진단 중 `ScriptExit()` 가 Listen 노드를 종료시켜 원인이라고 의심했으나 **기각**. 당시 실험 2건이 무효였다(① 서비스 호출이 Listen 단절로 실패해 관측값이 GUI 조작 결과였음 ② `{id:'t2', ...}` 처럼 콜론 뒤 공백 누락으로 `Failed to populate field`). 유효한 측정에서는 `ScriptExit()` 후 프로젝트가 정상적으로 분기를 돌고 Listen 노드로 복귀했다.

### [Fix] tm_driver 가 `ROS_LOCALHOST_ONLY=1` 로 기동돼 GUI 와 DDS 격리 — `run` 사전 점검 보강

- **문제**: 로봇과 TCP 는 붙어 있는데 GUI 에 로봇 상태가 안 뜸. `/feedback_states` 퍼블리셔 0, `ros2 node list` 에 tm_driver 부재.
- **원인**: tm_driver(pid 224066)가 `ROS_LOCALHOST_ONLY=1` 셸에서 수동 기동됨. task_manager 는 `0`. 값이 다르면 DDS 디스커버리 도메인이 분리돼 토픽이 상호 불가시. `run` 의 `preflight` 는 실행 중 드라이버의 **IP만** 비교해 "✓ 재사용" 으로 오판(`run:61-64` 구버전).
- **해결**: `run` 에 `ROS_LOCALHOST_ONLY`/`ROS_DOMAIN_ID` 를 `export`(기본 0), 실행 중 프로세스의 환경변수를 `/proc/<pid>/environ` 에서 읽는 `proc_env()` 추가, IP 가 같아도 DDS 설정이 다르면 종료 후 재기동하도록 분기 추가, 종료 로직을 `kill_driver()` 로 분리, `/feedback_states` 퍼블리셔 수를 실제 확인하는 `driver_topic_check()` 추가, launch 에 두 환경변수 명시 전달.
- **파일**: `run` (저장소 루트 상위 `/home/amap/Project/T-Robotics/jjh/run`)
- **검증**: `bash -n` 통과. `./run check` 출력 — `· DDS: ROS_LOCALHOST_ONLY=0 ROS_DOMAIN_ID=0`, `✓ tm_driver 실행 중 (pid=230392, robot_ip=169.254.88.255, LOCALHOST_ONLY=0, DOMAIN_ID=0) — 재사용`, `✓ /feedback_states 퍼블리셔 1개 — ROS 브리지 정상`. 재기동 후 GUI 로그 `로봇 연결 성공: 169.254.88.255`.
- **상태**: 완료 (참고: DDS 불일치 감지 분기는 현재 환경이 일치 상태라 실제 발동을 재현하지 못했고 정상 경로만 실측 확인)

---

## 2026-08-10

### [Feature] PTP 이동 대각선 금지 옵션(`decomposed_tcp`) — 축 분해로 충돌 위험 구간 제거

- **문제**: PTP 이동은 X·Y·Z 를 동시에 보간해 대각선 궤적을 그린다. 경로 중간에 장애물이 있으면 시작점과 목표점이 모두 안전해도 충돌한다. 이동 축을 분리해 궤적을 예측 가능하게 만들 옵션이 필요했다.
- **해결**: `move_to_point`·`go_home` 에 `decomposed_tcp` (bool, 기본 `False`) 파라미터 신설. 켜면 단일 PTP 명령을 축별 순차 **LINE_T(직선)** 명령으로 분해한다.
  - **분해 구간에 PTP 가 아니라 LINE_T 를 쓰는 이유**: PTP 는 관절 공간에서 보간하므로 시작·목표가 한 축으로만 달라도 TCP 의 실제 경로는 직선이 아니라 휜다. 즉 PTP 로 분해하면 "목표점만 축 정렬"일 뿐 경로는 대각선일 수 있어 충돌 회피 목적을 달성하지 못한다. LINE_T 는 직교 공간 직선을 보장한다. (최초 구현은 PTP_T 였고 사용자 지적으로 교정 — 실기에서 이 차이가 드러나기 전에 잡았다.)
  - 순서 — **상승/수평**: `회전 → Z축 → 긴 XY축 → 짧은 XY축`, **하강**: `회전 → 긴 XY축 → 짧은 XY축 → Z축`. 하강에서 Z 를 마지막에 두는 것은 목표 XY 도달 전에 내려가 장애물과 충돌하는 것을 막기 위함이며, 기존 `_build_pose_keep_segments` 의 상승 Z-먼저/하강 XY-먼저 규칙과 동일한 방향이다.
  - 회전(Rx/Ry/Rz)은 상승·하강 모두 **맨 처음** 적용해 이후 병진 구간에서 자세가 고정되도록 했다.
  - 이동량이 `DECOMPOSED_MIN_STEP_MM`(0.1mm) / `DECOMPOSED_MIN_STEP_DEG`(0.1°) 미만인 단계는 명령을 보내지 않고 건너뛴다. 다만 건너뛴 축 값이 유실되지 않도록 **마지막 웨이포인트는 항상 정확한 목표값으로 확정**한다(잔차 0). 이 처리가 없으면 임계값 미만 축이 마지막 단계 뒤에 올 때 목표점에 도달하지 못한다 — 신규 테스트에서 실제로 검출된 결함이다.
  - 단계 사이마다 `_stop_requested` 를 확인해 중단 요청에 반응하고, 한 단계라도 실패하면 남은 단계를 실행하지 않고 즉시 중단한다.
  - `motion_type='joint'` 은 축 분해가 성립하지 않으므로 옵션을 무시하고 기존 단일 `PTP_J` 로 실행하며 그 사실을 로그로 남긴다.
- **구조**: 코드베이스의 기존 패턴(`_build_pose_keep_segments`)을 따라 **웨이포인트 생성(`_build_decomposed_tcp_waypoints`, 순수함수)과 실행(`_move_to_position_decomposed`)을 분리**했다. 순차 실행이 성립하는 근거는 `main_window.py:194-235` 의 `_call_set_positions` 가 `_check_motion_complete()` 를 3회 연속 안정까지 폴링하는 블로킹 호출이라는 점이다.
- **각도 wrap 결함 (실기에서 검출·수정)**: 회전 단계 판정을 `abs(target - current)` 로 하던 탓에, 자세가 ±180° 근처일 때(로봇 실측 Rx 가 `-179.9994` ↔ `180.0` 로 오가는 구간) 차이를 **359.99°로 오판**해 현재 자세와 동일한 **무의미한 회전 명령**을 1단계로 발행했다. 단위 테스트는 깔끔한 정수 각도만 써서 놓쳤고 실기 로그에서 4단계가 나오며 드러났다. Qt-free 인 `CoordinateTransformer.angle_difference_deg()` 를 신설(정규화 `(t-c+180)%360-180`)해 사용. `robot_motion_service._normalize_angle_deg` 가 이미 동등한 로직을 갖지만 그 모듈은 `PyQt5` 를 import 하므로, 헤드리스인 웹 브리지(`BridgeJobExecutor`)를 Qt 에 결합시키지 않기 위해 재사용하지 않았다 — 두 구현의 통합은 후속 과제로 남긴다.
- **단위 검증 보강 (실기가 잡은 것을 단위가 잡도록)**: 최초 테스트가 wrap 결함을 놓친 원인은 **깨끗한 정수 각도만 썼기 때문**이다. 실측 자세를 그대로 fixture 로 넣고(`REAL_LOW`/`REAL_HIGH` = 로봇이 보고한 `-179.99981…`/`179.99942…` 원시값), 등가 각도쌍 7종 × 회전 3축을 파라미터화해 전수 검사하며, 실기에서 돌린 4개 시나리오를 `TestRealRobotScenarios` 로 박제했다. 테스트 34 → **72건**.
- **테스트가 정말 그 결함을 잡는지 증명 (mutation 확인)**: 선언만으로는 믿을 수 없으므로 수정 코드를 일시적으로 결함 버전으로 되돌려 실패를 확인했다 — 정규화를 `abs(target - current)` 로 되돌리면 **21건 실패**, LINE_T 를 PTP_T 로 되돌리면 `test_every_step_uses_line_t_for_straight_path` **1건 실패**. 양쪽 모두 복원 후 72건 전부 통과.
- **검증**: 전체 **207 passed / 1 failed**. 실패 1건은 기존 실패(`test_recipe_manager.py::test_manager_get_job_types_by_category`, `assert 'scan_ar_tag' in categories['Vision']`)로 본 변경과 무관. `colcon build` 성공. 공용 모듈 추출 후 mutation 확인 재실행 — 정규화를 되돌리면 **22건 실패**(티칭 경로 테스트 포함), 복원 시 84건 통과.
- **실기 검증 (로봇 169.254.122.16, 속도 10%)**: 웹 브리지 `POST /sequence/run` 경로(GUI 시퀀스 실행과 동일한 `job_executor`)로 수행. 각 단계 로그와 별개로 `/robot/status` 를 폴링해 **실제 좌표로 축 분리를 물리 검증**했다.
  - 옵션 OFF: 단일 이동, 로그에 `[decomposed_tcp]` 없음 — 기존 동작 무변화 확인.
  - ON 하강: 로그 `X축 → Y축 → Z축`. 실측 t+10s `[-261.95, 198.46, 297.41]`(X만 변화) → t+20s `[-268.28, 188.46, 293.63]`(XY 완료 후 Z 하강 시작). **Z 최후** 확인.
  - ON 상승: 로그 `Z축 → X축 → Y축`. 실측 t+10s `[-268.29, 188.46, 269.35]`(Z만 상승) → t+30s `[-248.23, ...]`(그 다음 X). **Z 최초** 확인.
  - ON 회전 포함(Rz 180→170): 로그 `회전 → X축 → Y축 → Z축`. 실측 샘플1 에서 **XYZ 는 그대로이고 Rz 만 173.6** 으로 변화 — 회전 선행·위치 고정 확인.
  - 도달 오차 0.00~0.01mm.
- **파일**: src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py, .../recipe_manager.py, .../services/coordinate_transformer.py, .../services/decomposed_move_planner.py(신규), .../services/teaching_service.py, .../tabs/task_edit_tab.py, .../test/test_decomposed_tcp_move.py(신규), .../test/test_teaching_decomposed_move.py(신규)
- **티칭 경로(`이 위치로 이동`)까지 확장**: 최초 구현은 **Job 시퀀스 실행 경로에만** 적용돼, Task 편집 탭에서 체크박스를 켜도 `이 위치로 이동` 은 단일 PTP 로 움직였다(사용자 실사용에서 발견). 그 버튼은 `_exec_motion_move()` → `teaching_service.move_to_position()` → `main_window._move_to_position` 이라는 **다른 경로**이고 분해 로직은 `job_executor` 안에만 있었기 때문이다.
  - **해결 구조**: 웨이포인트 생성 순수함수를 `services/decomposed_move_planner.py` (Qt-free) 로 추출하고 **두 경로가 공용으로 호출**한다. `job_executor._build_decomposed_tcp_waypoints` 는 공용 함수를 부르는 얇은 래퍼로 남겼고(기존 테스트 계약 유지), `teaching_service._move_decomposed_tcp()` 를 신설했다. 순서 규칙이 한 곳에만 존재하므로 두 경로가 갈릴 수 없으며, 동일 입력에 동일 결과를 내는지 검증하는 테스트(`TestPlannerSharedBySequenceAndTeaching`)를 뒀다. UI(`task_edit_tab`)는 체크 상태만 읽어 서비스에 넘긴다(로직 미포함 — UI/로직 분리 준수).
  - **실기 확인 (GUI 실행 로그)**: `[22:49:46] TCP 이동 시작 [대각선 금지: 축 분해]: X=-268.28mm, Y=188.46mm, Z=47.41mm, Rx=-180.00°, Ry=0.00°, Rz=170.00°, 속도=25.0%` → `[22:50:27] 축 분해 이동 완료 (하강, 3단계: X축 → Y축 → Z축)` → `이동 완료`. 약 300mm 하강에서 **Z 최후** 가 지켜졌고, 자세가 이미 Rz=170 이라 회전 단계는 생성되지 않았다(정상).
  - 티칭 경로 전용 테스트 12건 신규(`test_teaching_decomposed_move.py`) — LINE_T 사용·상승/하강 순서·회전 선행·±180 wrap·joint 무시·중간 실패 중단·미이동 등.
- **상태**: 완료 (코드·단위테스트·실기 검증, 시퀀스 경로 + 티칭 경로 양쪽).

---

## 2026-07-27

### [Fix] 웹 GUI 관절 표시가 6↔14 로 깜빡임 — 같은 ROS2 도메인의 타 로봇(TIAGo 시뮬레이션) 유입

- **문제**: 웹 GUI 상단 관절 표시가 6개↔14개로 계속 흔들림. 값도 우리 로봇과 무관한 수치가 섞여 나옴.
- **원인**: `/joint_states` **퍼블리셔가 2개**였다 — 우리 `tm_driver_node`(6관절 `joint_1..joint_6`, ≈65Hz)와 **타 PC 에서 돌던 TIAGo 계열 시뮬레이션**의 `joint_state_broadcaster`(14관절 `wheel_*`/`torso_lift_joint`/`head_*`/`arm_1..7`/`gripper_*`, ≈33Hz). 8초 실측: 6관절 523건 / 14관절 263건. 이 컴퓨터에 gazebo 프로세스가 없고 `ROS_LOCALHOST_ONLY=0` + 기본 도메인이라 **DDS 가 네트워크 너머 다른 그래프까지 붙은 것**. 구독자(`rosbridge`·`tm_web_bridge`·PyQt GUI)가 두 퍼블리셔 메시지를 번갈아 받아 표시가 깜빡였다.
  - 영향 범위 확인: `/tool_pose`·`/feedback_states`·`/techman_image/compressed` 는 퍼블리셔 1개라 **오염 없음**. 모션 완료 판정은 `tool_pose` 가 있으면 TCP 분기만 쓰므로(`robot_motion_service.py` `check_motion_complete`) **오판 없음**. 다만 `tool_pose` 가 끊긴 순간에는 joint 분기로 내려가 타 로봇 값과 비교할 잠재 위험이 있었다.
- **해결**: 근본 + 방어 2중.
  1. `scripts/web_gui.sh` `source_ros()` 에 **`export ROS_LOCALHOST_ONLY=1`** — DDS 탐색을 이 컴퓨터로 한정. 우리 ROS2 노드는 전부 로컬이고 원격 웹 접속은 rosbridge WebSocket(비-DDS)이라 원격 사용 영향 없음. (주의: 별도 터미널에서 이 스택 노드를 띄울 땐 같은 값을 export 해야 서로 보인다.)
  2. `robot_motion_service.py` 에 **`is_tm_joint_state(names, positions)`** 신설 — 앞 6개 관절 이름이 `joint_1..joint_6` 이 아니면 배제. `bridge_node._on_joint_state`·`main_window._on_joint_state` 양쪽에서 재사용(중복 구현 없음). 도메인 설정과 무관하게 오염을 차단한다.
- **검증**: 재기동 후 `/joint_states` **퍼블리셔 1개**, 8초 실측 **6관절 534건 / 14관절 0건**. `/robot/status` 관절값이 로봇 실제값과 일치(`[-174.35, 12.14, 66.91, 2.24, 87.5, -100.61]`). 단위 테스트 8건 신규(`test_joint_state_filter.py`) 포함 **123 passed / 1 failed(기존 실패)**, `colcon build` 성공.
- **파일**: scripts/web_gui.sh, src/TM_Robot_Task_Manager/tm_task_manager/services/robot_motion_service.py, .../main_window.py, src/tm_web_bridge/tm_web_bridge/bridge_node.py, src/TM_Robot_Task_Manager/test/test_joint_state_filter.py
- **상태**: 완료 (실기 확인 완료). 타 PC 의 시뮬레이션은 다른 사람 작업일 수 있어 건드리지 않음.

### [Fix] 시퀀스 실행 시 "set_positions 실패" — 로봇 명령 채널(Listen 노드) 단절인데 화면은 "연결됨"

- **문제**: 웹 GUI 에서 `pose_keep_move_to_point` 시퀀스를 실행하면 첫 구간에서 `자세유지 이동 실패(Z 상승): set_positions 실패` 후 중단. 화면 연결 상태는 정상으로 보였고 자세 값도 실시간 갱신되고 있어 원인 파악이 어려웠음. (로봇은 전혀 이동하지 않음 — 기록기 47,302 샘플 변동폭 위치 ≤0.006mm·자세 ≤0.0006°)
- **원인**: 두 겹이다.
  1. **로봇 측 Listen 노드 미실행** — PC 화면 프리즈로 리부팅하면서 TCP 연결이 끊겼고 로봇 프로젝트가 Listen 노드에서 빠져나감. 소켓 테스트 결과 **5890(Listen/TMSCT) timeout, 5891(Ethernet Slave/TMSVR) 정상**. 드라이버 로그에 `TM_ROS: (Listen node): Reconnecting...` 반복(`Connection timeout count:=137`). 명령 채널이 없으니 `set_positions` 가 `ok=false` → `bridge_node.py:154` 의 `"set_positions 실패"`. 과거 동일 패턴 기록 있음(본 문서 2026-07-07 "5890(Listen)은 Listen 프로젝트 미실행으로 닫힘").
  2. **상태 표시가 채널을 구분하지 않음** — `/robot/status` 의 `connected` 는 `bridge_node.py:486` `"connected": tcp is not None` 즉 **자세 데이터 수신 여부**만 본다. 자세는 5891 로 오므로 **명령 채널(5890)이 죽어도 `true`** 로 표시되어 오판을 유발했다.
- **해결**: (로봇 측) 펜던트에서 Listen 노드 포함 프로젝트 재실행 → 드라이버 자동 재연결(`TM_ROS: On listen node.` 확인). (코드, 3파일)
  - `bridge_node.py`: `feedback_states` 의 `is_sct_connected`·`is_svr_connected` 를 보관(`_on_feedback_state`), `/robot/status` 에 `sct_connected`·`svr_connected` 노출, `run_sequence` 에 **명령 채널 사전 확인**을 추가해 끊긴 상태면 조치 방법과 함께 거부(모션 게이트 검사 직후). 기존 `connected` 필드는 하위호환 위해 유지.
  - `bridgeClient.ts`: `RobotStatus` 에 두 필드 추가(옵셔널).
  - `MainManager.tsx`: 상단에 **명령채널 칩** 표시 — 끊기면 "명령채널 끊김 (펜던트에서 Listen 프로젝트 실행)".
- **검증**: `colcon build` 성공, `tsc -b` exit 0. 브리지 재기동 후 `/robot/status` → `sct_connected: true, svr_connected: true`, 5890 포트 열림 확인. 이후 동일 시퀀스가 **정상 실행**(테스트 A/B 왕복 성공, 자세 편차 최대 0.0021°).
- **파일**: src/tm_web_bridge/tm_web_bridge/bridge_node.py, ~/Desktop/TRobotics_Client/src/api/bridgeClient.ts, ~/Desktop/TRobotics_Client/src/main/pages/MainManager.tsx
- **상태**: 완료 (실기 검증 완료)

### [Fix] 웹 GUI Available Tasks 에 신규 Job 이 안 보임 — 프론트 하드코딩 목록

- **문제**: 신규 Job `pose_keep_move_to_point` 를 브리지에 등록했는데 웹 화면 Available Tasks 목록에 나타나지 않아 시퀀스에 추가할 수 없음.
- **원인**: 웹 프론트의 목록이 브리지 스키마가 아니라 **하드코딩 배열** — `TaskEditor.tsx:130-142` 의 `taskTree` Motion 항목이 5개로 고정. `/tasks/schema` 응답에는 정상 포함(28종)이라 파라미터 렌더링·실행 경로는 문제 없었고 **목록에만 누락**. (데스크탑 PyQt GUI 는 `task_edit_tab.py:81-105` 가 `JOB_TYPES` 에서 동적 생성이라 영향 없음)
- **해결**: `taskTree` Motion 배열에 `"pose_keep_move_to_point"` 1줄 추가.
- **검증**: `tsc -b` exit 0, vite 갱신 모듈 서빙 확인(HTTP 200 + 항목 포함), 사용자 화면에서 목록 노출·시퀀스 추가·실행 성공.
- **파일**: ~/Desktop/TRobotics_Client/src/main/pages/tabs/TaskEditor.tsx
- **상태**: 완료

---

---

## 2026-07-14

### [Issue] `ros2 action info` 단발 조회가 액션 서버를 0개로 오보 — DDS 탐색 지연 (거짓 보고 유발)

- **문제**: MoveIt 실행 경로를 조사하며 `ros2 action info /tmr_arm_controller/follow_joint_trajectory` 를 실행하니 `Action servers: 0` (클라이언트만 1). 이를 근거로 "궤적을 실행할 서버가 없다 = 실행 경로가 통째로 비어 있다"고 사용자에게 확정 보고했고, 이어서 `tm_driver` 소스·CMakeLists·바이너리 심볼까지 파고들며 헛수고를 했다.
- **원인**: **DDS 탐색 지연**. 액션 서버는 처음부터 있었다 — 재조회 3회 모두 `Action servers: 1 — /tm_driver_node [control_msgs/action/FollowJointTrajectory]`. `move_group` 로그에도 이미 `Added FollowJointTrajectory controller for tmr_arm_controller` · `Trajectory execution is managing controllers` 가 찍혀 있었다. 2026-07-13 의 `ros2 node list` 오판(tm_driver 중복 기동) 과 **동일한 실패 모드**인데, 함정 문구가 `ros2 node list`·"생존 판정" 으로 좁게 서술돼 있어 `action info` 에는 적용하지 않았다.
- **해결**: 인수인계 문서 §4 함정 #3 을 **모든 DDS 탐색 기반 조회**(`node list/info`·`action list/info`·`service list`·`topic list`)와 **모든 부재 판정**("없다"·"0개")으로 확장하고, **부재 판정 확정 조건**(① 2~3회 반복 조회 ② 소스·로그·`ss`·`pgrep` 등 탐색 비의존 경로 교차 확인 — 둘 중 하나 필수)을 명문화.
- **파일**: docs/handoff/2026-07-13-session-handoff.md §4-3, docs/claude-mistake/2026-07-14-001.md
- **상태**: 완료

### [확인] tm_driver 는 MoveIt 실행 경로를 **이미 제공**한다 (조사 결과)

- `tm_driver` 는 `moveit2_lib_auto_judge=true`(CMakeLists.txt:23,38) 이고 빌드 시 `moveit_ros_planning_interface` 가 발견되면 **`tm_ros2_composition_moveit.cpp` 변형**으로 빌드되어 `TmRos2SctMoveit` 이 `tmr_arm_controller/follow_joint_trajectory` **액션 서버를 연다**(`tm_ros2_movit_sct.cpp:3-8`). 현재 설치된 바이너리가 그 변형이며(심볼 확인), 런타임에서 서버 1개 확인.
- 즉 **계획(move_group) → 실행(tm_driver 액션 서버) 경로가 이미 연결**돼 있다. 별도의 ros2_control 하드웨어 인터페이스는 **불필요**하다(워크스페이스·업스트림 모두 0건이고, moveit_config 의 ros2_control 은 `mock_components/GenericSystem` = 가짜 하드웨어 전용).
- ⚠️ **안전 함의**: `move_group` 이 떠 있으면 `/move_action`·`/execute_trajectory` 를 호출하는 누구든 **웹 브리지의 모션 게이트를 우회해 로봇을 움직일 수 있다**. GUI 패널 설계 시 반드시 다룰 것.
- **상태**: 조사 완료 (설계 반영 필요)

---

## 2026-07-13

### [Fix] `tm_mod_urdf` 의 `modify_xacro` 가 이 워크스페이스에서 실행 불가 — `--symlink-install` 이면 모듈이 `build/` 로 잡힘

- **문제**: 실물 보정 URDF 를 만들려고 `ros2 run tm_mod_urdf modify_xacro tm20 tm20-calib +M` 을 돌리면 `[ERROR] workspace directory not find` 로 즉시 중단. 로봇 연결·서비스는 정상인데 파일이 생성되지 않는다.
- **원인**: 벤더 스크립트가 워크스페이스 루트를 **`__file__` 경로 문자열에서 유도**한다 — `modify_xacro.py:153-163` 이 `os.path.dirname(os.path.abspath(__file__))` 에서 `'src'` 또는 `'install'` 부분문자열을 찾아 그 앞을 루트로 삼는다. 이 워크스페이스는 `--symlink-install` 이라 모듈이 `.../TM_Robot_ros2_ws/build/tm_mod_urdf/tm_mod_urdf` 로 잡히고, 여기엔 `src`·`install` 이 **둘 다 없어** `ind == -1` → 중단. (실측: `find('src') = -1`, `find('install') = -1`)
- **해결**: 벤더 파일을 고치지 않고 **소스에서 직접 실행**(0줄 수정). 이러면 `__file__` 이 `src/...` 아래라 경로 유도가 성립한다.
  ```bash
  PKG=$PWD/src/Robot/tmrobot_official_packages/tm_mod_urdf
  PYTHONPATH=$PKG:$PYTHONPATH PYTHONNOUSERSITE=1 \
    python3 $PKG/tm_mod_urdf/modify_xacro.py tm20 tm20-calib +M
  ```
- **파일**: (수정 없음) 실행 방법만 변경 — 대상 `src/Robot/tmrobot_official_packages/tm_mod_urdf/tm_mod_urdf/modify_xacro.py:153-163`
- **상태**: 완료 (`macro.tm20-calib.urdf.xacro` 생성 확인, 원점 보정량 0.834mm 반영)

### [Issue] `tm20_run_move_group.launch.py` 는 `tm_driver` 를 자체 기동한다 — 웹 스택과 함께 쓰면 중복 기동

- **문제**: 벤더 launch 를 그대로 돌리면 이미 떠 있는 `tm_driver` 위에 **두 번째 tm_driver** 가 뜬다. 2026-07-13 의 과거 사고(`ros2 node list` 오판으로 tm_driver 중복 기동)와 **같은 결과**.
- **원인**: `tm20_run_move_group.launch.py:177-193` 이 `tm_driver_node` 와 `rviz_node` 를 LaunchDescription 에 포함한다. 웹 스택(`scripts/web_gui.sh`)이 이미 tm_driver 를 띄운 상태에서는 충돌한다.
- **해결**: 벤더 launch 는 **무수정**(단독 사용 시 여전히 유효)하고, 공존 전용 launch 를 신설했다 — `tm20_move_group_only.launch.py` 는 `move_group`+`robot_state_publisher`+`static_tf` 만 띄우고 `tm_driver`·RViz 를 **제외**해, 웹 스택이 이미 띄운 tm_driver 의 `/joint_states`·`/tmr_arm_controller/follow_joint_trajectory` 를 그대로 쓴다. 함께 `use_sim_time` 을 벤더 기본값 `True` → **`False`** 로 바로잡았다(`/clock` 퍼블리셔가 없는 실물 환경에 `True` 는 부적절).
- **검증**: 기동 후 `tm_driver` 실행 파일 프로세스 **1개 유지**(중복 0), `rviz2` 미기동, `use_sim_time=False` 확인, 실물 관절 기준 **계획 성공**(error_code=1, 궤적 9점, 0.024초), 웹 스택 포트(:8000·:9090·:6189·:3000) 전부 유지. 로봇 무이동(계획 전용).
- **스택 통합**: `scripts/web_gui.sh` 의 `SERVICES` 배열에 MoveIt 한 줄(포트 없음 → pgrep 패턴 `moveit_ros_move_group/move_group` 로 생존 판정, tm_driver 뒤에 붙도록 맨 끝) + `do_stop()` 에 `pkill -f "tm20_move_group_only.launch.py"` 한 줄 추가. 기존 `alive()` 가 "이미 실행 중이면 건너뜀"을 하므로 중복 기동은 구조적으로 차단된다. 실측: `start` 시 기존 6개 전부 "이미 실행 중(건너뜀)", MoveIt 만 신규 기동. 기동 후 `tm_driver` 1개·`move_group` 1개·`rviz2` 0개(`pgrep -x` 정확매칭), 계획 성공(error_code=1, 0.023초), 웹 포트 4개 유지.
- **파일**: src/Robot/tmrobot_official_packages/tm20_moveit_config/launch/tm20_move_group_only.launch.py (신규), scripts/web_gui.sh (SERVICES·do_stop 각 1줄 — 타 세션 미커밋 변경과 같은 파일에 있어 **이번 커밋에서는 제외**). 원인 파일 tm20_run_move_group.launch.py:177-193 은 무수정
- **상태**: 완료

### [Fix] 복수 기기에서 라이브 카메라를 켜면 조그가 크게 느려짐 — 클라이언트 자가클럭이 촬영을 N배로 증폭

- **문제**: 웹 GUI 여러 대에서 동시에 라이브 카메라를 켜면 조그 응답이 심하게 밀림. 단일 기기는 원격(Tailscale)이어도 부드러움 → 기기 수가 원인.
- **원인**: 라이브 촬영 **트리거가 클라이언트에 있었다**. `Vision.tsx` 가 프레임 도착마다 `snapVision()` 을 재호출하는 **자가 클럭** 구조였고, 브리지 `capture_still`(`bridge_node.py`)에는 **락·중복제거·레이트리밋이 전무**(jog 엔 `_jog_lock` 이 있는데 촬영엔 없음). 결과적으로 **기기 N대 = 로봇 촬영 요청 N배** → 로봇 명령 큐 포화 → 같은 로봇 채널을 쓰는 조그가 뒤에 적체. (참고: 네트워크·대역폭 문제가 아님 — 브리지 로컬 응답은 2ms, 링크는 기가비트)
- **해결**: 트리거를 **서버로 이관**. 브리지에 **시청자 관리 + 촬영 루프 1개**(`_live_viewers` TTL 5초 하트비트, `_live_running` 플래그) 신설, 엔드포인트 `POST /vision/live/join`·`/leave`·`GET /vision/live/status` 추가. 웹은 자가클럭을 제거하고 `join` 하트비트만 보내며, **이미지는 기존 pub/sub 구독 그대로**(여럿이 봐도 촬영은 1배, 아무도 안 쫓아냄). **조그 우선권**도 추가 — 조그 진행 중(`_jog_lock`)이면 루프가 촬영을 양보. 루프 클럭은 **프레임 실도착**(`/techman_image/compressed`)으로 폭주 방지(`capture_still` 은 스크립트 전송 3ms 후 즉시 반환하므로 대기 없이 반복하면 초당 수백 회 전송됨).
- **구현 중 발견·수정한 자체 버그 2건**:
  1. **경합(race)**: 루프 생존을 `Thread.is_alive()` 로 판정해, `leave` 직후 옛 스레드가 아직 살아있을 때 `join` 이 오면 새 루프를 만들지 않고 옛 루프는 그대로 종료 → **루프 0개**(실측 0장 재현). → **락으로 보호되는 `_live_running`** 로 교체해 종료 결정과 시작 결정을 같은 락에서 직렬화.
  2. **클럭 끊김 시 무성(無聲) 저하**: `jpeg_republish` 가 죽으면 프레임 이벤트가 안 와 루프가 3초 타임아웃 페이스로 조용히 느려짐. → 타임아웃 시 **경고 로그** 추가.
- **검증**: 토픽 직접 계수(`/techman_image`) — **시청자 1명 1.20 FPS / 3명 1.29 FPS (거의 동일)** = 로봇 부하가 시청자 수와 무관. 루프 시작 5/종료 5(잔존 0), 촬영 실패 0, 클럭 경고 0. 프론트 `tsc -b` 0 errors + `vite build` 성공, `colcon build` 성공. 사용자 실기(복수 기기) 확인 완료. 안전: `capture_still` 은 `Vision_DoJob`(무이동)이라 루프가 돌아도 로봇을 못 움직임(TMscript v2.18 §13.26 p.351-352 + 실측 TCP 불변).
- **주의(계측 함정)**: 초기 계측을 `tm_camera_bridge` 로그(`print()`) 로 셌더니 **블록 버퍼링** 때문에 "0장→0장→37장" 처럼 밀려 잡혀 오진할 뻔했다. 토픽 직접 구독 계수로 교체해 확정.
- **파일**: src/tm_web_bridge/tm_web_bridge/{bridge_node.py,api.py}, ~/Desktop/TRobotics_Client/src/{api/bridgeClient.ts,main/pages/tabs/Vision.tsx}
- **상태**: 완료 (실기 검증 완료)

### [Fix] 웹 GUI(vite) 기동 실패 — inotify watch 한도 소진(VS Code 가 99% 독식)

- **문제**: `vite` 가 `ENOSPC` (`syscall: 'watch'`) 로 죽어 웹 화면(:3000)이 안 뜸. 디스크 부족이 아님.
- **원인**: `fs.inotify.max_user_watches` 기본 **65,536** 인데 사용량이 **65,569** 로 초과. VS Code 2개 프로세스가 **64,948개(99%)** 를 독식. 근본은 워크스페이스의 `src/AI` (**12GiB, 188,694 파일** — Hailo SDK·protobuf·Catch2 등 벤더 트리)를 VS Code·cpptools 가 전부 인덱싱·감시하기 때문. 같은 뿌리로 VS Code + cpptools 가 **3.2GiB** 를 먹어 시스템 여유 메모리 145MiB·스왑 4.8GiB 의 압박을 유발(에디터 다운의 유력 원인).
- **해결**: `/etc/sysctl.d/99-inotify-watches.conf` 로 `fs.inotify.max_user_watches=524288` 상향(영구) + 즉시 반영. vite 정상 기동 확인.
- **미적용(사용자 판단 보류)**: `src/AI` 를 VS Code 인덱싱에서 제외(`files.watcherExclude`·`C_Cpp.files.exclude`·`search.exclude`). 사전조사 결과 활성 코드의 hailo `#include`/`import` **0건**, `src/AI` 는 colcon 패키지도 아님(package.xml 0개) → 제외해도 빌드·런타임 영향 없음. 에디터 다운이 재발하면 적용 검토.
- **파일**: /etc/sysctl.d/99-inotify-watches.conf (시스템)
- **상태**: 완료 (한도 상향), 인덱싱 제외는 보류

### [Fix] Claude 세션 종료 시 웹 GUI 서비스 6개가 전멸

- **문제**: 작업 도중 브리지·rosbridge·카메라 브리지 등이 **동시에 전부 죽음**. 로그 마지막이 `Shutting down` (크래시 아닌 **정상 종료**).
- **원인**: 서비스들을 Claude Code 의 백그라운드 태스크로 띄워 **세션 프로세스에 종속**됨 → 세션 종료 시 프로세스 그룹에 SIGTERM 이 전파되어 자식들이 함께 종료. `nohup` 만으로는 부족(SIGHUP 만 무시).
- **해결**: `scripts/web_gui.sh` 신설(start/stop/status/restart) — **`setsid` 로 새 세션·프로세스 그룹으로 완전 분리**해 기동. 세션ID 가 실제로 분리됨을 확인(서비스 6개 각자 고유 SID). 기동은 멱등(이미 떠 있으면 건너뜀).
- **부수 버그(수정 완료)**: 생존 판정에 `ros2 node list` 를 쓰니 DDS 탐색 지연으로 기동 직후 빈 목록이 와서 **tm_driver 를 중복 기동**시킴(실제로 2개 뜸). → 포트(`ss`)·`pgrep` 기반 판정으로 교체, 회귀 테스트로 중복 0 확인.
- **주의(도구 함정)**: `pkill -f "tm_web_bridge"` 는 **경로에 그 문자열이 들어간 `src/tm_web_bridge/scripts/jpeg_republish_node.py` 까지 죽이고**, 실행 중인 셸 자신도 매칭해 죽인다(exit 144). 종료는 **소켓 소유 PID**(`ss -tlnp`)로 특정할 것.
- **파일**: scripts/web_gui.sh
- **상태**: 완료

---

## 2026-07-10

### [Fix] 카메라 캘리브 저장 경로가 리터럴 `~` 폴더로 생성 (config save_path 버그)

- **문제**: `camera_calibration_node` 의 캘리브 결과가 홈 하위가 아니라 **리터럴 `~` 디렉토리**(노드 cwd 밑)에 저장되고, 지정 경로도 실제 패키지 위치와 불일치.
- **원인**: `src/Vision/ROS2/tm_camera_calibration/config/calibration_params.yaml:18` `save_path: "~/TM_Robot_ros2_ws/src/Vision/tm_camera_calibration/calibration_data"` — YAML 및 C++ 노드가 `~` 를 홈으로 **미확장** → `createCalibrationFolder()` 의 `std::filesystem::create_directories(save_path_ + ...)`(`camera_calibration_node.cpp:163`)가 cwd 밑에 리터럴 `~/...` 를 생성. 경로도 실제 패키지(`src/Vision/ROS2/tm_camera_calibration`)와 불일치(`ROS2` 누락).
- **해결**: `save_path` 를 실제 패키지의 **절대경로**(`/home/amap/Project/T-Robotics/kkw/TM_Robot_ros2_ws/src/Vision/ROS2/tm_camera_calibration/calibration_data`)로 수정(1줄 + 주석). 검증: 오버라이드 없이 `ros2 launch` → 로그 `Save path:` 가 절대경로 확인, `save_calibration` 이 그 경로에 저장(intrinsic 15뷰, 재투영 0.4575px). 참고: C++ 기본값(`camera_calibration_node.cpp:24-25`)도 같은 잘못된 경로 — config 가 우선이라 당장 무해하나 향후 rebuild 시 정정 권장(latent).
- **파일**: src/Vision/ROS2/tm_camera_calibration/config/calibration_params.yaml
- **상태**: 완료

---

## 2026-07-09

### [Fix] 새로고침 후에도 "모션 활성" 스위치가 ON 유지 — 서버 게이트가 실제 활성 상태로 잔존(안전 갭)

- **문제**: 브라우저 새로고침(F5) 후에도 상단 "모션 활성" 스위치가 ON 으로 유지. 단순 표시가 아니라 **로봇이 실제로 모션 활성 상태로 남아** jog/촬영이 그대로 동작하는 안전 갭(새 화면=안전 으로 오인 위험).
- **원인**: 스위치가 **서버(브리지) 게이트를 반영**(`~/Desktop/TRobotics_Client/src/main/pages/MainManager.tsx:64-76` — 700ms 폴링 `getStatus()`→`setMotionEnabledState`). 브리지 `motion_enabled` 는 서버측에서 유지되어 새로고침으로 리셋되지 않음(실측 `GET /motion/enable`={"motion_enabled":true}). redux-persist 미사용이라 Redux 는 false 로 초기화되나 700ms 내 폴링이 서버 true 로 덮어씀.
- **해결**: `MainManager` 마운트(로드/새로고침) 시 `setMotionEnabled(false)` 를 POST 하는 mount-effect 1개 추가 → 모든 페이지 로드가 **모션 비활성(안전)** 으로 시작, 사용자가 매번 의식적으로 재활성화. 부작용 검증: `set_motion_enabled`(`src/tm_web_bridge/tm_web_bridge/bridge_node.py:154`)는 플래그만 설정, `run_sequence` 게이트는 진입 1회 검사(`bridge_node.py:197`)라 executor 실행 중 시퀀스는 미중단. 검증: `tsc --noEmit` exit 0, 계약 테스트(`POST true→GET true`, `POST false→GET false`), vite HMR 리마운트 시 서버 게이트 true→false 실동작 확인.
- **파일**: ~/Desktop/TRobotics_Client/src/main/pages/MainManager.tsx
- **상태**: 완료 (소프트웨어·계약 검증 완료 — 브라우저 F5 최종 확인 권장)

### [Fix] 웹 Vision 촬영 이미지 표시가 수 초 걸림 — raw 15MB 를 rosbridge base64 로 전송

- **문제**: 웹 GUI Vision 탭에서 촬영 요청 후 카메라 이미지가 캔버스에 뜨는 데 수 초 소요(체감 매우 느림). 로봇→PC 실전송·수신은 정상.
- **원인**: TMvision 이미지가 2592×1944 bgr8 = **raw 15.1MB**. 이를 rosbridge 로 그대로 보내면 WebSocket 용 **base64 20.2MB** JSON 이 되어, 브라우저가 `JSON.parse`(20MB) + `atob`(15M 회) + **5.0M 회 픽셀 BGR→RGBA JavaScript 루프**를 수행 — 순수 JS 다중 루프가 병목(`~/Desktop/TRobotics_Client/src/main/pages/tabs/Vision.tsx:32-65` 구 `drawImage`). 브리지 수신→발행은 ~90ms(로그 실측)로 빠르고, 로봇→토픽 0.7s 는 물리·불가피. compressed_image_transport 플러그인 미설치.
- **해결**: 별도 `jpeg_republish` 노드 신설 — `/techman_image`(raw) 구독 → `cv2.imencode('.jpg', q80)` → `/techman_image/compressed`(sensor_msgs/CompressedImage) 발행. 웹은 이 토픽 구독 + `img.src="data:image/jpeg;base64,…"` **브라우저 native JPEG 디코드**로 변경(픽셀루프·atob 제거). 원본 raw·`aruco_detector`·정밀경로는 **무변경**(정밀 요구와 분리). 측정: 현실 이미지 JPEG q80 = **133KB**(raw base64 20.2MB 대비 **152배↓**). 검증: 노드 로그 재발행 확인, `tsc --noEmit` exit 0, vite 200, 사용자 실촬영 체감 "훨 빨라짐" 확인.
- **파일**: src/tm_web_bridge/scripts/jpeg_republish_node.py(신규), ~/Desktop/TRobotics_Client/src/main/pages/tabs/Vision.tsx
- **상태**: 완료 (실촬영 체감 개선 확인)

---

## 2026-07-08

### [Issue] 웹 브리지 jog 검증이 라이브 로봇을 과속 이동시켜 안전정지(0x03 0x35) 유발

- **문제**: tm_web_bridge `/jog` 를 curl 로 검증 중 라이브 로봇에 `Rx≈-100°/속도100%` 명령이 전달 → TM(Techman) 안전 알람 `0x03 0x35`(TCP/관절 속도가 협동 안전 한계 초과, Stop Category 2) → 로봇 경고음 → 사용자 비상정지 + 제어박스 **정상 종료(PC 종료 버튼)** → 이후 TMflow 부팅 실패(`start_server_fail`/`ServerErrorControlMode`) + 부팅 시 모터 덜컥. 부팅 화면에 부팅실패 에러·J5 하드웨어 보호·`0055FFCF`가 **동시 표시**(순차 아님).
- **원인**: 로봇 라이브 상태 미재확인(stale node list 근거로 오프라인 가정) 후 자동 검증으로 실모션 전송. 검증용 극단값(step 9999/속도 999%)이 clamp(당시 100mm/100°/100%) 되어도 큰 회전이 됨. `0x03 0x35`는 **하드웨어 손상이 아닌 복구 가능한 안전 위반 알람**(servo engaged 유지)임이 사용자 조회로 확인됨.
- **해결(코드, 재발 방지)**: `sanitize_jog` 로 회전축 ≤10° / 직선축 ≤50mm / 속도 ≤30% 분리 clamp, `/jog` motion-enable 게이트(기본 비활성). React 조그 패널 "모션 활성" 체크박스(기본 꺼짐). 검증은 로봇 미기동 상태에서만(단위테스트+게이트 차단 curl). 참고: 전송 속도는 명령별 일회성 파라미터(로봇에 저장 안 됨) — 되돌릴 값 없음, 기본값 하향으로 재발 차단.
- **에스컬레이션(2026-07-08 17:29)**: 정지 버튼 acknowledge + 재부팅 수 차례 시도해도 복구 실패. 추가 에러 **`J5 [Error][Hardware] The protection is on for motor hold (type2)`** 발생 = **J5(손목2) 모터 하드웨어 보호 latch**. 소프트 안전알람이 아니라 하드웨어 fault 로 판정 — 재부팅/정지버튼으로 안 풀림. 과속 회전(Rx≈-100°/100%)이 손목(J4~J6) 관절을 과부하/특이점 근처로 몰아 J5 서보 보호를 트립시킨 것으로 추정(정확 원인·복구는 TM 하드웨어 에러 매뉴얼 필요 — 저장소 부재, 추측 금지).
- **해결(로봇 복구, 2026-07-08 18:26)**: **전원 완전 차단 5분 유지(방전) → 재부팅 시 정상 복구.** J5 모터 hold 보호 latch 는 일반 재부팅/정지버튼으로는 안 풀렸으나 **완전 방전 콜드부팅**으로 클리어됨. 간단한 project 실행까지 검증 완료 = **하드웨어 손상 아님**. (교훈: TM(Techman) motor hold 보호 latch 는 짧은 재부팅이 아닌 완전 전원 방전이 필요할 수 있음.)
- **파일**: src/tm_web_bridge/tm_web_bridge/{api.py,bridge_node.py}, ~/Desktop/TRobotics_Client/src/{api/bridgeClient.ts,main/pages/tabs/TaskEditor.tsx}; 사건: docs/claude-mistake/2026-07-08-001.md; 경위서: docs/issues_and_fixes/techman-support-report-2026-07-08.md
- **상태**: ✅ **완료** — 로봇 정상 복구(완전 방전 콜드부팅) + 코드 재발방지(속도 클램프·모션 게이트) 완료

### [Fix] GUI 미구현 저장 기능 2건 구현 (로그 저장 / 정밀도 그래프 저장)

- **문제**: ① Run Monitor 탭 "로그 저장" 버튼이 파일 저장 없이 로그만 출력 ② 정밀도 테스트 탭 "그래프 저장" 이 "아직 구현 중" 메시지만 표시
- **원인**: 핸들러가 스텁 상태 — `tabs/run_monitor_tab.py:_on_save_log`(로그만), `tabs/precision_test_tab.py:_on_save_precision_graph`(메시지만)
- **해결**: ① `_on_save_log` — `textEdit_log.toPlainText()` 를 QFileDialog 로 선택한 경로에 저장(빈 로그 가드, 홈 디렉토리 기본 파일명 `tm_run_log_<ts>.log`). run_monitor_tab 에 `os`/`datetime`/`QFileDialog` import 추가. ② `_on_save_precision_graph` — 기존 3개 matplotlib figure(XY/YZ/ZX)를 `savefig(dpi=150)` 로 `<base>_XY/_YZ/_ZX.png` 저장(측정 데이터 없으면 경고). 검증: 구문·빌드 0 errors, QFileDialog/QMessageBox import 확인, matplotlib savefig 헤드리스 동작(Agg) 확인, GUI 재기동 정상. (버튼 실사용 확인 대기)
- **파일**: src/TM_Robot_Task_Manager/tm_task_manager/tabs/run_monitor_tab.py, tabs/precision_test_tab.py
- **상태**: 완료 (빌드·헤드리스 검증 통과)

### [Fix] GUI 속도 제어 무효 (20% vs 80% 동일 속도) — 퍼센트↔물리단위 변환 누락

- **문제**: GUI 에서 속도 20%로 이동한 것과 80%로 이동한 것의 실제 속도가 동일
- **원인**: 단위 불일치. GUI 는 velocity 를 퍼센트(0~100)로 `set_positions` 서비스에 전달(`services/teaching_service.py:161`, `services/tm_robot_ros2_motion.py:70`, `main_window.py:_call_set_positions`)하는데, tm_driver 는 물리단위로 해석 — PTP_J/PTP_T 는 `vel_pa=int(100*vel/π)` 후 100% 클램프(`tm_driver.cpp:131-132`), LINE_T 는 vel×1000 mm/s 직통(`tm_driver.cpp:147`, `tm_command.cpp:72`). 결과: 20%→int(100*20/π)=636→클램프 100%, 80%→2546→클램프 100% 로 둘 다 최고속. (별개 요인: 로봇 Project_Speed 5% 배율이 곱해지나 클램프가 주원인)
- **해결**: `services/coordinate_transformer.py` 에 `velocity_percent_to_service(motion_type, percent)` 추가 — PTP 계열 `(percent/100)*π` rad/s, LINE_T `(percent/100)*1.0` m/s, [0,100] 클램프. choke point `main_window.py:_call_set_positions` 및 우회 경로 `job_executor.py:_exec_align_to_ar_tag`(자체 클라이언트) 두 곳에서 request.velocity 설정 직전 변환. 검증: 단위 테스트(20%→드라이버 재해석 20%, 80%→80%) + 실기(J6 +10° 도달 20%=4.79s vs 80%=1.48s, 시간비 3.24 — 수정 전 1.0)
- **파일**: src/TM_Robot_Task_Manager/tm_task_manager/services/coordinate_transformer.py, main_window.py, job_executor.py
- **상태**: 완료 (참고: Project_Speed 5% 하에서는 GUI 20%→실효 1%, 80%→실효 4% — 정상 운용 시 펜던트에서 Project_Speed 상향 필요)

---

## 2026-07-07

### [Fix] GUI 이미지 캡처 버튼 복구 + 카메라 라이브 뷰 구현 (비전 탭)

- **문제**: ① GUI 이미지 캡처 버튼이 동작 안 함 ② 비전 탭 "카메라 시작" 버튼을 눌러도 무반응
- **원인**: ① 캡처 트리거가 구 프로젝트(ROS2_COM4) 전용 로직(`g_robot_command=3` 변수 쓰기 + `ScriptExit()`) — 현재 로봇 프로젝트("listen node DIO test")에 해당 변수·분기 부재, 게다가 `ScriptExit()`는 Listen 노드를 종료시켜 제어 채널 단절 위험 (`services/image_capture_service.py:131-146` 구버전) ② "카메라 시작/정지"는 원래 미구현 스텁(`main_window.py:908-913` 구버전, `pass`만 존재)
- **해결**: (사용자 승인 후) ① 캡처 트리거를 검증된 `Vision_DoJob_PTP("TM_IMG_Send", 100, 500)` 단일 전송으로 교체, 잡 이름은 모듈 상수 `VISION_CAPTURE_JOB` 로 분리, 캡처 타임아웃 3s→15s ② "카메라 시작" = QTimer 0.5s 폴링 + `is_capturing` 겹침 방지 가드로 주기 캡처 라이브 뷰(실효 약 1장/초 — 상한은 촬영 파이프라인 소요), "카메라 정지" = 타이머 중지, closeEvent 자동 정지 포함. 실기 검증: 캡처 버튼 → 비전 탭 실사진 표시 확인, 라이브 뷰 시작/정지 동작 사용자 확인 완료
- **파일**: src/TM_Robot_Task_Manager/tm_task_manager/services/image_capture_service.py, src/TM_Robot_Task_Manager/tm_task_manager/main_window.py
- **상태**: 완료 (참고: 라이브 뷰 중 로봇이 촬영 위치 점유 — 조그/레시피 실행 전 카메라 정지 권장. 1fps 초과 실시간이 필요하면 별도 카메라 직결 구조 검토)

### [Fix] 카메라 비전 파이프라인 최초 가동 — 로봇 카메라 → GUI 실사진 수신 성공

- **문제**: GUI 에 카메라 영상이 전혀 없음. 원인은 고장이 아니라 미설정 — TMvision 이미지는 로봇(TMflow)이 비전 잡 실행 시에만 HTTP POST 로 PC(:6189)에 push 하는 구조인데, 현재 로봇에는 비전 잡을 가진 프로젝트가 없었음(실행 중 프로젝트는 "listen node DIO test", 사진 속 ROS2_COM4 는 로봇에 부재)
- **원인**: ① 이미지 송신용 비전 잡 미존재 ② 플로우 수정 없이 실행할 방법 필요. TMscript `Vision_DoJob()` 계열이 해답 — 단 초기 위치(Start at Initial Position) 있는 잡은 `Vision_DoJob()` 불가(TMscript v2.18 §13.26 p.352), `Vision_DoJob_PTP()` 필요
- **해결**: (로봇 측) 사용자가 "listen node DIO test" 프로젝트에 비전 잡 `TM_IMG_Send` 생성 — 찾기(Find)→외부 감지(External Detection), URL `http://169.254.183.100:6189/api/DET` (TMvision v2.18 KR p.50-51 절차). (PC 측) Listen 채널 send_script 로 `Vision_DoJob_PTP("TM_IMG_Send", 100, 500)` 원격 실행 → 2592x1944 bgr8 실사진 0.7s 만에 `/techman_image` 수신 PASS. 참고: 최초 `Vision_DoJob()`(무이동 버전)은 응답 OK 이나 이미지 미전송 — 초기 위치 제약으로 추정, PTP 버전으로 해결
- **파일**: 저장소 코드 수정 없음 (로봇 측 비전 잡 + 원격 스크립트 실행)
- **상태**: 완료 — 비전 트리거 명령: `Vision_DoJob_PTP("TM_IMG_Send", 100, 500)` (send_script 경유)

### [Fix] 외부 PC → TM 로봇 ROS2 제어 링크 최초 검증 완료 (J6 +1° 미세 이동 PASS)

- **문제**: 코드 리뷰에서 `set_positions` 단위(deg vs rad) 불일치 의심([param] Medium, docs/code_review/TM_Robot_ros2_ws/2026-07-07.md) — 실기 검증 전 이동 명령 위험
- **원인**: 문서 간 표기 불일치. 실측 결과 드라이버가 관절 rad→deg 변환(`tm_command.cpp:42-53` `degs()`), 직교 m/rad→mm/deg 변환, velocity rad/s(π=100%), acc_time 초 단위(×1000→ms). 내부 문서 `docs/TM_Robot_Motion_Control_Reference.md` 의 "acc_time: ms" 표기는 오기(코드는 초)
- **해결**: J6 단독 +1°(0.01745rad)·속도 5%·fine_goal 미세 이동 테스트 — 결과 J6 +0.952°(판정 루프가 목표 0.05° 이내 진입 시점에 샘플링, 정상), 타 관절 변화 0.000°. PASS. 아울러 tm_custom_motion_control 이 deg 를 그대로 넘기는 문제(리뷰 High/Medium)는 실버그로 확정(드라이버가 rad 로 해석)
- **파일**: 스크래치 테스트 스크립트(임시, 저장소 외). 저장소 코드 수정 없음
- **상태**: 완료

### [Fix] Ethernet Slave Data Table 필수 항목 3개 누락 — tm_driver "data table is not correct!"

- **문제**: `tm_driver` 기동 시 `Required item End_DO3 / MA_Mode / Safeguard_A is NOT checked` 에러(총 46항목 중 44 체크). 연결·제어는 동작하나 FeedbackState 의 해당 필드(안전문 상태, 수동/자동 모드, End DO3)가 갱신되지 않음 — 안전 상태 가시성 저하
- **원인**: 로봇(TMflow) 측 `설정 → 연결 → Ethernet Slave → Data Table` 에서 위 3개 항목 미체크. 공식 가이드(src/Robot/tmrobot_official_packages/docs/README.md:133-161)는 전 항목 체크를 요구
- **해결**: (1차, 로봇 측) 사용자가 Data Table 에 `End_DO3`·`Ext_Safeguard`·`Operation_Mode` 추가(49항목) → `End_DO3` 에러 해소(3→2), 드라이버 재시작 후 재검증·관절값 정합 확인. (2차 분석) 잔여 `Safeguard_A`/`MA_Mode` 는 **TMflow 2.18 에 해당 명칭 항목이 존재하지 않음** — 신형 명칭 `Ext_Safeguard`(외부 보호)·`Operation_Mode`(0:수동 1:자동)로 개명됨([TMflow 설명서 v2.18 KR, page 281-282](../Software-Manual-TMflow_SW2.18_Rev1.02_KR.pdf)). 스트림 파싱 실측으로 로봇 테이블 49항목 전수 확인(구명칭 부재·신명칭 존재). 드라이버가 구명칭을 하드코딩(tm_robot_state.cpp:42,59)하므로 펜던트 설정으로는 해결 불가
- **파일**: 없음 (로봇 측 설정)
- **상태**: 완료 — 사용자 결정: **A(현행 유지)** 채택 (2026-07-07). 제어·상태 수신 무영향, 기동 시 에러 로그 2줄 잔존은 무시. 추후 B(개명 패치) 전환 가능성은 debt-002 로 등록(docs/debt/registry.md)

### [Fix] tm_aruco_detect 빌드 실패 — OpenCV 4.8 커스텀 빌드에 contrib aruco 헤더 부재

- **문제**: `colcon build` 시 `tm_aruco_detect` 컴파일 실패(`fatal error: opencv2/aruco.hpp: 그런 파일이나 디렉터리가 없습니다`) → 의존 대기 패키지(tm_msgs, tm_camera_calibration, image_sub) 전체 Aborted
- **원인**: `src/Vision/ROS2/tm_aruco_detect/include/tm_aruco_detect/aruco_detector.hpp:13` 이 구 contrib API 헤더 `<opencv2/aruco.hpp>` 를 include. 이 PC(Jetson)의 OpenCV 는 contrib 미포함 커스텀 4.8.0 빌드(`libopencv-dev 4.8.0-1-g6371ee1`)로 `/usr/include` 전역에 해당 헤더 없음(실측). 4.8 신 API 헤더(`opencv2/objdetect/aruco_detector.hpp`)는 존재
- **해결**: (1차) `tm_aruco_detect` 제외 재빌드로 나머지 6개 패키지 확보. (2차, 사용자 승인 후 근본 수정) ① 구 contrib API → OpenCV 4.8 objdetect API 포팅: `<opencv2/aruco.hpp>`→`<opencv2/objdetect/aruco_detector.hpp>`, `DetectorParameters::create()`→값 타입, `cv::aruco::detectMarkers()`→`ArucoDetector::detectMarkers()`, `estimatePoseSingleMarkers()`(4.8 main 부재)→`solvePnP(SOLVEPNP_IPPE_SQUARE)` 마커별 호출. ② 런타임 크래시(`setSize s>=0` assertion) 추가 발견 — cv_bridge(OpenCV 4.5d)와 노드(4.8) 이중 로드 충돌(ldd 실측: libopencv_core.so.408 + .so.4.5d 동시) → cv_bridge/image_transport 의존 제거, Image↔Mat 직접 변환으로 대체. 검증: 빌드 0 errors + 단일 4.8 링크(ldd) + 합성 마커(DICT_4X4_50, id23) 런타임 테스트 `/aruco/pose` 수신, z=0.1545m(이론 0.154m) PASS
- **파일**: src/Vision/ROS2/tm_aruco_detect/{include/tm_aruco_detect/aruco_detector.hpp, src/aruco_detector.cpp, CMakeLists.txt, package.xml}
- **상태**: 완료 (최종 승인은 별도 리뷰 lane — never-self-approve)

### [Issue] Vision 스택 전반의 cv_bridge 호환성 리스크 2건 (aruco 외 잔존)

- **문제**: ① C++ `tm_camera_calibration` 노드도 cv_bridge(4.5d)+시스템 OpenCV(4.8) 이중 링크 상태 — aruco 와 동일한 런타임 크래시 위험(빌드 시 동일 링커 경고, 이미지 수신 시 발현 가능). ② Python `cv_bridge` 는 NumPy 2.2.6 환경에서 import 시점 크래시(`_ARRAY_API not found`) — `scripts/tm_camera_bridge.py`·태스크 매니저 이미지 캡처 경로가 런타임에 터질 수 있음
- **원인**: ROS2 Humble apt cv_bridge 는 Ubuntu OpenCV 4.5.4d + NumPy 1.x 기준 빌드인데, 이 PC 는 커스텀 OpenCV 4.8 + NumPy 2.2.6
- **해결**: (Python 측 — 해결) GUI 기동 시 실제 발현(`main_window.py:15` cv_bridge import 크래시) → **`PYTHONNOUSERSITE=1` 우회 적용**: pip --user 의 numpy 2.2.6/opencv 5.0 을 무시하고 apt 정합 스택(numpy 1.21.5·cv2 4.5.4·scipy 1.8·cv_bridge)만 사용. `python3-waitress` apt 설치(카메라 브리지용). 추가로 구 워크스페이스 경로 하드코딩(`~/TM_Robot_ros2_ws/.../ui/*.ui` FileNotFoundError) → 심볼릭 링크 `/home/amap/TM_Robot_ros2_ws → ~/Project/T-Robotics/kkw/TM_Robot_ros2_ws` 로 해소. GUI 기동 성공(Traceback 0, IO 실시간 갱신, 창 표시 확인). **기동 커맨드**: `PYTHONNOUSERSITE=1 DISPLAY=:0 ros2 launch tm_task_manager task_manager.launch.py robot_ip:=169.254.122.16`
  (C++ 측 — 잔존) `tm_camera_calibration` 이중 OpenCV 링크는 미해결 — 이미지 스트림 수신 시 크래시 위험. 근본책(cv_bridge 소스 재빌드 또는 aruco 식 cv_bridge 제거)은 비전 기능 사용 전 결정
- **파일**: (시스템) apt python3-waitress 설치, `~/TM_Robot_ros2_ws` 심볼릭 링크. 저장소 코드 수정 없음
- **상태**: Python 측 완료 / C++ calibration 측 보류

### [Fix] 로봇 IP 변경으로 기존 설정 불일치 — 실제 로봇 주소 169.254.122.16 확인

- **문제**: 저장된 설정·launch 기본값의 robot_ip(`169.254.183.219`)로 로봇 접근 불가(ping 무응답)
- **원인**: 로봇 제어박스(TMflow, Windows)가 APIPA(link-local) 주소를 사용하며 주소가 변경됨. eno1 수동 감청으로 실제 주소 `169.254.122.16`(MAC 00:10:f3:bf:3f:60, Nexcom) 발견. TCP 5891(Ethernet Slave) OPEN + `$TMSVR` 스트림 수신으로 로봇 확정. 5890(Listen)은 Listen 프로젝트 미실행으로 닫힘
- **해결**: eno1 nmcli 프로파일에 `169.254.183.100/16` 영구 추가(재부팅 유지) → ping 0.26ms, 5891 접속 확인. config/launch 의 robot_ip 값 갱신은 미수행(실행 시 `robot_ip:=169.254.122.16` 인자로 대체 가능)
- **파일**: (시스템) NetworkManager `eno1` 프로파일. 저장소 파일 수정 없음
- **상태**: 완료 (잔여: 로봇 측 Listen 프로젝트 실행 후 5890 확인)

## 2026-07-05

### [Issue] kuks_claude_agent_setup 번들 설치 (설정 변경)
- **문제**: Claude Code 작업 규칙·훅 자산(kuks_claude_agent_setup)이 본 프로젝트에 미설치 상태
- **해결**: https://github.com/kuks2309/kuks_claude_agent_setup 의 프로젝트 대상 번들 10개 설치 (user_instruction, external_reference, code_review, sw_structure, coding, debt, issue_fix, mistake, git_workflow, reverse_engineering). 규칙은 `docs/claude_guideline/`, 훅 12개는 `.claude/settings.json` 에 등록. 전역 번들 중 acronym 은 기설치, computer_use 는 미설치(전역 대상이라 제외)
- **파일**: `CLAUDE.md`, `.gitignore`, `.claude/settings.json`, `docs/claude_guideline/**`, `docs/debt/registry.md`
- **상태**: 완료 (미결: issue_fix 번들의 정규 로그 경로 `docs/issues_and_fixes/issues_and_fixes.md` 와 기존 `docs/issues-fixes/ISSUES_AND_FIXES.md` 경로 충돌 — 사용자 결정 필요)

### [Fix] install_dependencies.sh 절대 경로 제거
- **문제**: 스크립트에 워크스페이스 절대 경로가 하드코딩됨 (`cd /home/amap/TM_Robot_ros2_ws`, 안내 문구 `cd ~/TM_Robot_ros2_ws`). 실제 워크스페이스 경로(`/home/amap/Project/T-Robotics/kkw/TM_Robot_ros2_ws`)와도 달라 rosdep 단계가 실패함
- **해결**: 스크립트 자신의 위치를 기준으로 워크스페이스 경로를 동적으로 산출 (`SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`). rosdep `cd`와 안내 문구 모두 `$SCRIPT_DIR` 사용으로 변경
- **파일**: `install_dependencies.sh`
- **상태**: 완료

---

## 2026-02-10

### [Critical Fix] Runtime 변환 기준점(reference.tm_jig_landmark) 설정 오류

> **[매우 중요] reference.tm_jig_landmark는 반드시 비전 시스템이 검출한 jig landmark의 robot base 절대좌표여야 합니다. TCP 스캔 위치(measure_point)와 혼동하면 안 됩니다.**

- **문제**: Runtime 변환 시 `reference.tm_jig_landmark`에 **measure_point의 TCP 위치**를 저장하여 변환 좌표가 완전히 틀림
- **핵심 개념 (모든 좌표는 robot base 기준)**:
  - **measure_point** (X=27.57, Y=574.71) = **TCP가 스캔하러 이동한 위치** (robot base 좌표)
  - **jig landmark 검출 좌표** = **비전 시스템(`g_TM_Landmark`)이 반환하는 landmark 위치** (robot base 좌표)
  - **기준 좌표계는 동일하게 robot base**이지만, **TCP 위치 ≠ landmark 위치** (서로 다른 물리적 위치)
  - TCP 위치를 landmark 좌표로 사용하면 모든 상대좌표 변환이 틀어짐
- **변환 흐름과 기준점의 역할 (모두 robot base 좌표)**:
  ```
  [변환 시] T_rel = T_reference^(-1) × T_absolute   ← reference = landmark 검출 좌표 (robot base)
  [실행 시] T_abs = T_detected    × T_rel            ← detected  = 실시간 landmark 검출 (robot base)

  reference ≠ detected → 좌표 오류 발생
  reference = detected (동일 위치) → 원본 절대좌표 정확히 복원
  ```
- **해결**:
  1. `convert_to_runtime.py`: 직전 Job(TCP 좌표) fallback 제거. `reference.tm_jig_landmark` 필수화
  2. `main_window.py`: Recipe 저장 시 `get_scan_data('jig_landmark')['landmark']`에서 **실제 검출 좌표** 자동 저장 (`_update_recipe_reference()`)
  3. 마스터 파일의 잘못된 reference 값 제거 (null로 초기화)
- **기준점 우선순위** (수정 후):
  1. 마스터 `reference.tm_jig_landmark` (필수 - landmark 검출 좌표)
  2. Jig Plate Calibration 파일 (fallback, 경고 표시)
  3. ~~직전 Job (TCP 좌표)~~ → **삭제** (TCP ≠ landmark)
- **절대 금지 사항**:
  - measure_point, move_to_point 등 TCP 위치를 landmark 좌표로 사용 금지
  - reference에 수동으로 TCP 좌표를 입력하지 말 것
  - 반드시 로봇에서 Recipe 실행 → scan_tm_landmark 검출 → 저장 순서로 등록
- **파일**:
  - `tools/convert_to_runtime.py` — fallback 3-3(직전 Job) 삭제, reference 필수화
  - `tm_task_manager/main_window.py` — `_update_recipe_reference()` (auto-save)
  - `config/recipes/tm_landmark_test4.yaml` — 잘못된 reference 제거
- **상태**: 완료

---

### [Feature] line_move_to_point Job 타입 추가 (LINE_T 직선 이동)
- **요청**: 기존 `move_to_point`는 PTP_T(곡선 경로)로 이동하여 직선 경로가 필요한 구간에서 충돌 위험 있음. 절대좌표 기반 직선 이동 명령 필요
- **해결**: `line_move_to_point` Job 타입 신규 추가 (SetPositions.LINE_T = 4)
  - **동작 방식**: 현재위치 입력(기준위치) + 오프셋 = 목표위치로 LINE_T 직선 이동
  - **파라미터**:
    - `X/Y/Z/Rx/Ry/Rz`: 기준위치 (현재위치 입력 버튼으로 설정)
    - `offset X/Y/Z`: 오프셋 (mm)
    - `velocity`: 속도 (%)
    - `motion_type`: tcp 고정 (LINE_T는 TCP만 지원)
  - **안전 체크**: 기준좌표가 모두 (0,0,0,0,0,0)이면 실행 차단 (경고 메시지 출력)
  - **coordinate_mode 지원**: relative 모드 시 Landmark 기준 좌표 변환 (teaching/execution 모드 분기)
  - `_move_to_position_line()`: 기존 `_move_to_position()`의 LINE_T 버전 헬퍼 메서드
- **기존 move_linear와 차이점**:
  - `move_linear`: Tool 좌표계 상대 오프셋 (Move_Line TPP)
  - `line_move_to_point`: 절대좌표 직선 이동 (LINE_T), 현재위치+오프셋 방식
- **파일**:
  - `tm_task_manager/recipe_manager.py` — JOB_TYPES에 line_move_to_point 추가
  - `tm_task_manager/job_executor.py` — 디스패치, `_move_to_position_line()`, `_exec_line_move_to_point()` 추가
  - `tm_task_manager/tabs/task_edit_tab.py` — UI 디스패치 및 `_exec_line_move_to_point()` 추가
- **상태**: 완료

### [Fix] line_move_to_point 기본값(0,0,0) 이동 시 타임아웃
- **문제**: `line_move_to_point` 최초 테스트 시 기본 파라미터 (0,0,0,0,0,0)으로 LINE_T 이동 명령 전송 → 로봇이 도달 불가능한 원점으로 이동 시도하여 30초 타임아웃 발생
- **원인**: 파라미터 기본값이 모두 0.0으로 설정되어 있어, "현재위치 입력" 없이 실행하면 원점(0,0,0)으로 이동 시도
- **해결**: `_exec_line_move_to_point()`에 좌표 전체가 (0,0,0,0,0,0)일 때 실행 차단하는 안전 체크 추가. 경고 메시지로 "현재위치 입력 버튼으로 기준위치를 설정해 주세요" 안내
- **파일**: `tm_task_manager/job_executor.py`
- **상태**: 완료

---

## 2026-02-09

### [Feature] Task Editor AI 인식 실행 기능 및 Jig Latch OPEN/CLOSE 판별
- **요구사항**:
  1. Task Editor에서 `ai_inspection` 작업 선택 시 "AI 인식 실행" 버튼으로 변경 및 실행 기능
  2. Jig Latch 검사에서 열림/닫힘 상태 판별 (마스크 주축 각도 기반)
  3. 판별 각도 임계값을 파라미터로 입력 가능하게
- **해결**:
  1. `DetectionResult`에 `angle`, `state` 필드 추가
  2. `AIDetectionService`에 `_calc_mask_angle_and_state()` 메서드 추가 (minAreaRect 주축 각도 → 90°±N° 이내=CLOSE, 그 외=OPEN)
  3. `set_angle_threshold()` / `angle_threshold` 속성 추가
  4. `recipe_manager.py` `ai_inspection` 파라미터에 `angle_threshold` 추가 (기본 15°, step 1°)
  5. `task_edit_tab.py`에 `_exec_ai_inspection()` 추가: 모델 자동 탐색/로드 → 이미지 캡처 → 추론 → 결과(각도/상태) 표시
  6. `_on_ai_inspection_result()`에서 `detection_completed` 시그널 수신하여 `label_tmLandmarkResult`에 결과 표시
  7. AI Detection 탭 결과 테이블에 Angle, State 컬럼 추가 (5→7컬럼)
  8. `_draw_annotations`에 라벨에 각도/상태 텍스트 추가
  9. `job_executor.py`에서도 `angle_threshold` 적용
- **파일**: `services/ai_detection_service.py`, `tabs/task_edit_tab.py`, `tabs/ai_detection_tab.py`, `ui/ai_detection_tab.ui`, `recipe_manager.py`, `job_executor.py`, `config/recipes/AI_test.yaml`
- **상태**: 완료

### [Fix] AI Detection Single Shot 추론 미실행 문제
- **문제**: AI Detection 탭에서 Single Shot 버튼 클릭 시 이미지 캡처는 성공하지만 YOLOv8 추론이 실행되지 않음. 모델은 정상 로드 상태(best.pt)
- **원인**: 동적 `connect()`/`disconnect()` one-shot 시그널 패턴에서 `image_captured` 시그널이 `_on_capture_then_detect` 슬롯에 전달되지 않음. PyQt5 cross-thread 시그널(QThread→MainThread) 처리 시, 동적으로 연결한 슬롯이 호출되지 않는 문제. 디버그 로그로 확인: `_on_capture_for_detect_finished`는 호출되지만 `_on_capture_then_detect`는 호출되지 않음
- **해결**:
  1. `connect_signals()`에서 `image_captured` → `_on_capture_then_detect` 영구 연결
  2. `_on_single_detection()`은 `_pending_single_detection` 플래그만 설정
  3. `_on_capture_then_detect()`에서 플래그 확인 후 시그널로 받은 `cv_image`를 직접 `run_inference()`에 전달
  4. 불필요한 `_on_capture_for_detect_error`, `_on_capture_for_detect_finished` 제거
  5. `main_window._on_image_captured()`에 `self.current_camera_image = cv_image` 추가
- **파일**: `tm_task_manager/tabs/ai_detection_tab.py`, `tm_task_manager/main_window.py`
- **상태**: 완료

### [Enhancement] Load Custom 버튼 초기 경로를 AI tasks 디렉토리로 설정
- **문제**: Load Custom... 버튼 클릭 시 파일 다이얼로그가 기본 경로(홈)에서 열려 모델 파일 탐색이 불편
- **해결**: `AIDetectionService.TASKS_ROOT` (`src/AI/tasks`)를 초기 경로로 설정. 경로가 존재하지 않으면 기본 경로 사용
- **파일**: `tm_task_manager/tabs/ai_detection_tab.py`
- **상태**: 완료

### [Fix] Image Capture 버튼 여러 번 눌러야 이미지 수신되는 문제
- **문제**: Vision 패널에서 Image Capture 버튼 클릭 시 한 번에 이미지가 오지 않고, 여러 번 클릭해야 수신됨
- **원인**: `techman_image` 토픽 구독이 일회성(one-shot) 패턴으로 구현되어 있었음. 매 캡처마다 구독을 생성→수신→파괴하는데, 새 구독 생성 시 DDS Discovery(Publisher 탐색)에 시간이 소요됨. 로봇이 `ScriptExit()` 후 바로 이미지를 발행하지만, Discovery가 완료되기 전에 발행되면 수신을 놓침
- **해결**: 일회성 구독 → 영구 구독(Persistent Subscription)으로 변경
  1. `TaskManagerNode.__init__`에서 `techman_image` 구독을 한 번만 생성 (DDS Discovery 1회)
  2. `_on_techman_image` 콜백에서 `waiting_for_techman_image` 플래그가 True일 때만 이미지 저장 (불필요한 수신 무시)
  3. `start_techman_image_subscription()`은 플래그만 리셋 (구독 재생성 불필요)
- **파일**: `tm_task_manager/main_window.py` (TaskManagerNode)
- **상태**: 완료

---

## 2026-02-08

### [Feature] Recipe 변환 시스템 개선 - runtime-only job 자동 삽입

- **요청**: master→runtime YAML 변환 시 `find_landmark` 등 runtime 전용 job을 수동 삽입하는 방식이 취약함
- **해결**: `convert_to_runtime.py`에 자동 삽입 시스템 구현
  - **RUNTIME_ONLY_JOBS 레지스트리**: runtime 전용 job 타입을 모듈 레벨 dict로 관리
  - **자동 삽입**: `scan_tm_landmark` 직전에 `find_landmark` 자동 삽입
  - **중복 방지**: 마스터에 이미 존재하는 job type은 삽입 건너뜀
  - **ID 재배정**: 삽입 후 1부터 순차 재배정
  - **날짜/헤더 처리**: `modified` 날짜 자동 갱신, YAML 상단 헤더 주석 추가
  - **외부 설정 파일**: `config/runtime_job_defaults.yaml`로 코드 수정 없이 파라미터 변경 가능
- **파일**:
  - `tools/convert_to_runtime.py` - RUNTIME_ONLY_JOBS, RecipeConverter 확장
  - `config/runtime_job_defaults.yaml` - 외부 파라미터 설정 (신규)
  - `job_executor.py` - `_exec_generate_runtime` 동기화
- **상태**: 완료

### [Fix] calculate_plate_pose Jig 데이터 손실 - TM Robot 글로벌 변수 덮어쓰기 문제

- **문제**: `scan_tm_landmark_jig`에서 `repeat_count: 3` 반복 측정 시, Jig2가 1/3 성공했으나 `calculate_plate_pose`에서 "Jig2 미검출" 오류 발생
- **원인**: `_exec_calculate_plate_pose`가 Python 저장 결과 대신 TM Robot 글로벌 변수(`g_Jig_Landmark1~4`)를 재읽기함. 2번째/3번째 스캔 실패 시 글로벌 변수가 "미검출" 상태로 덮어쓰기되어 첫 번째 성공 결과가 유실됨
- **해결**: Python 측에 Jig 스캔 결과를 저장하고 `calculate_plate_pose`가 저장된 결과를 사용하도록 변경
  1. `__init__`에 `self.jig_landmark_results = {}` 딕셔너리 추가
  2. `_exec_scan_tm_landmark_jig`에서 `final_pose`를 `jig_landmark_results[jig_number]`에 저장
  3. `_exec_calculate_plate_pose`에서 `vision_manager.execute_tm_landmark_jig_read()` 대신 `jig_landmark_results` 사용
- **파일**: `tm_task_manager/job_executor.py`
- **상태**: 완료

### [Feature] scan_tm_landmark 반복 측정 횟수 추가

- **요청**: 단일 측정 실패 시 재시도가 없어 스캔 실패율이 높음
- **해결**: master recipe의 scan job에 `repeat_count: 3` 추가
  - `scan_tm_landmark` (id:6): `repeat_count: 3`
  - `scan_tm_landmark_jig` (id:11,13,18,20): `repeat_count: 3`
  - 3회 반복 중 1회만 성공해도 유효 데이터로 계산 가능
- **파일**: `config/recipes/tm_landmark_test4.yaml`, `config/recipes/tm_landmark_test4_runtime.yaml`
- **상태**: 완료

### [Feature] find_landmark 태스크 추가 - 격자 패턴 Landmark 검색

- **요청**: 로봇이 티칭 위치로 이동했지만 마커가 다른 곳에 있을 때 검색 기능 필요
- **해결**: `find_landmark` 태스크 신규 구현
  - **기능**: XY 평면에서 격자 패턴으로 탐색 (Z축 고정, 안전 우선)
  - **탐색 순서**: 중심→외곽 (5→2→4→6→8→1→3→7→9)
  - **격자 배치 (3x3)**:
    ```
    1(-1,+1)  2(0,+1)  3(+1,+1)
    4(-1, 0)  5(0, 0)  6(+1, 0)
    7(-1,-1)  8(0,-1)  9(+1,-1)
    ```
  - **파라미터**:
    - `grid_step`: 격자 간격 (기본 30mm)
    - `grid_size`: 격자 크기 (3x3 또는 5x5)
    - `scan_timeout`: 각 위치 스캔 타임아웃 (기본 500ms)
    - `velocity`: 이동 속도 (기본 30%)
    - `on_found`: 발견 시 동작 (store_position / move_and_scan)
    - `on_not_found`: 미발견 시 동작 (abort / continue / ask_user)
- **기존 scan_tm_landmark와 역할 분리**:
  - `scan_tm_landmark`: 현재 위치에서 스캔 + repeat으로 안정값 획득
  - `find_landmark`: 마커가 시야 밖일 때 격자 탐색으로 찾기
- **파일**:
  - `recipe_manager.py`: JOB_TYPES에 find_landmark 정의 추가
  - `job_executor.py`: _exec_find_landmark() 메서드 및 분기 추가
  - `task_edit_tab.py`: UI 버튼 텍스트 및 실행 메서드 추가
- **상태**: 완료

### [Refactor] Task 카테고리 재구성 (Vision → Landmark, AR Tag, Calibration, Utility)

- **문제**: Vision 카테고리에 TM Landmark, AR Tag, Calibration, 파일 생성 등 성격이 다른 태스크들이 혼재되어 있음. 향후 영상처리 기능을 위해 Vision 카테고리를 비워둘 필요 있음
- **원인**: 초기 설계 시 비전 관련 작업을 모두 Vision으로 분류
- **해결**: 5개 카테고리로 분리
  - **Vision**: 향후 영상처리 기능용 (예약, 현재 비어있음)
  - **Landmark**: TM Landmark 관련 태스크
    - `scan_tm_landmark`, `scan_tm_landmark_jig`, `scan_align_tm_landmark`, `align_tm_landmark`
  - **AR Tag**: AR 태그 관련 태스크
    - `scan_ar_tag`, `wait_for_detection`, `align_to_ar_tag`, `move_to_ar_center`
  - **Calibration**: 캘리브레이션/계산 태스크
    - `calculate_plate_pose`
  - **Utility**: 파일/유틸리티 태스크
    - `generate_runtime`
- **파일**: `tm_task_manager/recipe_manager.py` (AVAILABLE_TASKS 카테고리 변경)
- **상태**: 완료

### [Refactor] Vision 폴더 구조 재구성 (ROS2/Python/Cpp 분리)

- **문제**: Vision 폴더에 ROS2 패키지만 존재. 향후 Python 플러그인 및 C++ 고성능 라이브러리 추가 필요
- **원인**: 초기 구성 시 ROS2 패키지만 고려
- **해결**: 실행 환경별 3개 폴더로 분리
  - **ROS2/**: ROS2 Node 기반 (실시간 스트림 처리)
    - `tm_aruco_detect/` - ArUco 마커 검출 (C++)
    - `tm_camera_calibration/` - 카메라 캘리브레이션 (C++)
  - **Python/**: Task Manager에서 직접 호출하는 플러그인
    - `plugins/base_plugin.py` - 플러그인 베이스 클래스
    - `plugins/` - 개별 플러그인들
    - `utils/` - 유틸리티 함수
  - **Cpp/**: 고성능 C++ 라이브러리 (pybind11로 Python에서 호출 가능)
    - `include/fast_vision.hpp` - 헤더
    - `src/fast_vision.cpp` - 구현
- **이동 내역**:
  - `Vision/tm_aruco_detect/` → `Vision/ROS2/tm_aruco_detect/`
  - `Vision/tm_camera_calibration/` → `Vision/ROS2/tm_camera_calibration/`
- **파일**: `src/Vision/` 전체 구조 변경
- **상태**: 완료

### [Feature] Vision Task 플러그인 시스템 구현

- **요청**: Vision 카테고리에 플러그인 기반 영상처리 태스크 추가
- **해결**: `vision_process` 태스크 및 플러그인 매니저 구현
  - **vision_process 태스크**: Recipe에서 플러그인 지정하여 영상처리 수행
    - `plugin`: 실행할 플러그인 이름
    - `input_source`: 입력 소스 (camera, file, variable)
    - `plugin_params`: 플러그인별 파라미터
    - `output_variable`: 결과 저장 변수명
    - `save_image`: 결과 이미지 저장 여부
  - **VisionPluginManager**: 플러그인 동적 로드 및 관리
  - **BaseVisionPlugin**: 플러그인 베이스 클래스 (추상)
  - **edge_detection**: Canny 엣지 검출 예시 플러그인
- **실행 흐름**: 이미지 취득 → 플러그인 로드 → 처리 → 결과 저장
- **파일**:
  - `tm_task_manager/recipe_manager.py` - vision_process 태스크 정의
  - `tm_task_manager/job_executor.py` - _exec_vision_process 메서드
  - `tm_task_manager/services/vision_plugin_manager.py` - 플러그인 매니저
  - `src/Vision/Python/plugins/edge_detection.py` - 예시 플러그인
- **상태**: 완료

### [Feature] C++ pybind11 바인딩 추가

- **요청**: C++ 고성능 영상처리 라이브러리를 Python에서 사용
- **해결**: pybind11을 사용하여 C++ 함수를 Python 모듈로 빌드
  - **bindings/py_fast_vision.cpp**: pybind11 바인딩 코드
    - `fast_edge_detect()`: 고속 Canny 엣지 검출
    - `fast_template_match()`: 고속 템플릿 매칭
    - `fast_find_contours()`: 고속 컨투어 검출
  - **CMakeLists.txt**: pybind11 빌드 설정 추가
  - **fast_edge 플러그인**: C++ 모듈 사용, OpenCV fallback 지원
- **빌드 방법**:
  ```bash
  cd src/Vision/Cpp
  mkdir build && cd build
  cmake .. && make
  # fast_vision.cpython-*.so 생성됨
  ```
- **파일**:
  - `src/Vision/Cpp/bindings/py_fast_vision.cpp` - pybind11 바인딩
  - `src/Vision/Cpp/CMakeLists.txt` - 빌드 설정
  - `src/Vision/Python/plugins/fast_edge.py` - C++ 기반 플러그인
- **상태**: 완료

---

## 2026-02-07

### [Refactor] AI 폴더 구조 재편 (tasks/ + engine/ 분리)

- **문제**: AI 관련 코드가 `Latch_detect/`, `Datasets/Jig-latch/`, `YoloV8/` 등에 산재. 작업(task)과 실행환경(engine)의 구분 없음
- **원인**: 초기 구성 시 플랫폼(PC/Hailo) 및 작업(task)별 분리 없이 도구 중심으로 배치
- **해결**: `tasks/` (WHAT) + `engine/` (HOW) 2계층 분리
  - `src/AI/engine/core/` — 공통 기반 모듈 (base_detector, model_registry)
  - `src/AI/engine/yolov8/` — PC 런타임 (기존 `YoloV8/` 이동)
  - `src/AI/engine/hailo/` — Hailo H8 런타임 (기존 `Hailo_H8/` 이동)
  - `src/AI/tasks/jig_latch/` — Jig Latch Detection (기존 `Datasets/Jig-latch/` + `Latch_detect/` 통합)
    - `data/` — 데이터셋 (train/valid/test)
    - `models/{pt,onnx,har,hef}/` — 모든 포맷 모델
    - `pc/` — PC 추론 스크립트
    - `hailo/` — Hailo 추론/컴파일 스크립트
    - `training/` — 학습 스크립트
  - `src/AI/tasks/tag_detect/` — Tag Detection 스켈레톤 (동일 패턴, 신규)
- **이동 내역**:
  - `Datasets/Jig-latch/` → `tasks/jig_latch/` (리네임+구조조정)
  - `Latch_detect/latch_predict.py` → `tasks/jig_latch/pc/latch_predict.py`
  - `Jig-latch/scripts/inference.py` → `tasks/jig_latch/pc/inference.py`
  - `Jig-latch/scripts/train_test_custom.py` → `tasks/jig_latch/training/train.py`
  - `Jig-latch/configs/yolov8s_seg_custom.yaml` → `tasks/jig_latch/hailo/hailo_model_config.yaml`
  - `YoloV8/` → `engine/yolov8/`
  - `Hailo_H8/` → `engine/hailo/`
- **삭제**: `Latch_detect/`, `Datasets/`
- **경로 업데이트**:
  - `ai_detection_service.py` — venv, 모델 경로 수정
  - `engine/yolov8/yolo.sh` — YOLO_DIR 수정
  - `engine/hailo/hailo.sh` — HAILO_DIR 수정
  - `tasks/jig_latch/data/data.yaml` — 데이터셋 경로 수정
  - `tasks/jig_latch/pc/inference.py` — PROJECT_ROOT 수정
- **파일**: `src/AI/` 전체
- **상태**: 완료

### [Feature] AI Detection 탭 — Detection/Runtime/Model 선택 UI 구현

- **문제**: AI Detection 탭이 단일 모델/단일 런타임만 지원. Task(jig_latch, tag_detect)와 Runtime(PC, Hailo H8) 선택 불가
- **해결**: Detection Setup GroupBox에 3단 캐스케이드 ComboBox 추가
  - `comboBox_detection` — 검출 대상 선택 (Jig Latch, Tag Detect)
  - `comboBox_runtime` — 런타임 선택 (PC, Hailo H8)
  - `comboBox_model` — 모델 자동 필터링 (`tasks/{task}/models/{pt|hef}/*.{pt|hef}`)
  - Detection/Runtime 변경 시 Model 목록 자동 갱신
  - Load Custom 버튼: Runtime에 따라 파일 필터 분기 (.pt / .hef)
- **원인 (탭 빈 화면 이슈)**: `main_window.ui`의 `tab_aiDetection`에 이미 `verticalLayout_aiDetection` 레이아웃 존재 → `init_ui()`에서 `QVBoxLayout()` 중복 생성 시도 → 위젯 미표시
- **해결**: 기존 레이아웃 `tab_aiDetection.layout()` 재사용하도록 수정
- **파일**:
  - `ui/ai_detection_tab.ui` — Detection Setup GroupBox (3 ComboBox + Label + Button)
  - `services/ai_detection_service.py` — `DETECTION_TASKS`, `RUNTIME_CONFIG` 레지스트리, `get_available_tasks()`, `get_available_runtimes()`, `get_available_models(task, runtime)` 추가
  - `tabs/ai_detection_tab.py` — `_init_detection_setup()`, `_refresh_model_combobox()`, `_on_detection_changed()`, `_on_runtime_changed()` 구현, 레이아웃 중복 생성 수정
- **상태**: 완료

---

## 2026-02-06

### [Issue] mark_jig_plate UI 위치 변경
- **문제**: `mark_jig_plate (1~4)` 섹션이 오른쪽 `jig_plate` 아래에 있어 불편함
- **해결**: `main_window.ui`에서 해당 섹션을 왼쪽 `jig_landmark` 아래로 이동
- **파일**: `ui/main_window.ui`
- **상태**: 완료

### [Issue] jig_plate 좌표는 계산값이어야 함
- **문제**: jig_plate는 4개 landmark로부터 계산되어야 하는데, "TM Flow에서 읽기" 버튼으로 되어 있음
- **원인**: 초기 설계 시 jig_plate를 단일 landmark처럼 처리
- **해결**:
  1. "TM Flow에서 읽기" → "4개 Mark로부터 계산" 버튼으로 변경
  2. "현재위치로 설정" 버튼 제거 (계산값이므로 불필요)
  3. `JigPlaneCalculator`를 사용한 계산 로직 연결
- **파일**:
  - `ui/main_window.ui` (버튼 변경)
  - `tabs/settings_tab.py` (`_on_calculate_jig_plate` 메서드 추가)
- **상태**: 완료

### [Issue] jig_plate "4개 Mark로부터 계산" 버튼 위치 및 레이아웃 변경
- **문제**: 버튼이 좌표 입력 필드 위에 있고, 버튼들이 2줄로 배치되어 불편함
- **해결**:
  1. 버튼을 좌표 입력 필드 아래로 이동
  2. "4개 Mark로부터 계산"과 "저장" 버튼을 한 줄에 좌우로 배치 (QHBoxLayout)
- **파일**: `ui/main_window.ui`
- **상태**: 완료

### [Issue] jig_landmark 버튼 레이아웃 정리
- **문제**: "현재위치로 설정" 버튼이 jig_landmark에는 불필요함
- **해결**:
  1. "현재위치로 설정" 버튼 삭제
  2. "TM Flow에서 읽기"와 "저장" 버튼을 좌표 필드 아래에 좌우로 배치
- **파일**: `ui/main_window.ui`
- **상태**: 완료

### [Feature] Jig Plate 3D 검증 도구 버튼 추가
- **요청**: jig_plate_validator.py 프로그램을 실행할 버튼 추가
- **구현**:
  1. "3D 검증" 버튼을 jig_plate 섹션에 추가 (계산/저장 버튼 옆)
  2. 클릭 시 jig_plate_validator.py를 별도 프로세스로 실행
  3. positions.yaml 경로 자동 전달
- **파일**:
  - `ui/main_window.ui` (버튼 추가)
  - `tabs/settings_tab.py` (`_on_open_jig_validator` 메서드 추가)
- **상태**: 완료

---

## 2026-08-30

### [Issue] sdc_gripper Job 오탐 — 직전 모션 래치 상태를 첫 폴링이 오판
- **문제**: `zefg_serial.move_to` 가 명령 직후 첫 폴링에서 직전 모션의 래치된 파지 상태(0x0041)를 읽고 오판 — 래치 Dropping → 즉시 "낙하 감지" 오탐 실패(실기 재현: pos 0.1mm 시점 실패 보고 후 실물은 35mm 정상 완주), 래치 Clamping → open 을 "파지 완료"로 오탐 성공(동일 원인 잠재 경로).
- **원인**: 슬레이브는 새 위치 명령 후에도 직전 모션의 최종 상태를 유지 응답(실기 관측 — HIL 정본 `src/Actuators/gripper/docs/hil/2026-08-29-zefg-c35-h0.md` §백드라이브·힘 순응 실측). 폴링 루프가 상태 신선도를 확인하지 않고 첫 표본부터 판정 사용.
- **해결**: Dropping/Clamping 판정을 Moving 관측 후 또는 `STATUS_GRACE_S`(0.3s) 경과 후에만 유효화(In place 는 위치 대조 있어 예외). 단위 테스트 래치 재현 2종 추가 — 8/8 PASS. Clamping 오탐 경로 동시 수정은 동일 근본 원인으로 포함(보고 완료). C++ 벤더 스택(ZefgSequencer)에도 동일 신선도 게이트 설계 반영(status_grace{300}, 변이 프로브 검증).
- **파일**: `src/TM_Robot_Task_Manager/tm_task_manager/hardware/zefg_serial.py`, `test/test_sdc_gripper.py` (상세: `src/TM_Robot_Task_Manager/docs/code_updates/2026-08-30-sdc-gripper-stale-status-fix.md`)
- **상태**: 완료 — orin 재배포 후 실기 오탐 재현 조건(래치 Dropping·35mm)에서 open 성공 확인 (2026-08-30 11:27)

---

## Template

### [Issue] 이슈 제목
- **문제**: 문제 설명
- **원인**: (파악된 경우) 원인 설명
- **해결**: 해결 방법
- **파일**: 관련 파일 경로
- **상태**: 진행중 / 완료 / 보류

---
