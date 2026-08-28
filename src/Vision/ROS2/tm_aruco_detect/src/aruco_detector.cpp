#include "tm_aruco_detect/aruco_detector.hpp"

#include <tf2/LinearMath/Quaternion.h>
#include <tf2/LinearMath/Matrix3x3.h>

namespace tm_aruco_detect
{

ArucoDetectorNode::ArucoDetectorNode(const rclcpp::NodeOptions & options)
: Node("aruco_detector_node", options)
{
  this->declare_parameter<std::string>("image_topic", "/techman_image");
  this->declare_parameter<std::string>("camera_frame", "camera_link");
  this->declare_parameter<int>("aruco_dict_id", cv::aruco::DICT_4X4_50);
  this->declare_parameter<double>("marker_size", 0.05);
  this->declare_parameter<bool>("publish_tf", true);
  this->declare_parameter<bool>("publish_debug_image", true);

  this->declare_parameter<std::vector<double>>("camera_matrix",
    {615.0, 0.0, 320.0, 0.0, 615.0, 240.0, 0.0, 0.0, 1.0});
  this->declare_parameter<std::vector<double>>("dist_coeffs",
    {0.0, 0.0, 0.0, 0.0, 0.0});

  image_topic_ = this->get_parameter("image_topic").as_string();
  camera_frame_ = this->get_parameter("camera_frame").as_string();
  aruco_dict_id_ = this->get_parameter("aruco_dict_id").as_int();
  marker_size_ = this->get_parameter("marker_size").as_double();
  publish_tf_ = this->get_parameter("publish_tf").as_bool();
  publish_debug_image_ = this->get_parameter("publish_debug_image").as_bool();

  auto cam_mat_vec = this->get_parameter("camera_matrix").as_double_array();
  camera_matrix_ = cv::Mat(3, 3, CV_64F, cam_mat_vec.data()).clone();

  auto dist_vec = this->get_parameter("dist_coeffs").as_double_array();
  dist_coeffs_ = cv::Mat(1, 5, CV_64F, dist_vec.data()).clone();

#if TM_ARUCO_USE_OBJDETECT_API
  aruco_dict_ = cv::aruco::getPredefinedDictionary(aruco_dict_id_);
  aruco_params_ = cv::aruco::DetectorParameters();
  aruco_detector_ = cv::aruco::ArucoDetector(aruco_dict_, aruco_params_);
#else
  aruco_dict_ = cv::aruco::getPredefinedDictionary(aruco_dict_id_);
  aruco_params_ = cv::aruco::DetectorParameters::create();
#endif

  image_sub_ = this->create_subscription<sensor_msgs::msg::Image>(
    image_topic_, 10,
    std::bind(&ArucoDetectorNode::imageCallback, this, std::placeholders::_1));

  pose_pub_ = this->create_publisher<geometry_msgs::msg::PoseStamped>(
    "aruco/pose", 10);

  if (publish_debug_image_) {
    debug_image_pub_ = this->create_publisher<sensor_msgs::msg::Image>(
      "aruco/debug_image", 10);
  }

  if (publish_tf_) {
    tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);
  }

  RCLCPP_INFO(this->get_logger(), "ArUco Detector Node initialized");
  RCLCPP_INFO(this->get_logger(), "  Image topic: %s", image_topic_.c_str());
  RCLCPP_INFO(this->get_logger(), "  Marker size: %.3f m", marker_size_);
  RCLCPP_INFO(this->get_logger(), "  ArUco dictionary: %d", aruco_dict_id_);
}

void ArucoDetectorNode::imageCallback(const sensor_msgs::msg::Image::SharedPtr msg)
{
  if (msg->encoding != "bgr8") {
    RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
      "Unsupported encoding: %s (bgr8 required)", msg->encoding.c_str());
    return;
  }
  const cv::Mat wrapped(
    msg->height, msg->width, CV_8UC3,
    const_cast<uint8_t *>(msg->data.data()), msg->step);
  cv::Mat image = wrapped.clone();

  detectMarkers(image);

  if (publish_debug_image_ && debug_image_pub_) {
    sensor_msgs::msg::Image debug_msg;
    debug_msg.header = msg->header;
    debug_msg.height = image.rows;
    debug_msg.width = image.cols;
    debug_msg.encoding = "bgr8";
    debug_msg.is_bigendian = 0;
    debug_msg.step = static_cast<uint32_t>(image.step);
    debug_msg.data.assign(image.datastart, image.dataend);
    debug_image_pub_->publish(debug_msg);
  }
}

