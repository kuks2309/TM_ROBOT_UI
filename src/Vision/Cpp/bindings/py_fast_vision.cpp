#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <opencv2/opencv.hpp>
#include "fast_vision.hpp"

namespace py = pybind11;

// 2D/3D uint8 numpy → cv::Mat 깊은 복사(그 외 차원은 예외).
// 주의: buf.ptr 를 rows×cols×ch packed 로 해석한다 — C-연속 배열 전제이며,
// 슬라이스 뷰 같은 비연속 배열은 stride 가 무시되어 왜곡된 이미지가 된다.
cv::Mat numpy_to_mat(py::array_t<uint8_t> input) {
    py::buffer_info buf = input.request();

    int rows, cols, channels;
    if (buf.ndim == 2) {
        rows = buf.shape[0];
        cols = buf.shape[1];
        channels = 1;
    } else if (buf.ndim == 3) {
        rows = buf.shape[0];
        cols = buf.shape[1];
        channels = buf.shape[2];
    } else {
        throw std::runtime_error("입력은 2D 또는 3D 배열이어야 합니다");
    }

    int type = channels == 1 ? CV_8UC1 : CV_8UC3;
    cv::Mat mat(rows, cols, type, (uint8_t*)buf.ptr);
    return mat.clone();
}

// cv::Mat → numpy 복사 — Mat 의 step 을 stride 로 넘겨 행 패딩이 있어도 안전하다.
py::array_t<uint8_t> mat_to_numpy(const cv::Mat& mat) {
    std::vector<ssize_t> shape;
    std::vector<ssize_t> strides;

    if (mat.channels() == 1) {
        shape = {mat.rows, mat.cols};
        strides = {static_cast<ssize_t>(mat.step[0]), static_cast<ssize_t>(mat.step[1])};
    } else {
        shape = {mat.rows, mat.cols, mat.channels()};
        strides = {static_cast<ssize_t>(mat.step[0]), static_cast<ssize_t>(mat.step[1]), 1};
    }

    return py::array_t<uint8_t>(shape, strides, mat.data);
}

PYBIND11_MODULE(fast_vision, m) {
    m.doc() = "고성능 영상처리 C++ 라이브러리 (pybind11)";

    m.def("fast_edge_detect", [](py::array_t<uint8_t> input, double threshold1, double threshold2) {
        cv::Mat mat = numpy_to_mat(input);
        cv::Mat result = fast_vision::fast_edge_detect(mat, threshold1, threshold2);
        return mat_to_numpy(result);
    },
    py::arg("input"),
    py::arg("threshold1") = 50.0,
    py::arg("threshold2") = 150.0,
    "고속 Canny 엣지 검출\n\n"
    "Args:\n"
    "    input: 입력 이미지 (numpy array)\n"
    "    threshold1: Canny 하한 임계값 (default: 50)\n"
    "    threshold2: Canny 상한 임계값 (default: 150)\n\n"
    "Returns:\n"
    "    엣지 이미지 (numpy array)");

    m.def("fast_template_match", [](py::array_t<uint8_t> image, py::array_t<uint8_t> templ, int method) {
        cv::Mat img = numpy_to_mat(image);
        cv::Mat tpl = numpy_to_mat(templ);
        auto [x, y, score] = fast_vision::fast_template_match(img, tpl, method);
        return py::make_tuple(x, y, score);
    },
    py::arg("image"),
    py::arg("templ"),
    py::arg("method") = cv::TM_CCOEFF_NORMED,
    "고속 템플릿 매칭\n\n"
    "Args:\n"
    "    image: 검색 대상 이미지\n"
    "    templ: 템플릿 이미지\n"
    "    method: 매칭 방법 (default: TM_CCOEFF_NORMED)\n\n"
    "Returns:\n"
    "    (x, y, score) 튜플");

    m.def("fast_find_contours", [](py::array_t<uint8_t> input, double min_area) {
        cv::Mat mat = numpy_to_mat(input);
        auto contours = fast_vision::fast_find_contours(mat, min_area);

        py::list result;
        for (const auto& contour : contours) {
            py::list points;
            for (const auto& pt : contour) {
                points.append(py::make_tuple(pt.x, pt.y));
            }
            result.append(points);
        }
        return result;
    },
    py::arg("input"),
    py::arg("min_area") = 100.0,
    "고속 컨투어 검출\n\n"
    "Args:\n"
    "    input: 입력 이미지\n"
    "    min_area: 최소 면적 필터 (default: 100)\n\n"
    "Returns:\n"
    "    컨투어 리스트 [[(x,y), ...], ...]");

    m.attr("TM_SQDIFF") = cv::TM_SQDIFF;
    m.attr("TM_SQDIFF_NORMED") = cv::TM_SQDIFF_NORMED;
    m.attr("TM_CCORR") = cv::TM_CCORR;
    m.attr("TM_CCORR_NORMED") = cv::TM_CCORR_NORMED;
    m.attr("TM_CCOEFF") = cv::TM_CCOEFF;
    m.attr("TM_CCOEFF_NORMED") = cv::TM_CCOEFF_NORMED;
}
