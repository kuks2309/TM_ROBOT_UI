#ifndef TM_ARUCO_DETECT__ARUCO_DETECTOR_HPP_
#define TM_ARUCO_DETECT__ARUCO_DETECTOR_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <tf2_ros/transform_broadcaster.h>

#include <opencv2/opencv.hpp>

// ArUco API 는 OpenCV 4.7 에서 contrib(aruco) → objdetect(ArucoDetector 클래스) 로 옮겨졌다.
// Jetson(4.8) 과 tc PC(Ubuntu 22.04, 4.5.4) 를 동시에 지원하기 위해 버전 분기한다.
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

class ArucoDetectorNode : public rclcpp::Node
{
public:
  explicit ArucoDetectorNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~ArucoDetectorNode() = default;

private:
  void imageCallback(const sensor_msgs::msg::Image::SharedPtr msg);

  void detectMarkers(cv::Mat & image);

  void publishMarkerPose(int marker_id, const cv::Vec3d & rvec, const cv::Vec3d & tvec);

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

  cv::Mat camera_matrix_;
  cv::Mat dist_coeffs_;
  double marker_size_;

  std::string image_topic_;
  std::string camera_frame_;
  int aruco_dict_id_;
  bool publish_tf_;
  bool publish_debug_image_;
};

}

#endif
