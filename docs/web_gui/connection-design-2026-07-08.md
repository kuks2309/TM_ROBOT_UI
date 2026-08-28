# 웹 GUI(TRobotics_Client) ↔ TM Robot 연결 아키텍처 설계

- 작성일: 2026-07-08 (KST)
- 대상 코드 버전: workspace `3663f7dc` (main)
- 상태: **설계(Design) — 구현 보류** (사용자 결정: "설계만")
- 관련: [[trobotics-client-webgui]], docs/code_review/TM_Task_Manager_unimplemented/2026-07-08.md

## 1. 배경 / 문제

`http://localhost:3000` 웹 GUI(`/home/amap/Desktop/TRobotics_Client`, Vite+React19)는 로봇에 연결되지 않는다. 원인은 IP 오입력이 아니라 **연결 로직 부재**다:

- `연결` 버튼 = `console.log("시스템 연결 시도...")` (MainManager.tsx:32) — 실제 통신 0.
- src 전체에 `fetch/WebSocket/axios/roslib` **0건**.
- IP 필드(`TaskEditor.tsx:422` `169.254.183.219`)·"Status: Disconnected"는 하드코딩 표시용.

## 2. 핵심 제약 (왜 IP만으로 안 되나)

브라우저 JS 는 **raw TCP 소켓을 열 수 없다.** TM Robot 은 5890(Listen 명령)/5891(Ethernet Slave 상태) raw TCP + ROS2(DDS)로만 접근된다. 따라서 웹 GUI 는 로봇 IP 를 직접 찍어도 통신 불가하며, 반드시 **브리지(HTTP/WebSocket ↔ ROS2/TCP)** 가 있어야 한다.

기존 PyQt `TM_Task_Manager` 는 브라우저가 아니라 native `tm_driver` ROS2 노드를 거치므로 동작한다 — 웹은 이 계층을 쓸 수 없다.

## 2.1 브리지의 역할 (통역기이자 실제 연결 주체)

브리지의 본질은 **IP 주입이 아니라 "프로토콜 통역"** 이다. 브라우저가 할 수 있는 통신(HTTP/WebSocket)과 로봇/ROS2 가 알아듣는 통신(DDS / raw TCP)이 서로 달라 **직접 대화가 불가능**하므로, 양쪽 말을 다 하는 통역사가 필요하다. 이 통역사가 브리지이며 로봇과 같은 네트워크에 있는 이 PC(Personal Computer)에서 돈다.

```
[브라우저]  ──HTTP/WebSocket──▶  [브리지 서버(이 PC)]  ──DDS / raw TCP──▶  [ROS2 / 로봇]
  통역 필요        (할 줄 앎)        ↑ 통역사              (할 줄 앎)
```

브리지가 하는 일 3가지:

1. **프로토콜 번역 (핵심)** — 브라우저의 WebSocket 메시지 → ROS2 토픽/서비스 호출로 변환, 반대로 ROS2 데이터 → 브라우저용 JSON 으로 변환해 반환.
2. **로봇 연결을 실제로 보유** — 로봇에 실제 접속하는 주체는 브라우저가 아니라 브리지 서버. → **로봇 IP 도 브리지 서버가 안다**(IP 주입은 "브리지가 연결의 주체"라는 사실의 *결과*이지 목적이 아님).
3. **데이터 가공·중계** — 카메라 영상 인코딩, 스트림 조절, 인증·접근제어.

흐름 예시:

```
"연결" 버튼(현재 console.log 만):
  브라우저 → ws → 브리지: "상태 구독 시작"
  브리지: (이미 로봇 IP 로 tm_driver 접속) joint_states·tool_pose 구독 → JSON push
  브라우저: "Connected" 표시 (하드코딩 "Disconnected" 대체)

Job 실행:
  브라우저 → HTTP POST /jobs/run (레시피명)
  브리지(FastAPI): 기존 job_executor 호출 → set_positions/send_script 로 로봇 명령 → 결과 응답
```

