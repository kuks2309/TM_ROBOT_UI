#include "fast_vision.hpp"

namespace fast_vision {

cv::Mat fast_edge_detect(const cv::Mat& input, double threshold1, double threshold2) {
    cv::Mat gray, edges;

    if (input.channels() == 3) {
        cv::cvtColor(input, gray, cv::COLOR_BGR2GRAY);
    } else {
        gray = input.clone();
    }

    cv::GaussianBlur(gray, gray, cv::Size(5, 5), 1.4);

    cv::Canny(gray, edges, threshold1, threshold2);

    return edges;
}

std::tuple<int, int, double> fast_template_match(
    const cv::Mat& image,
    const cv::Mat& templ,
    int method
) {
    cv::Mat result;
    cv::matchTemplate(image, templ, result, method);

    double minVal, maxVal;
    cv::Point minLoc, maxLoc;
    cv::minMaxLoc(result, &minVal, &maxVal, &minLoc, &maxLoc);

    cv::Point matchLoc;
    double score;
    if (method == cv::TM_SQDIFF || method == cv::TM_SQDIFF_NORMED) {
        matchLoc = minLoc;
        score = 1.0 - minVal;
    } else {
        matchLoc = maxLoc;
        score = maxVal;
    }

    return std::make_tuple(matchLoc.x, matchLoc.y, score);
}

std::vector<std::vector<cv::Point>> fast_find_contours(
    const cv::Mat& input,
    double min_area
) {
    cv::Mat binary;

    if (input.channels() == 3) {
        cv::cvtColor(input, binary, cv::COLOR_BGR2GRAY);
    } else {
        binary = input.clone();
    }

    if (cv::countNonZero(binary) > binary.total() * 0.5) {
        cv::threshold(binary, binary, 127, 255, cv::THRESH_BINARY);
    }

    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(binary, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);

    std::vector<std::vector<cv::Point>> filtered;
    for (const auto& contour : contours) {
        if (cv::contourArea(contour) >= min_area) {
            filtered.push_back(contour);
        }
    }

    return filtered;
}

}
