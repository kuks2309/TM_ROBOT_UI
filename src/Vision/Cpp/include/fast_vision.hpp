#ifndef FAST_VISION_HPP
#define FAST_VISION_HPP

#include <opencv2/opencv.hpp>
#include <vector>
#include <string>

namespace fast_vision {

// 엣지 검출 — BGR 이면 그레이 변환 후 GaussianBlur 5×5 σ1.4 → Canny(threshold1/2 는 히스테리시스 하한/상한).
cv::Mat fast_edge_detect(const cv::Mat& input, double threshold1 = 50.0, double threshold2 = 150.0);

// 템플릿 매칭 최적 위치(x, y = 좌상단 픽셀)와 점수. SQDIFF 계열은 최소 위치를 취하고
// 점수를 1-minVal 로 뒤집는다 — 이 값은 *_NORMED 에서만 [0,1] 의미를 가진다(비정규화 SQDIFF 주의).
std::tuple<int, int, double> fast_template_match(
    const cv::Mat& image,
    const cv::Mat& templ,
    int method = cv::TM_CCOEFF_NORMED
);

// 외곽(RETR_EXTERNAL) 컨투어 검출 후 min_area(px^2) 미만 제거.
// 비영 픽셀이 과반인 입력만 이진화한다 — 이진 이미지 입력을 전제한 휴리스틱.
std::vector<std::vector<cv::Point>> fast_find_contours(
    const cv::Mat& input,
    double min_area = 100.0
);

}

#endif
