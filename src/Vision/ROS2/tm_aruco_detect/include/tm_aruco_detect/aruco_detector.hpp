#ifndef TM_ARUCO_DETECT__ARUCO_DETECTOR_HPP_
#define TM_ARUCO_DETECT__ARUCO_DETECTOR_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <tf2_ros/transform_broadcaster.h>

#include <opencv2/opencv.hpp>

// OpenCV 4.7 에서 ArUco 가 contrib(aruco)에서 본체 objdetect 로 옮겨 타입·API 가 다르다 —
// 버전 매크로로 양쪽을 지원한다(구버전은 contrib 헤더 필요).
#if CV_VERSION_MAJOR > 4 || (CV_VERSION_MAJOR == 4 && CV_VERSION_MINOR >= 7)
#define TM_ARUCO_USE_OBJDETECT_API 1
#include <opencv2/objdetect/aruco_detector.hpp>
#else
#define TM_ARUCO_USE_OBJDETECT_API 0
#include <opencv2/aruco.hpp>
#endif

#include <vector>
#include <memory>

namespace tm_aruco_detect
{

// TM 카메라 이미지(bgr8)에서 ArUco 마커를 검출해 포즈를 발행하는 노드.
// solvePnP(IPPE_SQUARE)로 카메라 좌표계 포즈(m)를 구해 aruco/pose(PoseStamped) 발행,
// 옵션으로 마커별 TF(aruco_marker_<id>)와 주석 입힌 aruco/debug_image 를 낸다.
class ArucoDetectorNode : public rclcpp::Node
{
public:
  explicit ArucoDetectorNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~ArucoDetectorNode() = default;

private:
  // bgr8 만 처리(타 인코딩은 스로틀 에러 후 드롭 — cv_bridge 없이 수동 래핑이라서).
  void imageCallback(const sensor_msgs::msg::Image::SharedPtr msg);

  // 마커 검출 → 마커당 solvePnP → 포즈 발행·TF·축 드로잉.
  void detectMarkers(cv::Mat & image);

  // rvec(Rodrigues)→쿼터니언 변환 후 PoseStamped 발행. 다중 마커면 같은 토픽에 연속 N건.
  void publishMarkerPose(int marker_id, const cv::Vec3d & rvec, const cv::Vec3d & tvec);

  // camera_frame → aruco_marker_<id> 동적 TF 브로드캐스트(검출 프레임마다).
  void broadcastTF(int marker_id, const cv::Vec3d & rvec, const cv::Vec3d & tvec);

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr image_sub_;

  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr pose_pub_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr debug_image_pub_;

  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;

#if TM_ARUCO_USE_OBJDETECT_API
  cv::aruco::Dictionary aruco_dict_;
  cv::aruco::DetectorParameters aruco_params_;
  cv::aruco::ArucoDetector aruco_detector_;
#else
  cv::Ptr<cv::aruco::Dictionary> aruco_dict_;
  cv::Ptr<cv::aruco::DetectorParameters> aruco_params_;
#endif

  cv::Mat camera_matrix_;   // 3×3 내부 파라미터(fx 0 cx / 0 fy cy / 0 0 1), 단위 px
  cv::Mat dist_coeffs_;     // 왜곡 계수 5개 (k1 k2 p1 p2 k3)
  double marker_size_;      // 마커 한 변 길이(m) — solvePnP 평면 모델 스케일

  std::string image_topic_;
  std::string camera_frame_;
  int aruco_dict_id_;
  bool publish_tf_;
  bool publish_debug_image_;
};

}

#endif