**IP 위치의 의미**: 브라우저는 로봇에 직접 붙지 않으므로 IP 를 몰라도 된다(오히려 몰라야 깔끔). 그래서 `TaskEditor.tsx:422` 의 IP 필드가 표시용일 뿐 실제 연결에 안 쓰이는 게 정상이다. 실제로 붙는 브리지 서버가 IP 를 단일 소스(`tm_driver` launch 인자 / 브리지 config)로 관리하면 stale IP 혼란도 준다.

## 3. 옵션 비교

| 옵션 | 구성 | 장점 | 단점 |
| --- | --- | --- | --- |
| **A. rosbridge only** | `rosbridge_server`(:9090) + roslibjs | 백엔드 최소, 표준, 실시간 토픽/서비스 직접 | job_executor/recipe(파이썬 로직) 재사용 불가 — 토픽·서비스 수준만 |
| **B. Python 백엔드 only** | FastAPI 가 기존 `services/`·`job_executor` 래핑, React 는 REST/WS 호출 | TM_Task_Manager 로직 재사용·기능 동등성 | 구현량 큼, 실시간 스트림(영상/조인트) 별도 처리 필요 |
| **C. 하이브리드 (권장)** | 실시간=rosbridge, Job/레시피=얇은 FastAPI | 각 계층 강점 활용, 점진 확장 | 컴포넌트 2개 운용 |

## 4. 권장 아키텍처 (C. 하이브리드)

```
[Browser :3000 React]
   │   ├── roslibjs ──ws:9090──> [rosbridge_server] ──> ROS2 토픽/서비스
   │   │        · joint_states, tool_pose, aruco/pose, techman_image(구독)
   │   │        · set_io, set_positions, send_script(호출)
   │   └── fetch/WS ──http:PORT──> [FastAPI 브리지]
   │            · POST /jobs/run      → JobExecutor 재사용
   │            · GET  /recipes       → RecipeManager 재사용
   │            · GET  /robot/status  → RobotConnection 재사용
   └── 상태표시는 rosbridge 연결 상태 + FastAPI health 로 산출(하드코딩 제거)
```

- **로봇 IP 는 브라우저가 아니라 서버측(tm_driver launch / FastAPI config)에서 주입** — 웹 UI 의 IP 입력은 서버 설정 API 로 전달하는 용도로만.
- 실 로봇 IP 는 [[tm-robot-connection]] 기준(`169.254.122.16`, config 기본값 `169.254.183.219` 는 stale). 서버측 단일 소스로 관리.

## 5. 구현 시 필요한 작업 (착수 승인 시)

1. `rosbridge_suite` 설치 + launch 추가(QoS: sensor=best-effort, 명령=reliable — CLAUDE.md §5 준수).
2. React 에 `roslib` 의존성 추가 + 연결 상태 store(Redux) — `연결` 버튼을 실제 ROS2 연결로 교체.
3. (하이브리드) FastAPI 브리지 신규 패키지 — 기존 `services/` import 재사용, 신뢰경계 입력검증(coding.md §3).
4. 빈 탭 7개(0 byte)·"준비 중" 더미를 실제 컴포넌트로 — TM_Task_Manager 탭과 기능 매핑.

## 6. 리스크 / 미결

- **공개 API 신설**(FastAPI 엔드포인트) → coding.md §3 ADR + 신뢰경계 입력검증 필요.
- **비상정지의 웹 경유 신뢰성**: 안전 명령을 브라우저→ws→ROS2 경로에 의존하는 것의 위험. 물리 E-Stop 대체 불가 — 문서화 필요.
- rosbridge 노출 시 네트워크 접근제어(인증) — 현재 React 로그인은 우회(`isAuthenticated=true`) 상태.

## 7. 결정 (2026-07-08)

- 아키텍처: **C 하이브리드 확정** (사용자 승인).
- 브리지 위치: **이 워크스페이스 `src/`** (증분 2에서 `src/tm_web_bridge` 신규 패키지).

## 8. 구현 진행 상황

