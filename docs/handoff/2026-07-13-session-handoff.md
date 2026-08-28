# 세션 인수인계 — 2026-07-13 (KST)

> **왜 이 문서가 있나**: 작업 워크스페이스를 `kkw/TM_Robot_ros2_ws` → `KJW/TM_Robot_ros2_ws` 로 옮겼다.
> Claude 세션은 작업 디렉토리가 고정이라 **대화 맥락이 새 세션으로 안 넘어간다.** 그래서 이 문서로 인계한다.
> 새 세션은 이 문서부터 읽으면 바로 이어받을 수 있다.

## 0. 이관 시 한 일 (2026-07-13)

- `scripts/web_gui.sh` — 워크스페이스 경로 하드코딩 제거, **스크립트 위치에서 자동 유도**하도록 변경(또 옮겨도 안 깨짐).
- `src/Vision/ROS2/tm_camera_calibration/config/calibration_params.yaml` — `save_path` 를 KJW 절대경로로.
- **`build/ install/ log/` 삭제 후 클린 재빌드** — 복사된 `install/` 이 `--symlink-install` 탓에 **옛 워크스페이스(kkw)를 가리키는 심볼릭 링크 444개**를 갖고 있었다. 겉보기엔 멀쩡한데 **실제로는 옛 코드가 실행**되는 함정. 워크스페이스를 복사·이동할 땐 **반드시 재빌드**할 것.
- 구 워크스페이스(kkw)의 **파일은 일절 변경하지 않았다**. 거기서 띄웠던 서비스 프로세스만 정지(포트 해제).

---

## 1. 이 프로젝트가 뭔가

TM(Techman) 로봇을 **웹 GUI(브라우저)** 로 제어한다. 로봇 IP `169.254.122.16`.

**아키텍처 (하이브리드)**
```
브라우저 (React, 별도 프로젝트 ~/Desktop/TRobotics_Client — git 저장소 아님)
   ├── rosbridge (:9090) ──── 실시간 토픽 구독 (관절·TCP·이미지·AR 태그)
   └── HTTP (:8000) ───────── tm_web_bridge (FastAPI + rclpy) — 명령·서비스
                                   │ 기존 tm_task_manager 서비스 5개를 재사용하는 얇은 껍데기
                                   ▼
                              tm_driver → 로봇
```

**전체 스택 기동**: `./scripts/web_gui.sh start` (status/stop/restart 도 있음)
- 6종: tm_driver · 카메라 브리지(:6189) · rosbridge(:9090) · 웹 브리지(:8000) · JPEG 재발행 · vite(:3000)
- ⚠️ **TMflow 프로젝트는 로봇 내부에서 도는 것이라 PC 에서 못 켠다** — 로봇 펜던트에서 실행(Listen 노드 진입) 필요. 스크립트가 상태만 점검해 알려준다.

---

## 2. 지금까지 완료한 것

| 항목 | 상태 |
|---|---|
| 웹 GUI 로봇 연결 (조그·시퀀스·IO·좌표계) | ✅ |
| 전역 **모션 게이트**(상단 스위치, 로드 시 자동 OFF) | ✅ |
| Vision 탭 — 라이브 카메라 + AR 태그 + **TCP 조그** | ✅ |
| **Intrinsic 캘리브레이션** (재투영 0.4575px) | ✅ 2026-07-10 |
| **임의 포즈 무이동 촬영** 검증 (`Vision_DoJob`) | ✅ |
| **복수 기기 라이브 병목 해결** (서버 단일 촬영 루프) | ✅ 2026-07-13 |
| Hand-Eye ADR(Architecture Decision Record) 승인 | ✅ (착수 범위만 미정) |

상세: `docs/worklog/2026-07-{07..13}.md`, `docs/issues_and_fixes/issues_and_fixes.md`

---

## 3. 다음에 할 일 (우선순위)

