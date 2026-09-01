# src/tm_web_bridge — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/tm_web_bridge/launch/web_bridge.launch.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `generate_launch_description` | - | `LaunchDescription` | env 설정 + rosbridge include + tm_web_bridge Node | src/tm_web_bridge/launch/web_bridge.launch.py:11 |

## src/tm_web_bridge/scripts/jpeg_republish_node.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `JpegRepublish.__init__` | - | None | pub/sub 생성 | src/tm_web_bridge/scripts/jpeg_republish_node.py:18 |
| 2 | `JpegRepublish.on_image` | `msg: Image` | None | bgr8 변환→JPEG 인코딩→재발행 | jpeg_republish_node.py:28 |
| 3 | `main` | - | None | init→spin→정리 | jpeg_republish_node.py:51 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `JPEG_QUALITY` (상수) | __init__, on_image | JPEG 품질 80 | jpeg_republish_node.py:12 |

## src/tm_web_bridge/scripts/safety_area_view.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `pick_korean_font` | - | `str\|None` | 설치 폰트 중 한글 폰트 선택 | src/tm_web_bridge/scripts/safety_area_view.py:62 |
| 2 | `package_config_path` | - | `str` | 패키지 config/safety_area.yaml 경로 | safety_area_view.py:72 |
| 3 | `load_area` | `path, demo=False` | `(dict, str, bool)` | yaml 로드+기본값 병합 (데모/부재 fallback) | safety_area_view.py:78 |
| 4 | `corners` | `lo, hi` | `ndarray(8,3)` | 박스 8꼭짓점 | safety_area_view.py:106 |
| 5 | `faces` | `lo, hi` | `list[quad]` | 박스 6면 | safety_area_view.py:113 |
| 6 | `add_box` | `ax, lo, hi, color, alpha, lw, linestyle, fill` | None | Poly3DCollection 추가 | safety_area_view.py:119 |
| 7 | `point_in_area` | `area, p` | `bool` | 허용 박스 합집합 내 포함 판정 | safety_area_view.py:127 |
| 8 | `segment_intersects_box` | `p0, p1, lo, hi` | `bool` | slab 법 선분-AABB 교차 | safety_area_view.py:141 |
| 9 | `tool_inflation_mm` | `area` | `float` | 공구 반경 확장값 | safety_area_view.py:161 |
| 10 | `inflation_mm` | `area` | `float` | margin+공구 반경 합 | safety_area_view.py:172 |
| 11 | `check_segment` | `area, p0, p1, step_mm=10.0` | `(bool, str)` | 선분 샘플링 이탈검사 + 금지구역 교차검사 | safety_area_view.py:177 |
| 12 | `parse_path` | `text: str` | `(list, list)` | "x,y,z:x,y,z" 파싱 | safety_area_view.py:202 |
| 13 | `scene_bounds` | `area, paths` | `(lo, hi)` | 장면 경계+패딩 | safety_area_view.py:212 |
| 14 | `draw` | `area, paths, title, out, show, elev, azim` | None | 3D 도식·판정 출력·저장 | safety_area_view.py:227 |
| 15 | `main` | - | None | argparse → load → draw | safety_area_view.py:309 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `DEFAULT_TOOL` (상수) | load_area | 공구 기본값 | safety_area_view.py:17 |
| 2 | `DEFAULT_AREA` (상수) | load_area | 구역 기본값(비활성) | safety_area_view.py:21 |
| 3 | `DEMO_AREA` (상수) | load_area | 내장 데모 구성 | safety_area_view.py:30 |
| 4 | `BASE_POINT_MM` (상수) | scene_bounds, draw | 로봇 베이스 원점 | safety_area_view.py:45 |
| 5-9 | `C_KEEPIN/C_KEEPOUT/C_MARGIN/C_OK/C_BAD` (상수) | draw, add_box | 색상 | safety_area_view.py:48-52 |
| 10 | `FACE_ORDER` (상수) | faces | 면 인덱스 | safety_area_view.py:55 |

