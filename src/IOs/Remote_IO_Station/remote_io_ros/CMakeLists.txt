# remote_io_ros — ROS 조립층 (remote_io M4). Modbus·RMW·watchdog 은 remote_io_hal 소유.
cmake_minimum_required(VERSION 3.16)
project(remote_io_ros)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
add_compile_options(-Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch -Werror=implicit-fallthrough)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(tc_msgs REQUIRED)

# remote_io_hal 은 plain CMake — 설치본 우선, 미설치 시 소스트리 폴백(remote_io_sim 선례).
if(NOT TARGET remote_io_hal::impl)
  find_package(remote_io_hal CONFIG QUIET)
  if(NOT TARGET remote_io_hal::impl)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../remote_io_hal"
                     "${CMAKE_CURRENT_BINARY_DIR}/remote_io_hal")
  endif()
endif()

# 계약 변환·정책은 ROS 무관 — 노드와 분리해 단위 시험이 rclcpp 없이 돈다.
add_library(remote_io_ros_contract STATIC src/io_contract.cpp)
target_include_directories(remote_io_ros_contract PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_link_libraries(remote_io_ros_contract PUBLIC remote_io_hal::kernel)
set_target_properties(remote_io_ros_contract PROPERTIES POSITION_INDEPENDENT_CODE ON)

add_executable(remote_io_node src/remote_io_node.cpp)
target_link_libraries(remote_io_node remote_io_ros_contract remote_io_hal::impl)
ament_target_dependencies(remote_io_node rclcpp tc_msgs)

install(TARGETS remote_io_node DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(remote_io_ros_io_contract_test test/io_contract_test.cpp)
  if(TARGET remote_io_ros_io_contract_test)
    target_link_libraries(remote_io_ros_io_contract_test remote_io_ros_contract)
  endif()
endif()

ament_package()
