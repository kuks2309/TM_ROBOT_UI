# src/Vision — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/Vision/Cpp/bindings/py_fast_vision.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 4 | numpy_to_mat | input: py::array_t&lt;uint8&gt; | cv::Mat | 2D/3D numpy→Mat clone(그 외 차원 예외) | src/Vision/Cpp/bindings/py_fast_vision.cpp:12 |
| 5 | mat_to_numpy | mat: cv::Mat | py::array_t&lt;uint8&gt; | Mat→numpy 복사(1/3채널 shape·stride) | src/Vision/Cpp/bindings/py_fast_vision.cpp:34 |
| 6 | PYBIND11_MODULE(fast_vision) | m | — | 3함수 바인딩 + TM_* 상수 6종 노출 | src/Vision/Cpp/bindings/py_fast_vision.cpp:49 |
| 6a | PYBIND11_MODULE.λ1 | input, threshold1, threshold2 | array | fast_edge_detect 래퍼 | src/Vision/Cpp/bindings/py_fast_vision.cpp:52 |
| 6b | PYBIND11_MODULE.λ2 | image, templ, method | tuple | fast_template_match 래퍼 | src/Vision/Cpp/bindings/py_fast_vision.cpp:68 |
| 6c | PYBIND11_MODULE.λ3 | input, min_area | list | fast_find_contours 래퍼(점 튜플 리스트화) | src/Vision/Cpp/bindings/py_fast_vision.cpp:85 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | m.attr TM_SQDIFF~TM_CCOEFF_NORMED (상수) | 파이썬 소비자 | OpenCV 매칭 상수 재노출 | src/Vision/Cpp/bindings/py_fast_vision.cpp:108-113 |

## src/Vision/Cpp/src/fast_vision.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | fast_edge_detect | input: Mat, threshold1=50, threshold2=150 | Mat | 그레이→블러→Canny | src/Vision/Cpp/src/fast_vision.cpp:5 (선언 include/fast_vision.hpp:11) |
| 2 | fast_template_match | image, templ, method=TM_CCOEFF_NORMED | tuple&lt;int,int,double&gt; | 템플릿 매칭 최적 위치+점수 | src/Vision/Cpp/src/fast_vision.cpp:21 (선언 include/fast_vision.hpp:15) |
| 3 | fast_find_contours | input, min_area=100 | vector&lt;vector&lt;Point&gt;&gt; | 이진화 판단→외곽 컨투어→면적 필터 | src/Vision/Cpp/src/fast_vision.cpp:48 (선언 include/fast_vision.hpp:23) |

## src/Vision/Python/plugins/base_plugin.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | BaseVisionPlugin.__init__ | name: str, description: str="" | — | 이름·설명·초기화 플래그 | src/Vision/Python/plugins/base_plugin.py:10 |
| 2 | BaseVisionPlugin.initialize | params: Dict|None | bool | 플래그 세트 후 True | src/Vision/Python/plugins/base_plugin.py:15 |
| 3 | BaseVisionPlugin.process (abstract) | image: np.ndarray, params | Dict | 처리 계약 | src/Vision/Python/plugins/base_plugin.py:21 |
| 4 | BaseVisionPlugin.cleanup | — | None | 플래그 해제 | src/Vision/Python/plugins/base_plugin.py:25 |
| 5 | BaseVisionPlugin.is_initialized (property) | — | bool | 초기화 여부 | src/Vision/Python/plugins/base_plugin.py:29 |

## src/Vision/Python/plugins/edge_detection.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 6 | EdgeDetectionPlugin.__init__ | — | — | name="edge_detection" 등록 | src/Vision/Python/plugins/edge_detection.py:12 |
| 7 | EdgeDetectionPlugin.process | image, params(threshold1/2, blur_size, use_blur) | Dict | 그레이→(블러)→Canny, 엣지 통계 | src/Vision/Python/plugins/edge_detection.py:18 |

## src/Vision/Python/plugins/fast_edge.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 8 | FastEdgePlugin.__init__ | — | — | C++ 모듈 로드 시도 | src/Vision/Python/plugins/fast_edge.py:11 |
| 9 | FastEdgePlugin._load_cpp_module | — | bool | import fast_vision try/except | src/Vision/Python/plugins/fast_edge.py:19 |
| 10 | FastEdgePlugin.uses_cpp (property) | — | bool | C++ 백엔드 사용 여부 | src/Vision/Python/plugins/fast_edge.py:29 |
| 11 | FastEdgePlugin.process | image, params(threshold1/2) | Dict | C++ 또는 OpenCV 폴백 Canny + backend 표기 | src/Vision/Python/plugins/fast_edge.py:33 |

## src/Vision/Python/plugins/__init__.py

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | __all__ (상수) | import * | 3클래스 재수출(BaseVisionPlugin·EdgeDetectionPlugin·FastEdgePlugin) | src/Vision/Python/plugins/__init__.py:6 |

(src/Vision/Python/__init__.py · src/Vision/Python/utils/__init__.py 는 빈 패키지 마커 — 함수·전역 없음)

## src/Vision/ROS2/tm_aruco_detect/include/tm_aruco_detect/aruco_detector.hpp

| # | 심볼 | 종류 | 기능 | 위치(file:line) |
|---|---|---|---|---|
| d1 | TM_ARUCO_USE_OBJDETECT_API | 매크로 | OpenCV 4.7 objdetect/contrib aruco API 분기 | src/Vision/ROS2/tm_aruco_detect/include/tm_aruco_detect/aruco_detector.hpp:14 |
| d2 | ArucoDetectorNode | 클래스 선언 | 마커 검출 노드(멤버·private 메서드 선언 6종) | src/Vision/ROS2/tm_aruco_detect/include/tm_aruco_detect/aruco_detector.hpp:22 |

## src/Vision/ROS2/tm_aruco_detect/launch/aruco_detect.launch.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 7 | generate_launch_description | — | LaunchDescription | 인자 2종 + yaml 파라미터로 노드 기동 | src/Vision/ROS2/tm_aruco_detect/launch/aruco_detect.launch.py:10 |

## src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | ArucoDetectorNode::ArucoDetectorNode | options: NodeOptions | — | 파라미터 8종 declare/get, 카메라 행렬 구성, 검출기·sub/pub/TF 생성 | src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp:9 |
| 2 | ArucoDetectorNode::imageCallback (private) | msg: Image::SharedPtr | void | bgr8 검증→Mat 래핑·클론→detectMarkers→디버그 이미지 발행 | src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp:68 |
| 3 | ArucoDetectorNode::detectMarkers (private) | image: Mat& | void | 마커 검출→solvePnP(IPPE_SQUARE)→마커별 포즈 발행·TF·축 드로잉 | src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp:96 |
| 4 | ArucoDetectorNode::publishMarkerPose (private) | marker_id, rvec, tvec | void | Rodrigues→쿼터니언 변환 후 PoseStamped 발행 | src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp:142 |
| 5 | ArucoDetectorNode::broadcastTF (private) | marker_id, rvec, tvec | void | TransformStamped(aruco_marker_&lt;id&gt;) 브로드캐스트 | src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp:174 |
| 6 | main | argc, argv | int | spin(ArucoDetectorNode) | src/Vision/ROS2/tm_aruco_detect/src/aruco_detector.cpp:207 |