## src/tm_web_bridge/tm_web_bridge/api.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `_recipe_filename` | `name: str` | `str` | 파일명 살균 + .yaml 확장자 보정 | src/tm_web_bridge/tm_web_bridge/api.py:59 |
| 2 | `sanitize_jog` | `axis, direction, step, velocity` | `(bool,str,str,int,float,float)` | 축·방향 검증, step/velocity clamp | api.py:67 |
| 3 | `find_webgui_dist` | - | `str\|None` | 환경변수→워크스페이스→share 순 dist 탐색 | api.py:88 |
| 4 | `mount_webgui` | `app` | `app` | dist 존재 시 StaticFiles 마운트 | api.py:118 |
| 5 | `create_app` | `node: BridgeNode` | `FastAPI` | 앱 생성·CORS·전 라우트 등록 | api.py:131 |
| 5a | `create_app.robot_status` | - | dict | GET /robot/status | api.py:142-145 |
| 5b | `create_app.tasks_schema` | - | dict | GET /tasks/schema (JOB_TYPES) | api.py:147-150 |
| 5c | `create_app.list_recipes` | - | list | GET /recipes | api.py:154-162 |
| 5d | `create_app.get_recipe` | `filename: str` | dict | GET /recipes/{filename} (basename 살균) | api.py:164-171 |
| 5e | `create_app.save_recipe` | `req: RecipeSaveRequest` | dict | POST /recipes | api.py:173-187 |
| 5f | `create_app.motion_enable_status` | - | dict | GET /motion/enable | api.py:189-192 |
| 5g | `create_app.set_motion_enable` | `req: MotionEnableRequest` | dict | POST /motion/enable | api.py:194-197 |
| 5h | `create_app.jog` | `req: JogRequest` | dict | POST /jog → 살균 후 node.jog | api.py:199-208 |
| 5i | `create_app.sequence_run` | `req: SequenceRunRequest` | dict | POST /sequence/run | api.py:211-215 |
| 5j | `create_app.sequence_stop` | - | dict | POST /sequence/stop | api.py:217-221 |
| 5k | `create_app.sequence_status` | - | dict | GET /sequence/status | api.py:223-226 |
| 5l | `create_app.vision_capture` | `req: VisionCaptureRequest` | dict | POST /vision/capture (게이트 있음) | api.py:229-233 |
| 5m | `create_app.vision_snap` | `req: VisionCaptureRequest` | dict | POST /vision/snap (게이트 없음) | api.py:236-240 |
| 5n | `create_app.live_join` | `req: LiveViewerRequest` | dict | POST /vision/live/join | api.py:243-247 |
| 5o | `create_app.live_leave` | `req: LiveViewerRequest` | dict | POST /vision/live/leave | api.py:249-253 |
| 5p | `create_app.live_status` | - | dict | GET /vision/live/status | api.py:255-258 |
| 5q | `create_app.io_set` | `req: IoSetRequest` | dict | POST /io/set | api.py:261-265 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `LINEAR_AXES` (상수) | sanitize_jog | 선형축 집합 | api.py:14 |
| 2 | `ROTATION_AXES` (상수) | sanitize_jog | 회전축 집합 | api.py:15 |
| 3 | `VALID_AXES` (상수) | sanitize_jog | 유효축 합집합 | api.py:16 |
| 4 | `MAX_STEP_MM` (상수) | sanitize_jog | 선형 step 상한 50.0 | api.py:18 |
| 5 | `MAX_STEP_DEG` (상수) | sanitize_jog | 회전 step 상한 10.0 | api.py:19 |
| 6 | `MAX_VELOCITY_PERCENT` (상수) | sanitize_jog | 조그 속도 상한 30.0 | api.py:20 |
| 7 | `MIN_VELOCITY_PERCENT` (상수) | sanitize_jog | 조그 속도 하한 1.0 | api.py:21 |
| 8 | `WEBGUI_ENV` (상수) | find_webgui_dist, mount_webgui | dist 경로 환경변수명 | api.py:85 |

## src/tm_web_bridge/tm_web_bridge/bridge_executor.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `BridgeJobExecutor._exec_move_linear` | `job` (params: offset X/Y/Z, velocity) | `bool` | Move_Line 스크립트 전송(10s 대기) 후 이동 시작(2s)·완료(30s) 폴링 | src/tm_web_bridge/tm_web_bridge/bridge_executor.py:11 |
| 1a | `_exec_move_linear.λ1` | `_f` | None | future 완료 → done.set() | bridge_executor.py:50 |

