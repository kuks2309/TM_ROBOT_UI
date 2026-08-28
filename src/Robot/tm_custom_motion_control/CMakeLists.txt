cmake_minimum_required(VERSION 3.8)
project(tm_custom_motion_control)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# C++17 사용
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tm_msgs REQUIRED)

# Include directories
include_directories(include)

# Library
add_library(${PROJECT_NAME}_lib SHARED
  src/robot_client.cpp
  src/motion_control.cpp
  src/gripper_control.cpp
)
ament_target_dependencies(${PROJECT_NAME}_lib
  rclcpp
  rclcpp_action
  std_msgs
  geometry_msgs
  tm_msgs
)

# Motion Control Node
add_executable(motion_control_node src/motion_control_node.cpp)
target_link_libraries(motion_control_node ${PROJECT_NAME}_lib)
ament_target_dependencies(motion_control_node
  rclcpp
  rclcpp_action
  std_msgs
  std_srvs
  geometry_msgs
  tm_msgs
)

# Install
install(TARGETS
  ${PROJECT_NAME}_lib
  motion_control_node
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Export
ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME}_lib)
ament_export_dependencies(rclcpp rclcpp_action std_msgs std_srvs geometry_msgs tm_msgs)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
