# gripper_common — 회사(벤더) 무관 공용 계약 (헤더 온리 · ROS-free). ADR-005 D3.
cmake_minimum_required(VERSION 3.16)
project(gripper_common VERSION 0.1.0 LANGUAGES CXX)

add_library(gripper_common_kernel INTERFACE)
add_library(gripper_common::kernel ALIAS gripper_common_kernel)
target_include_directories(gripper_common_kernel INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(gripper_common_kernel INTERFACE cxx_std_17)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다(중복 등록 방지, hal 선례).
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR GRIPPER_COMMON_BUILD_TESTS)
  enable_testing()
  add_executable(gripper_common_contract_check test/common_contract_check.cpp)
  target_link_libraries(gripper_common_contract_check PRIVATE gripper_common_kernel)
  target_compile_options(gripper_common_contract_check PRIVATE -Wall -Wextra -Wpedantic)
  add_test(NAME gripper_common_contract_check COMMAND gripper_common_contract_check)
endif()

install(DIRECTORY include/ DESTINATION include)