## src/tm_web_bridge/tm_web_bridge/bridge_node.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `BridgeNode.__init__` | - | None | 구독 3+1개·서비스 클라이언트 3개·서비스 객체·락·라이브 상태 초기화 | src/tm_web_bridge/tm_web_bridge/bridge_node.py:52 |
| 2 | `BridgeNode._on_joint_state` | `msg: JointState` | None | TM 조인트 판별 후 motion_service 조인트 갱신 | bridge_node.py:100 |
| 3 | `BridgeNode._on_tool_pose` | `msg: PoseStamped` | None | TCP 포즈(쿼터니언) motion_service 갱신 | bridge_node.py:104 |
| 4 | `BridgeNode._on_feedback_state` | `msg: FeedbackState` | None | tcp_speed/joint_vel 갱신 + sct/svr 연결 플래그 갱신 | bridge_node.py:111 |
| 5 | `BridgeNode._call_set_positions` | `motion_type:int, positions:list, velocity, acc_time, blend_percentage=0, fine_goal=False` | `(bool, str)` | set_positions 비동기 호출 + Event 대기(10s) + 완료 판정 폴링(30s) | bridge_node.py:120 |
| 6 | `BridgeNode.set_motion_enabled` | `enabled: bool` | `bool` | 모션 게이트 토글 | bridge_node.py:169 |
| 7 | `BridgeNode.jog` | `axis, direction, step_mm, velocity_percent` | `(bool, str)` | 게이트·조그락 확인 후 teaching_service.jog_tcp 위임 | bridge_node.py:175 |
| 8 | `BridgeNode.current_tcp_pose` (property) | - | `list\|None` | motion_service 현재 TCP 반환 | bridge_node.py:199 |
| 9 | `BridgeNode._on_seq_log` | `message` | None | 시퀀스 로그 append (200개 유지) | bridge_node.py:205 |
| 10 | `BridgeNode.run_sequence` | `jobs: list[dict]` | `(bool, str)` | 게이트·sct 연결·화이트리스트·속도 clamp 검사 후 시퀀스 스레드 기동 | bridge_node.py:210 |
| 11 | `BridgeNode.stop_sequence` | - | `(bool, str)` | 정지 플래그 + job_executor.stop | bridge_node.py:265 |
| 12 | `BridgeNode.sequence_status` | - | `dict` | 실행 상태·인덱스·로그 40줄 반환 | bridge_node.py:271 |
| 13 | `BridgeNode.set_digital_output` | `module:int, pin:int, state:bool` | `(bool, str)` | 게이트·범위 검증 후 set_io 호출(5s) | bridge_node.py:284 |
| 14 | `BridgeNode._trigger_capture_command` | - | `(bool, str)` | GV 변수 기록 + ScriptExit 로 캡처 트리거 | bridge_node.py:318 |
| 15 | `BridgeNode.capture_vision` | `job_name=None` | `(bool, str)` | 게이트 확인 후 #14 위임 | bridge_node.py:334 |
| 16 | `BridgeNode.capture_still` | `job_name=None` | `(bool, str)` | 게이트 없이 #14 위임 (라이브용) | bridge_node.py:340 |
| 17 | `BridgeNode._on_frame` | `_msg: CompressedImage` | None | 프레임 도착 Event set | bridge_node.py:345 |
| 18 | `BridgeNode._prune_live_viewers` | - | None | TTL(5s) 초과 뷰어 제거 (락 보유 전제) | bridge_node.py:349 |
| 19 | `BridgeNode.live_join` | `viewer_id` | `(int, bool)` | 뷰어 등록, 라이브 루프 스레드 기동 | bridge_node.py:356 |
| 20 | `BridgeNode.live_leave` | `viewer_id` | `(int, bool)` | 뷰어 해제 | bridge_node.py:376 |
| 21 | `BridgeNode.live_status` | - | `dict` | 뷰어 수·라이브 여부 | bridge_node.py:384 |
| 22 | `BridgeNode._live_loop` | - | None | 뷰어 있는 동안 캡처→프레임 대기(3s) 반복, 조그 중 양보(0.35s) | bridge_node.py:392 |
| 23 | `BridgeNode.get_status` | - | `dict` | 연결·TCP·조인트·이동중·게이트 상태 반환 | bridge_node.py:426 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `SEQUENCE_WHITELIST` (상수) | run_sequence | 웹 시퀀스 허용 잡 타입 10종 | bridge_node.py:28 |
| 2 | `MAX_SEQ_VELOCITY` (상수) | run_sequence | 시퀀스 속도 상한 30.0 | bridge_node.py:42 |
| 3 | `LIVE_VIEWER_TTL` (상수) | _prune_live_viewers | 뷰어 만료 5.0s | bridge_node.py:44 |
| 4 | `LIVE_FRAME_TIMEOUT` (상수) | _live_loop | 프레임 대기 3.0s | bridge_node.py:45 |
| 5 | `LIVE_JOG_YIELD` (상수) | _live_loop | 조그 양보 0.35s | bridge_node.py:46 |