void ArucoDetectorNode::detectMarkers(cv::Mat & image)
{
  std::vector<int> marker_ids;
  std::vector<std::vector<cv::Point2f>> marker_corners;

#if TM_ARUCO_USE_OBJDETECT_API
  aruco_detector_.detectMarkers(image, marker_corners, marker_ids);
#else
  cv::aruco::detectMarkers(
    image, aruco_dict_, marker_corners, marker_ids, aruco_params_);
#endif

  if (marker_ids.empty()) {
    return;
  }

  cv::aruco::drawDetectedMarkers(image, marker_corners, marker_ids);

  const float half = static_cast<float>(marker_size_) / 2.0f;
  const std::vector<cv::Point3f> obj_points = {
    {-half,  half, 0.0f}, { half,  half, 0.0f},
    { half, -half, 0.0f}, {-half, -half, 0.0f}};
  std::vector<cv::Vec3d> rvecs(marker_ids.size()), tvecs(marker_ids.size());
  for (size_t i = 0; i < marker_ids.size(); ++i) {
    cv::solvePnP(
      obj_points, marker_corners[i], camera_matrix_, dist_coeffs_,
      rvecs[i], tvecs[i], false, cv::SOLVEPNP_IPPE_SQUARE);
  }

  for (size_t i = 0; i < marker_ids.size(); ++i) {
    cv::drawFrameAxes(image, camera_matrix_, dist_coeffs_, rvecs[i], tvecs[i], marker_size_ * 0.5);

    publishMarkerPose(marker_ids[i], rvecs[i], tvecs[i]);

    if (publish_tf_) {
      broadcastTF(marker_ids[i], rvecs[i], tvecs[i]);
    }

    RCLCPP_DEBUG(this->get_logger(),
      "Marker %d: tvec=[%.3f, %.3f, %.3f]",
      marker_ids[i], tvecs[i][0], tvecs[i][1], tvecs[i][2]);
  }
}

void ArucoDetectorNode::publishMarkerPose(
  int marker_id, const cv::Vec3d & rvec, const cv::Vec3d & tvec)
{
  geometry_msgs::msg::PoseStamped pose_msg;
  pose_msg.header.stamp = this->now();
  pose_msg.header.frame_id = camera_frame_;

  pose_msg.pose.position.x = tvec[0];
  pose_msg.pose.position.y = tvec[1];
  pose_msg.pose.position.z = tvec[2];

  cv::Mat rot_mat;
  cv::Rodrigues(rvec, rot_mat);

  tf2::Matrix3x3 tf_rot(
    rot_mat.at<double>(0, 0), rot_mat.at<double>(0, 1), rot_mat.at<double>(0, 2),
    rot_mat.at<double>(1, 0), rot_mat.at<double>(1, 1), rot_mat.at<double>(1, 2),
    rot_mat.at<double>(2, 0), rot_mat.at<double>(2, 1), rot_mat.at<double>(2, 2));

  tf2::Quaternion quat;
  tf_rot.getRotation(quat);

  pose_msg.pose.orientation.x = quat.x();
  pose_msg.pose.orientation.y = quat.y();
  pose_msg.pose.orientation.z = quat.z();
  pose_msg.pose.orientation.w = quat.w();

  pose_pub_->publish(pose_msg);
}

void ArucoDetectorNode::broadcastTF(
  int marker_id, const cv::Vec3d & rvec, const cv::Vec3d & tvec)
{
  geometry_msgs::msg::TransformStamped transform;
  transform.header.stamp = this->now();
  transform.header.frame_id = camera_frame_;
  transform.child_frame_id = "aruco_marker_" + std::to_string(marker_id);

  transform.transform.translation.x = tvec[0];
  transform.transform.translation.y = tvec[1];
  transform.transform.translation.z = tvec[2];

  cv::Mat rot_mat;
  cv::Rodrigues(rvec, rot_mat);

  tf2::Matrix3x3 tf_rot(
    rot_mat.at<double>(0, 0), rot_mat.at<double>(0, 1), rot_mat.at<double>(0, 2),
    rot_mat.at<double>(1, 0), rot_mat.at<double>(1, 1), rot_mat.at<double>(1, 2),
    rot_mat.at<double>(2, 0), rot_mat.at<double>(2, 1), rot_mat.at<double>(2, 2));

  tf2::Quaternion quat;
  tf_rot.getRotation(quat);

  transform.transform.rotation.x = quat.x();
  transform.transform.rotation.y = quat.y();
  transform.transform.rotation.z = quat.z();
  transform.transform.rotation.w = quat.w();

  tf_broadcaster_->sendTransform(transform);
}

}

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<tm_aruco_detect::ArucoDetectorNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