### 증분 1 — rosbridge 실시간 연결 (완료, 2026-07-08)

**변경/신규 파일** (프론트엔드 `~/Desktop/TRobotics_Client` — 별도 리포):
| 파일 | 유형 | 내용 |
| --- | --- | --- |
| `src/store/connectionSlice.ts` | 신규 | 연결 상태(status/host/heartbeat) Redux slice |
| `src/store/index.ts` | 신규 | Redux store |
| `src/ros/rosClient.ts` | 신규 | roslib 래퍼 — `ws://<host>:9090` 연결, `/joint_states` 구독→heartbeat |
| `src/main.tsx` | 변경 | `<Provider store>` 추가 |
| `src/main/pages/MainManager.tsx` | 변경 | `연결` 버튼=실제 연결/해제, 상태 Chip(하드코딩 "Disconnected" 대체) |

**의존성 추가**: `roslib` 2.1.0(npm, Apache-2.0/BSD), `ros-humble-rosbridge-suite` 2.0.7(apt, BSD).

**설계 포인트**: 연결 host 미지정 시 `window.location.hostname` 사용 → 로컬(localhost)·원격(PC IP) 접속 자동 대응. 로봇 IP는 브리지(rosbridge/`tm_driver`)측 소관, 브라우저는 rosbridge host만 앎.

**검증 (실측)**:
- TypeScript: `npx tsc -b` exit 0.
- rosbridge: `ros2 launch rosbridge_server rosbridge_websocket_launch.xml` → 9090 리스닝 확인.
- roslib E2E: 동일 roslib 경로로 `CONNECTION_OK` + `/joint_states` `HEARTBEAT_OK` 수신(name.length=6 → TM 6축).
- vite: `:3000`에서 신규 모듈 전부 HTTP 200 변환(roslib 사전번들 해석).
- (미자동화) 브라우저 버튼 클릭은 수동 확인 필요 — 연결 로직은 위 roslib 경로와 동일.

**기동 방법**:
```
# 1) rosbridge (로봇/tm_driver 는 별도 기동)
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
# 2) 웹 GUI
cd ~/Desktop/TRobotics_Client && npm run dev   # http://localhost:3000
# 3) 브라우저에서 '연결' 클릭 → 상태 Chip 이 '연결됨'으로 바뀌고 관절 수 표시
```

### 증분 2 — FastAPI 브리지 (예정)
`src/tm_web_bridge` 신규 패키지: `GET /recipes`·`GET /robot/status`(읽기 먼저) → `POST /jobs/run`. 공개 API 신설이므로 §6 ADR + 신뢰경계 입력검증 선행.

### 증분 2 — TCP jog (구현·검증 완료, 2026-07-08)

신규 패키지 `src/tm_web_bridge`(rclpy + FastAPI): `GET /robot/status`, `POST /jog`(TeachingService.jog_tcp 재사용, axis 화이트리스트·direction·clamp 검증). React: `src/api/bridgeClient.ts` + TaskEditor 조그 버튼 12개 배선.
- 실행파일 `lib/` 설치 위해 `setup.cfg` 필요. numpy 2.2.6(user-site)이 scipy 를 깨므로 launch 에서 `PYTHONNOUSERSITE=1` 설정 + fastapi/uvicorn 은 **시스템 site** 설치.
- 검증: colcon build OK, `/robot/status`·`/jog`(정상/거부/clamp) 응답 확인, React tsc.
- **라이브 저속 실모션 검증 완료(2026-07-08 18:36, 사용자 입회)**: 로봇 복구 후, 사용자가 GUI에서 속도 5%·거리 5mm·모션활성 체크 후 `Z+` 1회 클릭 → 실제 소량 이동 정상 확인(사용자 "확인 완료"). 검증 후 브리지 정지.