## src/tm_web_bridge/tm_web_bridge/server.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `main` | `args=None` | None | rclpy init, BridgeNode+executor spin 스레드 기동, uvicorn 서버 구동, 종료 정리 | src/tm_web_bridge/tm_web_bridge/server.py:12 |

## src/tm_web_bridge/tm_web_bridge/wizard_api.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `_Runner.__init__` | - | None | 락·스레드·상태 필드·sessions 초기화 | src/tm_web_bridge/tm_web_bridge/wizard_api.py:48 |
| 2 | `_Runner.blackboard` | `session: str` | dict | 세션 blackboard 반환(setdefault) | wizard_api.py:62 |
| 3 | `_Runner.reset` | `session: str` | None | 세션 blackboard 초기화 | wizard_api.py:67 |
| 4 | `_Runner.log` | `message: str` | None | 로그 append (400줄 유지) | wizard_api.py:72 |
| 5 | `_Runner.status` | - | dict | 실행 상태 스냅샷 (락 보호) | wizard_api.py:78 |
| 6 | `_Runner.start` | `node, name:str, params:dict, session:str` | `(bool,str)` | busy 검사 후 매크로 워커 스레드 기동 | wizard_api.py:94 |
| 6a | `start.bridge_log` | `message` | None | 로그 이중 전달(자체+기존 on_log) | wizard_api.py:120 |
| 6b | `start.worker` | - | None | run_macro 실행, 결과·on_log 복원 | wizard_api.py:129 |
| 7 | `_Runner.stop` | `node` | `(bool,str)` | job_executor.stop 위임 | wizard_api.py:157 |
| 8 | `register` | `app, node` | `app` | 8개 라우트 등록 | wizard_api.py:172 |
| 8a | `register.list_macros` | - | list | GET /macros (스펙+web_allowed) | wizard_api.py:175-195 |
| 8b | `register.run_macro_endpoint` | `name, req: MacroRunRequest` | dict | POST /macros/{name}/run (화이트리스트+게이트) | wizard_api.py:197-208 |
| 8c | `register.macro_status` | - | dict | GET /macros/status | wizard_api.py:210-213 |
| 8d | `register.macro_stop` | - | dict | POST /macros/stop | wizard_api.py:215-219 |
| 8e | `register.wizard_blackboard` | `session='default'` | dict | GET /wizard/blackboard (요약) | wizard_api.py:221-235 |
| 8f | `register.wizard_reset` | `req: SessionRequest` | dict | POST /wizard/reset | wizard_api.py:237-241 |
| 8g | `register.gripper_state` | - | dict | GET /gripper/state (백엔드 survey) | wizard_api.py:243-263 |
| 8h | `register.robot_profile_endpoint` | - | dict | GET /robot/profile (활성 프로필) | wizard_api.py:265-284 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `MACRO_WHITELIST` (상수) | run_macro_endpoint, list_macros | 웹 허용 매크로 8종 | wizard_api.py:14 |
| 2 | `MOTION_MACROS` (상수) | run_macro_endpoint, list_macros | 모션 게이트 대상 4종 | wizard_api.py:26 |
| 3 | `MAX_LOG_LINES` (상수) | log | 로그 상한 400 | wizard_api.py:33 |
| 4 | `RUNNER` (가변) | register 전 라우트 | 프로세스 전역 매크로 실행기 싱글턴 | wizard_api.py:169 |
