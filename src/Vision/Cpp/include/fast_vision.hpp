
#ifndef FAST_VISION_HPP
#define FAST_VISION_HPP

#include <opencv2/opencv.hpp>
#include <vector>
#include <string>

namespace fast_vision {

cv::Mat fast_edge_detect(const cv::Mat& input, double threshold1 = 50.0, double threshold2 = 150.0);

std::tuple<int, int, double> fast_template_match(
    const cv::Mat& image,
    const cv::Mat& templ,
    int method = cv::TM_CCOEFF_NORMED
);

std::vector<std::vector<cv::Point>> fast_find_contours(
    const cv::Mat& input,
    double min_area = 100.0
);

}

#endif