<a id="safety"></a>
### ⚠️ 안전 (2026-07-08 사고 반영)
- **검증은 로봇 미기동(또는 시뮬) 상태에서** 수행한다. 라이브 로봇 상대로 `/jog` 를 curl/자동 검증하면 실제 로봇이 움직인다(2026-07-08 사고: 검증 curl 이 Rx-100°/100% 실회전 유발 → 로봇 경고음 → 사용자 전원 차단, docs/claude-mistake/2026-07-08-001.md).
- 실모션 확인은 사용자 입회 + 저속 + 소량으로만. 모션 전 `/robot/status`·`/tool_pose` 로 라이브 상태 재확인.
- **하드닝 적용·검증 완료(2026-07-08)**: 회전축 clamp ≤ 10°, 직선축 ≤ 50mm, 속도 상한 ≤ 30%, `/jog` motion-enable 게이트(기본 **비활성** — 켜기 전 실모션 차단). React 조그 패널에 "모션 활성" 체크박스(기본 꺼짐, 켜야 버튼 활성). 검증(로봇 미기동): `sanitize_jog` 단위테스트 5/5, 게이트 비활성 시 `/jog` 로봇 접촉 전 차단 확인, 잘못된 axis 거부, 토글 정상.

### 증분 3 — 빈 탭 채우기: 읽기전용 3탭 (완료, 2026-07-08)

로봇 무동작(안전) 우선 원칙으로 **읽기전용 탭 3개**를 rosbridge 구독 기반으로 구현.
| 파일 | 내용 |
| --- | --- |
| `src/store/telemetrySlice.ts` | 신규 — joint/pose/feedback 텔레메트리 스토어 |
| `src/ros/rosClient.ts` | 확장 — `/joint_states`·`/tool_pose`·`/feedback_states` 구독 → 스토어 push |
| `src/main/pages/tabs/Monitor.tsx` | 실행 모니터 — 관절(deg)·TCP 위치 라이브 표시 |
| `src/main/pages/tabs/GlobalValue.tsx` | 글로벌 변수 — feedback_states 상태 필드(로봇에러/실행/estop/IO 등) |
| `src/main/pages/tabs/Setting.tsx` | 설정 — rosbridge/브리지 연결 정보 표시 |
| `tabs/list.ts`, `MainManager.tsx` | GlobalValue·Setting 더미(ReadyContent)→실 컴포넌트 배선 |

- **검증**: React `tsc -b` exit 0, vite `:3000` 신규 모듈 전부 HTTP 200 변환. 라이브 데이터는 사용자가 `연결` 클릭 시 표시(읽기전용, 로봇 무동작).
- **남은 탭(actuation, 미착수)**: IO Control / PS2 Joystick / 정밀도 / Hand-Eye / 좌표계 설정 — jog 수준 안전처리(게이트·clamp·입회) 후 진행.

### 증분 4 — Task 편집 탭 기능화 (완료, 2026-07-09)

TaskEditor 정적 목업 → 실동작. 로봇 무동작(표시·편집·fetch만).
- **백엔드**: `GET /tasks/schema`(=`RecipeManager.JOB_TYPES` 27종 파라미터 스키마, 단일 소스), `GET /robot/status`에 `current_joint_position`(deg) 추가.
- **프론트**: `bridgeClient.ts`(getTaskSchema·getStatus 추가). `TaskEditor.tsx`:
  - Task 그룹 선택 → "← Sequence에 추가" → Task Sequence 리스트에 추가(▲▼ 이동·복사·삭제 배선).
  - Task 파라미터: 선택 시퀀스 항목의 스키마대로 편집 위젯(float/int/choice/bool) 렌더, "현재위치 입력"으로 X/Y/Z/Rx/Ry/Rz 채움.
  - 로봇 현재 위치: 패널 4 Joint(deg)·TCP(mm/deg)를 `/robot/status` 폴링(300ms)으로 실시간 표시.
  - "이 위치로 이동"은 actuation → 비활성(안전, 별도 진행).
- **검증**: React `tsc -b` exit 0, vite 변환 정상, 백엔드 `/tasks/schema`(27종)·`/robot/status`(관절 추가) 응답 확인.

### 증분 5 — 시퀀스 저장/불러오기 + 좌표계 설정 탭 (완료, 2026-07-09)

