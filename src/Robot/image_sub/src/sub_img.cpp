#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include "opencv2/highgui/highgui.hpp"
#include "opencv2/imgproc/imgproc.hpp"
#include "ament_index_cpp/get_package_share_directory.hpp"

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"


// techman_image 토픽을 구독해 수신 프레임을 OpenCV 창으로 표시하는 노드.
// 표시는 detached 스레드의 무한 루프에서 돈다 — image 멤버는 콜백 스레드와
// 표시 스레드가 락 없이 공유한다.
class SubImg : public rclcpp::Node {
  private:
    cv::Mat image;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr imageSubscription;
    const std::string packageName = "image_sub";
    const std::string imageFileRelative = "/image/techman_robot.jpg";
    bool isShowPic;
    // 수신 프레임을 BGR 로 변환해 image 멤버에 복사한다.
    void get_new_image_callback(sensor_msgs::msg::Image::SharedPtr msg);
    // 무한 루프 imshow (30ms waitKey) — 표시 전용 스레드에서 실행.
    void show_image();

  public:
    // ROS 이미지 인코딩 문자열을 OpenCV 타입으로 매핑. 미지원 인코딩이면 runtime_error.
    static int encoding_to_mat_type(const std::string & encoding);
    SubImg();
};

int SubImg::encoding_to_mat_type(const std::string & encoding){
  if (encoding == "mono8") {
    return CV_8UC1;
  } else if (encoding == "bgr8") {
    return CV_8UC3;
  } else if (encoding == "mono16") {
    return CV_16SC1;
  } else if (encoding == "rgba8") {
    return CV_8UC4;
  } else if (encoding == "bgra8") {
    return CV_8UC4;
  } else if (encoding == "32FC1") {
    return CV_32FC1;
  } else if (encoding == "rgb8") {
    return CV_8UC3;
  }else if (encoding =="8UC3"){
    return CV_8UC3;
  }
  else {
    std::cout<<"the unknow image type is "<<encoding<<std::endl;
    throw std::runtime_error("Unsupported encoding type");
  }
}

void SubImg::get_new_image_callback(sensor_msgs::msg::Image::SharedPtr msg){
  try{
    // 메시지 버퍼를 복사 없이 랩핑 — 소유권 있는 사본은 아래 copyTo 로 만든다
    cv::Mat frame(msg->height, msg->width, SubImg::encoding_to_mat_type(msg->encoding),
      const_cast<unsigned char *>(msg->data.data()), msg->step);
    if (msg->encoding == "rgb8") {
      cv::cvtColor(frame, frame, cv::COLOR_RGB2BGR);
    }
    std::cout << "Width : " << frame.size().width << std::endl;
    std::cout << "Height: " << frame.size().height << std::endl;
    frame.copyTo(this->image);
    std::cout<<"after setting this->image = frame";
  }
  catch(std::runtime_error &exception){
    std::cout<<"there is an exception "<< exception.what()<< std::endl;
  }
}

void SubImg::show_image(){
  while(true){
    cv::imshow("showimage",this->image );
    cv::waitKey(30);
  }
}

SubImg::SubImg() : Node("test_image_sub"){
  // 패키지 share 의 견본 이미지를 초기 화면으로 로드 — 첫 프레임 수신 전 imshow 대비
  auto position = ament_index_cpp::get_package_share_directory(packageName);
  std::string fullIniImagePath = position + imageFileRelative;
  this->image = cv::imread(fullIniImagePath);
  isShowPic = true;
  imageSubscription = this->create_subscription<sensor_msgs::msg::Image>(
  "techman_image", 10, std::bind(&SubImg::get_new_image_callback, this, std::placeholders::_1));
  std::thread(&SubImg::show_image, this).detach();
}

int main(int argc, char *argv[]){
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<SubImg>());
  std::cout<<"end spin"<<std::endl;
  rclcpp::shutdown();

  return 0;
}