### ① Hand-Eye 서브시스템 구축 — **승인 완료, 착수 범위만 결정하면 시작**
- ADR: `docs/adr/2026-07-10-hand-eye-calibration.md`
- **확정**: 결정 A = 브리지(웹)에서 수집 / 결정 B = Python cv2 자체 solvePnP
- **미정**: 착수 범위 (WBS 전체 vs 우선 1~2단계(안전가드+수집))
- 전제는 **전부 충족**: intrinsic 완료, 무이동 촬영 검증, TCP 포즈 소스, 체스보드(6×8, 25mm)
- 목표 오차 사용자 희망 **±0.5mm** — 단 비전 단독으론 도전적(통상 ±1~3mm). **구축 후 실측해서 판단**하기로 함.

### ② MoveIt GUI 패널 — **🚨 블로커: 로봇 모델 미확정**
- MoveIt2 설치됨(26패키지), `/tmr_arm_controller/follow_joint_trajectory` 액션도 **이미 존재**.
- **문제**: 기록상 로봇은 **TM250250** 인데 워크스페이스엔 **TM25/TM20/TM16 URDF 가 0건** (tm5-700/900, tm5x, tm12, tm12x, tm14, tm14x 만 있음).
- **URDF 가 실물과 다르면 충돌 모델이 틀려 오히려 위험** → **실제 로봇 모델을 먼저 확인**해야 한다(TMflow 또는 명판).
- `moveit_py`(Python API) 는 **없음**. 브리지(Python)는 `moveit_msgs` 액션/서비스(`/move_action`, `/plan_kinematic_path`, `/compute_ik`)로 직접 호출하면 된다.
- 설계: 계획(무동작)과 실행(게이트 필수)을 **분리**. 3D 시각화는 별도 트랙(브라우저엔 RViz 없음).

### ③ 기타
- 해상도 정책: 라이브 속도를 위해 해상도를 낮추면 **intrinsic 캘리브(2592×1944 기준)가 무효** → 낮출 거면 재캘리브 필요.
- (선택) 라이브 루프 클럭을 원본 토픽으로 → 1.2 → 1.9 FPS 회복 (단 Jetson CPU 부하↑).
- (보류) `src/AI`(12GiB, 18.8만 파일)를 에디터 인덱싱에서 제외 — 에디터 다운 재발 시.

---

## 4. ⚠️ 반드시 알아야 할 함정들 (실제로 당한 것들)

1. **`npx tsc --noEmit` 은 아무것도 검사하지 않는다** — 웹 클라이언트 `tsconfig.json` 이 solution 스타일(`"files": []`)이라 **항상 exit 0**. **반드시 `npx tsc -b`** (또는 `npm run build`) 를 쓸 것. 이걸로 "검증 통과"를 오보한 사고: `docs/claude-mistake/2026-07-13-001.md`.
2. **`pkill -f "tm_web_bridge"` 금지** — 경로에 그 문자열이 든 `src/tm_web_bridge/scripts/jpeg_republish_node.py` 와 **실행 중인 셸 자신**까지 죽인다(exit 144 실제 발생). 종료는 **소켓 소유 PID**(`ss -tlnp | grep ':8000 '`)로 특정할 것.
3. **DDS 탐색 기반 조회로 "없다"를 확정하지 말 것** — `ros2 node list`/`node info`, `ros2 action list`/`action info`, `ros2 service list`, `ros2 topic list` 는 **전부 DDS 탐색 결과**라 지연·누락이 난다. 실제로 두 번 당했다: ① `ros2 node list` 가 기동 직후 빈 목록을 반환해 "안 떠있다" 오판 → tm_driver **중복 기동** ② `ros2 action info` 가 `Action servers: 0` 을 반환해 "궤적 실행 경로가 통째로 없다"고 **거짓 보고**(실제로는 `/tm_driver_node` 가 처음부터 제공 중, 재조회하니 1개. 기록: `docs/claude-mistake/2026-07-14-001.md`).
   - **부재 판정 확정 조건 (둘 중 하나 필수)**: ① **2~3회 반복 조회**로 결과가 안정적인지 확인 ② 소스 코드·로그·포트(`ss`)·`pgrep` 등 **탐색에 의존하지 않는 경로**로 교차 확인. 통과 전에는 "없다"를 보고하지 않는다.
   - 생존 판정은 포트(`ss`)나 `pgrep` 을 쓸 것.