로봇 무동작(파일 I/O·표시)만. 안전 배치.
- **백엔드**: `GET /recipes`(목록)·`GET /recipes/{filename}`(불러오기)·`POST /recipes`(저장) — 기존 `RecipeManager`(Qt 무관) 재사용, `config/recipes`에 YAML 저장(경로주입 방지 basename). 로봇 무동작.
- **프론트**: `bridgeClient`(listRecipes·loadRecipe·saveRecipe). `TaskEditor` 패널1에 레시피 이름+저장 / 선택+불러오기 UI(불러오면 시퀀스로 로드). `CoordSetup.tsx`(좌표계 설정 탭) — RobotBase 기준 TCP 실시간 표시(읽기전용), MainManager 더미→실 컴포넌트.
- **검증**: `tsc -b` exit 0, vite 변환 정상, 레시피 저장/목록/불러오기 왕복 curl 확인(config/recipes 저장), 테스트 레시피 정리.
- **남은 것(모션, 게이트 필요)**: 시퀀스 **실행**(job_executor), IO Control / PS2 Joystick / 정밀도 / Hand-Eye — 다음 게이트 배치.

### 증분 6 — 시퀀스 실행 v1 (구현·안전검증, 2026-07-09)

기존 `JobExecutor`(Qt 무관 확인)를 브리지에서 **헤드리스 재사용**. 로봇 모션 → 게이트+속도clamp+화이트리스트+정지.
- **접근**: BridgeNode 가 JobExecutor 의 `ros_node` 인터페이스 제공 — `_call_set_positions`(jog와 공유), `current_tcp_pose` 프로퍼티, `motion_service`. `JobExecutor(ros_node=self)` 인스턴스 + `on_log` 콜백.
- **화이트리스트**(2026-07-09 확장): `go_home / move_to_point / move_linear / line_move_to_point / wait`. `move_linear`는 원본이 `rclpy.spin_*` 사용(executor 충돌) → **`BridgeJobExecutor`(JobExecutor 서브클래스)가 `_exec_move_linear` 를 spin-free 로 오버라이드**(send_script call_async+Event, 완료대기 motion_service 폴링, job_executor.py 원본 무수정). `move_to_ar_offset` 은 **AR 스텁**(무동작)이라 제외 → hand-eye 트랙. 그 외 잡 거부.
- **안전**: (1) **모션 게이트**(기본 꺼짐) 통과해야 실행, (2) 각 잡 `velocity` **≤30% clamp**, (3) 화이트리스트 외 거부, (4) `stop()` 즉시 중단, (5) `run()` 은 별도 스레드(동기 블로킹).
- **엔드포인트**: `POST /sequence/run`·`POST /sequence/stop`·`GET /sequence/status`(state/index/total/logs).
- **프론트**: `bridgeClient`(runSequence·stopSequence·getSequenceStatus). TaskEditor 시퀀스 패널에 "▶ 시퀀스 실행"(모션 활성 시만)·"■ 정지" + 진행상태(500ms 폴링).
- **검증(로봇 무동작)**: colcon build OK, JobExecutor 헤드리스 import OK, 게이트 꺼짐→실행 거부(set_positions 이전), 화이트리스트 외(gripper_open) 거부, 빈 시퀀스 거부. **`wait`-only 시퀀스로 실행 엔진 end-to-end 검증**(running→index 진행→completed, 로그 확인, 로봇 무동작). **정지 검증**(긴 wait → stop → 인덱스 0 유지). React tsc/vite OK.
- **stop 상태 정규화**: JobExecutor 는 정지-중단 잡을 error 로 표시 → 브리지 `_seq_stop_flag` 로 `stopped` 정규화(JobExecutor 원본 무수정).
- **실로봇 모션 실행 미검증**: 화이트리스트 **모션 잡**(go_home/move_to_point/line_move) 실제 실행은 **사용자 입회 + 저속** 하에서만(자동 테스트 금지 — 2026-07-08 사고 교훈).
