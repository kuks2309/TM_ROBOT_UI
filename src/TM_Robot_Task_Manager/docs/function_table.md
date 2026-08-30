# src/TM_Robot_Task_Manager — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/TM_Robot_Task_Manager/launch/task_manager.launch.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `check_node_running` | `node_name: str` | `bool` | `ros2 node list` stdout 부분문자열 검사 | src/TM_Robot_Task_Manager/launch/task_manager.launch.py:12 |
| 2 | `launch_setup` | `context` | `list[Node]` | 미실행 노드 판별 후 tm_driver·tm_camera_bridge(vendor PYTHONPATH 주입)·camera_calibration_node·task_manager_node 구성 | src/TM_Robot_Task_Manager/launch/task_manager.launch.py:27 |
| 3 | `_profile_robot_ip` | `fallback: str` | `str` | 프로브 응답 IP → 프로필 값 → fallback 순 결정 | src/TM_Robot_Task_Manager/launch/task_manager.launch.py:121 |
| 4 | `generate_launch_description` | 없음 | `LaunchDescription` | robot_ip 인자 선언 + OpaqueFunction | src/TM_Robot_Task_Manager/launch/task_manager.launch.py:142 |

## src/TM_Robot_Task_Manager/launch/tm_system.launch.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `_profile_robot_ip` | `fallback: str` | `str` | 프로브→프로필→fallback IP 결정 (M13 #3 중복) | src/TM_Robot_Task_Manager/launch/tm_system.launch.py:11 |
| 2 | `generate_launch_description` | 없음 | `LaunchDescription` | robot_ip 인자 + tm_driver + task_manager_node | src/TM_Robot_Task_Manager/launch/tm_system.launch.py:32 |

## src/TM_Robot_Task_Manager/scripts/generate_macro_catalog.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `build_payload` | 없음 | `dict` | MACROS·JOB_TYPES 를 직렬화 payload(macros, jobs_using_macros)로 구성 | src/TM_Robot_Task_Manager/scripts/generate_macro_catalog.py:25 |
| 2 | `_param_rows` | `params: dict` | `list[tuple]` | 매크로 파라미터 스펙을 표 행(키·타입·기본값·제약·설명)으로 변환 | src/TM_Robot_Task_Manager/scripts/generate_macro_catalog.py:51 |
| 3 | `render_markdown` | `payload: dict` | `str` | 카탈로그 markdown 본문 생성 | src/TM_Robot_Task_Manager/scripts/generate_macro_catalog.py:66 |
| 4 | `main` | argv(`--out`, `--check`) | `int`(0/1) | 생성 모드 또는 --check 최신성 검사 후 종료코드 반환 | src/TM_Robot_Task_Manager/scripts/generate_macro_catalog.py:113 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `_PKG_ROOT` (상수) | 모듈 로드, main | 패키지 루트 경로; sys.path 삽입 및 기본 출력 폴더(`_PKG_ROOT.parents[1]/docs/macros`) 산출 | src/TM_Robot_Task_Manager/scripts/generate_macro_catalog.py:12 |

## src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `ZoomableGraphWidget.__init__` | `parent, title:str, compact:bool` | 없음 | 줌 가능한 matplotlib 위젯 초기화 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:44 |
| 2 | `ZoomableGraphWidget.setup_ui` | 없음 | 없음 | Figure/canvas/toolbar 구성, 스크롤·클릭 이벤트 연결 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:52 |
| 3 | `ZoomableGraphWidget._on_scroll` | `event` | 없음 | 마우스 휠 줌 (커서 기준 확대/축소) | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:75 |
| 4 | `ZoomableGraphWidget._on_double_click` | `event` | 없음 | 더블클릭 시 원래 축 범위 복원 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:102 |
| 5 | `ZoomableGraphWidget.save_original_limits` | 없음 | 없음 | 현재 축 범위를 원본으로 저장 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:108 |
| 6 | `ZoomableGraphWidget.clear` | 없음 | 없음 | 축 클리어 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:113 |
| 7 | `ZoomableGraphWidget.set_equal_aspect` | 없음 | 없음 | 등축 비율 설정 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:116 |
| 8 | `ZoomableGraphWidget.draw` | 없음 | 없음 | tight_layout + 렌더 + 원본 범위 저장 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:119 |
| 9 | `HandEyeDataAnalyzer.__init__` | `data: pd.DataFrame` | 없음 | 데이터 보관 후 즉시 `_analyze` | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:129 |
| 10 | `HandEyeDataAnalyzer._analyze` | 없음 | 없음 | 전체·위치별 통계 산출 호출 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:135 |
| 11 | `HandEyeDataAnalyzer._normalize_angle` | `angles: pd.Series` | `pd.Series` | 범위>180° 인 각도열을 +360 시프트로 랩 해제 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:139 |
| 12 | `HandEyeDataAnalyzer._calculate_overall_stats` | 없음 | 없음(`overall_stats` 저장) | Lm 6축 mean/std/3σ/min/max/range 산출 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:148 |
| 13 | `HandEyeDataAnalyzer._calculate_position_stats` | 없음 | 없음(`position_stats` 저장) | Pos 별 TCP 평균·Lm 축별 std/mean 산출 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:171 |
| 14 | `HandEyeDataAnalyzer.get_unique_positions` | 없음 | `int` | 측정 위치 수 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:197 |
| 15 | `HandEyeDataAnalyzer.get_repeat_count` | 없음 | `int` | 위치당 반복 횟수(총/위치수) | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:203 |
| 16 | `HandEyeDataAnalyzer.get_success_rate` | 없음 | `float` | 항상 100.0 반환(고정값) | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:209 |
| 17 | `HandEyeDataAnalyzer.get_z_levels` | 없음 | `List[float]` | TCP_Z 반올림 고유값 목록 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:213 |
| 18 | `MainWindow.__init__` | 없음 | 없음 | 상태 초기화, UI·시그널 연결 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:223 |
| 19 | `MainWindow.setup_ui` | 없음 | 없음 | .ui 로드, 중앙 위젯 구성 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:231 |
| 20 | `MainWindow.setup_graphs` | 없음 | 없음 | 개요4·히트맵·회전3·상관3 위젯 치환 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:249 |
| 21 | `MainWindow._replace_widget` | `widget_name, title, compact` | 없음 | placeholder → ZoomableGraphWidget 교체(grid/box 레이아웃 분기) | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:281 |
| 22 | `MainWindow.setup_connections` | 없음 | 없음 | 버튼·콤보 시그널 연결 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:308 |
| 23 | `MainWindow.open_csv_file` | 없음 | 없음 | 파일 다이얼로그로 CSV 선택 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:318 |
| 24 | `MainWindow.open_recent_file` | 없음 | 없음 | data/ 날짜 폴더에서 최신 handeye_test_*.csv 로드 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:330 |
| 25 | `MainWindow.load_csv` | `file_path: str` | 없음 | CSV 로드·검증·수치 변환 후 전체 갱신 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:344 |
| 26 | `MainWindow._update_z_level_combo` | 없음 | 없음 | Z 레벨 콤보 채움 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:373 |
| 27 | `MainWindow.update_all` | 없음 | 없음 | 요약~raw 테이블 8개 뷰 일괄 갱신 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:383 |
| 28 | `MainWindow.update_summary` | 없음 | 없음 | 총측정/위치/반복/성공률 라벨 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:397 |
| 29 | `MainWindow.update_overview_stats` | 없음 | 없음 | σ 라벨 + 판정(우수/양호/보통/재검토) 색상 표시 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:408 |
| 30 | `MainWindow.update_overview_graphs` | 없음 | 없음 | XY/YZ/ZX 산점도 + 회전 추이 4그래프 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:445 |
| 31 | `MainWindow.update_position_table` | 없음 | 없음 | 위치별 통계 테이블 채움 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:512 |
| 32 | `MainWindow.update_heatmap` | 없음 | 없음 | 선택 축·Z 레벨 필터로 TCP 격자 std 히트맵 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:531 |
| 33 | `MainWindow.update_rotation_graphs` | 없음 | 없음 | Rx/Ry/Rz 추이 + mean±σ 밴드 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:591 |
| 34 | `MainWindow.update_correlation_graphs` | 없음 | 없음 | TCP↔Lm 축별 상관 산점도 + r 값 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:654 |
| 35 | `MainWindow.update_raw_data_table` | 없음 | 없음 | 원시 데이터 15컬럼 테이블 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:708 |
| 36 | `MainWindow.export_report` | 없음 | 없음 | 텍스트 리포트 저장 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:732 |
| 37 | `MainWindow.save_graphs` | 없음 | 없음 | 10개 그래프 PNG 저장 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:783 |
| 38 | `main` | `sys.argv` | 없음(sys.exit) | QApplication 기동, argv[1] 있으면 자동 로드 | src/TM_Robot_Task_Manager/scripts/handeye_analyzer.py:806 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `SCRIPT_DIR` (상수) | 경로 산출 | 스크립트 폴더 | scripts/handeye_analyzer.py:17 |
| 2 | `PACKAGE_DIR` (상수) | UI_DIR/DATA_DIR | 패키지 루트 | scripts/handeye_analyzer.py:18 |
| 3 | `UI_DIR` (상수) | setup_ui | ui/ 폴더 | scripts/handeye_analyzer.py:19 |
| 4 | `DATA_DIR` (상수) | open_csv_file, open_recent_file, export_report | data/ 폴더 | scripts/handeye_analyzer.py:20 |

## src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `rotation_matrix_from_euler` | `rx, ry, rz`(deg) | `np.ndarray(3,3)` | Rz@Ry@Rx 회전행렬 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:53 |
| 2 | `get_landmark_corners` | `x..rz, size=40` | `np.ndarray(4,3)` | 랜드마크 4모서리 월드좌표 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:72 |
| 3 | `GraphWidget.__init__` | `parent, is_3d, compact` | 없음 | 2D/3D matplotlib 위젯 초기화 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:93 |
| 4 | `GraphWidget.setup_ui` | 없음 | 없음 | Figure/캔버스/툴바 + 이벤트 연결 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:102 |
| 5 | `GraphWidget._on_scroll` | `event` | 없음 | 2D 줌 (3D 는 무동작) | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:130 |
| 6 | `GraphWidget._on_double_click` | `event` | 없음 | 더블클릭 시 뷰 복원 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:158 |
| 7 | `GraphWidget.save_original_limits` | 없음 | 없음 | 축 범위(3D 는 z 포함) 저장 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:162 |
| 8 | `GraphWidget.reset_view` | 없음 | 없음 | 저장된 범위로 복원 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:169 |
| 9 | `GraphWidget.clear` | 없음 | 없음 | 축 클리어 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:178 |
| 10 | `GraphWidget.draw` | 없음 | 없음 | tight_layout + 렌더 + 범위 저장 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:181 |
| 11 | `ROS2Thread.__init__` | `node` | 없음 | 데몬 스핀 스레드 준비 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:191 |
| 12 | `ROS2Thread.run` | 없음 | 없음 | stop 이벤트까지 `spin_once(0.1s)` 루프 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:196 |
| 13 | `ROS2Thread.stop` | 없음 | 없음 | stop 이벤트 set | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:200 |
| 14 | `LandmarkVisualizerWindow.__init__` | 없음 | 없음 | 상태·UI·그래프·시그널 초기화 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:212 |
| 15 | `LandmarkVisualizerWindow.setup_ui` | 없음 | 없음 | ui/landmark_visualizer.ui 를 self 에 로드 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:230 |
| 16 | `LandmarkVisualizerWindow.setup_graphs` | 없음 | 없음 | 메인4 + 오버뷰4 위젯 치환 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:238 |
| 17 | `LandmarkVisualizerWindow._replace_widget` | `widget_name, is_3d, compact` | 없음 | placeholder → GraphWidget 교체 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:260 |
| 18 | `LandmarkVisualizerWindow.setup_connections` | 없음 | 없음 | 버튼·테이블·체크박스·메뉴 연결 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:284 |
| 19 | `LandmarkVisualizerWindow.open_csv` | 없음 | 없음 | 파일 다이얼로그 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:301 |
| 20 | `LandmarkVisualizerWindow.open_recent_file` | 없음 | 없음 | data/ 최신 precision_test_*.csv | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:310 |
| 21 | `LandmarkVisualizerWindow.load_csv` | `file_path` | 없음 | 통계행 절단·No. 필터·수치 변환 후 갱신 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:318 |
| 22 | `LandmarkVisualizerWindow.update_table` | 없음 | 없음 | 7컬럼 데이터 테이블 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:348 |
| 23 | `LandmarkVisualizerWindow.on_row_selected` | 없음 | 없음 | 선택 행 라벨 갱신 + 그래프 갱신 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:374 |
| 24 | `LandmarkVisualizerWindow.update_graphs` | 없음 | 없음 | 선택점 기준 3D·2D 3면 갱신 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:403 |
| 25 | `LandmarkVisualizerWindow._update_3d_graph` | `widget_name, selected_point, show_tcp` | 없음 | 3D 랜드마크 폴리곤 + TCP 마커 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:429 |
| 26 | `LandmarkVisualizerWindow._update_2d_graph` | `main/overview widget, 축 키·라벨, plane` | 없음 | 2D 투영 폴리곤 + TCP | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:470 |
| 27 | `LandmarkVisualizerWindow.toggle_ros_connection` | 없음 | 없음 | ROS 연결/해제 토글 (미설치 시 경고) | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:520 |
| 28 | `LandmarkVisualizerWindow.connect_ros` | 없음 | 없음 | rclpy.init, 노드+구독 2개 생성, 스핀 스레드 시작 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:532 |
| 29 | `LandmarkVisualizerWindow.disconnect_ros` | 없음 | 없음 | 스레드 stop/join, destroy_node, 라벨 복귀 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:565 |
| 30 | `LandmarkVisualizerWindow._tcp_callback` | `msg: Float32MultiArray` | 없음 | data≥6 이면 `tcp_updated` 시그널 emit | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:582 |
| 31 | `LandmarkVisualizerWindow._joint_callback` | `msg: JointState` | 없음 | position 있으면 `joint_updated` emit | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:586 |
| 32 | `LandmarkVisualizerWindow._on_tcp_updated` | `tcp: list` | 없음 | (메인스레드) current_tcp 갱신·라벨·그래프 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:590 |
| 33 | `LandmarkVisualizerWindow._on_joint_updated` | `joints: list` | 없음 | (메인스레드) 조인트 라벨 갱신 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:596 |
| 34 | `LandmarkVisualizerWindow.reset_all_views` | 없음 | 없음 | 전 그래프 뷰 복원 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:601 |
| 35 | `LandmarkVisualizerWindow.zoom_fit` | 없음 | 없음 | 그래프 재계산(=update_graphs) | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:606 |
| 36 | `LandmarkVisualizerWindow.export_image` | 없음 | 없음 | overview 제외 그래프 PNG 저장 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:610 |
| 37 | `LandmarkVisualizerWindow.closeEvent` | `event` | 없음 | 종료 시 ROS 해제 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:624 |
| 38 | `main` | `sys.argv` | 없음(sys.exit) | 앱 기동, argv[1] 자동 로드 | src/TM_Robot_Task_Manager/scripts/landmark_visualizer.py:630 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `LANDMARK_SIZE` (상수) | get_landmark_corners, _update_3d_graph | 랜드마크 한 변 40.0mm | scripts/landmark_visualizer.py:16 |
| 2 | `SCRIPT_DIR`/`PACKAGE_DIR`/`UI_DIR`/`DATA_DIR` (상수) | setup_ui, open_csv 등 | 경로 SSOT | scripts/landmark_visualizer.py:18-21 |
| 3 | `ROS2_AVAILABLE` (상수, import 시 1회 결정) | toggle_ros_connection | rclpy 존재 여부 플래그 | scripts/landmark_visualizer.py:47,49 |

## src/TM_Robot_Task_Manager/scripts/precision_analyzer.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `ZoomableGraphWidget.__init__` | `parent, title, compact` | 없음 | 줌 그래프 위젯 초기화 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:37 |
| 2 | `ZoomableGraphWidget.setup_ui` | 없음 | 없음 | Figure/캔버스/툴바 + 이벤트 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:45 |
| 3 | `ZoomableGraphWidget._on_scroll` | `event` | 없음 | 휠 줌 (xdata None 미검사) | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:68 |
| 4 | `ZoomableGraphWidget._on_double_click` | `event` | 없음 | 더블클릭 복원 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:93 |
| 5 | `ZoomableGraphWidget.save_original_limits` | 없음 | 없음 | 축 범위 저장 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:99 |
| 6 | `ZoomableGraphWidget.clear` | 없음 | 없음 | 축 클리어 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:104 |
| 7 | `ZoomableGraphWidget.set_equal_aspect` | 없음 | 없음 | 등축 설정 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:107 |
| 8 | `ZoomableGraphWidget.draw` | 없음 | 없음 | 렌더 + 범위 저장 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:110 |
| 9 | `PrecisionAnalyzer.calculate_statistics` (static) | `data: pd.DataFrame` | `dict` | 6축 mean/std/3σ/min/max/range | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:121 |
| 10 | `MainWindow.__init__` | 없음 | 없음 | 상태·UI·연결 초기화 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:144 |
| 11 | `MainWindow.setup_ui` | 없음 | 없음 | ui/precision_analyzer.ui 로드 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:152 |
| 12 | `MainWindow.setup_graphs` | 없음 | 없음 | 개요4·상세3·회전3 치환 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:170 |
| 13 | `MainWindow._replace_widget` | `widget_name, title, compact` | 없음 | placeholder 교체 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:200 |
| 14 | `MainWindow.setup_connections` | 없음 | 없음 | 버튼 4개 연결 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:224 |
| 15 | `MainWindow.open_csv_file` | 없음 | 없음 | 파일 다이얼로그 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:231 |
| 16 | `MainWindow.open_recent_file` | 없음 | 없음 | data/ 최신 precision_test_*.csv | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:243 |
| 17 | `MainWindow.load_csv` | `file_path` | 없음 | 통계행 절단·수치화 후 갱신 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:252 |
| 18 | `MainWindow.update_all` | 없음 | 없음 | 테이블·통계·그래프 일괄 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:283 |
| 19 | `MainWindow.update_table` | 없음 | 없음 | 14컬럼 데이터 테이블 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:293 |
| 20 | `MainWindow.update_overview_stats` | 없음 | 없음 | μ/σ·3σ 라벨 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:318 |
| 21 | `MainWindow.update_detail_stats` | 없음 | 없음 | 평면별 상세 통계 라벨 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:337 |
| 22 | `MainWindow.update_graphs` | 없음 | 없음 | XY/YZ/ZX 산점 + 회전 3그래프 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:372 |
| 23 | `MainWindow.export_csv` | 없음 | 없음 | 데이터 CSV 재저장 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:476 |
| 24 | `MainWindow.save_graphs` | 없음 | 없음 | 상세 6그래프 PNG 저장 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:493 |
| 25 | `MainWindow.load_from_manager` | `manager`(measurements 보유) | 없음 | 메모리 측정치→DataFrame→갱신 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:510 |
| 26 | `main` | `sys.argv` | 없음(sys.exit) | 앱 기동 | src/TM_Robot_Task_Manager/scripts/precision_analyzer.py:535 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `SCRIPT_DIR`/`PACKAGE_DIR`/`UI_DIR`/`DATA_DIR` (상수) | setup_ui, open_* | 경로 SSOT | scripts/precision_analyzer.py:15-18 |

## src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `ImagePub.__init__` | `nodeName, isTest, path` | 없음 | 퍼블리셔·Condition·큐 생성, 발행 스레드 시작(테스트 모드면 타이머+이미지 로드) | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:34 |
| 2 | `ImagePub.set_image_and_notify_send` | `img`(bytes 또는 ndarray) | 없음 | 큐 적재 + Condition notify | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:49 |
| 3 | `ImagePub.signal_handler` | `signal, frame` | 없음 | SIGINT 시 `close_thread` 호출 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:55 |
| 4 | `ImagePub.publish_test_image` | 없음 | 없음 | (테스트) 1초마다 좌우반전 이미지 큐잉 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:59 |
| 5 | `ImagePub.image_publisher` | `image: ndarray` | 없음 | 채널 수로 인코딩 판정 후 cv2→Image 발행 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:64 |
| 6 | `ImagePub.close_thread` | 없음 | 없음 | leaveThread 세트 + notify 로 스레드 탈출 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:86 |
| 7 | `ImagePub._drain_queue` | `isRequestData: bool` | 없음 | 큐 비우며 (HTTP 바이트면 imdecode 후) 발행, 예외 로깅 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:93 |
| 8 | `ImagePub.pub_data_thread` | `isRequestData: bool` | 없음 | Condition wait(1s) 루프로 큐 소비 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:111 |
| 9 | `ImagePub.fake_result` | `m_method: str` | `dict` | CLS/DET 가짜 감지 결과 생성 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:122 |
| 10 | `ImagePub.get_none` | (Flask request) | Flask JSON | `GET /api` 상태 응답 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:172 |
| 11 | `ImagePub.get` | `m_method` | Flask JSON | `GET /api/<m>` status 응답 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:181 |
| 12 | `ImagePub.post` | `m_method` | Flask JSON | POST 이미지(image/file 필드) 수신→큐잉, fake_result 응답 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:196 |
| 13 | `set_route` | `app: Flask, node: ImagePub` | 없음 | /api·/ai 라우트 + catch-all 등록 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:233 |
| 13a | `set_route.catch_all` | `path=''` | Flask JSON | 미등록 경로 POST 도 post() 로 처리 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:244 |
| 14 | `main` | 없음 | 없음 | rclpy 초기화, 노드·라우트·waitress 스레드 기동, spin | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:257 |
| 14a | `main._serve` | `port: int` | 없음 | waitress serve(0.0.0.0:port), 실패 로깅 | src/TM_Robot_Task_Manager/scripts/tm_camera_bridge.py:283 |

## src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | GlobalVariableScript.__init__ | node: Node | - | send_script/ask_item 클라이언트 + sct_response 구독 생성 | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:13 |
| 2 | GlobalVariableScript._sct_response_callback | msg: SctResponse | None | last_response/response_received 갱신 | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:37 |
| 3 | GlobalVariableScript.read_variable | variable_name, timeout_sec=5.0 | (bool, str) | ask_item(id="gv", wait 0.2s) 호출, '=' 뒤 값 파싱 | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:43 |
| 4 | GlobalVariableScript.write_variable | variable_name, value, timeout_sec=5.0 | (bool, str) | send_script("변수=값") 전송 | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:90 |
| 5 | GlobalVariableScript.send_script | script, timeout_sec=5.0 | (bool, str) | 임의 스크립트 전송 | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:133 |
| 6 | GlobalVariableScript.read_multiple_variables | variable_names: list, timeout_sec=5.0 | (bool, dict) | 순차 read_variable (실패 시 None) | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:172 |
| 7 | GlobalVariableScript.send_script_exit | script_id='test', timeout_sec=5.0 | bool | ScriptExit() 전송 (Listen Node 종료) | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:191 |
| 8 | GlobalVariableScript.read_base_name | timeout_sec=1.0 | Optional[str] | Base_Name 읽어 따옴표 제거 | src/TM_Robot_Task_Manager/tm_task_manager/global_variable_script.py:215 |

## src/TM_Robot_Task_Manager/tm_task_manager/hardware/gripper.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | GripperBackend.job_type | closing: bool | str | 파지/놓기 잡 타입 문자열 선택 | src/TM_Robot_Task_Manager/tm_task_manager/hardware/gripper.py:27 |
| 2 | GripperBackend.job_name | closing: bool | str | 한국어 잡 이름 생성 | src/TM_Robot_Task_Manager/tm_task_manager/hardware/gripper.py:31 |
| 3 | probe | backend, ros_node, timeout_sec=3.0 | str(ABSENT/BUILT/LIVE) | 클라이언트·msg모듈·서버생존 3단계 상태 판정 | src/TM_Robot_Task_Manager/tm_task_manager/hardware/gripper.py:57 |
| 4 | survey | ros_node, timeout_sec=3.0 | List[(backend, state)] | 전 백엔드 probe 일괄 | src/TM_Robot_Task_Manager/tm_task_manager/hardware/gripper.py:86 |
| 5 | detect | ros_node, timeout_sec=3.0 | Optional[GripperBackend] | 첫 LIVE 백엔드 반환 | src/TM_Robot_Task_Manager/tm_task_manager/hardware/gripper.py:91 |
| 6 | resolve | explicit: Optional[str], ros_node, timeout_sec | GripperBackend (raises NoGripperDetected) | 명시 지정 검증 또는 자동 감지 | src/TM_Robot_Task_Manager/tm_task_manager/hardware/gripper.py:99 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | ABSENT/BUILT/LIVE (상수) | probe, detect | 상태 문자열 | gripper.py:10-12 |
| 2 | SMC (상수) | ORDER | SMC 백엔드 정의 (action, gripper_ros.action) | gripper.py:37-41 |
| 3 | SCHUNK (상수) | ORDER, pallet_recipe_generator | SCHUNK 백엔드 정의 (service, tc_msgs.srv) | gripper.py:42-46 |
| 4 | ORDER (상수) | survey, BACKENDS | 감지 우선순위 (SMC→SCHUNK) | gripper.py:48 |
| 5 | BACKENDS (상수) | resolve, PalletRecipeGenerator | id→백엔드 dict | gripper.py:49 |

