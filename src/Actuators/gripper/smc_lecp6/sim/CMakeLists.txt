# gripper_sim — plain CMake (ROS-free · 스테이션 접근 0)
cmake_minimum_required(VERSION 3.16)
project(gripper_sim VERSION 0.1.0 LANGUAGES CXX)

if(NOT TARGET gripper_motion)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../motion" "${CMAKE_CURRENT_BINARY_DIR}/gripper_motion")
endif()

add_library(gripper_sim STATIC
  src/lecp6_plant.cpp
  src/sim_ports.cpp)
add_library(gripper_sim::sim ALIAS gripper_sim)
target_include_directories(gripper_sim
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
target_link_libraries(gripper_sim PUBLIC gripper_hal_kernel PRIVATE gripper_hal_warnings)
target_compile_features(gripper_sim PUBLIC cxx_std_17)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다(중복 등록 방지).
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR GRIPPER_SIM_BUILD_TESTS)
  enable_testing()
  add_executable(gripper_sil_test test/gripper_sil_test.cpp)
  target_link_libraries(gripper_sil_test PRIVATE gripper_sim gripper_motion gripper_hal_warnings)
  add_test(NAME gripper_sil_test COMMAND gripper_sil_test)
endif()

install(DIRECTORY include/ DESTINATION include)
install(TARGETS gripper_sim EXPORT gripper_simTargets)
install(EXPORT gripper_simTargets
  FILE gripper_simTargets.cmake
  NAMESPACE gripper_sim::
  DESTINATION share/gripper_sim/cmake)
