# gripper_ros — 조립층(ament). 코어(gripper_hal·gripper_motion)는 plain CMake 라 add_subdirectory 로 붙인다.
cmake_minimum_required(VERSION 3.16)
# rosidl 생성물은 C 타깃을 만든다 — CXX 만 선언하면 링커 언어를 못 정한다.
project(gripper_ros VERSION 0.1.0 LANGUAGES C CXX)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(tc_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/GripperCommand.action")

# ROS-free 코어. 이 경계가 «로봇 없이 도는 회귀» 의 범위를 정한다(ADR-001 D3).
if(NOT TARGET gripper_motion)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../gripper_motion" "${CMAKE_CURRENT_BINARY_DIR}/gripper_motion")
endif()

add_library(gripper_ros_core STATIC
  src/config_loader.cpp
  src/result_map.cpp)
target_include_directories(gripper_ros_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_link_libraries(gripper_ros_core PUBLIC gripper_motion gripper_hal_impl PRIVATE gripper_hal_warnings)
target_compile_features(gripper_ros_core PUBLIC cxx_std_17)

add_executable(gripper_node
  src/gripper_node.cpp
  src/node_params.cpp
  src/ros_station_io_client.cpp)
target_link_libraries(gripper_node gripper_ros_core)
ament_target_dependencies(gripper_node rclcpp rclcpp_action rclcpp_lifecycle tc_msgs)
# 같은 패키지가 만든 인터페이스를 쓰므로 생성 타깃에 직접 링크한다.
rosidl_get_typesupport_target(cpp_typesupport "${PROJECT_NAME}" "rosidl_typesupport_cpp")
target_link_libraries(gripper_node "${cpp_typesupport}")

# SIL 스테이션 — 로봇 없이 폐루프를 돌리기 위한 시험 장비(실기 배포 대상 아님).
if(NOT TARGET gripper_sim)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../gripper_sim" "${CMAKE_CURRENT_BINARY_DIR}/gripper_sim")
endif()
add_executable(sim_station_node src/sim_station_node.cpp)
target_link_libraries(sim_station_node gripper_ros_core gripper_sim)
ament_target_dependencies(sim_station_node rclcpp tc_msgs)

install(TARGETS gripper_node sim_station_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest QUIET)
  add_executable(gripper_ros_core_test test/gripper_ros_core_test.cpp)
  target_link_libraries(gripper_ros_core_test PRIVATE gripper_ros_core gripper_hal_warnings)
  add_test(NAME gripper_ros_core_test COMMAND gripper_ros_core_test)
endif()

ament_package()