## src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | JobExecutor.__init__ | ros_node, vision_manager, ai_detection_service | - | 상태·콜백·공유 캐시(detected_* 등) 초기화 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:69 |
| 2 | JobExecutor._log | message: str | None | on_log 콜백으로 로그 전달 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:112 |
| 3 | JobExecutor.last_origin_check_result (property) | - | Any | macro_blackboard 의 origin_check_result 반환 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:116 |
| 4 | JobExecutor._macro_context | - | MacroContext | 매크로 실행 컨텍스트 생성 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:120 |
| 5 | JobExecutor._run_macro_sequence | job: Job, macro_defs: List[Dict] | bool | JOB_TYPES 의 macros 정의를 순차 실행(run_macro) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:123 |
| 6 | JobExecutor._wait_for_listen_node | timeout: float=10.0 | bool | spin_once 폴링으로 is_sct_connected 대기 (미사용 데드 코드) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:147 |
| 7 | JobExecutor._set_state | state: ExecutionState | None | 상태 전이 + on_state_changed 콜백 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:167 |
| 8 | JobExecutor.load_recipe | recipe: Recipe | None | Recipe 적재, 인덱스 0, IDLE | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:172 |
| 9 | JobExecutor.run | - | bool | run_from(0) 위임 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:177 |
| 10 | JobExecutor.run_from | start_index: int=0 | bool | 검증 후 blackboard 초기화, 정방향 실행 시작 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:180 |
| 11 | JobExecutor.run_reverse_from | start_index: int | bool | 역순(_direction=-1) 실행 시작 (blackboard 는 유지) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:204 |
| 12 | JobExecutor.pause | - | None | RUNNING→PAUSED | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:226 |
| 13 | JobExecutor.resume | - | bool | PAUSED→RUNNING 후 다음 잡 실행 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:231 |
| 14 | JobExecutor.stop | - | None | _stop_requested 세트, STOPPED, 인덱스 0 리셋 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:238 |
| 15 | JobExecutor.step | - | bool | 현재 잡 1개만 실행 후 PAUSED | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:244 |
| 16 | JobExecutor._execute_next_job | - | bool | 종료 판정(정/역방향) 후 현재 잡 실행 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:258 |
| 17 | JobExecutor._execute_current_job | - | bool | 잡 실행 + 콜백 + 성공 시 인덱스 증감·재귀 계속, 예외 시 ERROR | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:275 |
| 18 | JobExecutor._create_transform_matrix | pose: Dict[str,float] | np.ndarray(4x4) | XYZ+ZYX euler → 동차변환행렬 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:312 |
| 19 | JobExecutor._extract_pose | T: np.ndarray | Dict[str,float] | 동차변환행렬 → pose dict | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:325 |
| 20 | JobExecutor._transform_relative_to_absolute | rel_pose: Dict | Dict | tm_transform_matrix 로 상대→절대 변환 (행렬 없으면 그대로) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:341 |
| 21 | JobExecutor._convert_to_robot_positions | motion_type, x..rz | List[float] | deg/mm → rad/m (SetPositions 단위) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:350 |
| 22 | JobExecutor._move_to_position | motion_type, x..rz, velocity, decomposed_tcp=False | (bool, str) | PTP_J/PTP_T 이동 — ros_node._call_set_positions 위임, 분해 이동 분기 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:372 |
| 23 | JobExecutor._build_decomposed_tcp_waypoints | current_pose, target: List[float] | (waypoints, label) | decomposed_move_planner 위임 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:402 |
| 24 | JobExecutor._move_to_position_decomposed | x..rz, velocity | (bool, str) | 축 분해 LINE_T 다단 이동 (중단 요청 체크) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:406 |
| 25 | JobExecutor._move_to_position_line | motion_type, x..rz, velocity | (bool, str) | LINE_T 단일 직선 이동 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:445 |
| 26 | JobExecutor._execute_job | job: Job | bool | job.type → _exec_* 50여 분기 디스패치 (macros 우선) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:463 |
| 27 | JobExecutor._exec_go_home | job | bool | RobotBase 좌표계 확인 후 HOME 이동 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:569 |
| 28 | JobExecutor._exec_move_to_point | job | bool | (상대→절대 변환 포함) PTP 포인트 이동 + 위치 검증 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:599 |
| 29 | JobExecutor._verify_move_position | job, target x..rz, tcp_before | None | 이동 후 TCP 실측 오차 로그 (1mm 초과 시 경고성 로그) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:670 |
| 30 | JobExecutor._exec_move_linear | job | bool | send_script 로 Move_Line("TPP",...) 전송 + is_moving 안정화 폴링 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:690 |
| 31 | JobExecutor._exec_line_move_to_point | job | bool | 기준좌표+오프셋 LINE_T 직선 이동 (0 좌표 거부) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:775 |
| 32 | JobExecutor._build_descent_segments | x,y,from_z,to_z,velocity,decel_zone_mm,decel_velocity | List[Tuple] | Z 하강 감속 구간 분할 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:858 |
| 33 | JobExecutor._build_straight_segments | cur/target xyz, velocity, decel | List[Tuple] | 직선 경로 감속 분할 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:872 |
| 34 | JobExecutor._build_pose_keep_segments | tcp_before, target xyz, velocity, decel, straight | List[Tuple] | 자세유지 이동 구간(Z상승→XY / XY→Z하강) 계획 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:895 |
| 35 | JobExecutor._log_orientation_deviation | label, lock_rx/ry/rz | Optional[float] | 이동 종점 자세 편차 측정·로그 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:933 |
| 36 | JobExecutor._exec_pose_keep_move_to_point | job | bool | 자세 고정 다단 LINE_T 이동 (감속 구간 포함) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:956 |
| 37 | JobExecutor._exec_move_to_ar_offset | job | bool | AR 태그 기준 목표 계산 — 로그만, 실이동 없음(스텁) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1042 |
| 38 | JobExecutor._exec_scan_ar_tag | job | bool | vision_manager.get_tag 폴링, 검출 시 g_robot_command=2 + ScriptExit | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1058 |
| 39 | JobExecutor._exec_wait_for_detection | job | bool | 로그만 남기고 즉시 True(스텁) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1099 |
| 40 | JobExecutor._exec_gripper_open | job | bool | g_robot_command=10 쓰기 + delay | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1107 |
| 41 | JobExecutor._exec_gripper_close | job | bool | g_robot_command=9 쓰기 + delay | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1124 |
| 42 | JobExecutor._exec_gripper_home | job | bool | g_robot_command=11 쓰기 + delay | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1141 |
| 43 | JobExecutor._exec_smc_grip | job | bool | _exec_smc_gripper(job,'grip') | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1158 |
| 44 | JobExecutor._exec_smc_release | job | bool | _exec_smc_gripper(job,'release') | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1161 |
| 45 | JobExecutor._exec_smc_home | job | bool | _exec_smc_gripper(job,'home') | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1164 |
| 46 | JobExecutor._exec_smc_gripper | job, profile: str | bool | gripper_ros GripperCommand 액션 send_goal→result 대기 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1167 |
| 47 | JobExecutor._exec_schunk_gripper | job, command: int | bool | tc_msgs GripperCommand 서비스 호출(received 확인) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1221 |
| 48 | JobExecutor._exec_read_distance | job | bool | tc_msgs DistanceCommand 서비스로 거리 2ch 읽기 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1257 |
| 49 | JobExecutor._exec_read_digital_io | job | bool | gv_manager.read_variable(di_name) 로 DI 읽기 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1292 |
| 50 | JobExecutor._exec_check_magazine | job | bool | magazine_state_service 슬롯 재고 판정, 불일치 시 #51 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1310 |
| 51 | JobExecutor._handle_magazine_mismatch | params: Dict | bool | on_mismatch stop/skip/ignore 처리 (skip 은 current_job_index 점프) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1350 |
| 52 | JobExecutor._exec_write_digital_io | job | bool | SetIO 서비스로 Ctrl/End DO 쓰기 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1394 |
| 53 | JobExecutor._exec_read_analog_io | job | bool | io_control_service 우선, 폴백 gv_manager 로 AI 읽기 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1450 |
| 54 | JobExecutor._exec_align_to_ar_tag | job | bool | AR 정렬 목표 계산 — `if self.ros_node: pass` 실이동 없음(스텁) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1478 |
| 55 | JobExecutor._exec_move_to_ar_center | job | bool | AR 중심 목표 계산 — 실이동 없음(스텁) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1514 |
| 56 | JobExecutor._exec_align_tm_landmark | job | bool | 현 위치 고정 + Landmark 자세로 PTP_T (전용 클라이언트 생성, spin 없는 busy-wait) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1540 |
| 56a | JobExecutor._exec_sdc_tcp_base | job | bool | sdc_tcp_base 위치 — positions.yaml 의 sdc_tcp_base(rx/ry/rz 3값) 읽어 현 위치 유지, 자세만 LINE_T (_move_to_position_line 정본 경로) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1612 |
| 56b | JobExecutor._exec_sdc_palette_tcp_align | job | bool | palette 마커 수직 정렬 — 근사식(-rx, ry+o_ry, -rz; offset 은 positions.yaml) 자세의 Z축을 마커 법선에 회전행렬 스냅으로 정확 일치(법선각 0°), 현 위치 유지·자세만 LINE_T | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1657 |
| 56b-0 | JobExecutor._marker_perpendicular_orientation | align_offsets | (rx, ry, rz) deg | 직전 스캔 마커 법선 스냅 목표 자세 계산 — 56b·56c 공용 헬퍼 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1684 |
| 56c | JobExecutor._exec_sdc_palette_inlet_move | job | bool | 팔래트 입구 이동 — 목표 위치 = 최신 스캔 마커위치 + R_marker@(YAML 기준 오프셋 + dx/dy/dz 보정), **목표 자세 = 마커 법선 스냅(내장, sdc_palette_tcp_align offset 재독)** — 위치+자세 동시 LINE_T | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1794 |
| 56d | JobExecutor._exec_sdc_marker_move | job | bool | 마커 frame 상대 이동 — 목표 = 현 위치 + R_marker@(dx,dy,dz 파라미터), X·Y=표면 평행·Z+=법선 방향, 자세 유지·LINE_T (move_linear 대체, debt-025) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1790 |
| 57 | JobExecutor._exec_find_landmark | job | bool | 3x3/5x5 격자 나선 탐색 스캔, 발견 시 저장/정밀 재스캔 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1610 |
| 58 | JobExecutor.scan_landmark_averaged | repeat_count, outlier_method, wait_time, jig_number, analysis_target | (pose, analysis) | 반복 스캔 + outlier 제거 평균 (매크로·settings_tab 도 사용) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1749 |
| 59 | JobExecutor._exec_scan_tm_landmark | job | bool | Landmark 스캔 → tm_transform_matrix 갱신 + 좌표계 자동 저장 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1808 |
| 60 | JobExecutor._exec_scan_tm_landmark_jig | job | bool | Jig(1~4) landmark 스캔 → jig_landmark_results 저장 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1853 |
| 61 | JobExecutor.vision_origin_check | repeat_count=5, outlier_method='iqr', move_to_reference=True, velocity=20.0, wait_after_command=100 | bool | vision_origin_check 매크로 실행 (settings_tab 에서 호출) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1881 |
| 62 | JobExecutor._exec_move_to_jig_landmark | job | bool | [프로토타입] Jig landmark + 오프셋 위치로 자세 유지 이동 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1896 |
| 63 | JobExecutor._exec_calculate_plate_pose | job | bool | Jig1~4 로 평면 pose 계산 + 직사각형 검증 + 저장 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1959 |
| 64 | JobExecutor._confirm_plate_rectangle | landmarks, params, blocking=True | bool | JigPlateValidator 직사각형 검증, 실패 시 작업자 확인 콜백 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2005 |
| 65 | JobExecutor._resolve_plate_pose_files | source_path, file_prefix, average_count | List[Path] | 저장본 YAML 파일 목록 해석(파일/폴더, 최신 N개) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2053 |
| 66 | JobExecutor._exec_load_plate_pose | job | bool | 저장본 랜드마크 평균으로 평면 pose 복원 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2071 |
| 67 | JobExecutor._plate_pose_file_name | job, saved_at: str | str | <레시피>_<캡션>_<시각>.yaml 파일명 생성(문자 정제) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2117 |
| 68 | JobExecutor._save_plate_pose | save_dir, plate_pose, landmarks, job, operator | bool | 평면 pose + 4 landmark YAML 저장 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2129 |
| 69 | JobExecutor._exec_save_landmark_pose | job | bool | tm_landmark_pose 검증 후 저장 위임 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2173 |
| 70 | JobExecutor._save_landmark_pose | save_dir, pose, job, operator | bool | landmark 단일 pose YAML 저장 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2197 |
| 71 | JobExecutor._landmark_pose_age_min | path, data | Optional[float] | 저장본 나이(분) — saved_at 우선, 폴백 mtime | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2232 |
| 72 | JobExecutor._load_landmark_pose_from_files | params | (pose, msg) | 저장본 평균 landmark 로드(유효시간 검사 포함) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2246 |
| 73 | JobExecutor._landmark_frame_inputs | params | ((landmark, frame_mode, relative), reason) | 마커좌표계 이동 입력 해석(latest_scan/file) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2300 |
| 74 | JobExecutor._landmark_frame_target | params | (target, reason) | 마커좌표계 목표 pose 계산(반경 상한·tool offset) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2326 |
| 75 | JobExecutor._exec_move_to_landmark_pose | job | bool | 마커좌표계 목표로 자세유지 이동 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2353 |
| 76 | JobExecutor.estimate_landmark_frame_target | params | (offset, msg) | 현 TCP 를 마커좌표계 오프셋으로 역산 (task_edit_tab 사용) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2375 |
| 77 | JobExecutor.estimate_landmark_frame_tool_offset | params | (offset, msg) | 그리퍼 오차(6DOF) 역산 (task_edit_tab 사용) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2392 |
| 78 | JobExecutor._plane_normal_tilt_deg | plate_pose | float | 평면 법선의 base +Z 대비 기울기(deg) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2412 |
| 79 | JobExecutor._check_landmark_diagonal_diff | max_diff_mm: float | (bool, str) | Jig 4점 대각선 길이 차 검증 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2417 |
| 80 | JobExecutor._read_tcp_or_log | what: str | Optional[List[float]] | 현재 TCP 읽기(실패 시 로그) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2445 |
| 81 | JobExecutor._move_pose_keep | label, target, velocity, decel_zone_mm, decel_velocity, straight=False | bool | 2단(제자리 자세정렬→자세유지 접근) 공통 이동 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2452 |
| 82 | JobExecutor._exec_save_pose | job | bool | 현 TCP 를 saved_poses[key] 에 저장 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2516 |
| 83 | JobExecutor._exec_move_to_saved_pose | job | bool | 저장 자세로 _move_pose_keep 복귀 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2527 |
| 84 | JobExecutor._exec_move_to_plane_pose | job | bool | 평면좌표계 목표 이동(기울기·반경·z>0 가드) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2574 |
| 85 | JobExecutor._plane_align_base_target | params | (target, tcp_before, tilt_deg) | 평면 수직 정렬 목표 계산(배치·기울기 가드) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2628 |
| 86 | JobExecutor._plane_align_tool_offset (static) | params | dict | offset_* 파라미터 → tool offset dict | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2680 |
| 87 | JobExecutor.estimate_plane_align_tool_offset | params | (offset, msg) | 평면 정렬 그리퍼 오차 역산 (task_edit_tab 사용) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2686 |
| 88 | JobExecutor._exec_align_to_plane_normal | job | bool | 평면 법선 수직 정렬 2단 이동 (#81 과 동일 패턴 인라인 구현) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2711 |
| 89 | JobExecutor._exec_measure_plane_distance | job | bool | TCP-평면 부호거리·정렬편차 측정 로그 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2794 |
| 90 | JobExecutor._exec_generate_runtime | job | bool | tools/convert_to_runtime 으로 마스터→런타임 YAML 변환 (sys.path 주입) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2829 |
| 91 | JobExecutor._read_and_store_landmark_result | - | bool | AskItem 으로 g_tm_landmark_detect/g_TM_Landmark 읽어 저장 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2895 |
| 92 | JobExecutor._exec_measure_point | job | bool | 측정점 이동(#28 과 동일 변환 블록) + end 시 on_measure_point 콜백 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2952 |
| 93 | JobExecutor._exec_vision_process | job | bool | Vision 플러그인 실행 (runtime_vars 미초기화 — 평가 후보 참조) | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:3025 |
| 94 | JobExecutor._exec_ai_inspection | job | bool | AI 모델 로드→TM Flow 촬영 트리거→techman_image 수신→추론 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:3130 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | POSE_KEEP_MIN_SEGMENT_MM (상수) | #34, #36, #81, #88 | 이동 생략 최소 구간 0.1mm | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:48 |
| 2 | POSE_KEEP_DECEL_ZONE_MM (상수) | #36, #75, #83, #84, #88 | 하강 감속 구간 기본 40mm | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:50 |
| 3 | POSE_KEEP_DECEL_VELOCITY (상수) | #34, #36, #75, #83, #84, #88 | 감속 구간 속도 기본 10% | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:51 |
| 4 | POSE_KEEP_DECEL_MARGIN_MM (상수) | #32, #33 | 감속 분할 마진 5mm | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:52 |
| 5 | PLANE_ALIGN_MAX_TILT_DEG (상수) | #84, #85 | 평면 기울기 상한 30° | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:54 |
| 6 | PLANE_ALIGN_MAX_DIAGONAL_DIFF_MM (상수) | #85 | 대각선 차 상한 10mm | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:55 |
| 7 | PLANE_ALIGN_MIN_ROTATION_DEG (상수) | #81, #88 | 자세 정렬 생략 임계 0.01° | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:56 |
| 8 | JobExecutor.LANDMARK_POSE_KEYS (상수, 클래스) | #69~#77 | landmark pose 필수 키 6종 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2171 |
| 9 | JobExecutor.LANDMARK_FRAME_OFFSET_KEYS (상수, 클래스) | #73 | 마커좌표계 오프셋 키 6종 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:2230 |
| 10 | ExecutionState (enum 상수) | 전 실행 함수 | IDLE/RUNNING/PAUSED/STOPPED/ERROR/COMPLETED | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:59-65 |

## src/TM_Robot_Task_Manager/tm_task_manager/macros/base.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | MacroResult.success | message='', **data | MacroResult | 성공 결과 생성 | macros/base.py:22 |
| 2 | MacroResult.failure | message, **data | MacroResult | 실패 결과 생성 | macros/base.py:26 |
| 3 | MacroContext.__init__ | executor, blackboard: Optional[dict] | - | executor 참조·blackboard 보관 | macros/base.py:37 |
| 4 | MacroContext.log | message: str | None | executor._log 위임 | macros/base.py:41 |
| 5 | MacroContext.ros_node (property) | - | node | executor.ros_node | macros/base.py:45 |
| 6 | MacroContext.vision_manager (property) | - | VisionManager | executor.vision_manager | macros/base.py:49 |
| 7 | MacroContext.vision_origin_check_service (property) | - | 서비스 | executor 위임 | macros/base.py:53 |
| 8 | MacroContext.coordinate_system_manager (property) | - | 관리자 | executor 위임 | macros/base.py:57 |
| 9 | MacroContext.is_stop_requested (property) | - | bool | executor._stop_requested 읽기 | macros/base.py:61 |
| 10 | MacroContext.clear_stop_request | - | None | executor._stop_requested=False | macros/base.py:66 |
| 11 | MacroContext.move_to_position | *args, **kwargs | (bool,str) | executor._move_to_position 위임 | macros/base.py:69 |
| 12 | MacroContext.move_pose_keep | label, target: dict, velocity, decel_zone_mm, decel_velocity, straight | bool | executor._move_pose_keep 위임 | macros/base.py:72 |
| 13 | MacroContext.scan_landmark_averaged | *args, **kwargs | (pose,stats) | executor 위임 | macros/base.py:78 |
| 14 | MacroContext.emit | callback_name: str, payload | None | executor 콜백 동적 발화 | macros/base.py:81 |
| 15 | MacroContext.put | key, value | None | blackboard 쓰기 | macros/base.py:87 |
| 16 | MacroContext.get | key, default=None | Any | blackboard 읽기 | macros/base.py:91 |
| 17 | MacroContext.has | key | bool | blackboard 존재 확인 | macros/base.py:94 |
| 18 | MacroSpec.defaults | - | Dict | params 기본값 dict | macros/base.py:109 |
| 19 | MacroSpec.blackboard_requires | - | List[str] | config: 접두어 제외 요구 | macros/base.py:113 |
| 20 | MacroSpec.external_requires | - | List[str] | config: 접두어 요구만 | macros/base.py:117 |
| 21 | register | name, summary, category, params, requires, produces | decorator | 매크로 등록 (중복 시 ValueError) | macros/base.py:125 |
| 21a | register.decorator | fn: Callable | Callable | MACROS[name]=MacroSpec 등록 | macros/base.py:130 |
| 22 | get_macro | name | Optional[MacroSpec] | 레지스트리 조회 | macros/base.py:142 |
| 23 | run_macro | name, ctx, params | MacroResult | 기본값 병합→선행조건 검사→실행→반환형 검증 | macros/base.py:146 |
| 24 | validate_sequence | uses: List[str] | (bool, List[str]) | 열 단위 requires/produces 정합 검사 | macros/base.py:177 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | EXTERNAL_PREFIX (상수) | blackboard_requires, external_requires | 'config:' 외부요구 접두어 | macros/base.py:11 |
| 2 | MACROS (가변) | register, get_macro, run_macro, validate_sequence | 전역 매크로 레지스트리 dict | macros/base.py:122 |

## src/TM_Robot_Task_Manager/tm_task_manager/macros/builtin.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | wait | ctx, duration: int=1000(ms) | MacroResult | 정지요청 폴링하며 대기 | macros/builtin.py:16 |
| 2 | vision_origin_check | ctx, move_to_reference=True, velocity=20.0, repeat_count=5, outlier_method='iqr', wait_after_command=100 | MacroResult | 기준자세 복귀→반복측정→편차 판정→알람 | macros/builtin.py:57 |

## src/TM_Robot_Task_Manager/tm_task_manager/macros/pallet_teach.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | _current_tcp | ctx | Optional[List[float]] | ros_node.current_tcp_pose 6축 읽기 | macros/pallet_teach.py:35 |
| 2 | _tcp_dict | pose: List[float] | Dict[str,float] | 리스트→xyzrxryrz dict | macros/pallet_teach.py:43 |
| 3 | normalize_plate_pose_up | plate_pose: dict | dict | 법선 z<0 이면 y·z축 반전해 위로 정규화 | macros/pallet_teach.py:48 |
| 4 | package_root | - | str | paths.PACKAGE_ROOT 지연 조회 | macros/pallet_teach.py:64 |
| 5 | resolve_measurement_dir | source_path: str | str | 상대경로를 패키지 루트 기준 절대화 | macros/pallet_teach.py:69 |
| 6 | list_measurement_files | source_path, file_prefix='', max_files=0 | List[str] | 최신순 yaml 목록 | macros/pallet_teach.py:76 |
| 7 | average_marks_with_outliers | file_paths, outlier_method='iqr' | (marks, used, skipped, stats) | jig1~4 파일 간 outlier 제거 평균 | macros/pallet_teach.py:90 |
| 8 | pallet_load_measurements | ctx, source_path, file_prefix, max_files=5, outlier_method='iqr', file_paths=None | MacroResult | 저장 측정 평균→plate_pose 산출 | macros/pallet_teach.py:165 |
| 9 | pallet_capture_marker | ctx, repeat_count=10, outlier_method='3sigma', wait_after_command=0 | MacroResult | 위치 마커 6축 측정·저장 | macros/pallet_teach.py:233 |
| 10 | pallet_scan_4corners | ctx, pitch_x, pitch_y, trim_x, trim_y, velocity=25, repeat_count=10, outlier_method='3sigma', wait_after_command=0 | MacroResult | 4꼭짓점 이동·스캔→평면 pose | macros/pallet_teach.py:290 |
| 11 | pallet_center_approach | ctx, standoff_mm=150, rz_mode='plane', velocity=20 | MacroResult | 평면 법선 위 standoff 로 정렬 이동 | macros/pallet_teach.py:398 |
| 12 | pallet_capture_teach | ctx, slot='pick' | MacroResult | 현재 TCP 를 평면 상대값으로 슬롯 저장 | macros/pallet_teach.py:445 |
| 13 | pallet_emit_recipes | ctx, pallet_name, mount='fixed', pitch/trim, operator, gripper='', descent='plane_normal', overwrite=False | MacroResult | 그리퍼 resolve→PalletRecipeGenerator.emit | macros/pallet_teach.py:495 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | DEFAULT_CORNER_PLAN (상수) | pallet_scan_4corners | jig 순회 순서 (4→2→1→3, 단위 이동) | macros/pallet_teach.py:25 |
| 2 | TEACH_SLOTS (상수) | pallet_capture_teach | approach/pick/place 슬롯 | macros/pallet_teach.py:32 |

## src/TM_Robot_Task_Manager/tm_task_manager/main_window.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | TaskManagerNode.__init__ | - | - | 구독 4·클라이언트 4(+선택 3)·안전가드 초기화 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:73 |
| 2 | TaskManagerNode._init_safety_guard | - | None | 안전구역 로드, MotionGuard/BoundaryMonitor/MotionGateway/RobotStopService 생성 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:152 |
| 2a | _init_safety_guard.log (이너) | message | None | get_logger().warn 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:163 |
| 3 | TaskManagerNode.reload_safety_area | - | (bool, str) | 안전구역 설정 재적재·검증 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:195 |
| 4 | TaskManagerNode.current_joint_position (property) | - | list | motion_service 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:210 |
| 5 | TaskManagerNode.current_tcp_pose (property) | - | list | motion_service 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:214 |
| 6 | TaskManagerNode.current_base_name (property+setter) | value | str | motion_service 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:218,222 |
| 7 | TaskManagerNode.robot_moving (property) | - | bool | motion_service.is_moving | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:226 |
| 8 | TaskManagerNode.target_position (property+setter) | value | list | motion_service 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:230,234 |
| 9 | TaskManagerNode.last_position_error / last_rotation_error / last_joint_error (property 3) | - | float | motion_service 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:238,242,246 |
| 10 | TaskManagerNode._on_joint_state | msg: JointState | None | TM 조인트 판별 후 motion_service 갱신 + UI 콜백 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:251 |
| 11 | TaskManagerNode._on_tool_pose | msg: PoseStamped | None | TCP pose(quaternion) 갱신 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:258 |
| 12 | TaskManagerNode._on_feedback_state | msg: FeedbackState | None | 속도·is_sct_connected·IO 상태 갱신 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:266 |
| 13 | TaskManagerNode._on_techman_image | msg: Image | None | 프레임 캐시 push + 대기 플래그 처리 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:287 |
| 14 | TaskManagerNode.start_techman_image_subscription | - | int(baseline) | 새 프레임 대기 시작(seq 기준선 반환) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:296 |
| 15 | TaskManagerNode.wait_techman_image | baseline, timeout_sec, should_stop, spin=False | (msg, err) | 기준선 이후 프레임 대기 (spin 옵션) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:304 |
| 15a | wait_techman_image.on_poll (이너) | - | None | spin_once(0.05s) 폴링 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:319 |
| 16 | TaskManagerNode._check_motion_complete | - | bool | motion_service 완료 판정 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:329 |
| 17 | TaskManagerNode._motion_kind_of | motion_type | str | SetPositions 상수 → 안전가드 모션 종류 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:332 |
| 18 | TaskManagerNode._log_motion_command | kind, positions, velocity | None | 이동 명령 진단 로그(단위 환산) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:344 |
| 19 | TaskManagerNode._call_set_positions | motion_type, positions, velocity, acc_time, blend, fine_goal | (bool, str) | 안전 게이트웨이 경유 이동 명령 전송 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:373 |
| 20 | TaskManagerNode._send_set_positions | 상동 | (bool, str) | set_positions 호출 + 완료 폴링(30s, 안정 3회) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:394 |
| 21 | TaskManagerNode.start_subscriptions | - | None | techman_image/aruco pose 구독 생성(중복 2번째 techman_image) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:444 |
| 22 | TaskManagerNode.stop_subscriptions | - | None | 위 구독 해제 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:464 |
| 23 | TaskManagerNode._on_image | msg: Image | None | cv 변환 후 image_callback 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:476 |
| 24 | TaskManagerNode._on_pose | msg: PoseStamped | None | pose_callback 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:484 |
| 25 | MainWindow.__init__ | ros_node=None | - | 서비스 20여 개·탭 12개 조립, QTimer 2개 시작 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:492 |
| 26 | MainWindow._spin_ros | - | None | 10ms 마다 spin_once(timeout 0); 예외 시 self.close() | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:630 |
| 27 | MainWindow._connect_signals | - | None | 메뉴·버튼·탭 시그널 연결 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:638 |
| 28 | MainWindow._init_ui | - | None | IP 표시·상태바·탭 init_ui 일괄 호출 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:667 |
| 29 | MainWindow._init_ip_display | - | None | PC/로봇 IP 표시·저장 연결 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:698 |
| 30 | MainWindow._get_all_network_interfaces | - | list | NetworkManager 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:711 |
| 31 | MainWindow._get_local_ip | - | str | NetworkManager 위임(유선 우선) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:714 |
| 32 | MainWindow._load_robot_ip_from_config | - | str | config_manager 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:717 |
| 33 | MainWindow._on_robot_ip_changed | - | None | IP 입력 저장 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:720 |
| 34 | MainWindow._save_robot_ip_to_config | ip | None | 저장(실패 로그) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:726 |
| 35 | MainWindow._on_find_robot_ip | - | None | 백그라운드 스레드로 로봇 IP 스캔 + QTimer 폴링 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:732 |
| 35a | _on_find_robot_ip.scan_thread (이너) | - | None | NetworkManager.scan_for_robot(5890/5891) 실행, _scan_result/_scan_done 기록 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:743 |
| 35b | _on_find_robot_ip.check_scan_complete (이너) | - | None | _scan_done 폴링 후 완료 처리 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:752 |
| 36 | MainWindow._on_scan_complete | - | None | 스캔 결과 UI 반영·저장 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:764 |
| 37 | MainWindow._on_refresh_pc_ip | - | None | 인터페이스 선택 다이얼로그로 PC IP 설정 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:775 |
| 38 | MainWindow._on_position_taught | taught_data: dict | None | 티칭 위치 로그 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:807 |
| 39 | MainWindow._on_new | - | None | 새 Recipe(확인 다이얼로그) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:814 |
| 40 | MainWindow._on_open | - | None | 파일 다이얼로그로 Recipe 로드 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:829 |
| 41 | MainWindow._update_recipe_reference | recipe | None | scan 잡 있으면 tm_jig_landmark 기준점을 recipe.reference 에 기록 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:853 |
| 42 | MainWindow._on_save | - | None | 저장(경로 없으면 save_as) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:885 |
| 43 | MainWindow._on_save_as | - | None | 다른 이름 저장 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:902 |
| 44 | MainWindow._on_about | - | None | About 다이얼로그 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:931 |
| 45 | MainWindow._on_emergency_stop | - | None | job_executor.stop() + 로그 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:935 |
| 46 | MainWindow._on_origin_check_alarm | result | None | 기준점 편차 초과 크리티컬 다이얼로그 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:940 |
| 47 | MainWindow._on_plate_rect_alarm | payload | bool | 직사각형 검증 실패 → 저장/중단 선택 다이얼로그 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:960 |
| 48 | MainWindow._update_joint_display | joint_positions | None | 조인트 캐시 갱신 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:991 |
| 49 | MainWindow._update_robot_status_display | - | None | 100ms 타이머 — 조인트/TCP lineEdit 갱신 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:995 |
| 50 | MainWindow._on_start_camera | - | None | 500ms 라이브 뷰 타이머 시작 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1019 |
| 51 | MainWindow._on_camera_live_tick | - | None | 캡처 중 아니면 capture_image(15s) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1030 |
| 52 | MainWindow._on_stop_camera | - | None | 라이브 뷰 정지 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1035 |
| 53 | MainWindow._on_capture_error | msg: str | None | 캡처 실패 시 라이브 뷰 자동 정지 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1042 |
| 54 | MainWindow._on_image_capture | - | None | 단발 캡처 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1049 |
| 55 | MainWindow._on_image_captured | cv_image | None | 캡처 이미지 UI 반영 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1052 |
| 56 | MainWindow._on_image_save | - | None | 캡처 이미지 저장 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1058 |
| 57 | MainWindow._save_captured_image | cv_image | Optional[str] | data/images/날짜/ 에 PNG 저장 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1065 |
| 58 | MainWindow._on_detect_chessboard / _on_capture_calib_image / _on_run_calibration / _on_save_calibration | - | None | calib_service 위임 4종 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1088,1091,1094,1097 |
| 59 | MainWindow._on_calib_status_changed / _on_chessboard_detected / _on_calib_image_captured / _on_calibration_completed / _on_calibration_saved | status/success/message | None | 캘리브레이션 시그널 핸들러 5종 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1101,1104,1110,1117,1123 |
| 60 | MainWindow._move_to_position | motion_type, positions, velocity, acc_time, blend, fine_goal | (bool, str) | ros_node._call_set_positions 위임 (jog_service 콜백) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1130 |
| 61 | MainWindow._update_task_sequence | - | None | Task 리스트 위젯 재구성 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1145 |
| 62 | MainWindow.current_tcp_orientation (property) | - | Any | coordinate_system_manager 위임 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1156 |
| 63 | MainWindow._log_style_for | message, kind=None | Optional[tuple] | 로그 문구 키워드로 스타일(fail/warn/ok) 결정 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1173 |
| 64 | MainWindow._strip_log_premark | message | str | 선행 이모지 마크 제거 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1187 |
| 65 | MainWindow._log | message, kind=None | None | 타임스탬프+HTML 스타일 로그, processEvents 호출 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1195 |
| 66 | MainWindow._update_recent_files_menu | - | None | 최근 파일 메뉴 재구성 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1229 |
| 67 | MainWindow._open_recent_file | file_path | None | 최근 파일 열기(없으면 목록 제거) | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1245 |
| 68 | MainWindow.closeEvent | event | None | 타이머 정지·구독 해제·TF 정지·pkill 카메라 브리지 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1268 |
| 69 | main | - | (exit) | rclpy.init → TaskManagerNode → QApplication → MainWindow → exec_ → 종료 정리 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1300 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | _SMC_GRIPPER_AVAILABLE (상수, import 시 결정) | TaskManagerNode.__init__ (:123) | gripper_ros 소싱 여부 플래그 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:50-55 |
| 2 | _TC_MSGS_AVAILABLE (상수, import 시 결정) | TaskManagerNode.__init__ (:130) | tc_msgs 소싱 여부 플래그 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:57-61 |
| 3 | MainWindow.LOG_STYLES (상수, 클래스) | _log_style_for | 로그 분류 키워드·색상 테이블 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1161-1169 |
| 4 | MainWindow.LOG_PREMARKS (상수, 클래스) | _strip_log_premark | 제거 대상 선행 마크 목록 | src/TM_Robot_Task_Manager/tm_task_manager/main_window.py:1171 |

## src/TM_Robot_Task_Manager/tm_task_manager/paths.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | _from_upward_search | - | Path or None | 부모 디렉토리 상향으로 package.xml 탐색 | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:12 |
| 2 | _from_share_dir | - | Path or None | ament share 에서 소스 트리 역산(try/except) | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:20 |
| 3 | _find_package_root | - | Path | 두 리졸버 순차 시도, 실패 시 RuntimeError | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:34 |
| 4 | ui | name: str | str | UI_DIR 하위 파일 경로 | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:60 |
| 5 | config | name: str | str | CONFIG_DIR 하위 파일 경로 | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:65 |
| 6 | log_resolved | logger=None | str | 해석된 경로 일람 로그/print | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:70 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | _PACKAGE_NAME (상수) | #2, #3 | 'tm_task_manager' | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:8 |
| 2 | _MARKER (상수) | #1, #2 | 'package.xml' | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:9 |
| 3 | PACKAGE_ROOT (상수, import 시 확정) | 패키지 전역(job_executor:2055 등) | 소스 패키지 루트 | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:48 |
| 4 | SRC_ROOT (상수) | AI_ROOT 계산 | 워크스페이스 src/ | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:49 |
| 5 | UI_DIR / CONFIG_DIR / DATA_DIR / SCRIPTS_DIR / AI_ROOT / ROBOTS_DIR (상수 6종) | ui(), config(), robot_profile._robots_dir, main_window:1018 등 | 리소스 디렉토리 | src/TM_Robot_Task_Manager/tm_task_manager/paths.py:51-57 |

## src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | Job.__init__ | job_id, job_type, name, params, caption, coordinate_mode, original_absolute, robot_base | - | 잡 필드 초기화 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:11 |
| 2 | Job.sync_robot_base | - | None | params 의 6좌표를 robot_base 로 복사 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:23 |
| 3 | Job.to_dict | - | Dict | 직렬화 (absolute 시 robot_base 자동 포함) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:27 |
| 4 | Job.from_dict (classmethod) | data: Dict | Job | 역직렬화 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:46 |
| 5 | Recipe.__init__ | name, description | - | 메타·잡 리스트 초기화 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:61 |
| 6 | Recipe.add_job | job | None | 추가 + id 재부여 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:73 |
| 7 | Recipe.insert_job | index, job | None | 삽입 + id 재부여 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:77 |
| 8 | Recipe.duplicate_job | index | bool | deepcopy 복제 후 다음 위치 삽입 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:82 |
| 9 | Recipe.remove_job | index | None | 삭제 + id 재부여 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:91 |
| 10 | Recipe.move_job_up | index | bool | 앞으로 스왑 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:96 |
| 11 | Recipe.move_job_down | index | bool | 뒤로 스왑 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:103 |
| 12 | Recipe._update_ids | - | None | 1-base 로 id 재부여 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:110 |
| 13 | Recipe.to_dict | - | Dict | 직렬화(modified 갱신) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:114 |
| 14 | Recipe.from_dict (classmethod) | data | Recipe | 역직렬화 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:131 |
| 15 | RecipeManager.__init__ | recipe_dir=None | - | 레시피 폴더 결정(install/build 경로 역산) + 최근 파일 로드 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:943 |
| 16 | RecipeManager._ensure_directory | - | None | 폴더 생성 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:962 |
| 17 | RecipeManager.new_recipe | name, description | Recipe | 새 Recipe 생성·현재화 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:965 |
| 18 | RecipeManager.load_recipe | file_path, auto_reconvert=False | Recipe | YAML 로드 + 마스터 변경 감지 경고(재변환은 미구현 pass) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:969 |
| 19 | RecipeManager.save_recipe | recipe=None, file_path=None | str | 주석 헤더 포함 YAML 저장 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1005 |
| 20 | RecipeManager.list_recipes | - | List[Dict] | 폴더 내 레시피 메타 나열(오류 무시) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1041 |
| 21 | RecipeManager.create_job | job_type, name=None, params=None | Job | JOB_TYPES 기본값으로 잡 생성 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1060 |
| 22 | RecipeManager.get_job_types_by_category | - | Dict[str, List[str]] | 카테고리별 잡 타입 목록 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1080 |
| 23 | RecipeManager.get_job_type_info | job_type | Optional[Dict] | JOB_TYPES 조회 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1089 |
| 24 | RecipeManager._get_recent_files_path | - | str | .recent_files.txt 경로 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1093 |
| 25 | RecipeManager._load_recent_files | - | None | 최근 파일 로드(~ 확장·존재 필터) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1096 |
| 26 | RecipeManager._save_recent_files | - | None | 최근 파일 저장(~ 축약) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1113 |
| 27 | RecipeManager.add_to_recent_files | file_path | None | 최근 파일 선두 삽입(최대 4) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1128 |
| 28 | RecipeManager.get_recent_files | - | List[str] | 복사본 반환 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1141 |
| 29 | RecipeManager.clear_recent_files | - | None | 목록 비움 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1144 |
| 30 | RecipeManager.remove_from_recent_files | file_path | bool | 목록에서 제거 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:1148 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | Job.COORDINATE_KEYS (상수, 클래스) | sync_robot_base, to_dict | 6좌표 키 목록 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:9 |
| 2 | RecipeManager.CATEGORY_ORDER (상수, 클래스) | UI(task_edit_tab)에서 사용 | 카테고리 표시 순서 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:152 |
| 3 | RecipeManager.JOB_TYPES (상수, 클래스, 817줄) | create_job, get_job_type*, job_executor._execute_job(:466), UI | 잡 스키마 단일 근원(54종 — sdc_tcp_base·sdc_palette_tcp_align·sdc_palette_inlet_move(dx/dy/dz 보정 2026-08-30)·sdc_marker_move 추가 2026-08-29, sdc_* Job 의 자세·offset 값은 config/positions.yaml positions.* 에서 실행 시 재독) | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:154-980 |

## src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | RobotConnectionManager.__init__ | node: Node | - | connect 클라이언트·feedback 구독 생성 | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:22 |
| 2 | RobotConnectionManager._set_state | state | None | 상태 전이 + on_state_changed 콜백 | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:46 |
| 3 | RobotConnectionManager._on_feedback_state | msg: FeedbackState | None | error_code==0 → is_robot_ready 갱신·콜백 | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:52 |
| 4 | RobotConnectionManager.connect | robot_ip: str, timeout_sec=5.0 | (bool, str) | connect_tmsvr 호출(server=0, reconnect=True) | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:66 |
| 5 | RobotConnectionManager.disconnect | - | (bool, str) | 로컬 상태만 DISCONNECTED (드라이버 호출 없음) | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:118 |
| 6 | RobotConnectionManager.get_connection_info | - | dict | 상태 요약 | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:136 |
| 7 | RobotConnectionManager.is_connected | - | bool | state==CONNECTED | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:145 |
| 8 | RobotConnectionManager.is_ready | - | bool | 연결 + 로봇 정상 | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:149 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | ConnectionState (enum 상수) | 전 함수 | DISCONNECTED/CONNECTING/CONNECTED/ERROR | src/TM_Robot_Task_Manager/tm_task_manager/robot_connection.py:11-16 |

## src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | _robots_dir | - | str | paths.CONFIG_DIR/robots 경로 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:24 |
| 2 | available | - | List[str] | 프로필 yaml 파일명 목록 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:30 |
| 3 | load | robot_id: str | Dict | 프로필 yaml 로드(+id/_path 보강), 없으면 ProfileError | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:42 |
| 4 | local_ipv4 | - | List[str] | getaddrinfo + UDP 프로브로 로컬 IPv4 수집(127.* 제외) | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:58 |
| 5 | _detect_id_without_probe | - | Optional[str] | env→active.txt→IP 교집합 (포트 프로브 제외) | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:80 |
| 6 | candidate_robot_ips | - | List[(id, ip)] | 고정 프로필 우선 + 전체 프로필 robot_ip 후보 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:107 |
| 6a | candidate_robot_ips.add (이너) | robot_id | None | 중복 없이 후보 추가 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:112 |
| 7 | reachable | ip, port=5890, timeout_sec=1.0 | bool | TCP connect_ex 도달성 검사 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:132 |
| 8 | probe_robot_ip | timeout_sec=1.0 | (id, ip) or (None, None) | 후보 중 첫 도달 로봇 반환 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:148 |
| 9 | probe_report | timeout_sec=1.0 | str | 후보별 응답/무응답 보고 문자열 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:157 |
| 10 | detect_id | - | Optional[str] | env→active.txt→IP 교집합→포트 프로브 (#5 로직 중복 포함) | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:166 |
| 11 | active | required=False | Optional[Dict] | detect_id 후 프로필 로드(실패 시 ProfileError 옵션) | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:197 |
| 12 | robot_ip | default=None | Optional[str] | 활성 프로필의 robot_ip | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:211 |
| 13 | gripper_id | default='' | str | 활성 프로필의 gripper.id | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:222 |
| 14 | describe | - | str | 프로필 요약 문자열 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:233 |
| 15 | ProfileError (class) | - | - | RuntimeError 파생 예외 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:19 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | ENV_VAR (상수) | #5, #10 | 'TM_ROBOT_ID' | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:12 |
| 2 | ACTIVE_FILE (상수) | #5, #10, #11 | 'active.txt' | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:13 |
| 3 | ROBOT_PORT (상수) | #7, #8, #9, launch | 5890 | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:15 |
| 4 | PROBE_TIMEOUT_SEC (상수) | #7~#9 | 1.0s | src/TM_Robot_Task_Manager/tm_task_manager/robot_profile.py:16 |

## src/TM_Robot_Task_Manager/tm_task_manager/safety/boundary_monitor.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | BoundaryJudge.__init__ | area: dict | - | 구역·직전점 초기화 | safety/boundary_monitor.py:21 |
| 2 | BoundaryJudge.previous (property) | - | Optional[List[float]] | 직전 표본 | safety/boundary_monitor.py:25 |
| 3 | BoundaryJudge.reset | - | None | 직전점 소거 | safety/boundary_monitor.py:29 |
| 4 | BoundaryJudge.update | point_mm | Optional[str] | 점/선분 검사 후 위반 사유 반환 | safety/boundary_monitor.py:33 |
| 5 | BoundaryMonitor.__init__ | area, sample_fn, stop_fn, poll_sec=0.05, on_violation, log_callback | - | 스레드·락·이벤트 준비 | safety/boundary_monitor.py:63 |
| 6 | BoundaryMonitor.state (property) | - | str | 락 보호 상태 읽기 | safety/boundary_monitor.py:84 |
| 7 | BoundaryMonitor.message (property) | - | str | 락 보호 메시지 읽기 | safety/boundary_monitor.py:89 |
| 8 | BoundaryMonitor.is_watching (property) | - | bool | state==watching | safety/boundary_monitor.py:94 |
| 9 | BoundaryMonitor.set_area | area | None | 구역 교체+Judge 재생성 | safety/boundary_monitor.py:98 |
| 10 | BoundaryMonitor._log | message | None | 콜백 로그 | safety/boundary_monitor.py:107 |
| 11 | BoundaryMonitor.start | - | bool | watching 전이+감시 스레드 기동 | safety/boundary_monitor.py:111 |
| 12 | BoundaryMonitor.stop | timeout=1.0 | None | 이벤트 세트+join+idle 복귀 | safety/boundary_monitor.py:126 |
| 13 | BoundaryMonitor.reset | - | None | idle 복귀·메시지 소거 | safety/boundary_monitor.py:141 |
| 14 | BoundaryMonitor._run | - | None | 폴링 루프: 표본→판정→위반 시 정지 | safety/boundary_monitor.py:148 |
| 15 | BoundaryMonitor._trigger_stop | reason | None | stopped 전이+stop_fn 호출+콜백 | safety/boundary_monitor.py:165 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | DEFAULT_POLL_SEC (상수) | __init__ | 0.05s 폴링 주기 | safety/boundary_monitor.py:11 |
| 2 | STATE_IDLE/WATCHING/STOPPED (상수) | 상태 전이 전반 | 3상 상태 문자열 | safety/boundary_monitor.py:13-15 |

## src/TM_Robot_Task_Manager/tm_task_manager/safety/motion_guard.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | GuardDecision.summary | - | str | 허용/거부·검사여부 한 줄 요약 | safety/motion_guard.py:38 |
| 2 | rotation_matrix_deg | rx,ry,rz (deg) | List[List[float]] | ZYX 회전행렬 (순수 파이썬) | safety/motion_guard.py:47 |
| 3 | tool_offset_to_base | tcp_pose, dx,dy,dz | List[float] | 공구 오프셋→베이스 목표점 | safety/motion_guard.py:60 |
| 4 | MotionGuard.__init__ | area=None, log_callback=None | - | 구역 로드(기본 load_area)·기록 리스트 | safety/motion_guard.py:79 |
| 5 | MotionGuard.area (property) | - | dict | 현재 구역 | safety/motion_guard.py:85 |
| 6 | MotionGuard.enabled (property) | - | bool | sa.is_enabled | safety/motion_guard.py:89 |
| 7 | MotionGuard.reload | path=None | dict | 구역 재로드 | safety/motion_guard.py:93 |
| 8 | MotionGuard.set_area | area | None | 구역 교체 | safety/motion_guard.py:98 |
| 9 | MotionGuard.records | - | List[GuardDecision] | 기록 사본 | safety/motion_guard.py:101 |
| 10 | MotionGuard.unchecked_records | - | List[GuardDecision] | 허용+미검사 기록 | safety/motion_guard.py:105 |
| 11 | MotionGuard.clear_records | - | None | 기록 소거 | safety/motion_guard.py:109 |
| 12 | MotionGuard._log | message | None | 콜백 로그 | safety/motion_guard.py:112 |
| 13 | MotionGuard._record | decision | GuardDecision | 기록 append+200개 트림+비정상만 로그 | safety/motion_guard.py:116 |
| 14 | MotionGuard.check | kind, tcp_pose, target_mm, offset_mm, label | GuardDecision | 종류별 판정 본체 | safety/motion_guard.py:125 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | MOTION_LINE/LINE_RELATIVE/PTP_TCP/PTP_JOINT/VISION_JOB (상수) | check, MotionGateway | 모션 종류 식별자 | safety/motion_guard.py:13-17 |
| 2 | EXACT_KINDS/PTP_KINDS (상수) | check | 종류 그룹 | safety/motion_guard.py:19-20 |
| 3 | MAX_RECORDS (상수) | _record | 기록 상한 200 | safety/motion_guard.py:22 |

## src/TM_Robot_Task_Manager/tm_task_manager/safety/safety_area.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | config_path | - | str | paths.config('safety_area.yaml') | safety/safety_area.py:32 |
| 2 | load_area | path=None | dict | yaml 로드+기본값 병합 (파일 없으면 DEFAULT) | safety/safety_area.py:38 |
| 3 | save_area | area, path=None | str | yaml 저장 (디렉토리 생성) | safety/safety_area.py:64 |
| 4 | validate_area | area: dict | (bool, str) | 박스 구조·범위·베이스 포함·마진·공구 검증 | safety/safety_area.py:73 |
| 5 | is_enabled | area | bool | enabled 플래그 | safety/safety_area.py:135 |
| 6 | tool_inflation_mm | area | float | 공구 반경 팽창값 | safety/safety_area.py:140 |
| 7 | keep_out_inflation_mm | area | float | margin+공구 반경 | safety/safety_area.py:151 |
| 8 | point_in_area | area, xyz_mm | bool | 허용 박스 합집합 포함 검사 | safety/safety_area.py:156 |
| 9 | violations | area, points_mm | List[dict] | 이탈점별 최근접 박스·초과량 | safety/safety_area.py:170 |
| 10 | describe_violation | violation | str | 위반 한국어 설명 | safety/safety_area.py:205 |
| 11 | segment_intersects_box | p0, p1, lo, hi | bool | slab 법 선분-AABB 교차 | safety/safety_area.py:218 |
| 12 | keep_out_hits | area, p0_mm, p1_mm=None | List[dict] | 팽창된 금지 박스 교차 목록 | safety/safety_area.py:240 |
| 13 | describe_keep_out_hit | hit | str | 금지구역 히트 설명 | safety/safety_area.py:267 |
| 14 | segment_in_allowed | area, p0, p1, step_mm=10 | (bool, Optional[dict]) | 10mm 샘플링 허용구역 검사 | safety/safety_area.py:276 |
| 15 | check_point | area, point_mm | (bool, str) | 허용+금지 종합 점 판정 | safety/safety_area.py:301 |
| 16 | check_segment | area, p0, p1, step_mm=10 | (bool, str) | 허용 샘플링+금지 slab 종합 선분 판정 | safety/safety_area.py:313 |
| 17 | joint_limits_config | area | dict | joint_limits 절 (없으면 기본값 사본) | safety/safety_area.py:155 |
| 18 | joint_limits_enabled | area | bool | 조인트 한계 활성 여부 (카르테시안과 독립) | safety/safety_area.py:164 |
| 19 | validate_joint_limits | area | (bool, str) | joint_limits 구조·범위·margin 검증 | safety/safety_area.py:169 |
| 20 | check_joints | area, joints_deg, extra_margin_deg=0 | (bool, str) | 6축이 (모델한계−margin) 안인지 판정 — 사전 거부·실시간 감시 공용 | safety/safety_area.py:195 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | CONFIG_FILE_NAME (상수) | config_path | 'safety_area.yaml' | safety/safety_area.py:11 |
| 2 | BASE_POINT_MM (상수) | validate_area | 로봇 베이스 원점 | safety/safety_area.py:14 |
| 3 | DEFAULT_TOOL (상수) | load_area, DEFAULT_AREA | 공구 기본 (enabled·r45mm) | safety/safety_area.py:16-20 |
| 4 | DEFAULT_AREA (상수) | load_area | 비활성 기본 구역 | safety/safety_area.py:39-48 |
| 5 | DEFAULT_JOINT_LIMITS (상수) | load_area, joint_limits_config | TM20M URDF 기준 조인트 한계 기본값 (J3 는 TM14 보수값 ±163°), margin 5°·auto_stop | safety/safety_area.py:22-37 |

## src/TM_Robot_Task_Manager/tm_task_manager/safety/joint_guard.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | JointGuard.__init__ | area, stop_fn=None, log_callback=None | - | 감시 상태(latch) 초기화 | safety/joint_guard.py:12 |
| 2 | JointGuard.update | joints_deg: Sequence[float] | Optional[str] | (한계−margin) 위반 시 로그+정지 1회(latch), 복귀+1° 이력으로 재무장. 위반 사유 반환 | safety/joint_guard.py:18 |

## src/TM_Robot_Task_Manager/test/test_joint_guard.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `_area` | **overrides | dict | joint_limits 활성 area 생성 헬퍼 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:10 |
| 2 | `test_default_limits_match_tm20_conservative` | 없음 | - | 기본 한계값(J3 ±163 보수값 포함) 검증 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:22 |
| 3 | `test_check_joints_inside_ok` | 없음 | - | 범위 안 통과 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:31 |
| 4 | `test_check_joints_margin_violation` | 없음 | - | 한계−margin 침범 시 거부+사유 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:36 |
| 5 | `test_check_joints_disabled_passes` | 없음 | - | 비활성 시 무조건 통과 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:43 |
| 6 | `test_guard_stops_once_and_rearms` | 없음 | - | 위반 시 정지 1회(latch)·복귀 후 재무장 검증 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:48 |
| 7 | `test_guard_auto_stop_off_logs_only` | 없음 | - | auto_stop=false 면 정지 미호출 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:66 |
| 8 | `test_validate_joint_limits` | 없음 | - | 검증기 정상/뒤집힘/margin 과대 판정 | src/TM_Robot_Task_Manager/test/test_joint_guard.py:75 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/ai_detection_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | AIDetectionService.__init__ | - | - | venv 주입·상태 초기화 | services/ai_detection_service.py:56 |
| 2 | ._add_venv_to_path | - | None | yolov8_env site-packages sys.path 삽입 | services/ai_detection_service.py:68 |
| 3 | .get_available_tasks | - | List[(id,표시명)] | tasks/ 하위 존재 task 목록 | services/ai_detection_service.py:88 |
| 4 | .get_available_runtimes | - | List[(id,표시명)] | pc/hailo | services/ai_detection_service.py:97 |
| 5 | .get_available_models | task='', runtime='' | List[(이름,경로)] | tasks/<t>/models/{pt,hef}/*.ext | services/ai_detection_service.py:100 |
| 6 | .load_model | model_path: str | bool | ultralytics YOLO 로드+시그널 | services/ai_detection_service.py:121 |
| 7 | .set_confidence_threshold | threshold: float | None | 0~1 클램프 | services/ai_detection_service.py:153 |
| 8 | .set_angle_threshold | threshold: float | None | 1~45 클램프 (_angle_threshold) | services/ai_detection_service.py:158 |
| 9 | .angle_threshold (property) | - | float | getattr 기본 15.0 | services/ai_detection_service.py:162 |
| 10 | .is_model_loaded (property) | - | bool | 모델 존재 | services/ai_detection_service.py:166 |
| 11 | .run_inference | cv_image: np.ndarray | bool | predict→DetectionResult 목록→시그널 | services/ai_detection_service.py:170 |
| 12 | ._calc_mask_angle_and_state | mask, image_shape | (angle, state) | minAreaRect 각도→OPEN/CLOSE | services/ai_detection_service.py:251 |
| 13 | ._draw_annotations | image, results | np.ndarray | 마스크·박스·라벨 렌더 | services/ai_detection_service.py:299 |
| 14 | ._get_class_color | class_id | (b,g,r) | 10색 순환 | services/ai_detection_service.py:354 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | AI_ROOT/TASKS_ROOT (클래스 상수) | 모델 탐색 | paths.AI_ROOT 기반 경로 | services/ai_detection_service.py:40-41 |
| 2 | YOLOV8_VENV_PATH/HAILO_VENV_PATH (클래스 상수) | _add_venv_to_path | venv 경로 | services/ai_detection_service.py:43-44 |
| 3 | DETECTION_TASKS/RUNTIME_CONFIG (클래스 상수) | task/model 조회 | task·런타임 사전 | services/ai_detection_service.py:46-54 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/camera_calibration_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node=None | - | 클라이언트 4종 생성(노드 있을 때) | services/camera_calibration_service.py:23 |
| 2 | .captured_count (property) | - | int | 캡처 성공 수 | services/camera_calibration_service.py:36 |
| 3 | .reset_captured_count | - | None | 카운트 0 | services/camera_calibration_service.py:40 |
| 4 | ._init_service_clients | - | None | Trigger 클라이언트 4종 create_client | services/camera_calibration_service.py:43 |
| 5 | ._check_service_available | client, service_name | bool | wait_for_service(1s)+오류 시그널 | services/camera_calibration_service.py:56 |
| 6 | .detect_chessboard | - | None | 비동기 호출+콜백 등록 | services/camera_calibration_service.py:74 |
| 7 | .capture_image | - | None | 〃 | services/camera_calibration_service.py:84 |
| 8 | .run_calibration | - | None | 〃 | services/camera_calibration_service.py:94 |
| 9 | .save_calibration | - | None | 〃 | services/camera_calibration_service.py:104 |
| 10 | ._on_detect_done | future | None | 결과→chessboard_detected 시그널 | services/camera_calibration_service.py:115 |
| 11 | ._on_capture_done | future | None | 성공 시 카운트++→image_captured | services/camera_calibration_service.py:127 |
| 12 | ._on_run_done | future | None | →calibration_completed | services/camera_calibration_service.py:144 |
| 13 | ._on_save_done | future | None | →calibration_saved | services/camera_calibration_service.py:156 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/command_gate.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | log_callback=None | - | busy/라벨/거부수 초기화 | services/command_gate.py:12 |
| 2 | .busy (property) | - | bool | 점유 여부 | services/command_gate.py:18 |
| 3 | .current_label (property) | - | str | 점유 명령 라벨 | services/command_gate.py:22 |
| 4 | .rejected_count (property) | - | int | 거부 누적 | services/command_gate.py:26 |
| 5 | .acquire | label='명령' | bool | busy면 거부수++·False, 아니면 점유 | services/command_gate.py:30 |
| 6 | .release | - | None | 해제+거부 로그 | services/command_gate.py:40 |
| 7 | .run | label, func, *args, **kwargs | Any/None | acquire→func→finally release | services/command_gate.py:58 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/config_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | config_path=None | - | 기본 paths.config('positions.yaml') | services/config_manager.py:9 |
| 2 | ._load_config | - | dict | 캐시 로드(실패 시 {} + print) | services/config_manager.py:15 |
| 3 | ._save_config | config: dict | None | yaml 저장+캐시 갱신 (실패 raise) | services/config_manager.py:28 |
| 4 | .reload | - | dict | 캐시 무효화 후 재로드 | services/config_manager.py:40 |
| 5 | .get_config_path | - | str | 경로 반환 | services/config_manager.py:44 |
| 6 | .get_robot_ip | - | Optional[str] | robot.ip | services/config_manager.py:47 |
| 7 | .set_robot_ip | ip: str | None | robot.ip 설정+저장 | services/config_manager.py:51 |
| 8 | .get_home_position | - | Optional[dict] | positions.home | services/config_manager.py:66 |
| 9 | .set_home_position | values: dict | None | positions.home.values 설정 | services/config_manager.py:70 |
| 10 | .get | key_path: str, default=None | Any | dot-path 조회 | services/config_manager.py:81 |
| 11 | .set | key_path: str, value | None | dot-path 설정+저장 | services/config_manager.py:96 |
| 12 | .delete | key_path: str | bool | dot-path 삭제+저장 | services/config_manager.py:110 |
| 13 | .get_all | - | dict | 얕은 복사 반환 | services/config_manager.py:127 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/coordinate_system_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | config_manager=None, log_callback=None, ros_node=None | - | 정의 로드·TF 상태 초기화 | services/coordinate_system_manager.py:66 |
| 2 | ._log | message | None | 콜백 로그 | services/coordinate_system_manager.py:81 |
| 3 | ._create_pose_dict | x..rz=0 | dict | pose dict 생성 | services/coordinate_system_manager.py:85 |
| 4 | ._create_default_definition | name | dict | 타입별 기본 정의 | services/coordinate_system_manager.py:88 |
| 5 | .get_tool_pose | name | Optional[dict] | 정의 또는 기본 tool_pose 사본 | services/coordinate_system_manager.py:110 |
| 6 | .set_tool_pose | name, x..rz | bool | robot_base 제외 설정 | services/coordinate_system_manager.py:121 |
| 7 | .set_tool_pose_from_list | name, values | bool | 6원소 검증 후 위임 | services/coordinate_system_manager.py:143 |
| 8 | .get_scan_data | name | Optional[Any] | 정의의 scan_data | services/coordinate_system_manager.py:150 |
| 9 | .set_single_landmark_scan | name, landmark, tcp_pose | bool | 단일 스캔 저장+tool_pose 동기화 | services/coordinate_system_manager.py:158 |
| 10 | .add_multi_landmark_scan | name, landmark, tcp_pose | bool | 다중 스캔 append | services/coordinate_system_manager.py:186 |
| 11 | .clear_multi_landmark_scan | name | bool | 다중 스캔 초기화 | services/coordinate_system_manager.py:216 |
| 12 | .get_landmark_count | name | int | 다중 스캔 수 | services/coordinate_system_manager.py:228 |
| 13 | .get_current_system | - | str | 현재 좌표계명 | services/coordinate_system_manager.py:237 |
| 14 | .set_current_system | name | bool | 현재 좌표계 변경 | services/coordinate_system_manager.py:240 |
| 15 | .get_current_tcp_orientation | - | (rx,ry,rz) | 현재 좌표계 tool_pose 자세 | services/coordinate_system_manager.py:249 |
| 16 | .get_current_tool_pose | - | Optional[dict] | 현재 tool_pose | services/coordinate_system_manager.py:256 |
| 17 | .save_to_config | backup_type=None | bool | 정의+current 저장(+백업) | services/coordinate_system_manager.py:260 |
| 18 | ._save_coordinate_backup | coordinate_type | bool | positions.yaml→data/jig_mark 복사 | services/coordinate_system_manager.py:277 |
| 19 | .load_from_config | - | bool | 정의·current 로드 | services/coordinate_system_manager.py:307 |
| 20 | .get_system_type | name | Optional[str] | 타입 조회 | services/coordinate_system_manager.py:329 |
| 21 | .get_system_names | - | List[str] | 지원 좌표계 사본 | services/coordinate_system_manager.py:332 |
| 22 | .get_definition | name | Optional[dict] | 정의 사본 | services/coordinate_system_manager.py:335 |
| 23 | .reset_to_defaults | name=None | bool | 일부/전체 기본화 | services/coordinate_system_manager.py:342 |
| 24 | .set_ros_node | ros_node | None | TF broadcaster 준비 | services/coordinate_system_manager.py:358 |
| 25 | ._euler_to_quaternion | rx,ry,rz (deg) | (qx,qy,qz,qw) | RPY→쿼터니언 | services/coordinate_system_manager.py:365 |
| 26 | ._create_transform_stamped | parent, child, pose(mm/deg) | TransformStamped | mm→m 변환 TF 생성 | services/coordinate_system_manager.py:385 |
| 27 | .publish_tf | - | bool | TF 트리(랜드마크·플레이트·마크4) 발행 | services/coordinate_system_manager.py:412 |
| 28 | ._calculate_center_pose | scan_data_list | Optional[dict] | 랜드마크 산술 평균 중심 | services/coordinate_system_manager.py:479 |
| 29 | ._calculate_relative_pose | parent_pose, child_pose | dict | 성분별 차감 상대 pose | services/coordinate_system_manager.py:510 |
| 30 | .start_tf_publishing | interval_sec=1.0 | bool | create_timer 주기 발행 | services/coordinate_system_manager.py:530 |
| 31 | .stop_tf_publishing | - | None | 타이머 취소 | services/coordinate_system_manager.py:544 |
| 32 | ._tf_timer_callback | - | None | enabled 시 publish_tf | services/coordinate_system_manager.py:551 |
| 33 | .compute_jig_plate_coordinates | - | bool | 4점→평면 pose 계산·저장 | services/coordinate_system_manager.py:556 |
| 34 | .get_computed_data | name | Optional[dict] | computed 결과 | services/coordinate_system_manager.py:592 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | ROS2_AVAILABLE (상수) | set_ros_node, publish_tf 등 | tf2_ros import 성공 여부 | services/coordinate_system_manager.py:11-18 |
| 2 | SUPPORTED_SYSTEMS/SYSTEM_TYPES/DEFAULT_TOOL_POSE/TF_FRAME_* (클래스 상수) | 전반 | 좌표계 정의 테이블 | services/coordinate_system_manager.py:31-64 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/coordinate_transformer.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .velocity_percent_to_service | motion_type: int, percent | float | %→m/s 또는 rad/s | services/coordinate_transformer.py:17 |
| 2 | .euler_to_rotation_matrix | rx,ry,rz (rad) | 3x3 list | ZYX 회전행렬 | services/coordinate_transformer.py:25 |
| 3 | .quaternion_to_euler | qx,qy,qz,qw | (rx,ry,rz) deg | 쿼터니언→오일러 | services/coordinate_transformer.py:39 |
| 4 | .transform_tool_to_base | tool_delta, tcp_orientation(deg) | List[float] | 공구 변위→베이스 변위 | services/coordinate_transformer.py:58 |
| 5 | .angle_difference_deg | target, current | float | 최단 각도차 절댓값 | services/coordinate_transformer.py:76 |
| 6 | .deg_to_rad / 7 .rad_to_deg | angle | float | 단위 변환 | services/coordinate_transformer.py:82,86 |
| 8 | .mm_to_m / 9 .m_to_mm | value | float | 단위 변환 | services/coordinate_transformer.py:90,94 |
| 10 | .convert_tcp_to_service_format | tcp_pose(mm/deg) | List[float](m/rad) | 서비스 포맷 | services/coordinate_transformer.py:98 |
| 11 | .convert_joint_to_service_format | joint_pose(deg) | List[float](rad) | 서비스 포맷 | services/coordinate_transformer.py:110 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | MAX_JOINT_VELOCITY (상수) | velocity_percent_to_service | π rad/s 상한 | services/coordinate_transformer.py:5 |
| 2 | MAX_TCP_SPEED (상수) | 〃 | 1.0 m/s 상한 | services/coordinate_transformer.py:6 |
| 3 | _MOTION_LINE_T (상수) | 〃 | LINE_T=4 매직값 | services/coordinate_transformer.py:11 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/decomposed_move_planner.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | build_decomposed_tcp_waypoints | current_pose: List[6], target: List[6] | ([(label, pose)], order_label) | 축 분해 경유점 생성 | services/decomposed_move_planner.py:12 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | DECOMPOSED_MIN_STEP_MM (상수) | #1 | 0.1mm 최소 이동 | services/decomposed_move_planner.py:8 |
| 2 | DECOMPOSED_MIN_STEP_DEG (상수) | #1 | 0.1° 최소 회전 | services/decomposed_move_planner.py:9 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/gripper_override_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node, log_callback=None | - | 노드·로그 보관 | services/gripper_override_service.py:24 |
| 2 | ._smc_client | - | Optional | node.gripper_action_client | services/gripper_override_service.py:29 |
| 3 | ._schunk_client | - | Optional | node.schunk_gripper_client | services/gripper_override_service.py:32 |
| 4 | .backends | - | List[str] | 존재 백엔드 나열 | services/gripper_override_service.py:35 |
| 5 | .available | - | bool | 백엔드 존재 여부 | services/gripper_override_service.py:44 |
| 6 | .unavailable_reason | - | str | 불가 사유 문구 | services/gripper_override_service.py:47 |
| 7 | .force_release | timeout_sec=30 | (bool, str) | SMC→SCHUNK 순 시도 | services/gripper_override_service.py:54 |
| 8 | ._force_release_smc | timeout_sec | (state, reason) | 액션 goal 전송·결과 대기 | services/gripper_override_service.py:84 |
| 9 | ._force_release_schunk | timeout_sec | (state, reason) | 서비스 call·received 확인 | services/gripper_override_service.py:132 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | GRIPPER_ACTION_TIMEOUT_SEC (상수) | force_release | 30초 결과 대기 | services/gripper_override_service.py:4 |
| 2 | _SERVER_WAIT_SEC/_GOAL_ACCEPT_WAIT_SEC (상수) | _force_release_* | 3s/5s 대기 | services/gripper_override_service.py:5-6 |
| 3 | _OK/_UNAVAILABLE/_FAILED (상수) | 3상 판정 | 상태 문자열 | services/gripper_override_service.py:9 |
| 4 | SCHUNK_RELEASE_COMMAND (상수) | _force_release_schunk | command=2 | services/gripper_override_service.py:12 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/handeye_test_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | job_executor=None, vision_manager=None, log_callback=None | - | 상태·콜백 초기화 | services/handeye_test_manager.py:17 |
| 2 | ._log | message | None | 콜백 로그 | services/handeye_test_manager.py:41 |
| 3 | .generate_positions | base_position, x_step,x_count, y_step,y_count, z_step,z_count | List[dict] | 그리드 생성 | services/handeye_test_manager.py:46 |
| 4 | ._generate_xy_offsets | step, count | List[float] | -count..count 오프셋 | services/handeye_test_manager.py:73 |
| 5 | ._generate_z_offsets | step, count | List[float] | 0..count-1 오프셋 | services/handeye_test_manager.py:79 |
| 6 | ._generate_zigzag_xy | base, x_offsets, y_offsets, z_off | List[dict] | 지그재그 순회 | services/handeye_test_manager.py:85 |
| 7 | .add_position / 8 .remove_position / 9 .clear_positions / 10 .get_positions | pos/index | - | 위치 목록 CRUD | services/handeye_test_manager.py:110,113,117,120 |
| 11 | .save_positions | filename | bool | yaml 저장 | services/handeye_test_manager.py:124 |
| 12 | .load_positions | filename | bool | yaml 로드 | services/handeye_test_manager.py:138 |
| 13 | .start_test | repeat_count=3, scan_delay_sec=0.5 | (bool,str) | 실행 상태 초기화 | services/handeye_test_manager.py:153 |
| 14 | .stop_test / 15 .reset_test | - | None | 중지/초기화 | services/handeye_test_manager.py:174,178 |
| 16 | .run_single_measurement | - | (bool, Optional[dict], str) | 1스텝: 이동→스캔→기록→전진 | services/handeye_test_manager.py:185 |
| 17 | ._move_to_position | pos: dict | (bool,str) | 안전구역 검사+Line CPP 스크립트 전송 | services/handeye_test_manager.py:245 |
| 18 | ._execute_landmark_scan | - | (bool, dict) | vision_manager 스캔+읽기 | services/handeye_test_manager.py:298 |
| 19 | .get_current_tcp | - | List[6] | 노드 TCP 또는 0벡터 | services/handeye_test_manager.py:323 |
| 20 | ._get_current_tcp | - | List[6] | #19 위임 | services/handeye_test_manager.py:331 |
| 21 | ._advance_to_next | - | None | 위치/반복 인덱스 전진 | services/handeye_test_manager.py:334 |
| 22 | .is_test_complete | - | bool | 반복 완료 여부 | services/handeye_test_manager.py:342 |
| 23 | .get_total_measurements | - | int | 위치수×반복수 | services/handeye_test_manager.py:345 |
| 24 | .calculate_statistics | - | dict | 위치별 Y/Ry mean·std + 위치간 range | services/handeye_test_manager.py:349 |
| 25 | .format_statistics_text | - | str | 통계 텍스트 | services/handeye_test_manager.py:397 |
| 26 | .export_to_csv | filename | bool | 측정 CSV 저장 | services/handeye_test_manager.py:416 |
| 27 | .get_default_csv_path | - | str | install/build 경로 역산 저장 경로 | services/handeye_test_manager.py:445 |
| 28 | .get_measurements | - | List[dict] | 측정 원본 | services/handeye_test_manager.py:470 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/image_capture_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | ImageCaptureWorker.__init__ | ros_node, gv_manager, timeout_sec=3.0 | - | 파라미터 보관 | services/image_capture_service.py:30 |
| 2 | ImageCaptureWorker.stop | - | None | 중단 플래그 | services/image_capture_service.py:37 |
| 3 | ImageCaptureWorker.run | - | None | 캡처 시퀀스 본체 | services/image_capture_service.py:41 |
| 3a | run._send (이너) | - | (bool,str) | g_robot_command=3 + ScriptExit | services/image_capture_service.py:53 |
| 4 | ImageCaptureService.__init__ | ros_node=None, gv_manager=None | - | 워커·최종이미지 초기화 | services/image_capture_service.py:108 |
| 5 | .set_ros_node / 6 .set_gv_manager | node/manager | None | 주입 | services/image_capture_service.py:115,118 |
| 7 | .last_captured_image (property) | - | Optional[np.ndarray] | 최종 이미지 | services/image_capture_service.py:121 |
| 8 | .is_capturing (property) | - | bool | 워커 실행 중 | services/image_capture_service.py:125 |
| 9 | .capture_image | timeout_sec=3.0 | None | 중복 방지 후 워커 기동 | services/image_capture_service.py:129 |
| 10 | .cancel_capture | - | None | stop+wait(1s) | services/image_capture_service.py:155 |
| 11 | ._on_image_ready | cv_image | None | 보관+image_captured emit | services/image_capture_service.py:163 |
| 12 | ._on_error | error_msg | None | capture_error 중계 | services/image_capture_service.py:167 |
| 13 | ._on_worker_finished | - | None | 워커 해제+finished emit | services/image_capture_service.py:170 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | VISION_CAPTURE_COMMAND_VAR (상수) | run._send | 'g_robot_command' | services/image_capture_service.py:13 |
| 2 | VISION_CAPTURE_COMMAND (상수) | run._send | 3 (캡처 잡) | services/image_capture_service.py:14 |
| 2 | ERR_TIMEOUT/ERR_STOPPED (상수) | wait_after | 오류 문구('중단 요청' 은 image_capture_service.py:82 과 결합) | services/image_frame_cache.py:10-11 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/image_frame_cache.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | max_frames=16 | - | 락·deque·시퀀스 초기화 | services/image_frame_cache.py:24 |
| 2 | .push | frame | int(seq) | 프레임 추가+시퀀스 증가 | services/image_frame_cache.py:30 |
| 3 | .baseline | - | int | 현재 시퀀스 | services/image_frame_cache.py:38 |
| 4 | .peek | - | (frame, seq, at) | 최신 프레임 조회 | services/image_frame_cache.py:43 |
| 5 | .take_after | baseline: int | Optional[frame] | baseline 초과 첫 프레임 | services/image_frame_cache.py:51 |
| 6 | .wait_after | baseline, timeout_sec, should_stop=None, on_poll=None, poll_interval=0.05 | (frame, err) | 폴링 대기 | services/image_frame_cache.py:59 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | POLL_INTERVAL_SEC (상수) | wait_after | 0.05s 폴링 | services/image_frame_cache.py:7 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/image_processing_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | gv_manager=None, ros_node=None | - | 상태 초기화 | services/image_processing_service.py:23 |
| 2 | .apply_threshold | image, threshold_value | Optional[np.ndarray] | 이진화+시그널 | services/image_processing_service.py:29 |
| 3 | .save_image | file_path | bool | imwrite 저장 | services/image_processing_service.py:49 |
| 4 | .get_processed_image | - | Optional | 처리 결과 | services/image_processing_service.py:65 |
| 5 | .has_processed_image | - | bool | 존재 여부 | services/image_processing_service.py:68 |
| 6 | .capture_techman_image | timeout_sec=3.0 | bool | 동기 캡처 시퀀스 | services/image_processing_service.py:71 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/io_control_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node | - | 상태 배열·그리퍼 설정 로드 | services/io_control_service.py:40 |
| 2 | ._load_gripper_config | - | dict | io_config.yaml 의 gripper 절 (실패 시 기본) | services/io_control_service.py:56 |
| 3 | .cb_di / 4 .cb_do / 5 .ee_di / 6 .ee_do (property) | - | List[bool] | 상태 사본 | services/io_control_service.py:78,82,86,90 |
| 7 | .update_io_state | cb_di, cb_do, ee_di, ee_do, cb_ai=None, ee_ai=None | None | 정규화·변경 시 시그널 | services/io_control_service.py:95 |
| 8 | ._normalize_list | data, expected_len | List[bool] | 길이 맞춤 bool화 | services/io_control_service.py:138 |
| 9 | .set_digital_output | module, pin, state | bool | SetIO call_async | services/io_control_service.py:147 |
| 10 | .set_cb_do / 11 .set_ee_do | pin, state | bool | 모듈 고정 위임 | services/io_control_service.py:171,174 |
| 12 | .grip / 13 .release | - | bool | 설정 핀 True 펄스 없음 단발 set | services/io_control_service.py:180,186 |
| 14 | .read_digital_input | di_name: str | (bool, Optional[bool], str) | 이름 파싱 캐시 읽기 | services/io_control_service.py:192 |
| 15 | .write_digital_output_by_name | do_name, state('ON'/'OFF') | (bool, str) | 이름 파싱 DO 쓰기 | services/io_control_service.py:214 |
| 16 | .read_analog_input | ai_name | (bool, Optional[float], str) | 이름 파싱 AI 읽기 | services/io_control_service.py:235 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | CB_DI_COUNT 등 카운트 (클래스 상수) | 전반 | 핀 수 정의 | services/io_control_service.py:27-33 |
| 2 | MODULE_CONTROL_BOX/END_MODULE, IO_TYPE_DO (클래스 상수) | set_digital_output | SetIO 인코딩 | services/io_control_service.py:36-38 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/jog_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node=None, teaching_service=None, move_callback=None, command_gate=None | - | 의존 주입·기본 파라미터 | services/jog_service.py:20 |
| 2 | .set_ros_node / 3 .set_move_callback | node/callback | None | 주입 갱신 | services/jog_service.py:31,34 |
| 4 | .get_params | - | (step_mm, velocity%) | 파라미터 조회 | services/jog_service.py:37 |
| 5 | .set_params | step_mm=None, velocity_percent=None | bool | 변경 시 params_changed emit | services/jog_service.py:40 |
| 6 | ._current_tcp_pose | - | Optional[List] | node.current_tcp_pose | services/jog_service.py:58 |
| 7 | ._prepare | - | (bool, pose, err) | 의존·위치 사전 검사 | services/jog_service.py:63 |
| 8 | ._log_intent | kind, axis, direction | None | 노드 로거 기록 | services/jog_service.py:76 |
| 9 | ._acquire / 10 ._release | label | bool/None | CommandGate 점유/해제 | services/jog_service.py:85,90 |
| 11 | .jog | axis, direction | bool | 게이트+단발 조그 | services/jog_service.py:94 |
| 12 | ._jog | axis, direction | bool | TeachingService.jog_tcp 위임 | services/jog_service.py:104 |
| 13 | .jog_continuous | axis, direction | bool | 게이트+연속 조그 | services/jog_service.py:119 |
| 14 | ._jog_continuous | axis, direction | bool | jog_tcp_continuous 위임 | services/jog_service.py:129 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | JOG_STEP_MM_DEFAULT (상수) | __init__ | 10.0mm | services/jog_service.py:6 |
| 2 | JOG_VELOCITY_PERCENT_DEFAULT (상수) | __init__ | 20% | services/jog_service.py:7 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/joystick_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | JoystickWorker.__init__ | device_path | - | 경로·플래그 | services/joystick_service.py:25 |
| 2 | JoystickWorker.run | - | None | select 루프→이벤트 해석→시그널 | services/joystick_service.py:30 |
| 3 | JoystickWorker.stop | - | None | 루프 종료 플래그 | services/joystick_service.py:75 |
| 4 | JoystickService.__init__ | config_path=None | - | 설정 로드·타이머 2종 준비 | services/joystick_service.py:117 |
| 5 | ._load_config | config_path | dict | yaml 로드 실패 시 DEFAULT_CONFIG.copy() | services/joystick_service.py:134 |
| 6 | .get_jog_step_mm / 7 .get_jog_step_deg / 8 .get_jog_velocity / 9 .get_current_mode | - | float/str | 설정·모드 조회 | services/joystick_service.py:149,152,155,158 |
| 10 | .start | - | None | 워커 생성·시그널 연결·기동 | services/joystick_service.py:162 |
| 11 | .stop | - | None | 타이머·워커 정지 | services/joystick_service.py:177 |
| 12 | .set_enabled | enabled: bool | None | 조그 타이머 on/off | services/joystick_service.py:187 |
| 13 | ._on_axis_changed | axis_id, value | None | 데드맨 판정·모드 전환·값 저장 | services/joystick_service.py:200 |
| 14 | ._on_button_changed | button_id, pressed | None | (미사용 pass) | services/joystick_service.py:239 |
| 15 | ._on_connection_changed | connected | None | 재연결 타이머 기동 | services/joystick_service.py:242 |
| 16 | ._on_error | message | None | status_changed 중계 | services/joystick_service.py:249 |
| 17 | ._try_reconnect | - | None | 장치 재출현 시 stop→start | services/joystick_service.py:252 |
| 18 | ._process_jog | - | None | 활성 모드 축별 jog_requested emit | services/joystick_service.py:260 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | JS_EVENT_SIZE/FORMAT (상수) | run | 8바이트 'IhBB' | services/joystick_service.py:10-11 |
| 2 | JS_EVENT_BUTTON/AXIS/INIT (상수) | run | 이벤트 타입 비트 | services/joystick_service.py:12-14 |
| 3 | DEFAULT_CONFIG (클래스 상수) | _load_config 등 | 장치·데드존·축맵·조그 기본 | services/joystick_service.py:94-115 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/landmark_analyzer.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | circular_mean_deg | values | float | atan2 기반 원형 평균 | services/landmark_analyzer.py:27 |
| 2 | angle_deviation_deg | values, center | np.ndarray | ±180 정규화 편차 | services/landmark_analyzer.py:35 |
| 3 | circular_std_deg | values | float | 원형 표준편차 | services/landmark_analyzer.py:41 |
| 4 | LandmarkAnalyzer.__init__ | - | - | 측정 리스트 | services/landmark_analyzer.py:54 |
| 5 | .reset | - | None | 초기화 | services/landmark_analyzer.py:57 |
| 6 | .add_measurement | x..rz | None | 측정 추가(타임스탬프) | services/landmark_analyzer.py:60 |
| 7 | ._get_values_array | target='xyz' | np.ndarray | 3열/6열 행렬 | services/landmark_analyzer.py:66 |
| 8 | ._filter_by_mask | mask | List | 마스크 필터 | services/landmark_analyzer.py:75 |
| 9 | .remove_outliers_iqr | target='xyz' | List | 열별 IQR 1.5 필터 (<4건 통과) | services/landmark_analyzer.py:78 |
| 10 | .remove_outliers_3sigma | target='xyz' | List | 열별 3σ 필터 (<3건 통과) | services/landmark_analyzer.py:100 |
| 11 | .analyze | method='none', target='xyz' | Dict | 평균·표준편차·제거 수 | services/landmark_analyzer.py:122 |
| 12 | .get_final_pose | method='none', target='xyz' | Dict | 최종 pose+detected | services/landmark_analyzer.py:178 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | ANGLE_COLUMNS (상수) | (선언만, 직접 사용처 없음) | 각도 열 이름 | services/landmark_analyzer.py:24 |
| 2 | ANGLE_COLUMN_START (클래스 상수) | remove_outliers_* | 3번째 열부터 각도 | services/landmark_analyzer.py:52 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/magazine_state_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node | - | 가용성 판정+구독 생성 | services/magazine_state_service.py:29 |
| 2 | ._make_qos | - | QoSProfile | RELIABLE·VOLATILE·KEEP_LAST·depth10 | services/magazine_state_service.py:49 |
| 3 | ._on_state | msg: MagazineState | None | 상태 캐시+시그널 | services/magazine_state_service.py:60 |
| 4 | .is_valid | - | bool | 수신됨∧valid | services/magazine_state_service.py:67 |
| 5 | .slot_present | slot: int | Optional[bool] | 슬롯 재고 (무효 시 None) | services/magazine_state_service.py:71 |
| 6 | .present_list | - | List[bool] | 재고 사본 | services/magazine_state_service.py:79 |
| 7 | .slot_name | slot | str | 한국어 슬롯명 | services/magazine_state_service.py:82 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | _MagazineState (상수/모듈) | __init__ | try import 결과 (없으면 None) | services/magazine_state_service.py:7-10 |
| 2 | SLOT_COUNT/SLOT_NAMES/TOPIC (클래스 상수) | 전반 | 6슬롯·이름·토픽 | services/magazine_state_service.py:23-27 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/motion_gateway.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | guard, tcp_pose_fn=None, monitor=None, log_callback=None | - | 의존 주입 | services/motion_gateway.py:19 |
| 2 | .guard (property) / 3 .monitor (property) | - | MotionGuard/monitor | 접근자 | services/motion_gateway.py:28,32 |
| 4 | .set_monitor | monitor | None | 감시자 주입 | services/motion_gateway.py:36 |
| 5 | ._log | message | None | 콜백 로그 | services/motion_gateway.py:39 |
| 6 | ._tcp_pose | - | Optional[Sequence] | tcp_pose_fn 안전 호출 | services/motion_gateway.py:43 |
| 7 | ._clear_stopped_state | - | None | STOPPED→reset (갇힘 탈출) | services/motion_gateway.py:51 |
| 8 | ._watching (contextmanager) | - | yield | monitor.start/stop 괄호 | services/motion_gateway.py:57 |
| 9 | .check | kind, target_mm, offset_mm, label | GuardDecision | 검사만 | services/motion_gateway.py:69 |
| 10 | .send | kind, sender, target_mm, offset_mm, label, watch=True | (bool,str) | 검사+감시+송신 본체 | services/motion_gateway.py:77 |
| 11 | .send_line | sender, target_mm, label='Line', watch | (bool,str) | LINE 송신 | services/motion_gateway.py:106 |
| 12 | .send_line_relative | sender, offset_mm, label, watch | (bool,str) | 상대 LINE | services/motion_gateway.py:111 |
| 13 | .send_ptp_tcp | sender, target_mm=None, label, watch | (bool,str) | PTP(구역 활성 시 거부됨) | services/motion_gateway.py:116 |
| 14 | .send_ptp_joint | sender, label, watch | (bool,str) | PTP_J | services/motion_gateway.py:121 |
| 15 | .send_vision_job | sender, label, watch | (bool,str) | 비전 잡(미검사 허용) | services/motion_gateway.py:125 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | Sender (상수, 타입 별칭) | 시그니처 | Callable[[], (bool,str)] | services/motion_gateway.py:9 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/network_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .get_all_network_interfaces | - | List[dict] | 인터페이스 나열·분류 | services/network_manager.py:11 |
| 2 | .get_local_ip | preferred_wired=True | str | 우선순위 IP 선택 (없으면 127.0.0.1) | services/network_manager.py:43 |
| 3 | .scan_for_robot | local_ip=None, ports=[5890,5891], timeout=0.1, max_workers=50 | List[str] | 서브넷 포트 스캔 | services/network_manager.py:70 |
| 3a | scan_for_robot.check_port (이너) | ip, port | Optional[str] | connect_ex 검사 | services/network_manager.py:94 |
| 4 | .parse_subnet | ip | str | 앞 3옥텟 | services/network_manager.py:120 |
| 5 | .is_valid_ip | ip | bool | IPv4 형식 검증 | services/network_manager.py:128 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/offset_preset_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | config_path=None | - | 기본: services/../..(=패키지)/config/plane_align_offsets.yaml | services/offset_preset_service.py:19 |
| 2 | ._load_all | - | Dict[str, Dict] | 파일 로드+정규화 (실패 시 {}) | services/offset_preset_service.py:27 |
| 3 | ._normalize | values: Dict | Dict[str,float] | 키별 float 화 (실패 0.0) | services/offset_preset_service.py:48 |
| 4 | .list_names | - | List[str] | 정렬된 이름 | services/offset_preset_service.py:59 |
| 5 | .get | name | Optional[Dict] | 단일 조회 | services/offset_preset_service.py:62 |
| 6 | .save | name, offset | (bool,str) | 저장/덮어쓰기 | services/offset_preset_service.py:65 |
| 7 | .delete | name | (bool,str) | 삭제 | services/offset_preset_service.py:82 |
| 8 | ._write | presets | (bool,str) | yaml 재기록 | services/offset_preset_service.py:95 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | DEFAULT_PRESET_FILENAME (상수) | __init__ | 파일명 | services/offset_preset_service.py:9 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/pallet_recipe_generator.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | _round_pose | pose, digits=3 | Dict | 6축 반올림 | services/pallet_recipe_generator.py:56 |
| 2 | _radius_3d | pose | float | 원점 거리 | services/pallet_recipe_generator.py:60 |
| 3 | snap_rotation_to_plane | pose | Dict | rx=180,ry=0,rz 90° 스냅 | services/pallet_recipe_generator.py:66 |
| 4 | PalletRecipeGenerator.__init__ | recipe_dir=None, package_root=None, gripper=SCHUNK, descent='plane_normal' | - | 경로·그리퍼·하강모드 확정 (모드 오류 ValueError) | services/pallet_recipe_generator.py:84 |
| 5 | .emit | pallet_name, mount, plate_pose, teach_poses, scan_start_tcp, marker_pose, marker_view_tcp, plate_marks, pitch/trim, operator, snap_rotation=False, overwrite=False | List[str] | 검증→문서 생성→파일 기록 | services/pallet_recipe_generator.py:103 |
| 6 | ._validate (static) | name, mount, plate_pose, teach_poses, marker_pose | None(raise) | 이름 패턴·마운트·티칭 검증 | services/pallet_recipe_generator.py:173 |
| 7 | ._header (static) | name, summary, operator | Dict | 레시피 헤더 | services/pallet_recipe_generator.py:193 |
| 8 | ._job (static) | job_id, job_type, name, caption, params | Dict | 잡 dict | services/pallet_recipe_generator.py:204 |
| 9 | ._renumber (static) | jobs | List | id 1..N 재부여 | services/pallet_recipe_generator.py:213 |
| 10 | ._recipe_info | job_id, description, operator | Dict | recipe_info 잡 | services/pallet_recipe_generator.py:220 |
| 11 | ._grip_job | job_id, closing, caption='' | Dict | 백엔드별 파지/놓기 잡 | services/pallet_recipe_generator.py:229 |
| 12 | ._settle_job | job_id | Dict | 2000ms 대기 잡 | services/pallet_recipe_generator.py:234 |
| 13 | ._linear_job | job_id, caption, dz_mm, velocity_mms | Dict | 공구축 직선 잡 | services/pallet_recipe_generator.py:238 |
| 14 | ._fixed_cali | pallet_name, scan_start_tcp, pitch, trim, operator | Dict | 4점 측정 캘리 레시피 | services/pallet_recipe_generator.py:248 |
| 15 | ._write_plate_snapshot | pallet_name, plate_pose, plate_marks, operator | str(path) | 측정 스냅샷 yaml | services/pallet_recipe_generator.py:306 |
| 16 | ._load_plate_job | job_id, pallet_name | Dict | plate_pose 로드 잡 (직사각 가드 파라미터) | services/pallet_recipe_generator.py:338 |
| 17 | ._plane_motion | pallet_name, teach_poses, slot, operator, snap_rotation | Dict | 고정식 픽/플레이스 레시피 | services/pallet_recipe_generator.py:351 |
| 17a | ._plane_motion.plane_job (이너) | job_id, caption, pose, velocity, straight, decel | Dict | 평면좌표 이동 잡 | services/pallet_recipe_generator.py:367 |
| 18 | ._marker_scan | pallet_name, marker_view_tcp, operator | Dict | 마커 스캔 레시피 | services/pallet_recipe_generator.py:448 |
| 18a | ._marker_scan.point_job (이너) | job_id, caption, z | Dict | 포인트 이동 잡 | services/pallet_recipe_generator.py:455 |
| 19 | ._landmark_motion | pallet_name, marker_pose, teach_poses, slot, operator, snap_rotation | Dict | 비고정식 픽/플레이스 레시피 | services/pallet_recipe_generator.py:491 |
| 19a | ._landmark_motion.landmark_job (이너) | job_id, caption, pose, velocity, decel | Dict | 마커좌표 이동 잡 | services/pallet_recipe_generator.py:519 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | CORNER_PLAN (상수) | _fixed_cali | 4점 순회 계획 (pallet_teach.DEFAULT_CORNER_PLAN 과 동일값 중복) | services/pallet_recipe_generator.py:19 |
| 2 | MOUNT_FIXED/FLOATING/MOUNTS (상수) | emit/_validate | 마운트 종류 | services/pallet_recipe_generator.py:21-23 |
| 3 | NAME_PATTERN (상수) | _validate | 이름 정규식 | services/pallet_recipe_generator.py:25 |
| 4 | APPROACH_LIFT_MM~GRIP_SETTLE_MS 군 (상수) | 잡 생성 전반 | 리프트·속도·감속·타임아웃 파라미터 | services/pallet_recipe_generator.py:30-40 |
| 5 | DESCENT_* / TCP_*_VELOCITY_MMS / MARKER_VIEW_LIFT_MM / RADIUS_MARGIN_MM / DEFAULT_SCAN_VELOCITY (상수) | 잡 생성 | 하강 모드·속도 | services/pallet_recipe_generator.py:42-53 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/plate_pose_dataset.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | AxisStat.value_range (property) | - | float | max-min | services/plate_pose_dataset.py:43 |
| 2 | normalize_jig_order | marks: List[dict] | List[dict] | 표준 jig 순서 정렬 | services/plate_pose_dataset.py:48 |
| 3 | PlatePoseDataset.__init__ | - | - | root/records/pallet/variant | services/plate_pose_dataset.py:72 |
| 4 | .default_root (static) | - | Path | paths.DATA_DIR/plate_pose_calc | services/plate_pose_dataset.py:78 |
| 5 | .set_root | root_path | bool | 루트 설정+팔레트 존재 확인 | services/plate_pose_dataset.py:83 |
| 6 | .list_pallets | - | List[str] | 하위 디렉토리 나열 | services/plate_pose_dataset.py:91 |
| 7 | ._variant_files | pallet, variant | List[Path] | raw/corrected 파일 목록 | services/plate_pose_dataset.py:96 |
| 8 | .load | pallet, variant='corrected' | (bool,str) | 전 파일 파싱·요약 | services/plate_pose_dataset.py:104 |
| 9 | ._parse_file | path | Optional[PlateRecord] | yaml→레코드 (jig1~4 필수) | services/plate_pose_dataset.py:136 |
| 10 | .jig_series | jig_index | Dict[axis, List] | 축별 시계열 | services/plate_pose_dataset.py:168 |
| 11 | .jig_deviation_series | jig_index | Dict[axis, List] | 중심 편차(각도 원형) | services/plate_pose_dataset.py:177 |
| 12 | .jig_statistics | jig_index | List[AxisStat] | 축별 통계 (PrecisionTestManager 재사용) | services/plate_pose_dataset.py:196 |
| 13 | .all_statistics | - | List[AxisStat] | 4개 jig 통계 | services/plate_pose_dataset.py:234 |
| 14 | .mean_marks | - | List[dict] | jig 별 평균 마크 | services/plate_pose_dataset.py:240 |
| 15 | .build_validator | marks=None | Optional[JigPlateValidator] | 검증기 구성 | services/plate_pose_dataset.py:253 |
| 16 | .geometry_report | marks=None | (변길이, 결과) | 직사각/Z 검사 | services/plate_pose_dataset.py:264 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | JIG_KEYS/POSE_AXES/ANGLE_AXES (상수) | 파싱·통계 | 키 정의 | services/plate_pose_dataset.py:12-14 |
| 2 | DATASET_DIR_NAME/CORRECTED_SUBDIR (상수) | 경로 | 디렉토리명 | services/plate_pose_dataset.py:15-16 |
| 3 | VARIANT_RAW/CORRECTED (상수) | load/_variant_files | 변형 종류 | services/plate_pose_dataset.py:18-19 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/precision_test_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | MeasurementData.__init__ | x..rz, tcp_x..tcp_rz=0, timestamp=None | - | 측정 레코드 | services/precision_test_manager.py:10 |
| 2 | MeasurementData.to_dict | - | Dict | dict 화 | services/precision_test_manager.py:28 |
| 3 | Statistics.__init__ | - | - | mean/std/3σ 18필드 0 초기화 | services/precision_test_manager.py:49 |
| 4 | PrecisionTestManager.__init__ | - | - | 상태·콜백 초기화 | services/precision_test_manager.py:81 |
| 5 | ._log | message | None | on_log 콜백 | services/precision_test_manager.py:99 |
| 6 | .reset | - | None | 측정·통계 초기화 | services/precision_test_manager.py:103 |
| 7 | .add_measurement | x..rz, tcp_* | None | 추가+통계 갱신 | services/precision_test_manager.py:109 |
| 8 | ._update_statistics | - | None | 평균·표준편차·3σ 재계산 | services/precision_test_manager.py:119 |
| 9 | .get_statistics | - | Statistics | 통계 반환 | services/precision_test_manager.py:152 |
| 10 | .get_measurements_as_arrays | - | Dict[str,List] | 축별 배열 | services/precision_test_manager.py:155 |
| 11 | .export_to_csv | filepath | bool | 측정+통계 CSV | services/precision_test_manager.py:165 |
| 12 | .get_progress_percentage | - | float | 진행률 | services/precision_test_manager.py:219 |
| 13 | .start_dynamic_test | recipe, job_executor, ros_node | (bool,str) | measure_point(end) 검증 후 시작 | services/precision_test_manager.py:225 |
| 14 | .run_next_iteration | - | None | 콜백 배선+레시피 재실행 | services/precision_test_manager.py:249 |
| 15 | ._on_executor_state_changed | state | None | COMPLETED→on_recipe_completed | services/precision_test_manager.py:268 |
| 16 | .on_measure_point_reached | - | None | TCP 기록+콜백 | services/precision_test_manager.py:275 |
| 17 | .on_recipe_completed | - | None | 종료/다음 반복 판단 | services/precision_test_manager.py:291 |
| 18 | ._finish_test | - | None | 종료 처리+콜백 | services/precision_test_manager.py:304 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/robot_motion_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | is_tm_joint_state | names, positions | bool | TM 조인트 상태 판별 | services/robot_motion_service.py:10 |
| 2 | .__init__ | - | - | 상태 초기화 | services/robot_motion_service.py:32 |
| 3 | .current_joint_position (property) | - | Optional[List] | 조인트(deg) | services/robot_motion_service.py:50 |
| 4 | .current_tcp_pose (property) | - | Optional[List] | TCP(mm/deg) | services/robot_motion_service.py:54 |
| 5 | .current_base_name (property+setter) | -/value | str/- | 현재 좌표계명 | services/robot_motion_service.py:58,62 |
| 6 | .is_moving (property) | - | bool | 이동 중 | services/robot_motion_service.py:66 |
| 7 | .target_position (property+setter) | -/value | Optional[List] | 목표(서비스 단위 m/rad) | services/robot_motion_service.py:70,74 |
| 8 | .last_position_error / 9 .last_rotation_error / 10 .last_joint_error (property) | - | Optional[List] | 최근 오차 | services/robot_motion_service.py:78,82,86 |
| 11 | .update_joint_state | positions_rad | None | rad→deg 캐시+시그널 | services/robot_motion_service.py:91 |
| 12 | .update_tcp_pose | x_m..qw | None | m→mm·쿼터니언→오일러+시그널 | services/robot_motion_service.py:99 |
| 13 | .update_feedback_state | tcp_speed, joint_vel | None | 속도 놈→이동 판정+시그널 | services/robot_motion_service.py:111 |
| 14 | .check_motion_complete | - | bool | 목표 대비 허용오차+정지 판정 | services/robot_motion_service.py:132 |
| 15 | .get_motion_complete_message | - | str | 오차 요약 문구 | services/robot_motion_service.py:186 |
| 16 | .clear_motion_state | - | None | 목표·오차 소거 | services/robot_motion_service.py:198 |
| 17 | ._quaternion_to_euler_deg (static) | qx..qw | (rx,ry,rz) | 쿼터니언→오일러 | services/robot_motion_service.py:206 |
| 18 | ._normalize_angle_deg (static) | angle | float | ±180 정규화(while 루프) | services/robot_motion_service.py:225 |
| 19 | ._angle_difference_deg | target, current | float | 최단 각도차 | services/robot_motion_service.py:233 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | TM_JOINT_NAMES (상수) | is_tm_joint_state | joint_1..6 이름 튜플 | services/robot_motion_service.py:7 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/robot_stop_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | node, log_callback=None | - | 지연 클라이언트 | services/robot_stop_service.py:17 |
| 2 | ._log | message | None | 콜백 로그 | services/robot_stop_service.py:22 |
| 3 | ._get_client | - | Optional[client] | SetEvent 클라이언트 지연 생성 | services/robot_stop_service.py:26 |
| 4 | ._request | func_value: int | SetEvent.Request | func/arg0/arg1 구성 | services/robot_stop_service.py:35 |
| 5 | ._send | func_value, what, timeout_sec=0.5 | (bool,str) | wait_for_service+call_async | services/robot_stop_service.py:43 |
| 6 | .stop | - | (bool,str) | STOP 전송 | services/robot_stop_service.py:57 |
| 7 | .pause | - | (bool,str) | PAUSE 전송 | services/robot_stop_service.py:61 |
| 8 | .resume | - | (bool,str) | RESUME 전송 | services/robot_stop_service.py:65 |
| 9 | .stop_sync | timeout_sec=3.0 | (bool,str) | STOP 동기 확인 | services/robot_stop_service.py:69 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | SERVICE_NAME (상수) | _get_client/_send | 'set_event' | services/robot_stop_service.py:4 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/teaching_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node=None | - | 조그 상태 초기화 | services/teaching_service.py:14 |
| 2 | .teach_current_position | current_joint_position, current_tcp_pose, motion_type='tcp' | Optional[dict] | 티칭 dict+시그널 | services/teaching_service.py:21 |
| 3 | .jog_tcp | axis, direction, step_mm, velocity_percent, current_tcp_pose, current_tcp_orientation, move_callback | (bool,str) | 단발 조그 (0.5s 레이트리밋) | services/teaching_service.py:48 |
| 4 | .jog_tcp_continuous | 〃 | (bool,str) | 연속 조그 (레이트리밋 없음) | services/teaching_service.py:110 |
| 5 | .move_to_position | motion_type, positions, velocity, move_callback, decomposed_tcp=False | (bool,str) | 종류별 이동 위임 | services/teaching_service.py:168 |
| 6 | ._move_decomposed_tcp | positions, velocity, move_callback | (bool,str) | 축 분해 LINE_T 순차 실행 | services/teaching_service.py:198 |
| 7 | .extract_position_from_params | param_widgets: dict | Optional[(str, List)] | 위젯→(motion_type, 좌표) | services/teaching_service.py:237 |
| 8 | .set_position_to_params | param_widgets, motion_type, positions | bool | 좌표→위젯 역주입 | services/teaching_service.py:253 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/tm_landmark_align_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node=None, log_callback=None, gv_manager=None | - | script/ros2 모션 헬퍼 구성 (gateway 는 node.motion_gateway) | services/tm_landmark_align_service.py:20 |
| 2 | ._log | message | None | 콜백/노드 로그 | services/tm_landmark_align_service.py:30 |
| 3 | .change_to_vision_base | - | (bool,str) | ChangeBase(vision_TM_Landmark_detection) | services/tm_landmark_align_service.py:36 |
| 4 | .change_to_robot_base | - | (bool,str) | ChangeBase(RobotBase) | services/tm_landmark_align_service.py:43 |
| 5 | .change_coordinate_system | base_name, align_pose=False, current_tcp=None, velocity=50.0 | (bool,str) | 전환+선택적 자세 정렬 | services/tm_landmark_align_service.py:50 |
| 6 | ._get_target_pose_for_base | base_name | (rx,ry,rz) 또는 (None×3) | 목표 자세 결정 (RobotBase=180,0,180 / vision_*=전역변수) | services/tm_landmark_align_service.py:93 |
| 7 | .move_to_landmark_center | z_distance, velocity=100.0 | (bool,str) | line_cpp(0,0,z, 180,0,180) | services/tm_landmark_align_service.py:116 |
| 8 | .align_to_landmark | z_distance=100.0, velocity=100.0, wait_time=0.5 | (bool,str) | 전환→중심 정렬→대기 | services/tm_landmark_align_service.py:136 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | VISION_BASE_NAME (클래스 상수) | change_to_vision_base | 'vision_TM_Landmark_detection' | services/tm_landmark_align_service.py:18 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/tm_robot_ros2_motion.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | ros_node: Node, log_callback=None | - | 노드·로그 보관 | services/tm_robot_ros2_motion.py:20 |
| 2 | ._log | message | None | 콜백/노드 로그 | services/tm_robot_ros2_motion.py:24 |
| 3 | .move_ptp_joint | joint_positions[6](rad), velocity=10.0, acc_time=0.2, blend=0, fine_goal=False | (bool,str) | PTP_J 위임 | services/tm_robot_ros2_motion.py:30 |
| 4 | .move_ptp_tcp | tcp_position[6](m/rad), 〃 | (bool,str) | PTP_T 위임 | services/tm_robot_ros2_motion.py:47 |
| 5 | .move_line_tcp | tcp_position[6](m/rad), 〃 | (bool,str) | LINE_T 위임 | services/tm_robot_ros2_motion.py:64 |
| 6 | ._call_set_positions | motion_type, positions, velocity, acc_time, blend, fine_goal | (bool,str) | node._call_set_positions 위임 (없으면 실패 문구) | services/tm_robot_ros2_motion.py:81 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | PTP_J/PTP_T/LINE_T (클래스 상수) | 3종 메서드 | SetPositions.Request 상수 별칭 | services/tm_robot_ros2_motion.py:16-18 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/tm_robot_script_motion.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | gv_manager, log_callback=None, gateway=None | - | 의존 보관 | services/tm_robot_script_motion.py:19 |
| 2 | .set_gateway | gateway | None | 게이트 주입 | services/tm_robot_script_motion.py:25 |
| 3 | ._log | message | None | 콜백 로그 | services/tm_robot_script_motion.py:28 |
| 4 | ._guard | kind, label, target_mm=None, offset_mm=None | (bool,str) | gateway.check 래퍼 (없으면 통과) | services/tm_robot_script_motion.py:32 |
| 5 | .change_base | base_name | (bool,str) | ChangeBase("...") 전송 | services/tm_robot_script_motion.py:45 |
| 6 | .line_cpp | x..rz, velocity_mm=100.0, acc_time_ms=200, blend=0, fine_goal=True | (bool,str) | Line("CPP",...) 전송 (guard 'line') | services/tm_robot_script_motion.py:59 |
| 7 | .ptp_cpp | x..rz, velocity_percent=10.0, 〃 | (bool,str) | PTP("CPP",...) 전송 (guard 'ptp_tcp') | services/tm_robot_script_motion.py:92 |
| 8 | .line_relative | dx..drz, velocity_mm=100.0, acc_time_ms=200 | (bool,str) | Move_Line("TPP",...) 전송 (guard 'line_relative') | services/tm_robot_script_motion.py:125 |
| 9 | .send_raw_script | script: str | (bool,str) | 구역 활성 시 모션 키워드 거부 후 전송 | services/tm_robot_script_motion.py:154 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | MOTION_KEYWORDS (상수) | send_raw_script | Line(/PTP(/Move_Line(/Move_PTP(/Vision_DoJob_PTP(/Circle( | services/tm_robot_script_motion.py:11-13 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/vision_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | gv_manager=None, ros_node=None | - | 태그 캐시·ConnectTM 클라이언트 | services/vision_manager.py:28 |
| 2 | ._init_connect_tm_client | - | None | create_client(ConnectTM,'connect_tmsvr') | services/vision_manager.py:36 |
| 3 | ._pause_ethernet_slave | timeout_sec=2.0 | bool | TMSVR 연결 해제 요청 | services/vision_manager.py:50 |
| 4 | ._resume_ethernet_slave | timeout_sec=2.0 | bool | TMSVR 재연결 요청 | services/vision_manager.py:84 |
| 5 | .update_tag_pose | tag_id, pose_data | None | 태그 캐시+시그널 | services/vision_manager.py:118 |
| 6 | .get_tag / 7 .has_tag / 8 .get_all_tags | tag_id | - | 캐시 조회 | services/vision_manager.py:123,126,129 |
| 9 | .clear_tags | - | None | 캐시 소거+시그널 | services/vision_manager.py:132 |
| 10 | .send_script_exit | - | bool | gv_manager 위임 | services/vision_manager.py:140 |
| 11 | ._wait_for_robot_command_zero | timeout_sec=3.0, poll_interval=0.05 | bool | 비0 관찰 후 0 복귀 폴링 | services/vision_manager.py:145 |
| 12 | .write_variable | var_name, value | bool | 쓰기+ScriptExit('vm') | services/vision_manager.py:189 |
| 13 | .execute_tm_landmark_scan | wait_time=0.1, pause_ethernet=True | (bool,str) | cmd=2 스캔 시퀀스 | services/vision_manager.py:198 |
| 14 | .execute_tm_landmark_jig_scan | jig_number(1~4), wait_time=0.1, pause_ethernet=True | (bool,str) | cmd=3+jig 스캔 | services/vision_manager.py:235 |
| 15 | .execute_scan_align_tm_landmark | wait_time=0.1, pause_ethernet=True | (bool,str) | cmd=1 정렬 (폴링 없이 sleep) | services/vision_manager.py:273 |
| 16 | .execute_tm_landmark_read | - | (bool, dict/str) | g_TM_Landmark 파싱 | services/vision_manager.py:299 |
| 17 | .execute_tm_landmark_jig_read | jig_number | (bool, dict/str) | g_Jig_Landmark{n} 파싱 | services/vision_manager.py:321 |
| 18 | .remove_tag | tag_id | bool | 캐시 삭제+시그널 | services/vision_manager.py:347 |
| 19 | .get_tag_count | - | int | 태그 수 | services/vision_manager.py:354 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/vision_origin_check_service.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | normalize_angle_deg | angle | float | ±180 정규화 | services/vision_origin_check_service.py:31 |
| 2 | .__init__ | config_manager=None, log_callback=None | - | 기본 ConfigManager 생성 | services/vision_origin_check_service.py:44 |
| 3 | ._log | message | None | 콜백 로그 | services/vision_origin_check_service.py:49 |
| 4 | .is_pose (static) | value | bool | 6키 수치 dict 검사 | services/vision_origin_check_service.py:53 |
| 5 | ._clean_pose (static) | pose | Dict[str,float] | float 화 | services/vision_origin_check_service.py:60 |
| 6 | ._positive_float (static) | value, fallback | float | 양수 변환 (실패 fallback) | services/vision_origin_check_service.py:64 |
| 7 | .has_reference | - | bool | 기준 존재 | services/vision_origin_check_service.py:72 |
| 8 | .load_reference | - | Optional[dict] | 기준 로드+구조 검증 | services/vision_origin_check_service.py:76 |
| 9 | .get_reference_tcp_pose | - | Optional[List[6]] | 학습 TCP 리스트 | services/vision_origin_check_service.py:85 |
| 10 | .save_reference | tcp_pose, landmark, measure=None, std=None | bool | 기준 저장(learned_at·tolerance 포함) | services/vision_origin_check_service.py:93 |
| 11 | .get_tolerance | - | {'xyz','rpy'} | 저장/기본 허용범위 | services/vision_origin_check_service.py:129 |
| 12 | .set_tolerance | xyz, rpy | bool | 허용범위 저장(양수 검증) | services/vision_origin_check_service.py:139 |
| 13 | .evaluate | measured, tolerance=None | Optional[VisionOriginCheckResult] | 6축 편차 판정 | services/vision_origin_check_service.py:162 |
| 14 | .format_deltas (static) | deltas | str | 편차 문자열 | services/vision_origin_check_service.py:216 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | POSE_KEYS/POSITION_KEYS/ROTATION_KEYS (상수) | 전반 | 축 키 | services/vision_origin_check_service.py:8-10 |
| 2 | CONFIG_ROOT (상수) | 저장/로드 | 'vision_origin_check' | services/vision_origin_check_service.py:12 |
| 3 | DEFAULT_TOLERANCE_XYZ/RPY (상수) | get_tolerance/evaluate | 1.0mm/0.5deg | services/vision_origin_check_service.py:15-16 |

## src/TM_Robot_Task_Manager/tm_task_manager/services/vision_plugin_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | .__init__ | - | - | 플러그인 dict·경로 | services/vision_plugin_manager.py:19 |
| 2 | .load_plugins | - | None | 폴더 순회 로드(1회) | services/vision_plugin_manager.py:24 |
| 3 | ._load_plugin | name, path | None | spec 로드→서브클래스 탐색→등록 | services/vision_plugin_manager.py:46 |
| 4 | .get_plugin | name | Optional[Any] | 지연 로드 후 조회 | services/vision_plugin_manager.py:72 |
| 5 | .get_available_plugins | - | List[str] | 이름 목록 | services/vision_plugin_manager.py:78 |
| 6 | .get_plugin_info | name | Optional[dict] | name/description/initialized | services/vision_plugin_manager.py:83 |
| 7 | .reload_plugins | - | None | 초기화 후 재로드 | services/vision_plugin_manager.py:93 |
| 8 | get_vision_plugin_manager | - | VisionPluginManager | 모듈 싱글턴 | services/vision_plugin_manager.py:103 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | VISION_PYTHON_PATH (상수) | 모듈 로드 시 sys.path 삽입, __init__ | Vision/Python 절대경로 | services/vision_plugin_manager.py:11-13 |
| 2 | _instance (가변) | get_vision_plugin_manager | 싱글턴 보관 | services/vision_plugin_manager.py:100 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/ai_detection_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `AIDetectionTab.__init__` | `main_window` | - | ui/타이머/단건 플래그 초기화 | tabs/ai_detection_tab.py:18 |
| 2 | `AIDetectionTab.init_ui` | - | None | share dir 에서 .ui 로드·셋업·confidence·100ms 타이머 생성 | tabs/ai_detection_tab.py:29 |
| 3 | `AIDetectionTab._init_detection_setup` | - | None | task/runtime 콤보 채움·모델 목록 갱신 | tabs/ai_detection_tab.py:66 |
| 4 | `AIDetectionTab._refresh_model_combobox` | - | None | task+runtime 조합의 모델 목록 재구성 | tabs/ai_detection_tab.py:87 |
| 5 | `AIDetectionTab._init_confidence_controls` | - | None | 0.5 초기값 + 슬라이더↔스핀 양방향 연결 | tabs/ai_detection_tab.py:108 |
| 6 | `AIDetectionTab.connect_signals` | - | None | 서비스 시그널 4종 + 콤보/버튼 + image_captured 연결 | tabs/ai_detection_tab.py:123 |
| 7 | `AIDetectionTab._on_model_loaded` | `success: bool, message: str` | None | 로드 성공/실패 로그 | tabs/ai_detection_tab.py:158 |
| 8 | `AIDetectionTab._on_detection_completed` | `detections: List, annotated_image: np.ndarray, fps: float` | None | FPS·이미지·결과 테이블 갱신 | tabs/ai_detection_tab.py:164 |
| 9 | `AIDetectionTab._on_detection_error` | `error_msg: str` | None | 에러 로그 | tabs/ai_detection_tab.py:172 |
| 10 | `AIDetectionTab._on_status_changed` | `status: str` | None | 상태 라벨 | tabs/ai_detection_tab.py:175 |
| 11 | `AIDetectionTab._on_detection_changed` | `index: int` | None | task 변경 시 모델 목록 갱신 | tabs/ai_detection_tab.py:180 |
| 12 | `AIDetectionTab._on_runtime_changed` | `index: int` | None | runtime 변경 시 모델 목록 갱신 | tabs/ai_detection_tab.py:185 |
| 13 | `AIDetectionTab._on_model_changed` | `index: int` | None | 선택 모델 즉시 로드 | tabs/ai_detection_tab.py:190 |
| 14 | `AIDetectionTab._on_load_custom_model` | - | None | runtime 별 필터 파일 다이얼로그→로드 | tabs/ai_detection_tab.py:199 |
| 15 | `AIDetectionTab._on_confidence_changed` | `threshold: float` | None | 서비스 임계값 설정 | tabs/ai_detection_tab.py:219 |
| 16 | `AIDetectionTab._on_toggle_detection` | `checked: bool` | None | 연속 검출 타이머 시작/정지·버튼 문구 | tabs/ai_detection_tab.py:223 |
| 17 | `AIDetectionTab._on_single_detection` | - | None | 단건: 플래그 set 후 이미지 캡처 요청(3s) | tabs/ai_detection_tab.py:238 |
| 18 | `AIDetectionTab._on_capture_then_detect` | `cv_image` | None | 캡처 완료 시 현재 이미지 갱신·추론 실행 | tabs/ai_detection_tab.py:256 |
| 19 | `AIDetectionTab._run_detection` | - | None | 타이머 틱마다 current_camera_image 추론 | tabs/ai_detection_tab.py:266 |
| 20 | `AIDetectionTab._display_image` | `cv_image: np.ndarray` | None | 라벨 크기 맞춤 리사이즈 후 표시 | tabs/ai_detection_tab.py:279 |
| 21 | `AIDetectionTab._update_results_table` | `detections: List` | None | 7열 결과 테이블 재구성 | tabs/ai_detection_tab.py:308 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/base_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `BaseTab.__init__` | `main_window` | - | 메인 윈도우 참조 저장 | tabs/base_tab.py:8 |
| 2 | `BaseTab.ros_node` (property) | - | node | main_window.ros_node 위임 | tabs/base_tab.py:11 |
| 3 | `BaseTab.recipe_manager` (property) | - | RecipeManager | 위임 접근자 | tabs/base_tab.py:15 |
| 4 | `BaseTab.job_executor` (property) | - | JobExecutor | 위임 접근자 | tabs/base_tab.py:19 |
| 5 | `BaseTab.vision_manager` (property) | - | VisionManager | 위임 접근자 | tabs/base_tab.py:23 |
| 6 | `BaseTab.gv_manager` (property) | - | GVManager | 위임 접근자 | tabs/base_tab.py:27 |
| 7 | `BaseTab.config_manager` (property) | - | ConfigManager | 위임 접근자 | tabs/base_tab.py:31 |
| 8 | `BaseTab._log` | `message: str, kind=None` | None | 메인 윈도우 `_log` 위임(종류 선택) | tabs/base_tab.py:35 |
| 9 | `BaseTab.connect_signals` | - | - | 추상 — NotImplementedError | tabs/base_tab.py:41 |
| 10 | `BaseTab.init_ui` | - | None | 기본 no-op | tabs/base_tab.py:45 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/global_variables_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `GlobalVariablesTab.__init__` | `main_window` | - | 초기화, mw 보관 | tabs/global_variables_tab.py:12 |
| 2 | `GlobalVariablesTab.connect_signals` | - | None | 읽기/쓰기/히스토리삭제 버튼 연결 | tabs/global_variables_tab.py:16 |
| 3 | `GlobalVariablesTab.init_ui` | - | None | 히스토리 테이블 헤더 리사이즈 설정 | tabs/global_variables_tab.py:22 |
| 4 | `GlobalVariablesTab._on_read_variable` | - | None | gv_manager.read_variable 호출, 결과 표시·히스토리 추가 | tabs/global_variables_tab.py:27 |
| 5 | `GlobalVariablesTab._on_write_variable` | - | None | write_variable + send_script_exit('gv'), 결과 표시 | tabs/global_variables_tab.py:54 |
| 6 | `GlobalVariablesTab._add_variable_history` | `variable_name, value` | None | 히스토리 0행 삽입, 100행 초과분 제거 | tabs/global_variables_tab.py:92 |
| 7 | `GlobalVariablesTab._on_clear_variable_history` | - | None | 히스토리 테이블 전체 삭제 | tabs/global_variables_tab.py:106 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/handeye_test_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `HandEyeTestTab.__init__` | `main_window` | - | 초기화 (ui/manager None) | tabs/handeye_test_tab.py:16 |
| 2 | `HandEyeTestTab.connect_signals` | - | None | no-op (연결은 init_ui 내부) | tabs/handeye_test_tab.py:22 |
| 3 | `HandEyeTestTab.init_ui` | - | None | .ui 로드·mw.handeye_ui 보관·매니저·시그널·라벨 초기화 | tabs/handeye_test_tab.py:26 |
| 4 | `HandEyeTestTab._init_manager` | - | None | HandEyeTestManager 생성 + 콜백 3종 배선 | tabs/handeye_test_tab.py:42 |
| 5 | `HandEyeTestTab._connect_handeye_signals` | - | None | 버튼 14종 + 스핀박스 3종 연결 | tabs/handeye_test_tab.py:55 |
| 6 | `HandEyeTestTab._on_read_current_tcp` | - | None | 현재 TCP → 기준 스핀박스 6개 | tabs/handeye_test_tab.py:79 |
| 7 | `HandEyeTestTab._update_total_positions_label` | - | None | 총 측정 위치 수 라벨 계산 | tabs/handeye_test_tab.py:97 |
| 8 | `HandEyeTestTab._on_generate_positions` | - | None | 기준+스텝/개수로 위치 그리드 생성 | tabs/handeye_test_tab.py:109 |
| 9 | `HandEyeTestTab._on_clear_positions` | - | None | 위치 목록 초기화 | tabs/handeye_test_tab.py:130 |
| 10 | `HandEyeTestTab._update_positions_table` | - | None | 위치 테이블 재구성 | tabs/handeye_test_tab.py:135 |
| 11 | `HandEyeTestTab._on_add_current_position` | - | None | 현재 TCP 를 목록에 추가 | tabs/handeye_test_tab.py:151 |
| 12 | `HandEyeTestTab._on_delete_selected_position` | - | None | 선택 행(역순) 삭제 | tabs/handeye_test_tab.py:165 |
| 13 | `HandEyeTestTab._on_save_positions` | - | None | YAML 저장 다이얼로그 | tabs/handeye_test_tab.py:180 |
| 14 | `HandEyeTestTab._on_load_positions` | - | None | YAML 로드 다이얼로그 | tabs/handeye_test_tab.py:192 |
| 15 | `HandEyeTestTab._on_start_test` | - | None | 반복수·지연 설정→start_test→측정 루프 개시 | tabs/handeye_test_tab.py:202 |
| 16 | `HandEyeTestTab._run_next_measurement` | - | None | run_single_measurement→완료/오류/다음(QTimer 100ms) | tabs/handeye_test_tab.py:224 |
| 17 | `HandEyeTestTab._handle_measurement_error` | `error_msg: str` | None | 계속/중단 질의 | tabs/handeye_test_tab.py:244 |
| 18 | `HandEyeTestTab._on_stop_test` | - | None | manager.stop_test + 버튼 복원 | tabs/handeye_test_tab.py:257 |
| 19 | `HandEyeTestTab._on_reset_test` | - | None | manager.reset_test + 테이블/진행 초기화 | tabs/handeye_test_tab.py:265 |
| 20 | `HandEyeTestTab._on_measurement_complete` | `measurement: dict` | None | 측정 테이블 갱신 | tabs/handeye_test_tab.py:275 |
| 21 | `HandEyeTestTab._on_test_complete` | - | None | is_running=False·버튼 복원·통계 표시 | tabs/handeye_test_tab.py:278 |
| 22 | `HandEyeTestTab._on_progress_update` | `current: int, total: int` | None | 진행바/라벨 갱신 | tabs/handeye_test_tab.py:290 |
| 23 | `HandEyeTestTab._update_measurements_table` | - | None | 측정 15열 테이블 재구성(실패 적색) | tabs/handeye_test_tab.py:297 |
| 24 | `HandEyeTestTab._on_export_csv` | - | None | CSV 저장 다이얼로그 | tabs/handeye_test_tab.py:326 |
| 25 | `HandEyeTestTab._on_open_analyzer` | - | None | handeye_analyzer.py 서브프로세스 실행(CSV 자동 저장) | tabs/handeye_test_tab.py:340 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/io_control_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `IOControlTab.__init__` | `main_window` | - | 위젯 캐시 리스트 5종 초기화 | tabs/io_control_tab.py:19 |
| 2 | `IOControlTab.init_ui` | - | None | .ui 로드·위젯 캐시·LED 초기화·매거진 그룹 구성 | tabs/io_control_tab.py:30 |
| 3 | `IOControlTab._cache_widget_references` | - | None | label_cb_di_0..15 등 getattr 수집 | tabs/io_control_tab.py:53 |
| 4 | `IOControlTab._init_led_styles` | - | None | 모든 DI LED OFF 스타일 | tabs/io_control_tab.py:77 |
| 5 | `IOControlTab._build_magazine_group` | `layout: QVBoxLayout` | None | 서비스 가용성별 매거진 그룹/안내 박스 | tabs/io_control_tab.py:81 |
| 6 | `IOControlTab._make_magazine_label` | `slot: int` | QLabel | 슬롯 라벨 생성·등록 | tabs/io_control_tab.py:102 |
| 7 | `IOControlTab._update_magazine` | `present: List[bool], raw: List[bool], valid: bool` | None | 슬롯별 있음/비어있음/확인불가 표시 | tabs/io_control_tab.py:112 |
| 8 | `IOControlTab.connect_signals` | - | None | io 서비스 시그널 5종 + 매거진 + DO 버튼 + grip/release | tabs/io_control_tab.py:130 |
| 9 | `IOControlTab._connect_do_buttons` | - | None | DO 버튼 clicked→set_cb_do/set_ee_do (핀 캡처 람다) | tabs/io_control_tab.py:162 |
| 10 | `IOControlTab._update_cb_di_leds` | `states: List[bool]` | None | CB DI LED 갱신 (+info 로그) | tabs/io_control_tab.py:179 |
| 11 | `IOControlTab._update_cb_do_leds` | `states: List[bool]` | None | CB DO 버튼 체크 상태 동기화 | tabs/io_control_tab.py:187 |
| 12 | `IOControlTab._update_ee_di_leds` | `states: List[bool]` | None | EE DI LED 갱신 | tabs/io_control_tab.py:192 |
| 13 | `IOControlTab._update_ee_do_leds` | `states: List[bool]` | None | EE DO 버튼 체크 상태 동기화 | tabs/io_control_tab.py:198 |
| 14 | `IOControlTab._on_grip` | - | None | io_control_service.grip | tabs/io_control_tab.py:204 |
| 15 | `IOControlTab._on_release` | - | None | io_control_service.release | tabs/io_control_tab.py:209 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `IOControlTab.LED_ON_STYLE` (클래스 상수) | #10,#12 | LED 켜짐 스타일 | tabs/io_control_tab.py:13 |
| 2 | `IOControlTab.LED_OFF_STYLE` (클래스 상수) | #4,#10,#12 | LED 꺼짐 스타일 | tabs/io_control_tab.py:14 |
| 3 | `IOControlTab.MGZ_PRESENT_STYLE` (클래스 상수) | #7 | 매거진 있음 스타일 | tabs/io_control_tab.py:15 |
| 4 | `IOControlTab.MGZ_EMPTY_STYLE` (클래스 상수) | #7 | 매거진 비어있음 스타일 | tabs/io_control_tab.py:16 |
| 5 | `IOControlTab.MGZ_STALE_STYLE` (클래스 상수) | #5,#6,#7 | 미수신/확인불가 스타일 | tabs/io_control_tab.py:17 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/keyboard_control_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `_KeyCaptureWidget.__init__` | `jog_service` | - | 콜백 필드·포커스 정책 초기화 | tabs/keyboard_control_tab.py:26 |
| 2 | `_KeyCaptureWidget._current_step` | - | float | jog_service.get_params 의 step | tabs/keyboard_control_tab.py:33 |
| 3 | `_KeyCaptureWidget._set_step` | `mm: float` | float | 하한(1mm) 클램프 후 set_params | tabs/keyboard_control_tab.py:37 |
| 4 | `_KeyCaptureWidget._notify` | `text: str` | None | on_action 콜백 호출 | tabs/keyboard_control_tab.py:42 |
| 5 | `_KeyCaptureWidget.keyPressEvent` | `event` | None | 축 이동/스텝 1~9·0·=·− 처리 (auto-repeat 무시) | tabs/keyboard_control_tab.py:46 |
| 6 | `_KeyCaptureWidget.hideEvent` | `event` | None | releaseKeyboard + on_hidden 콜백 | tabs/keyboard_control_tab.py:84 |
| 7 | `KeyboardControlTab.__init__` | `main_window` | - | 위젯 필드 초기화 | tabs/keyboard_control_tab.py:95 |
| 8 | `KeyboardControlTab.connect_signals` | - | None | no-op | tabs/keyboard_control_tab.py:104 |
| 9 | `KeyboardControlTab.init_ui` | - | None | 코드 UI 구성·override 가용성 반영·탭 삽입(PS2 탭 뒤) | tabs/keyboard_control_tab.py:108 |
| 10 | `KeyboardControlTab._on_mode_toggled` | `checked: bool` | None | grab/releaseKeyboard + 문구 전환 | tabs/keyboard_control_tab.py:167 |
| 11 | `KeyboardControlTab._on_capture_action` | `text: str` | None | 상태 라벨 갱신 | tabs/keyboard_control_tab.py:178 |
| 12 | `KeyboardControlTab._on_capture_hidden` | - | None | 숨김 시 모드 버튼 해제 | tabs/keyboard_control_tab.py:181 |
| 13 | `KeyboardControlTab._on_force_open` | - | None | 경고 확인 후 gripper_override_service.force_release | tabs/keyboard_control_tab.py:185 |
| 14 | `KeyboardControlTab._on_params_changed` | `step_mm: float, velocity_percent: int` | None | 스텝 라벨 갱신 | tabs/keyboard_control_tab.py:210 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `_STEP_MIN_MM` (상수) | #3 | 스텝 하한 1mm | tabs/keyboard_control_tab.py:7 |
| 2 | `_STEP_RESET_MM` (상수) | #5 | 0 키 리셋값 10mm | tabs/keyboard_control_tab.py:8 |
| 3 | `_STEP_BIG_MM` (상수) | #5 | =/− 증감폭 10mm | tabs/keyboard_control_tab.py:9 |
| 4 | `_KeyCaptureWidget._AXIS_KEYMAP` (클래스 상수) | #5 | 키→(축,방향) 매핑 8종 | tabs/keyboard_control_tab.py:15 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/pallet_teach_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `PalletTeachTab.__init__` | `main_window` | - | blackboard·busy·poll 필드 초기화 | tabs/pallet_teach_tab.py:32 |
| 2 | `PalletTeachTab.init_ui` | - | None | 시퀀스 검증→스크롤 페이지에 step1~5+로그 구성→탭 삽입 | tabs/pallet_teach_tab.py:47 |
| 3 | `PalletTeachTab._build_step1` | - | QGroupBox | 종류 라디오·pitch/trim 스핀 4종 | tabs/pallet_teach_tab.py:86 |
| 4 | `PalletTeachTab._build_step2` | - | QGroupBox | 위치 마커 촬영 버튼/상태 | tabs/pallet_teach_tab.py:132 |
| 5 | `PalletTeachTab._build_step3` | - | QGroupBox | 4점 측정 승인 버튼/상태 | tabs/pallet_teach_tab.py:153 |
| 6 | `PalletTeachTab._build_step3_alt` | - | QGroupBox | 측정 파일 선택 목록·outlier 방법·평면 만들기 | tabs/pallet_teach_tab.py:174 |
| 7 | `PalletTeachTab._build_step4` | - | QGroupBox | standoff·정렬 모드·중심 접근·픽/플레이스 저장 | tabs/pallet_teach_tab.py:252 |
| 8 | `PalletTeachTab._build_step5` | - | QGroupBox | 이름·작업자·그리퍼 라디오·감지·하강 방식·레시피 생성 | tabs/pallet_teach_tab.py:302 |
| 9 | `PalletTeachTab._selected_gripper` | - | str | 그리퍼 라디오의 gripper_id | tabs/pallet_teach_tab.py:367 |
| 10 | `PalletTeachTab._selected_descent` | - | str | 하강 라디오의 descent_id | tabs/pallet_teach_tab.py:372 |
| 11 | `PalletTeachTab._on_probe_gripper` | - | None | hardware.gripper.survey 로 LIVE 백엔드 감지·라디오 자동 선택 | tabs/pallet_teach_tab.py:379 |
| 12 | `PalletTeachTab._build_log` | - | QGroupBox | 진행 기록 QPlainTextEdit(500블록) | tabs/pallet_teach_tab.py:395 |
| 13 | `PalletTeachTab._is_floating` | - | bool | 비고정식 여부 | tabs/pallet_teach_tab.py:406 |
| 14 | `PalletTeachTab._refresh_enabled` | - | None | blackboard 상태·busy 로 버튼 활성화 일괄 갱신 | tabs/pallet_teach_tab.py:409 |
| 15 | `PalletTeachTab._append_log` | `message: str` | None | 탭 로그 + 전역 로그 이중 기록 | tabs/pallet_teach_tab.py:435 |
| 16 | `PalletTeachTab._run` | `macro_name: str, params: Dict, on_done: Callable` | None | busy 가드→MacroContext 구성→워커 스레드+150ms poll 시작 | tabs/pallet_teach_tab.py:442 |
| 16a | `PalletTeachTab._run.worker` (이너) | - | None | run_macro 실행, 예외 포함 `_result` 저장, `_done` 마크 | tabs/pallet_teach_tab.py:461 |
| 16b | `PalletTeachTab._run.poll` (이너) | - | None | done 시 타이머 정지·결과/예외 처리·on_done·재활성화 | tabs/pallet_teach_tab.py:470 |
| 17 | `PalletTeachTab._confirm_motion` | `title: str, body: str` | bool | 로봇 동작 확인 다이얼로그 | tabs/pallet_teach_tab.py:492 |
| 18 | `PalletTeachTab._on_capture_marker` | - | None | pallet_capture_marker 매크로 실행 | tabs/pallet_teach_tab.py:499 |
| 18a | `PalletTeachTab._on_capture_marker.done` (이너) | `result` | None | 마커 좌표 상태 표시 | tabs/pallet_teach_tab.py:500 |
| 19 | `PalletTeachTab._start_dir` | - | str | 측정 폴더 시작 경로 해석 | tabs/pallet_teach_tab.py:509 |
| 20 | `PalletTeachTab._listed_paths` | - | List[str] | 목록 위젯의 파일 경로들(UserRole) | tabs/pallet_teach_tab.py:513 |
| 21 | `PalletTeachTab._set_listed_paths` | `paths: List[str]` | None | 목록 재구성 + 상태 문구 | tabs/pallet_teach_tab.py:517 |
| 22 | `PalletTeachTab._on_pick_files` | - | None | 다중 파일 선택·목록 병합 | tabs/pallet_teach_tab.py:529 |
| 23 | `PalletTeachTab._on_pick_folder` | - | None | 폴더 선택→측정 파일 최신순 채움 | tabs/pallet_teach_tab.py:539 |
| 24 | `PalletTeachTab._on_clear_files` | - | None | 목록 비우기 | tabs/pallet_teach_tab.py:552 |
| 25 | `PalletTeachTab._on_remove_selected_files` | - | None | 선택 항목 제외 | tabs/pallet_teach_tab.py:555 |
| 26 | `PalletTeachTab._on_load_measurements` | - | None | pallet_load_measurements 매크로 실행 | tabs/pallet_teach_tab.py:563 |
| 26a | `PalletTeachTab._on_load_measurements.done` (이너) | `result` | None | 평균 중심·대체 상태 표시 | tabs/pallet_teach_tab.py:566 |
| 27 | `PalletTeachTab._on_scan_corners` | - | None | pitch 검증·동작 확인→pallet_scan_4corners 실행 | tabs/pallet_teach_tab.py:583 |
| 27a | `PalletTeachTab._on_scan_corners.done` (이너) | `result` | None | 중심·자세 상태 표시 | tabs/pallet_teach_tab.py:596 |
| 28 | `PalletTeachTab._on_center_approach` | - | None | 동작 확인→pallet_center_approach 실행 | tabs/pallet_teach_tab.py:611 |
| 29 | `PalletTeachTab._on_capture_teach` | `slot: str('pick'\|'place')` | None | pallet_capture_teach 실행 | tabs/pallet_teach_tab.py:625 |
| 30 | `PalletTeachTab._on_emit_recipes` | - | None | 이름 검증→pallet_emit_recipes 실행 | tabs/pallet_teach_tab.py:628 |
| 30a | `PalletTeachTab._on_emit_recipes.done` (이너) | `result` | None | 생성 경로 표시·안내 다이얼로그 | tabs/pallet_teach_tab.py:634 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `TAB_TITLE` (상수) | #2 | 탭 제목 '팔레트 티칭' | tabs/pallet_teach_tab.py:20 |
| 2 | `TAB_INSERT_INDEX` (상수) | #2 | 탭 삽입 위치 1 | tabs/pallet_teach_tab.py:22 |
| 3 | `FIXED_SEQUENCE` (상수) | #2(FLOATING 경유) | 고정식 매크로 순서 4종 | tabs/pallet_teach_tab.py:24 |
| 4 | `FLOATING_SEQUENCE` (상수) | #2 | 비고정식 순서(마커 촬영 선행) | tabs/pallet_teach_tab.py:26 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/precision_test_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `PrecisionTestTab.__init__` | `main_window` | - | figure/canvas/ax 필드 12종 + dataset 필드 초기화 | tabs/precision_test_tab.py:24 |
| 2 | `PrecisionTestTab.connect_signals` | - | None | no-op (연결은 init_ui 내부에서) | tabs/precision_test_tab.py:50 |
| 3 | `PrecisionTestTab.init_ui` | - | None | PrecisionTestManager 생성(mw 에 보관), .ui 로드, 시그널·그래프·데이터셋 블록 초기화 | tabs/precision_test_tab.py:54 |
| 4 | `PrecisionTestTab._connect_precision_test_signals` | - | None | 모드 라디오·시작/중지/리셋·내보내기 버튼 연결 | tabs/precision_test_tab.py:80 |
| 5 | `PrecisionTestTab._init_precision_test_graphs` | - | None | 4개 Figure/Canvas 를 위젯에 장착 | tabs/precision_test_tab.py:94 |
| 6 | `PrecisionTestTab._on_test_mode_changed` | - | None | static/dynamic 전환·recipe 라벨 갱신 | tabs/precision_test_tab.py:142 |
| 7 | `PrecisionTestTab._update_precision_recipe_label` | - | None | 현재 recipe 파일명 표시 | tabs/precision_test_tab.py:152 |
| 8 | `PrecisionTestTab._on_start_precision_test` | - | None | 반복수 설정·is_running=True·모드별 시작 | tabs/precision_test_tab.py:165 |
| 9 | `PrecisionTestTab._run_static_precision_test` | - | None | landmark 스캔+읽기→측정 추가→QTimer(100ms) 재귀 체인 | tabs/precision_test_tab.py:184 |
| 10 | `PrecisionTestTab._handle_measurement_error` | `error_msg: str` | None | 계속/중단 질의 다이얼로그 | tabs/precision_test_tab.py:223 |
| 11 | `PrecisionTestTab._run_dynamic_precision_test` | - | None | manager 콜백 4종 배선 후 start_dynamic_test | tabs/precision_test_tab.py:238 |
| 12 | `PrecisionTestTab._on_precision_test_completed` | - | None | 종료 처리 위임 | tabs/precision_test_tab.py:253 |
| 13 | `PrecisionTestTab._on_request_next_iteration` | - | None | 500ms 후 다음 회차 | tabs/precision_test_tab.py:256 |
| 14 | `PrecisionTestTab._finish_precision_test` | - | None | is_running=False·버튼 복원·UI 갱신 | tabs/precision_test_tab.py:259 |
| 15 | `PrecisionTestTab._on_stop_precision_test` | - | None | is_running=False·버튼 복원 | tabs/precision_test_tab.py:272 |
| 16 | `PrecisionTestTab._on_reset_precision_test` | - | None | manager.reset + UI 갱신 | tabs/precision_test_tab.py:282 |
| 17 | `PrecisionTestTab._on_export_precision_csv` | - | None | install/build 경로 추론→data/날짜 폴더에 CSV 저장 | tabs/precision_test_tab.py:288 |
| 18 | `PrecisionTestTab._on_save_precision_graph` | - | None | XY/YZ/ZX 3종 PNG 저장 | tabs/precision_test_tab.py:321 |
| 19 | `PrecisionTestTab._on_open_precision_analyzer` | - | None | sys.path 주입 후 precision_analyzer 창 실행 | tabs/precision_test_tab.py:353 |
| 20 | `PrecisionTestTab._update_precision_test_ui` | - | None | 진행바·통계 라벨·측정 테이블·그래프 일괄 갱신 | tabs/precision_test_tab.py:376 |
| 21 | `PrecisionTestTab._update_precision_test_graphs` | - | None | 4개 산점도 clear→재플롯 | tabs/precision_test_tab.py:420 |
| 22 | `PrecisionTestTab._init_plate_dataset_block` | - | None | PlatePoseDataset 생성(mw 에 보관)·그래프·시그널·루트 설정 | tabs/precision_test_tab.py:473 |
| 23 | `PrecisionTestTab._connect_plate_dataset_signals` | - | None | 데이터셋 버튼·체크박스 연결 | tabs/precision_test_tab.py:485 |
| 24 | `PrecisionTestTab._init_plate_dataset_graphs` | - | None | 2x2 산점도 Figure + 3D Figure 장착 | tabs/precision_test_tab.py:497 |
| 25 | `PrecisionTestTab._refresh_pallet_combo` | - | None | 팔레트 폴더 목록 콤보 갱신 | tabs/precision_test_tab.py:527 |
| 26 | `PrecisionTestTab._current_dataset_variant` | - | str | raw/corrected 선택 | tabs/precision_test_tab.py:540 |
| 27 | `PrecisionTestTab._on_browse_dataset_root` | - | None | 루트 폴더 선택·검증 | tabs/precision_test_tab.py:547 |
| 28 | `PrecisionTestTab._on_load_plate_dataset` | - | None | dataset.load → 통계·산점도·형상 갱신 | tabs/precision_test_tab.py:563 |
| 29 | `PrecisionTestTab._update_dataset_stats_table` | - | None | 통계 테이블 채우기 | tabs/precision_test_tab.py:583 |
| 30 | `PrecisionTestTab._update_dataset_scatter` | - | None | 절대/편차 뷰 산점도 4면 재플롯 | tabs/precision_test_tab.py:603 |
| 31 | `PrecisionTestTab._on_dataset_view_toggled` | - | None | 절대/편차 토글 재플롯 | tabs/precision_test_tab.py:637 |
| 32 | `PrecisionTestTab._side_pair_colors` | `sides: dict, validator` | dict | 변쌍 차이 허용 초과 시 적색 매핑 | tabs/precision_test_tab.py:641 |
| 33 | `PrecisionTestTab._draw_jig_rectangle` | `ax, marks, sides, colors, label, annotate` | None | 4점 변·대각선·중심 3D 드로잉 | tabs/precision_test_tab.py:654 |
| 34 | `PrecisionTestTab._update_jig_shape` | - | None | 평균 4점 형상 검사·PASS/FAIL·3D 갱신 (겹쳐보기 분기) | tabs/precision_test_tab.py:693 |
| 35 | `PrecisionTestTab._fill_jig_check_table` | `sides: dict, results` | None | 변 길이 + 검사 결과 테이블 | tabs/precision_test_tab.py:735 |
| 36 | `PrecisionTestTab._centred` (static) | `marks` | list | 중심 정렬 좌표 변환 | tabs/precision_test_tab.py:769 |
| 37 | `PrecisionTestTab._update_jig3d_overlay` | - | None | 전체 팔레트 겹쳐 3D + 요약 테이블 | tabs/precision_test_tab.py:774 |
| 38 | `PrecisionTestTab._fill_overlay_summary_table` | `summary_rows` | None | 팔레트별 최악 항목/판정 테이블 | tabs/precision_test_tab.py:825 |
| 39 | `PrecisionTestTab._apply_equal_3d_range` | `ax, marks` | None | 3D 등축 범위 설정 | tabs/precision_test_tab.py:859 |
| 40 | `PrecisionTestTab._on_overlay_toggled` | - | None | 겹쳐보기 토글 재드로잉 | tabs/precision_test_tab.py:873 |
| 41 | `PrecisionTestTab._dataset_default_path` | `suffix: str` | str | data/날짜/파일명 기본 경로 생성 | tabs/precision_test_tab.py:878 |
| 42 | `PrecisionTestTab._on_export_dataset_csv` | - | None | 통계·변길이·형상검사 CSV 저장 | tabs/precision_test_tab.py:890 |
| 43 | `PrecisionTestTab._save_figure` | `figure, suffix: str, title: str` | None | Figure PNG 저장 공통 | tabs/precision_test_tab.py:940 |
| 44 | `PrecisionTestTab._on_save_dataset_graph` | - | None | 산점도 저장 | tabs/precision_test_tab.py:958 |
| 45 | `PrecisionTestTab._on_save_jig_shape` | - | None | 3D 그래프 저장 | tabs/precision_test_tab.py:961 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `PrecisionTestTab.JIG_COLORS` (클래스 상수) | #30,#33 | jig 1~4 색상 | tabs/precision_test_tab.py:463 |
| 2 | `PrecisionTestTab.DATASET_PLANES` (클래스 상수) | #24,#30 | 4개 평면 정의(축·라벨·제목) | tabs/precision_test_tab.py:464 |
| 3 | `PrecisionTestTab.PALLET_OVERLAY_COLORS` (클래스 상수) | #37 | 겹쳐보기 팔레트 색 6종 | tabs/precision_test_tab.py:470 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/ps2_joystick_test_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `PS2JoystickTestTab.__init__` | `main_window` | - | 버튼 12·축 8 상태 배열 초기화 | tabs/ps2_joystick_test_tab.py:12 |
| 2 | `PS2JoystickTestTab.connect_signals` | - | None | no-op | tabs/ps2_joystick_test_tab.py:19 |
| 3 | `PS2JoystickTestTab.init_ui` | - | None | .ui 로드·시그널 연결·초기 표시 | tabs/ps2_joystick_test_tab.py:23 |
| 4 | `PS2JoystickTestTab._connect_joystick_signals` | - | None | mode/connection/status_changed 연결 | tabs/ps2_joystick_test_tab.py:37 |
| 5 | `PS2JoystickTestTab._connect_worker_signals` | - | None | js._worker 존재 시 axis/button_changed 연결 | tabs/ps2_joystick_test_tab.py:43 |
| 6 | `PS2JoystickTestTab._init_display` | - | None | 설정 표시·축 진행바 50 초기화 | tabs/ps2_joystick_test_tab.py:50 |
| 7 | `PS2JoystickTestTab._on_axis_changed` | `axis_id: int, value: float` | None | 축 값 저장·표시 (id≥8 무시) | tabs/ps2_joystick_test_tab.py:77 |
| 8 | `PS2JoystickTestTab._on_button_changed` | `button_id: int, pressed: bool` | None | 버튼 상태 저장·표시 (id≥12 무시) | tabs/ps2_joystick_test_tab.py:83 |
| 9 | `PS2JoystickTestTab._on_mode_changed` | `mode: str` | None | 모드 라벨·색상 인디케이터 | tabs/ps2_joystick_test_tab.py:89 |
| 10 | `PS2JoystickTestTab._on_connection_changed` | `connected: bool` | None | 연결 표시 + 재연결 시 워커 시그널 재연결 | tabs/ps2_joystick_test_tab.py:96 |
| 11 | `PS2JoystickTestTab._on_status_changed` | `message: str` | None | 상태 메시지 라벨 | tabs/ps2_joystick_test_tab.py:101 |
| 12 | `PS2JoystickTestTab._update_connection_display` | `connected: bool` | None | 연결 LED 색/문구 | tabs/ps2_joystick_test_tab.py:105 |
| 13 | `PS2JoystickTestTab._update_axis_display` | `axis_id: int, value: float` | None | [-1,1]→[0,100] 진행바·수치 라벨 | tabs/ps2_joystick_test_tab.py:118 |
| 14 | `PS2JoystickTestTab._update_button_display` | `button_id: int, pressed: bool` | None | 버튼 인디케이터 색 | tabs/ps2_joystick_test_tab.py:132 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/run_monitor_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `RunMonitorTab.__init__` | `main_window` | - | 반복 실행 카운터 4종 초기화 | tabs/run_monitor_tab.py:16 |
| 2 | `RunMonitorTab.connect_signals` | - | None | 실행 버튼 9종 + 탭 전환 + executor 콜백 3종 할당 | tabs/run_monitor_tab.py:25 |
| 3 | `RunMonitorTab.init_ui` | - | None | Job 목록 초기 갱신 | tabs/run_monitor_tab.py:44 |
| 4 | `RunMonitorTab._on_tab_changed` | `index: int` | None | 본 탭 진입 시 목록 갱신 | tabs/run_monitor_tab.py:47 |
| 5 | `RunMonitorTab._update_monitor_jobs` | - | None | 현재 recipe 의 Job 목록 재구성 + 상태 리셋 | tabs/run_monitor_tab.py:51 |
| 6 | `RunMonitorTab._validate_vision_origin_check_placement` | `recipe` | (bool, str) | 정책별 첫/마지막 Job 타입 검증 | tabs/run_monitor_tab.py:63 |
| 7 | `RunMonitorTab._check_vision_origin_placement_or_warn` | `recipe` | bool | 검증 실패 시 경고 다이얼로그 | tabs/run_monitor_tab.py:94 |
| 8 | `RunMonitorTab._on_run` | - | None | PAUSED→resume, 아니면 검증→load_recipe→run | tabs/run_monitor_tab.py:109 |
| 9 | `RunMonitorTab._on_pause` | - | None | executor.pause | tabs/run_monitor_tab.py:127 |
| 10 | `RunMonitorTab._on_stop` | - | None | 반복 중지 + executor.stop | tabs/run_monitor_tab.py:130 |
| 11 | `RunMonitorTab._on_step` | - | None | IDLE 이면 load 후 step | tabs/run_monitor_tab.py:134 |
| 12 | `RunMonitorTab._on_run_from` | - | None | 선택 행부터 실행 | tabs/run_monitor_tab.py:148 |
| 13 | `RunMonitorTab._on_run_reverse` | - | None | 선택 행부터 역방향 실행 | tabs/run_monitor_tab.py:165 |
| 14 | `RunMonitorTab._on_repeat_run` | - | None | 반복 횟수 설정 후 첫 반복 시작 | tabs/run_monitor_tab.py:180 |
| 15 | `RunMonitorTab._start_repeat_iteration` | - | None | n회차 로드+run+상태바 | tabs/run_monitor_tab.py:196 |
| 16 | `RunMonitorTab._stop_repeat` | - | None | 반복 중지·결과 요약 로그 | tabs/run_monitor_tab.py:206 |
| 17 | `RunMonitorTab._repeat_suffix` | - | str | 상태 문구용 반복 진행 접미사 | tabs/run_monitor_tab.py:221 |
| 18 | `RunMonitorTab._set_status` | `text, done: int, total: int, state: str` | None | 상태 라벨+진행바 색/서식 갱신 | tabs/run_monitor_tab.py:229 |
| 19 | `RunMonitorTab._reset_status` | `text: str` | None | 상태 초기화 | tabs/run_monitor_tab.py:247 |
| 20 | `RunMonitorTab._on_executor_state_changed` | `state(ExecutionState)` | None | 버튼 활성화·반복 진행·완료/오류 처리, 동적 정밀도 테스트 연계 | tabs/run_monitor_tab.py:254 |
| 21 | `RunMonitorTab._on_executor_job_started` | `index: int, job` | None | 현재 행 선택 + 상태 run 표시 | tabs/run_monitor_tab.py:316 |
| 22 | `RunMonitorTab._on_executor_job_completed` | `index: int, job, success: bool` | None | 목록 O/X 마킹·실패 배경색·상태 갱신 | tabs/run_monitor_tab.py:323 |
| 23 | `RunMonitorTab._on_clear_log` | - | None | 로그 위젯 clear | tabs/run_monitor_tab.py:339 |
| 24 | `RunMonitorTab._on_save_log` | - | None | 로그를 파일로 저장 (OSError 처리) | tabs/run_monitor_tab.py:342 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `VISION_ORIGIN_CHECK_JOB_TYPE` (상수) | #6 | 기준점 확인 Job 타입 문자열 | tabs/run_monitor_tab.py:10 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/settings_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `SettingsTab.__init__` | `main_window` | - | 초기화 | tabs/settings_tab.py:11 |
| 2 | `SettingsTab.connect_signals` | - | None | 액션·버튼 20여종 + jog 12버튼 + connection_manager 콜백 연결 | tabs/settings_tab.py:15 |
| 3 | `SettingsTab.init_ui` | - | None | 로봇 IP 로드, 라디오 초기화, TF 비활성, 기준점 표시 | tabs/settings_tab.py:81 |
| 4 | `SettingsTab._on_connect` | - | None | connection_manager.connect(ip, 5s) 결과 반영 | tabs/settings_tab.py:140 |
| 5 | `SettingsTab._on_disconnect` | - | None | 연결 해제·버튼 상태 반영 | tabs/settings_tab.py:168 |
| 6 | `SettingsTab._on_connection_state_changed` | `state(ConnectionState)` | None | 상태별 로그·버튼 활성화 | tabs/settings_tab.py:184 |
| 7 | `SettingsTab._on_robot_status_changed` | `is_ready: bool` | None | 준비 상태 로그 | tabs/settings_tab.py:206 |
| 8 | `SettingsTab._on_read_base` | - | None | 좌표계 이름 읽어 콤보 동기화 | tabs/settings_tab.py:213 |
| 9 | `SettingsTab._on_apply_coordinate_system` | - | None | landmark_align_service.change_coordinate_system | tabs/settings_tab.py:225 |
| 10 | `SettingsTab._update_base_display` | - | None | base 이름 표시·vision base 시 경고색, ros_node.current_base_name 갱신 | tabs/settings_tab.py:239 |
| 11 | `SettingsTab._on_jog` | `axis, direction` | None | jog_service.jog | tabs/settings_tab.py:276 |
| 12 | `SettingsTab._on_jog_params_changed` | `step_mm: float, velocity_percent: int` | None | 스핀박스 동기화(blockSignals) | tabs/settings_tab.py:279 |
| 13 | `SettingsTab._init_tcp_pose_radiobuttons` | - | None | csm 현재 좌표계에 맞춰 라디오 체크 | tabs/settings_tab.py:288 |
| 14 | `SettingsTab._update_tcp_pose_labels` | - | None | (빈 구현) | tabs/settings_tab.py:301 |
| 15 | `SettingsTab._on_tcp_pose_changed` | `name: str, checked: bool` | None | 좌표계 설정 + 목표 자세로 PTP_T 이동 | tabs/settings_tab.py:304 |
| 16 | `SettingsTab._on_apply_tcp_pose` | - | None | 체크된 라디오 기준으로 #15 와 동일 이동 수행 | tabs/settings_tab.py:340 |
| 17 | `SettingsTab._on_read_jig_landmark` | - | None | g_TM_Landmark → jig landmark 스핀박스 | tabs/settings_tab.py:382 |
| 18 | `SettingsTab._on_calculate_jig_plate` | - | None | 4 Mark → JigPlaneCalculator 평면 산출·기입 | tabs/settings_tab.py:393 |
| 19 | `SettingsTab._on_open_jig_validator` | - | None | jig_plate_validator.py 서브프로세스 실행 | tabs/settings_tab.py:442 |
| 20 | `SettingsTab._read_tm_landmark_to_ui` | `name, spin_x..spin_rz` | None | g_TM_Landmark 읽기·파싱·기입 공통 | tabs/settings_tab.py:465 |
| 21 | `SettingsTab._on_read_mark_jig_plate` | `mark_num: int` | None | g_Jig_Landmark{n} 읽기·파싱·기입 | tabs/settings_tab.py:490 |
| 22 | `SettingsTab._on_save_jig_landmark` | - | None | csm 단일 landmark 설정+config 저장 | tabs/settings_tab.py:528 |
| 23 | `SettingsTab._on_save_jig_plate` | - | None | tool pose + 4 mark 다중 스캔 저장 | tabs/settings_tab.py:558 |
| 24 | `SettingsTab._on_tf_enable_changed` | `state` | None | csm TF 발행 시작/중지 | tabs/settings_tab.py:614 |
| 25 | `SettingsTab._reference_spinboxes` | - | list | 기준점 스핀박스 6개 수집 | tabs/settings_tab.py:635 |
| 26 | `SettingsTab._update_reference_display` | - | None | 허용오차·기준점·학습이력·σ 표시 | tabs/settings_tab.py:639 |
| 27 | `SettingsTab._on_reference_save_tolerance` | - | None | 허용오차 저장 | tabs/settings_tab.py:681 |
| 28 | `SettingsTab._on_reference_learn` | - | None | 조건 검증(RobotBase·TCP)→scan_landmark_averaged→save_reference | tabs/settings_tab.py:693 |
| 29 | `SettingsTab._on_vision_origin_check_now` | - | None | job_executor.vision_origin_check 실행·PASS/FAIL 표시 | tabs/settings_tab.py:748 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/task_edit_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `TaskEditTab.__init__` | `main_window` | - | 위젯 dict 초기화, `_init_ps2_jog` 호출 | tabs/task_edit_tab.py:18 |
| 2 | `TaskEditTab._init_ps2_jog` | - | None | joystick_service 시그널 4종 연결 + 체크박스 토글 연결 | tabs/task_edit_tab.py:27 |
| 3 | `TaskEditTab.connect_signals` | - | None | 시퀀스 목록·버튼 7종·트리 더블클릭·컨텍스트메뉴 연결 | tabs/task_edit_tab.py:37 |
| 4 | `TaskEditTab.init_ui` | - | None | 사용 가능 Task 트리 초기화 | tabs/task_edit_tab.py:61 |
| 5 | `TaskEditTab._init_available_tasks` | - | None | JOB_TYPES 를 카테고리별 트리 구성·전개 | tabs/task_edit_tab.py:64 |
| 6 | `TaskEditTab._on_available_task_double_clicked` | `item, column` | None | 리프 더블클릭 시 Task 추가 | tabs/task_edit_tab.py:87 |
| 7 | `TaskEditTab._on_add_task_to_sequence` | - | None | create_job → recipe.add_job → 목록 갱신 | tabs/task_edit_tab.py:91 |
| 8 | `TaskEditTab._on_delete_task_from_sequence` | - | None | 선택 Job 삭제 | tabs/task_edit_tab.py:106 |
| 9 | `TaskEditTab._on_move_task_up` | - | None | Job 위로 이동 | tabs/task_edit_tab.py:116 |
| 10 | `TaskEditTab._on_move_task_down` | - | None | Job 아래로 이동 | tabs/task_edit_tab.py:124 |
| 11 | `TaskEditTab._on_copy_task_in_sequence` | - | None | Job 복제 | tabs/task_edit_tab.py:132 |
| 12 | `TaskEditTab._on_task_sequence_context_menu` | `position` | None | 복사/이동/삭제 컨텍스트 메뉴 | tabs/task_edit_tab.py:143 |
| 13 | `TaskEditTab._update_task_sequence` | - | None | 시퀀스 리스트위젯 재구성 | tabs/task_edit_tab.py:168 |
| 14 | `TaskEditTab._on_apply_params` | - | None | UI→job.params 저장 후 목록 갱신 | tabs/task_edit_tab.py:179 |
| 15 | `TaskEditTab._on_task_sequence_selected` | `row: int` | None | 선택 Job 파라미터 폼 표시 | tabs/task_edit_tab.py:190 |
| 16 | `TaskEditTab._display_task_params` | `job` | None | 파라미터 타입별 위젯 동적 생성(200줄) + 실행버튼 라벨 분기 | tabs/task_edit_tab.py:198 |
| 17 | `TaskEditTab._exec_button_label` | `job` | str | 실행 버튼 기본 라벨 결정 | tabs/task_edit_tab.py:402 |
| 18 | `TaskEditTab._on_motion_type_changed` | `motion_type` | None | 라벨 갱신 위임 | tabs/task_edit_tab.py:409 |
| 19 | `TaskEditTab._update_param_labels` | `motion_type` | None | tcp/joint 에 따라 X..Rz ↔ J1..J6 라벨 전환 | tabs/task_edit_tab.py:412 |
| 20 | `TaskEditTab._clear_params_ui` | - | None | 파라미터 폼 전체 제거 | tabs/task_edit_tab.py:443 |
| 21 | `TaskEditTab._on_browse_dirpath` | `path_edit` | None | 저장 폴더 선택 다이얼로그 | tabs/task_edit_tab.py:456 |
| 22 | `TaskEditTab._save_params_from_ui` | `job` | None | 위젯→job.params 역직렬화(list 는 ast.literal_eval) + sync_robot_base | tabs/task_edit_tab.py:467 |
| 23 | `TaskEditTab._selected_job` | - | Job\|None | 현재 선택 Job 반환 | tabs/task_edit_tab.py:519 |
| 24 | `TaskEditTab._on_teach_position` | - | None | 현재 로봇 위치를 파라미터에 티칭(타입별 분기) | tabs/task_edit_tab.py:526 |
| 25 | `TaskEditTab._on_move_to_params` | - | None | command_gate 획득 후 `_move_to_params` 실행/해제 | tabs/task_edit_tab.py:592 |
| 26 | `TaskEditTab._move_to_params` | - | None | job.type 18종 분기 → 각 `_exec_*` 디스패치 | tabs/task_edit_tab.py:604 |
| 27 | `TaskEditTab._exec_gripper_command` | `command_value: int, command_name: str` | None | g_robot_command 쓰기로 그리퍼 명령 | tabs/task_edit_tab.py:704 |
| 28 | `TaskEditTab._exec_read_digital_io` | - | None | io_control_service.read_digital_input | tabs/task_edit_tab.py:716 |
| 29 | `TaskEditTab._exec_write_digital_io` | - | None | write_digital_output_by_name | tabs/task_edit_tab.py:734 |
| 30 | `TaskEditTab._exec_read_analog_io` | - | None | read_analog_input | tabs/task_edit_tab.py:756 |
| 31 | `TaskEditTab._exec_find_landmark` | - | None | 임시 Job 구성 → job_executor._exec_find_landmark | tabs/task_edit_tab.py:774 |
| 32 | `TaskEditTab._exec_scan_tm_landmark` | - | None | vision_manager 스캔+읽기, 결과 저장·표시 | tabs/task_edit_tab.py:822 |
| 33 | `TaskEditTab._exec_scan_tm_landmark_jig` | - | None | Jig 번호별 스캔+읽기 | tabs/task_edit_tab.py:846 |
| 34 | `TaskEditTab._exec_scan_align_tm_landmark` | - | None | 스캔+정렬 후 결과 읽기 | tabs/task_edit_tab.py:875 |
| 35 | `TaskEditTab._exec_align_tm_landmark` | - | None | landmark_align_service.align_to_landmark | tabs/task_edit_tab.py:894 |
| 36 | `TaskEditTab._exec_move_linear` | - | None | 저장 후 job_executor._exec_move_linear | tabs/task_edit_tab.py:906 |
| 37 | `TaskEditTab._exec_line_move_to_point` | - | None | job_executor._exec_line_move_to_point | tabs/task_edit_tab.py:922 |
| 38 | `TaskEditTab._exec_pose_keep_move_to_point` | - | None | job_executor._exec_pose_keep_move_to_point | tabs/task_edit_tab.py:938 |
| 39 | `TaskEditTab._exec_selected_job` | `label: str` | None | 범용 — job_executor._execute_job | tabs/task_edit_tab.py:954 |
| 40 | `TaskEditTab._exec_align_to_plane_normal` | - | None | job_executor._exec_align_to_plane_normal | tabs/task_edit_tab.py:969 |
| 41 | `TaskEditTab._add_offset_preset_row` | `layout` | None | 오차 preset 콤보+적용/저장/삭제 행 추가 | tabs/task_edit_tab.py:987 |
| 42 | `TaskEditTab._read_offset_widgets` | - | dict\|None | offset_{x,y,rx,ry,rz} 위젯 값 수집 | tabs/task_edit_tab.py:1025 |
| 43 | `TaskEditTab._write_offset_widgets` | `offset: dict` | bool | preset 값을 위젯에 기입 | tabs/task_edit_tab.py:1033 |
| 44 | `TaskEditTab._offset_preset_name` | - | str | 콤보 현재 텍스트 | tabs/task_edit_tab.py:1040 |
| 45 | `TaskEditTab._on_apply_offset_preset` | - | None | preset 조회→위젯 기입 | tabs/task_edit_tab.py:1046 |
| 46 | `TaskEditTab._on_save_offset_preset` | - | None | preset 저장 + 콤보 갱신 | tabs/task_edit_tab.py:1063 |
| 47 | `TaskEditTab._on_delete_offset_preset` | - | None | preset 삭제 + 콤보 갱신 | tabs/task_edit_tab.py:1082 |
| 48 | `TaskEditTab._teach_landmark_frame_offset` | `job` | None | executor 로 그리퍼 오차 추산→tool_offset_* 기입 | tabs/task_edit_tab.py:1102 |
| 49 | `TaskEditTab._teach_plane_align_offset` | `job` | None | 평면 정렬 오차 추산→offset 위젯 기입 | tabs/task_edit_tab.py:1121 |
| 50 | `TaskEditTab._exec_measure_plane_distance` | - | None | job_executor._exec_measure_plane_distance | tabs/task_edit_tab.py:1135 |
| 51 | `TaskEditTab._exec_motion_move` | - | None | teaching_service.move_to_position (joint/tcp, 축분해 옵션) | tabs/task_edit_tab.py:1152 |
| 52 | `TaskEditTab._on_ps2_jog_toggled` | `enabled: bool` | None | joystick_service.set_enabled | tabs/task_edit_tab.py:1188 |
| 53 | `TaskEditTab._on_ps2_jog_requested` | `axis: str, direction: int` | None | jog_service.jog_continuous | tabs/task_edit_tab.py:1191 |
| 54 | `TaskEditTab._on_ps2_mode_changed` | `mode: str` | None | 모드 라벨 갱신 | tabs/task_edit_tab.py:1194 |
| 55 | `TaskEditTab._on_ps2_connection_changed` | `connected: bool` | None | 상태 라벨 갱신 | tabs/task_edit_tab.py:1197 |
| 56 | `TaskEditTab._on_ps2_status_changed` | `message: str` | None | print 출력 | tabs/task_edit_tab.py:1201 |
| 57 | `TaskEditTab._exec_ai_inspection` | - | None | 모델 자동선택·로드→시그널 연결→이미지 캡처 트리거 | tabs/task_edit_tab.py:1204 |
| 58 | `TaskEditTab._on_ai_inspection_result` | `detections, annotated_image, fps` | None | 결과 표시 + 시그널 해제 | tabs/task_edit_tab.py:1261 |
| 59 | `TaskEditTab._on_ai_inspection_error` | `error_msg` | None | 에러 표시 + 시그널 해제 | tabs/task_edit_tab.py:1290 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `TaskEditTab.OFFSET_PRESET_KEYS` (클래스 상수) | #42,#43 | 오차 preset 키 5종 | tabs/task_edit_tab.py:985 |
| 2 | `TaskEditTab.LANDMARK_FRAME_OFFSET_KEYS` (클래스 상수) | #48 | tool_offset 키 6종 | tabs/task_edit_tab.py:1100 |

## src/TM_Robot_Task_Manager/tm_task_manager/tabs/vision_tab.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `VisionTab.__init__` | `main_window` | - | 초기화 | tabs/vision_tab.py:14 |
| 2 | `VisionTab.connect_signals` | - | None | 태그테이블·threshold·저장·jog·vision_manager·image_processing_service 연결 | tabs/vision_tab.py:18 |
| 3 | `VisionTab._connect_jog_signals` | - | None | 6축 ± 12버튼 + step/velocity 스핀박스 ↔ jog_service | tabs/vision_tab.py:45 |
| 4 | `VisionTab._on_jog_params_changed` | `step_mm: float, velocity_percent: int` | None | 스핀박스 blockSignals 후 동기화 | tabs/vision_tab.py:63 |
| 5 | `VisionTab.init_ui` | - | None | no-op | tabs/vision_tab.py:72 |
| 6 | `VisionTab.update_camera_image` | `cv_image(np.ndarray)` | None | BGR→RGB→QPixmap 스케일 표시 + mw.current_camera_image 갱신 | tabs/vision_tab.py:76 |
| 7 | `VisionTab.update_tag_pose` | `pose_msg(PoseStamped)` | None | frame_id 에서 tag_id 파싱 → vision_manager.update_tag_pose | tabs/vision_tab.py:94 |
| 8 | `VisionTab._on_tag_updated` | `tag_id: str, tag_data: dict` | None | 태그 테이블 갱신 위임 | tabs/vision_tab.py:114 |
| 9 | `VisionTab._update_tag_table` | - | None | 전체 태그 테이블 재구성 | tabs/vision_tab.py:117 |
| 10 | `VisionTab._on_tag_selection_changed` | - | None | 선택 태그 ID·위치·쿼터니언 라벨 표시 | tabs/vision_tab.py:135 |
| 11 | `VisionTab._on_use_selected_tag` | - | None | 선택 태그를 기준 태그(spinBox_tagId)로 설정 | tabs/vision_tab.py:155 |
| 12 | `VisionTab._on_apply_threshold` | - | None | image_processing_service.apply_threshold | tabs/vision_tab.py:169 |
| 13 | `VisionTab._on_processing_completed` | `processed_image` | None | 처리 이미지 표시 위임 | tabs/vision_tab.py:180 |
| 14 | `VisionTab._display_processed_image` | `image` | None | gray/color 분기 QImage 변환·표시 | tabs/vision_tab.py:183 |
| 15 | `VisionTab._on_save_processed_image` | - | None | 파일 다이얼로그 → image_processing_service.save_image | tabs/vision_tab.py:201 |

## src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plane_calculator.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | JigPlaneCalculator.__init__ | - | - | marks 리스트 | tools/jig_plane_calculator.py:48 |
| 2 | .load_from_yaml | yaml_path | bool | coordinate_definitions.jig_plate.scan_data 로드 | tools/jig_plane_calculator.py:51 |
| 3 | .load_from_marks | marks: List[Mark] | bool | 4개 검증 로드 | tools/jig_plane_calculator.py:79 |
| 4 | .load_from_dicts | mark_dicts | bool | dict 4개 로드 | tools/jig_plane_calculator.py:86 |
| 5 | .calculate_plane_pose | - | Optional[PlanePose] | 중심+축 벡터→오일러 | tools/jig_plane_calculator.py:97 |
| 6 | ._rotation_matrix_to_euler_zyx (static) | R | (rx,ry,rz) deg | 행렬→ZYX 오일러(짐벌 분기) | tools/jig_plane_calculator.py:147 |
| 7 | .get_plane_info | - | Optional[str] | 리포트 텍스트 | tools/jig_plane_calculator.py:163 |
| 8 | .to_dict | - | Optional[dict] | pose dict | tools/jig_plane_calculator.py:207 |
| 9 | .calculate_distance_matrix | - | Optional[dict] | 6개 상호거리 | tools/jig_plane_calculator.py:216 |
| 9a | .calculate_distance_matrix.dist (이너) | m1, m2 | float | 유클리드 거리 | tools/jig_plane_calculator.py:221 |
| 10 | .to_full_dict | - | Optional[dict] | pose+거리+시각 | tools/jig_plane_calculator.py:234 |
| 11 | _rotation_matrix_from_pose | pose | np.ndarray | scipy ZYX 회전행렬 | tools/jig_plane_calculator.py:257 |
| 12 | plane_normal_from_pose | pose | np.ndarray | 단위 법선 (퇴화 ValueError) | tools/jig_plane_calculator.py:266 |
| 13 | signed_point_to_plane_distance | point, plane_pose | float | 부호 거리 | tools/jig_plane_calculator.py:275 |
| 14 | pose_in_plane_frame | plate_pose, tcp_pose | dict | 절대→평면 상대 | tools/jig_plane_calculator.py:287 |
| 15 | pose_from_plane_frame | plate_pose, relative_pose | dict | 평면 상대→절대 | tools/jig_plane_calculator.py:310 |
| 16 | average_landmarks_from_files | file_paths | (averaged, used, skipped) | jig1~4 단순 평균 | tools/jig_plane_calculator.py:342 |
| 17 | tcp_pose_for_plane_normal | plane_pose, standoff_mm, rz_mode='keep', current_tcp=None | dict | 법선 접근 자세 (검증 ValueError) | tools/jig_plane_calculator.py:385 |
| 18 | apply_tool_offset | base_pose, offset(5키) | dict | 공구 오프셋 합성 (z=0) | tools/jig_plane_calculator.py:452 |
| 19 | tool_offset_from_poses | base_pose, actual_pose | (offset, dz) | 오프셋 역산 | tools/jig_plane_calculator.py:488 |
| 20 | main | argv(--config) | None | CLI 검산 | tools/jig_plane_calculator.py:517 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | MIN_AXIS_NORM (상수) | plane_normal, tcp_pose_for_plane_normal | 1e-9 퇴화 판정 | tools/jig_plane_calculator.py:252 |
| 2 | MIN_KEEP_PROJECTION (상수) | tcp_pose_for_plane_normal | 1e-6 투영 하한 | tools/jig_plane_calculator.py:254 |
| 3 | TOOL_OFFSET_KEYS (상수) | apply_tool_offset, offset_preset_service | 5키 정의 | tools/jig_plane_calculator.py:449 |

## src/TM_Robot_Task_Manager/tm_task_manager/tools/jig_plate_validator.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | rotation_matrix_from_euler | rx,ry,rz (deg) | np.ndarray | Rz@Ry@Rx 회전행렬 | tools/jig_plate_validator.py:52 |
| 2 | get_landmark_corners | x,y,z,rx,ry,rz, size=40 | np.ndarray(4,3) | 랜드마크 사각형 꼭짓점 | tools/jig_plate_validator.py:71 |
| 3 | ValidationResult.__str__ | - | str | PASS/FAIL 한 줄 | tools/jig_plate_validator.py:109 |
| 4 | JigPlateValidator.__init__ | - | - | marks/jig_landmark/results | tools/jig_plate_validator.py:127 |
| 5 | .load_from_yaml | yaml_path | bool | jig_landmark+jig_plate scan_data 로드 | tools/jig_plate_validator.py:132 |
| 6 | .load_from_dicts | mark_dicts | bool | dict 4개 로드 | tools/jig_plate_validator.py:177 |
| 7 | .get_side_lengths | - | Dict[str,float] | 6개 변/대각 거리 | tools/jig_plate_validator.py:192 |
| 8 | ._distance | m1, m2 | float | 유클리드 거리 | tools/jig_plate_validator.py:207 |
| 9 | ._angle_between_vectors | v1, v2 | float(deg) | 벡터 사이각 | tools/jig_plate_validator.py:214 |
| 10 | .check_rectangle | - | List[ValidationResult] | 대향변·대각·직각 검사 | tools/jig_plate_validator.py:227 |
| 11 | .check_plane_parallelism | - | List[ValidationResult] | jig_landmark 대비 Ry 편차 | tools/jig_plate_validator.py:286 |
| 12 | .check_z_consistency | - | List[ValidationResult] | Z 평균 편차 | tools/jig_plate_validator.py:309 |
| 13 | .run_validation | - | str | 전 검사+리포트 텍스트 | tools/jig_plate_validator.py:330 |
| 14 | .calculate_center | - | Optional[Mark] | 중심(rx 랩어라운드 보정) | tools/jig_plate_validator.py:389 |
| 15 | ValidatorWindow.__init__ | - | - | ui 로드·플롯·시그널·기본 yaml | tools/jig_plate_validator.py:418 |
| 16 | ._setup_plots | - | None | 2D/Z/3D Figure 구성 | tools/jig_plate_validator.py:438 |
| 17 | ._connect_signals | - | None | 버튼 3종 연결 | tools/jig_plate_validator.py:466 |
| 18 | ._get_jig_data_dir | - | Path | data/jig_mark 최신 날짜 폴더 | tools/jig_plate_validator.py:471 |
| 19 | ._try_load_default_yaml | - | None | 최신 jig_plate_*.yaml 또는 positions.yaml | tools/jig_plate_validator.py:484 |
| 20 | ._on_load_yaml | - | None | 파일 다이얼로그 | tools/jig_plate_validator.py:494 |
| 21 | ._load_yaml | file_path | None | 로드+자동 검사 | tools/jig_plate_validator.py:505 |
| 22 | ._on_run_validation | - | None | 검사+플롯 갱신 | tools/jig_plate_validator.py:515 |
| 23 | ._update_2d_plot | - | None | XY 실측/이상 사각형 | tools/jig_plate_validator.py:529 |
| 24 | ._update_z_plot | - | None | Z 막대+허용선 | tools/jig_plate_validator.py:568 |
| 25 | ._update_3d_plot | - | None | 3D 랜드마크·법선 | tools/jig_plate_validator.py:603 |
| 26 | ._on_save_report | - | None | Report/날짜/ 텍스트 저장 | tools/jig_plate_validator.py:689 |
| 27 | main | argv(--config) | None | QApplication 기동 | tools/jig_plate_validator.py:718 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | plt.rcParams 폰트 설정 (가변, import 부수효과) | 모듈 로드 시 | 한글 폰트 탐색·설정 | tools/jig_plate_validator.py:38-47 |
| 2 | LANDMARK_SIZE (상수) | get_landmark_corners, 3D 플롯 | 40mm | tools/jig_plate_validator.py:49 |
| 3 | TOLERANCE_* 5종 (클래스 상수) | check_* | 허용값 (1.0mm/0.5°/1.0mm) | tools/jig_plate_validator.py:121-125 |

## src/TM_Robot_Task_Manager/tm_task_manager/tools/landmark_frame.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | landmark_frame_rotation | landmark: dict, frame_mode='rz_only' | np.ndarray | 모드별 회전행렬 (미지 모드 ValueError) | tools/landmark_frame.py:20 |
| 2 | _origin | landmark | np.ndarray | 원점 벡터 | tools/landmark_frame.py:40 |
| 3 | pose_from_landmark_frame | landmark, relative, frame_mode | dict | 상대→절대 | tools/landmark_frame.py:45 |
| 4 | pose_in_landmark_frame | landmark, pose, frame_mode | dict | 절대→상대 | tools/landmark_frame.py:66 |
| 5 | apply_tool_offset_6dof | base_pose, offset | dict | 공구계 6DOF 오프셋 합성 | tools/landmark_frame.py:88 |
| 6 | tool_offset_6dof_from_poses | base_pose, actual_pose | dict | 두 pose 간 오프셋 역산 | tools/landmark_frame.py:107 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | POSE_KEYS (상수) | (선언 — 파일 내 직접 사용 없음) | 축 키 | tools/landmark_frame.py:13 |
| 2 | FRAME_MODE_RZ_ONLY/FULL/FRAME_MODES (상수) | landmark_frame_rotation, pallet_recipe_generator | 모드 식별 | tools/landmark_frame.py:15-17 |
| 3 | TOOL_OFFSET_6DOF_KEYS (상수) | (외부 사용용 선언) | 오프셋 키 | tools/landmark_frame.py:85 |

## src/TM_Robot_Task_Manager/tm_task_manager/tools/landmark_parser.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | _echo | value: str | str | 원문 200자 제한 에코 | tools/landmark_parser.py:25 |
| 2 | parse_tm_landmark | value: str | (bool, LandmarkPose/str) | 중괄호 6값 파싱 | tools/landmark_parser.py:33 |
| 3 | parse_tm_landmark_to_dict | value, detected=None | (bool, dict/str) | dict 변환(+detected) | tools/landmark_parser.py:61 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | RAW_ECHO_LIMIT (상수) | _echo | 200자 | tools/landmark_parser.py:22 |

## src/TM_Robot_Task_Manager/tm_task_manager/tools/record_place_pose.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | read_current_tcp | timeout_sec=5.0 | Optional[Dict] | 임시 노드로 tool_pose 1건 수신 | tools/record_place_pose.py:32 |
| 1a | read_current_tcp._on_pose (이너) | msg: PoseStamped | None | 첫 메시지 변환·저장 | tools/record_place_pose.py:47 |
| 2 | build_reference | plate_dir: Path, prefix | (plate_pose, used, skipped) | 측정파일 평균→평면 pose | tools/record_place_pose.py:78 |
| 3 | _fmt | pose | str | 6축 포맷 | tools/record_place_pose.py:98 |
| 4 | print_summary | out_dir, pallet | int | 기록 통계 출력 | tools/record_place_pose.py:103 |
| 5 | main | argv | int | 기준 구축→TCP 수신→상대 계산→yaml 저장 | tools/record_place_pose.py:134 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | PACKAGE_ROOT (상수) | 기본 경로 | parents[2] 패키지 루트 | tools/record_place_pose.py:26 |
| 2 | DEFAULT_PLATE_DIR/DEFAULT_OUT_DIR (상수) | main | data/plate_pose_calc·place_pose | tools/record_place_pose.py:27-28 |
| 3 | POSE_KEYS (상수) | 저장·출력 | 축 키 | tools/record_place_pose.py:29 |
| 4 | sys.path 삽입 (가변, import 부수효과) | 모듈 로드 | parents[2] 삽입 | tools/record_place_pose.py:17 |

## src/TM_Robot_Task_Manager/tools/convert_to_runtime.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `RecipeConverter.__init__` | `jig_plate_file, runtime_job_config, landmark_pose_file: Optional[str]` | 없음 | 소스 파일 경로 보관 | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:38 |
| 2 | `RecipeConverter.create_transform_matrix` | `pose: Dict[str,float]` | `np.ndarray(4,4)` | ZYX 오일러(deg)→동차변환행렬 | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:45 |
| 3 | `RecipeConverter.extract_pose` | `T: np.ndarray` | `Dict`(소수 2자리) | 행렬→X..Rz 추출(반올림) | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:59 |
| 4 | `RecipeConverter.load_jig_plate_calibration` | 없음 | `Optional[Dict]` | jig_landmark.tool_pose 읽기(불완전/실패 시 None) | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:76 |
| 5 | `RecipeConverter.load_landmark_pose` | 없음 | `Optional[Dict]` | landmark_pose YAML 의 landmark 키 읽기 | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:111 |
| 6 | `RecipeConverter._load_runtime_job_params` | `job_type: str` | `Dict` | 기본 파라미터 + runtime_job_defaults.yaml 병합 | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:145 |
| 7 | `RecipeConverter._insert_runtime_only_jobs` | `jobs: list` | `list` | find_landmark 등 삽입 + id 재부여 | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:160 |
| 8 | `RecipeConverter.convert_to_relative` | `master_file, output_file: str` | `bool` | 전체 변환 파이프라인(기준점 탐색→상대화→역변환 검증→저장) | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:197 |
| 9 | `find_latest_jig_plate_file` | 없음 | `Optional[str]` | data/jig_mark 최신 mtime YAML | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:377 |
| 10 | `find_latest_landmark_pose_file` | 없음 | `Optional[str]` | data/landmark_pose 최신 YAML | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:393 |
| 11 | `find_latest_runtime_job_config` | 없음 | `Optional[str]` | config/runtime_job_defaults.yaml 존재 확인 | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:409 |
| 12 | `main` | `sys.argv`(master, output, jig_plate) | `int` | 인자 해석 → 변환 실행 → 종료코드 | src/TM_Robot_Task_Manager/tools/convert_to_runtime.py:419 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | `RUNTIME_ONLY_JOBS` (상수) | _load_runtime_job_params, _insert_runtime_only_jobs | Runtime 전용 job 정의(find_landmark, 삽입 위치·기본 파라미터) | tools/convert_to_runtime.py:18-32 |

## src/TM_Robot_Task_Manager/tools/test_job_executor_integration.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `test_coordinate_mode_detection` | 없음 | `bool` | job id 구간별 기대 모드와 대조 | src/TM_Robot_Task_Manager/tools/test_job_executor_integration.py:18 |
| 2 | `test_job_params_separation` | 없음 | `bool` | coordinate_mode 가 params 가 아닌 job 레벨에 있는지 | src/TM_Robot_Task_Manager/tools/test_job_executor_integration.py:75 |
| 3 | `test_original_absolute_storage` | 없음 | `bool` | relative job 전부 original_absolute 보유 확인 | src/TM_Robot_Task_Manager/tools/test_job_executor_integration.py:112 |

## src/TM_Robot_Task_Manager/tools/test_job_executor_transform.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `MockJobExecutor.__init__` | 없음 | 없음 | 변환행렬·기준 pose 초기화 | src/TM_Robot_Task_Manager/tools/test_job_executor_transform.py:17 |
| 2 | `MockJobExecutor._create_transform_matrix` | `pose` | `ndarray(4,4)` | ZYX→동차행렬 (M7 #2 중복) | src/TM_Robot_Task_Manager/tools/test_job_executor_transform.py:21 |
| 3 | `MockJobExecutor._extract_pose` | `T` | `dict`(반올림 없음) | 행렬→pose | src/TM_Robot_Task_Manager/tools/test_job_executor_transform.py:34 |
| 4 | `MockJobExecutor._transform_relative_to_absolute` | `rel_pose` | `dict` | T_tm @ T_rel 후 추출 | src/TM_Robot_Task_Manager/tools/test_job_executor_transform.py:50 |
| 5 | `test_transform_consistency` | 없음 | `bool` | 8케이스 executor vs converter 대조 | src/TM_Robot_Task_Manager/tools/test_job_executor_transform.py:62 |
| 5a | `test_transform_consistency.compare_pose` | `p1, p2, tolerance=0.01` | `(bool, key, diff)` | 축별 허용오차 비교(각도 랩 처리) | src/TM_Robot_Task_Manager/tools/test_job_executor_transform.py:110 |

## src/TM_Robot_Task_Manager/tools/test_recipe_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `test_load_runtime_file` | 없음 | `int`(0/1) | runtime 5파일 필드·모드 분포 검사 | src/TM_Robot_Task_Manager/tools/test_recipe_manager.py:15 |
| 2 | `test_save_load_cycle` | 없음 | 없음 | 저장→재로드 비교 출력(판정 미반환) | src/TM_Robot_Task_Manager/tools/test_recipe_manager.py:94 |

## src/TM_Robot_Task_Manager/tools/verify_conversion.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `create_transform_matrix` | `pose: dict` | `np.ndarray(4,4)` | ZYX 오일러→동차행렬 (M7 #2 와 중복 구현) | src/TM_Robot_Task_Manager/tools/verify_conversion.py:12 |
| 2 | `extract_pose` | `T` | `dict` | 행렬→pose(2자리 반올림) (M7 #3 중복) | src/TM_Robot_Task_Manager/tools/verify_conversion.py:30 |
| 3 | `verify_runtime_file` | `runtime_file: str` | `bool` | reference 로드→relative job 역변환 오차 판정 | src/TM_Robot_Task_Manager/tools/verify_conversion.py:48 |
| 3a | `verify_runtime_file.angle_diff` | `a1, a2` | `float` | 360° 랩 고려 각도차 | src/TM_Robot_Task_Manager/tools/verify_conversion.py:96 |

## src/TM_Robot_Task_Manager/tools/verify_recipe_manager.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `verify_job_class` | 없음 | `bool`(항상 True) | Job 생성·to_dict/from_dict 필드 보존 출력 | src/TM_Robot_Task_Manager/tools/verify_recipe_manager.py:17 |
| 2 | `verify_recipe_class` | 없음 | `bool`(항상 True) | Recipe 메타필드 왕복 출력 | src/TM_Robot_Task_Manager/tools/verify_recipe_manager.py:53 |
| 3 | `verify_runtime_file_loading` | 없음 | `bool` | 실파일 로드 후 필드 체크리스트 판정 | src/TM_Robot_Task_Manager/tools/verify_recipe_manager.py:100 |
| 4 | `verify_save_load_cycle` | 없음 | `bool` | 저장→재로드 동등성 비교(임시파일) | src/TM_Robot_Task_Manager/tools/verify_recipe_manager.py:144 |
| 5 | `verify_all_runtime_files` | 없음 | `bool` | runtime 5파일 필수 필드 전수 확인 | src/TM_Robot_Task_Manager/tools/verify_recipe_manager.py:191 |

## src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `executor` (fixture) | 없음 | JobExecutor | current_tcp_pose 모킹된 실행기 + 로그 수집 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:15 |
| 2 | `_job` | **params | Job | sdc_tcp_base Job 생성(wait 0 기본) | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:24 |
| 3 | `_logs` | executor | str | 수집 로그 결합 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:29 |
| 4 | `_patch_entry` | entry | patcher | ConfigManager.get_position 모킹 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:33 |
| 5 | `test_position_entry_registered_in_yaml` | 없음 | - | 실제 positions.yaml 의 sdc_tcp_base 등록(90/-22/-90) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:37 |
| 6 | `test_job_type_is_registered` | 없음 | - | JOB_TYPES 등록(Motion, velocity·wait 만) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:44 |
| 7 | `test_dispatch_reaches_handler` | executor | - | _execute_job 분기 도달 검증 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:52 |
| 8 | `test_keeps_position_and_applies_yaml_orientation` | executor | - | 위치 유지 + yaml 자세 인자 검증 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:59 |
| 9 | `test_fails_when_entry_missing` | executor | - | yaml 미등록 시 False + 이동 미호출 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:71 |
| 10 | `test_fails_on_wrong_values_count` | executor | - | values 3개 아니면 False | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:79 |
| 11 | `test_fails_without_current_tcp` | executor | - | TCP 미수신 시 False + 이동 미호출 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:88 |
| 12 | `test_fails_without_ros_node` | 없음 | - | ros_node 부재 시 False | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:97 |
| 13 | `test_fails_when_motion_rejected` | executor | - | 이동 거부 시 False + 실패 로그 | src/TM_Robot_Task_Manager/test/test_sdc_tcp_base.py:106 |

## src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `executor` (fixture) | 없음 | JobExecutor | current_tcp_pose·detected_landmark_pose 모킹된 실행기 + 로그 수집 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:17 |
| 2 | `_job` | **params | Job | sdc_palette_tcp_align Job 생성(wait 0 기본) | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:27 |
| 3 | `_logs` | executor | str | 수집 로그 결합 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:32 |
| 4 | `_patch_entry` | entry | patcher | ConfigManager.get_position 모킹 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:36 |
| 5 | `test_offset_entry_registered_in_yaml` | 없음 | - | 실제 positions.yaml 의 sdc_palette_tcp_align 등록([0,-22,0]) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:40 |
| 6 | `test_job_type_is_registered` | 없음 | - | JOB_TYPES 등록(Landmark, velocity·wait 만) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:47 |
| 7 | `test_dispatch_reaches_handler` | executor | - | _execute_job 분기 도달 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:55 |
| 8 | `test_keeps_position_and_reaches_expected_target` | executor | - | 위치 유지 + 스냅 목표 euler 기대값 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:62 |
| 8a | `test_target_z_axis_matches_marker_normal` | executor | - | 목표 Z축 ≡ 마커 법선 0.01° 이내(지그 공차 0.4° 요구) | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:79 |
| 9 | `test_fails_without_landmark_scan` | executor | - | 스캔 전 실행 시 False + 이동 미호출 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:75 |
| 10 | `test_fails_when_entry_missing` | executor | - | yaml 미등록 시 False | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:84 |
| 11 | `test_fails_on_wrong_values_count` | executor | - | offset 3개 아니면 False | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:92 |
| 12 | `test_fails_without_current_tcp` | executor | - | TCP 미수신 시 False | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:101 |
| 13 | `test_fails_when_motion_rejected` | executor | - | 이동 거부 시 False + 실패 로그 | src/TM_Robot_Task_Manager/test/test_sdc_palette_tcp_align.py:110 |

## src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `executor` (fixture) | 없음 | JobExecutor | current_tcp_pose·detected_landmark_pose(6DOF) 모킹 + 로그 수집 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:18 |
| 2 | `_job` | **params | Job | sdc_palette_inlet_move Job 생성(wait 0 기본) | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:29 |
| 3 | `_logs` | executor | str | 수집 로그 결합 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:34 |
| 4 | `_patch_entry` | entry | patcher | ConfigManager.get_position 모킹 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:38 |
| 5 | `test_offset_entry_registered_in_yaml` | 없음 | - | 실제 positions.yaml 등록([65.4, 220.74, -310.54]) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:42 |
| 6 | `test_job_type_is_registered` | 없음 | - | JOB_TYPES 등록(Landmark, velocity·wait 만) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:49 |
| 7 | `test_dispatch_reaches_handler` | executor | - | _execute_job 분기 도달 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:57 |
| 8 | `test_moves_to_marker_relative_inlet_keeping_orientation` | executor | - | 목표 = 마커+R@offset(실측 입구 좌표 재현) + 자세 유지 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:64 |
| 8a | `test_correction_params_shift_target_in_marker_frame` | executor | - | dx/dy/dz 보정이 마커 frame 으로 목표에 가산되는지 검증 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:85 |
| 9 | `test_fails_without_landmark_scan` | executor | - | 스캔 전 실행 시 False + 이동 미호출 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:79 |
| 10 | `test_fails_when_entry_missing` | executor | - | yaml 미등록 시 False | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:88 |
| 11 | `test_fails_on_wrong_values_count` | executor | - | offset 3개 아니면 False | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:96 |
| 12 | `test_fails_without_current_tcp` | executor | - | TCP 미수신 시 False | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:105 |
| 13 | `test_fails_when_motion_rejected` | executor | - | 이동 거부 시 False + 실패 로그 | src/TM_Robot_Task_Manager/test/test_sdc_palette_inlet_move.py:114 |

## src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `executor` (fixture) | 없음 | JobExecutor | current_tcp_pose·detected_landmark_pose 모킹 + 로그 수집 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:16 |
| 2 | `_job` | **params | Job | sdc_marker_move Job 생성(wait 0 기본) | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:27 |
| 3 | `_logs` | executor | str | 수집 로그 결합 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:32 |
| 4 | `test_job_type_is_registered` | 없음 | - | JOB_TYPES 등록(Landmark, dx/dy/dz/velocity/wait) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:36 |
| 5 | `test_dispatch_reaches_handler` | executor | - | _execute_job 분기 도달 검증 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:44 |
| 6 | `test_dz_moves_along_marker_normal_keeping_orientation` | executor | - | dz=50 이동벡터 ≡ 마커 Z축×50mm + 자세 유지 검증 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:50 |
| 7 | `test_dx_dy_move_parallel_to_marker_surface` | executor | - | dx·dy 이동벡터의 법선 성분 0 (표면 평행) 검증 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:66 |
| 8 | `test_fails_without_landmark_scan` | executor | - | 스캔 전 실행 시 False + 이동 미호출 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:82 |
| 9 | `test_fails_without_current_tcp` | executor | - | TCP 미수신 시 False | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:90 |
| 10 | `test_fails_when_motion_rejected` | executor | - | 이동 거부 시 False + 실패 로그 | src/TM_Robot_Task_Manager/test/test_sdc_marker_move.py:98 |

## sdc_gripper_open / sdc_gripper_close (HITBOT Z-EFG-C35 직결 RTU)

상세 권위본: `tm_task_manager/hardware/docs/function_table.md`(RTU 헬퍼 전 함수) · `test/docs/function_table.md`(단위 8종). 장치 계약은 C++ 벤더 스택(`src/Actuators/gripper/hitbot_zefg/`)과 이중 정의 — debt-026 동기화 의무.

| # | 심볼 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | JOB_TYPES `sdc_gripper_open`/`sdc_gripper_close` | — | dict | Gripper 카테고리 2항목 — params: position(open 0.0 / close 16.56=실측 파지)·speed 20·current 0.3·timeout 5 | src/TM_Robot_Task_Manager/tm_task_manager/recipe_manager.py:795,805 |
| 2 | dispatch elif 2분기 | job_type | bool | `_exec_sdc_gripper(opening=True/False)` 위임 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:532-535 |
| 3 | `_exec_sdc_gripper` | job, opening | bool | params 추출→`zefg_serial.move_to` 호출→성공/실패 로그 | src/TM_Robot_Task_Manager/tm_task_manager/job_executor.py:1170 |
| 4 | `zefg_serial.move_to` | pos·speed·current·timeout | (bool, 사유) | 범위검증(밖=무송신)→속도·전류·위치 기록→폴링. Dropping/Clamping 은 Moving 관측 또는 STATUS_GRACE_S(0.3s) 후에만 판정(래치 오탐 방지 — 실기 검증 2026-08-30) | src/TM_Robot_Task_Manager/tm_task_manager/hardware/zefg_serial.py:114-163 |
