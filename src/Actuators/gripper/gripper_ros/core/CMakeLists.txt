# gripper_ros 의 ROS-free 부분만 빌드하는 plain CMake 프로젝트.
# ament 없이도 설정 적재·결과 매핑 회귀가 돌아야 한다(ADR-001 D3).
cmake_minimum_required(VERSION 3.16)
project(gripper_ros_core VERSION 0.1.0 LANGUAGES CXX)

set(GRIPPER_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")

if(NOT TARGET gripper_motion)
  add_subdirectory("${GRIPPER_ROOT}/gripper_motion" "${CMAKE_CURRENT_BINARY_DIR}/gripper_motion")
endif()

add_library(gripper_ros_core STATIC
  "${CMAKE_CURRENT_SOURCE_DIR}/../src/config_loader.cpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/../src/result_map.cpp")
target_include_directories(gripper_ros_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/../src")
target_link_libraries(gripper_ros_core PUBLIC gripper_motion gripper_hal_impl PRIVATE gripper_hal_warnings)
target_compile_features(gripper_ros_core PUBLIC cxx_std_17)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR GRIPPER_ROS_CORE_BUILD_TESTS)
  enable_testing()
  add_executable(gripper_ros_core_test "${CMAKE_CURRENT_SOURCE_DIR}/../test/gripper_ros_core_test.cpp")
  target_link_libraries(gripper_ros_core_test PRIVATE gripper_ros_core gripper_hal_warnings)
  add_test(NAME gripper_ros_core_test COMMAND gripper_ros_core_test)
endif()
