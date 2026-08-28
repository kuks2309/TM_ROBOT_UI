cmake_minimum_required(VERSION 3.8)
project(magazine_detect)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(rclcpp REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(tc_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MagazineState.msg"
  DEPENDENCIES builtin_interfaces
)

# 판독 코어 — ROS 무관. 하드웨어 없이 시험된다.
# STATIC 이다: 이 패키지 안에서만 쓰는 내부 코어라 설치·배포할 표면이 아니다.
# 공유 라이브러리로 두면 실행파일이 런타임에 libmagazine_table.so 를 찾는데,
# 그것을 install 하지 않으면 로봇에서 exit 127 로 죽는다.
add_library(magazine_table STATIC src/magazine_table.cpp)
set_property(TARGET magazine_table PROPERTY POSITION_INDEPENDENT_CODE ON)
target_include_directories(magazine_table PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>)
target_compile_features(magazine_table PUBLIC cxx_std_17)

add_executable(magazine_detect_node src/magazine_detect_node.cpp)
target_link_libraries(magazine_detect_node magazine_table)
ament_target_dependencies(magazine_detect_node rclcpp tc_msgs builtin_interfaces)
rosidl_get_typesupport_target(cpp_typesupport ${PROJECT_NAME} rosidl_typesupport_cpp)
target_link_libraries(magazine_detect_node "${cpp_typesupport}")

install(TARGETS magazine_detect_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config/ DESTINATION share/${PROJECT_NAME}/config)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_magazine_table test/test_magazine_table.cpp)
  target_link_libraries(test_magazine_table magazine_table)
endif()

ament_package()