4. **`tm_camera_bridge` 로그는 블록 버퍼링** — `print()` 라 파일 로그가 뭉텅이로 늦게 flush 된다. 프레임 수를 로그로 세면 "0→0→37" 처럼 밀려서 **오진한다**. 토픽을 직접 구독해 셀 것.
5. **`PYTHONNOUSERSITE=1` 필수** — user-site numpy 2.x 가 scipy/cv_bridge 를 깨뜨린다. 브리지·비전 노드 실행 시 항상 붙일 것.
6. **`set -u` + ROS `setup.bash`** — setup 스크립트가 미정의 변수를 참조해 셸이 즉시 종료(무출력)된다. 쉘 스크립트에 `set -u` 쓰지 말 것.
7. **워크스페이스 복사/이동 시 `install/` 재빌드 필수** — `--symlink-install` 링크가 옛 경로를 가리킨다(이번 이관에서 444개 발견).
8. **클린 빌드는 메시지 패키지를 먼저 빌드해야 한다** — `custom_package/package.xml` 에 **`tm_msgs` 의존 선언이 누락**돼 있는데 `CMakeLists.txt` 는 `find_package(tm_msgs REQUIRED)` 를 한다(`ament_index_cpp`·`tf2_geometry_msgs` 도 미선언). 그래서 colcon 이 빌드 순서를 몰라 병렬로 돌리다 **`tm_msgs` 가 아직 없는 상태에서 `custom_package` 가 configure 실패** → 나머지 패키지도 연쇄 중단(Aborted). 기존 워크스페이스는 이미 빌드된 `install/` 이 있어 안 드러났던 **잠재 버그**.
   - **우회(파일 무수정)**: `colcon build --packages-select tm_msgs techman_robot_msgs` 를 먼저 돌린 뒤 전체 빌드.
   - **정식 수정(미적용)**: `custom_package/package.xml` 에 `tm_msgs`·`ament_index_cpp`·`tf2_geometry_msgs` 의존 추가. 벤더 패키지라 사용자 승인 후 진행할 것.

---

## 5. 안전 규칙 (로봇)

- **2026-07-08 사고**: 검증용 curl 이 라이브 로봇에 `Rx≈-100°/속도100%` 를 보내 안전정지(`0x03 0x35`) + J5 모터 보호 latch 발생. **전원 5분 완전 차단 후 콜드부팅으로 복구**(하드웨어 손상 없음). 기록: `docs/claude-mistake/2026-07-08-001.md`.
- 이후 도입한 가드: **모션 게이트(기본 OFF)** · 속도 clamp(jog ≤30%, 회전 ≤10°, 시퀀스 ≤30%) · 화이트리스트.
- **실모션 검증은 사용자 입회 + 저속 + 소량으로만.** 라이브 로봇에 임의로 모션 curl 금지.
- **무이동인 것**: `Vision_DoJob()`(현재 위치 촬영) — 구조적으로 로봇을 못 움직임(TMscript v2.18 §13.26 p.351-352 + 실측 TCP 불변). 그래서 라이브 촬영 루프는 게이트 없이 돈다.
- **이동하는 것**: `Vision_DoJob_PTP()`(초기위치로 이동 후 촬영), jog, 시퀀스 → **전부 모션 게이트 필수**.

---

## 6. 프로젝트 규칙 (CLAUDE.md 요약)

- 지시한 것만 수행. **코딩 전 구조 제시 → 승인 → 실행.**
- 증거 없이 "동일/완료" 선언 금지.
- 트리거별 SOP 가 있다(응답 전 의무 선행 점검): 코드작성(`coding/`), 이슈수정(`issue_fix/`), 코드리뷰(`code_review/`), SW구조(`sw_structure/`), 외부매뉴얼(`external_reference/`), 실수기록(`mistake/`), git(`git_workflow/`), 부채(`debt/`) — 전부 `docs/claude_guideline/` 아래.
- 영어 약자는 첫 등장 시 `약어(영어 단어)` 병기.
