# src/AI — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/AI/engine/yolov8/verify_yolov8.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | main (verify) | — | int | torch/ultralytics/cv2 import·모델 로드 검증 | src/AI/engine/yolov8/verify_yolov8.py:5 |

## src/AI/tasks/jig_latch/pc/inference.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 2 | parse_args | — | Namespace | 모델/폴더/신뢰도/크기/모드 인자 | src/AI/tasks/jig_latch/pc/inference.py:39 |
| 3 | load_model | model_path | YOLO|None | 존재 확인 후 YOLO 로드(실패 None) | src/AI/tasks/jig_latch/pc/inference.py:62 |
| 4 | get_class_colors | — | Dict[int,BGR] | 클래스 색상표 | src/AI/tasks/jig_latch/pc/inference.py:84 |
| 5 | draw_segmentation_results | image, results, conf_threshold | ndarray | 마스크 오버레이+minAreaRect 각도→OPEN/CLOSE 판정·주석 | src/AI/tasks/jig_latch/pc/inference.py:91 |
| 6 | ImageViewer.__init__ | image_files, model, args | — | 뷰어 상태 초기화 | src/AI/tasks/jig_latch/pc/inference.py:217 |
| 7 | ImageViewer.process_image | idx | (image, result, path) | 리사이즈→추론→드로잉 | src/AI/tasks/jig_latch/pc/inference.py:228 |
| 8 | ImageViewer.save_current_image | — | None | 현재 결과 저장 | src/AI/tasks/jig_latch/pc/inference.py:247 |
| 9 | ImageViewer.update_display | — | None | 원본/결과 2패널 갱신 | src/AI/tasks/jig_latch/pc/inference.py:257 |
| 10 | ImageViewer.on_key | event | None | ←/→/s/q 키 처리 | src/AI/tasks/jig_latch/pc/inference.py:287 |
| 11 | ImageViewer.on_close | event | None | 창 닫힘 처리 | src/AI/tasks/jig_latch/pc/inference.py:308 |
| 12 | ImageViewer.close_viewer | — | None | 뷰어 종료 | src/AI/tasks/jig_latch/pc/inference.py:311 |
| 13 | ImageViewer.run | — | None | figure 생성·이벤트 연결·show | src/AI/tasks/jig_latch/pc/inference.py:318 |
| 14 | run_batch_inference | model, args | None | 폴더 전체 추론·저장(headless) | src/AI/tasks/jig_latch/pc/inference.py:338 |
| 15 | run_single_inference | model, args | None | 단일 이미지 추론(표시/저장) | src/AI/tasks/jig_latch/pc/inference.py:391 |
| 16 | main (inference) | — | None | 인자→모델 로드→모드 분기 | src/AI/tasks/jig_latch/pc/inference.py:442 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | font_path (상수) / font_prop (가변·미사용) | 모듈 로드 시 | 한글 폰트 rcParams 설정 | src/AI/tasks/jig_latch/pc/inference.py:19-23 / latch_predict.py:18-21 |
| 2 | PROJECT_ROOT (상수) | DEFAULT_* 경로 | 스크립트 기준 상위 경로 | src/AI/tasks/jig_latch/pc/inference.py:25 |
| 3 | DEFAULT_MODEL_PATH·TEST_DIR·OUTPUT_DIR·IMAGE_WIDTH(640)·HEIGHT(480)·CONFIDENCE(0.7) (상수) | parse_args | 기본 인자 | src/AI/tasks/jig_latch/pc/inference.py:27-32 |
| 4 | CLASS_NAMES (상수) | draw/main | {0:"jig_latch"} | src/AI/tasks/jig_latch/pc/inference.py:34-36 |

## src/AI/tasks/jig_latch/pc/latch_predict.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 17 | parse_args | — | Namespace | 구버전 인자(320×640 기본) | src/AI/tasks/jig_latch/pc/latch_predict.py:31 |
| 18 | load_trained_model | model_path | YOLO|None | 모델 로드 | src/AI/tasks/jig_latch/pc/latch_predict.py:50 |
| 19 | get_class_colors | — | Dict | 색상표 | src/AI/tasks/jig_latch/pc/latch_predict.py:64 |
| 20 | get_class_names | — | Dict | {0:"latch"} | src/AI/tasks/jig_latch/pc/latch_predict.py:71 |
| 21 | draw_segmentation_results | image, results, conf_threshold | ndarray | #5 와 동일 파이프라인 구버전(state 미초기화) | src/AI/tasks/jig_latch/pc/latch_predict.py:78 |
| 22 | ImageViewer.__init__ | image_files, model, args | — | 뷰어 상태 | src/AI/tasks/jig_latch/pc/latch_predict.py:191 |
| 23 | ImageViewer.process_image | idx | tuple | 추론·드로잉 | src/AI/tasks/jig_latch/pc/latch_predict.py:202 |
| 24 | ImageViewer.save_current_image | — | None | 저장 | src/AI/tasks/jig_latch/pc/latch_predict.py:221 |
| 25 | ImageViewer.update_display | — | None | 패널 갱신 | src/AI/tasks/jig_latch/pc/latch_predict.py:230 |
| 26 | ImageViewer.on_key | event | None | 키 처리 | src/AI/tasks/jig_latch/pc/latch_predict.py:259 |
| 27 | ImageViewer.on_close | event | None | 닫힘 처리 | src/AI/tasks/jig_latch/pc/latch_predict.py:280 |
| 28 | ImageViewer.close_viewer | — | None | 종료 | src/AI/tasks/jig_latch/pc/latch_predict.py:283 |
| 29 | ImageViewer.run | — | None | 뷰어 구동 | src/AI/tasks/jig_latch/pc/latch_predict.py:290 |
| 30 | process_test_images | model, args | None | 배치/뷰어 분기 처리 | src/AI/tasks/jig_latch/pc/latch_predict.py:305 |
| 31 | main (latch_predict) | — | None | 인자→모델→처리 | src/AI/tasks/jig_latch/pc/latch_predict.py:350 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 5 | DEFAULT_MODEL_PATH(상대 "../YoloV8_train/…")·TEST_DIR·OUTPUT_DIR·WIDTH(320)·HEIGHT(640)·CONFIDENCE(0.7) (상수) | parse_args | 구버전 기본 인자 | src/AI/tasks/jig_latch/pc/latch_predict.py:23-28 |

## src/AI/tasks/jig_latch/training/train.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| — | (train.py — 함수 없음, 모듈 레벨 스크립트) | — | — | yolov8s-seg 학습·검증 실행 | src/AI/tasks/jig_latch/training/train.py:6-48 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 6 | model, results, device 등 (가변, train.py 모듈 레벨) | 스크립트 본문 | 학습 실행 상태 | src/AI/tasks/jig_latch/training/train.py:16-26,45 |
