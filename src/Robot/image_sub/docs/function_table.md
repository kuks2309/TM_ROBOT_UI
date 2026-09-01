# src/Robot/image_sub — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/Robot/image_sub/src/sub_img.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `SubImg::encoding_to_mat_type` (static) | `encoding: const std::string&` | `int` (CV 타입) | 인코딩 문자열→OpenCV 타입 매핑, 미지원 시 throw | src/Robot/image_sub/src/sub_img.cpp:35 |
| 2 | `SubImg::get_new_image_callback` | `msg: Image::SharedPtr` | void | msg 버퍼 랩핑→BGR 변환→`image` 로 copyTo | sub_img.cpp:59 |
| 3 | `SubImg::show_image` | - | void | 무한 루프 imshow(30ms waitKey) | sub_img.cpp:77 |
| 4 | `SubImg::SubImg` (ctor) | - | - | 초기 이미지 로드, 구독 생성, 표시 스레드 detach | sub_img.cpp:84 |
| 5 | `main` | `argc, argv` | `int` | init→spin→shutdown | sub_img.cpp:95 |
