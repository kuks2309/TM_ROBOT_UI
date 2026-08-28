# gripper_motion — plain CMake (ROS-free 를 빌드 사실로 강제, gripper_hal 선례)
cmake_minimum_required(VERSION 3.16)
project(gripper_motion VERSION 0.1.0 LANGUAGES CXX)

if(NOT TARGET gripper_hal_kernel)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../hal" "${CMAKE_CURRENT_BINARY_DIR}/gripper_hal")
endif()

add_library(gripper_motion STATIC
  src/fsm_types.cpp
  src/gripper_fsm.cpp)
add_library(gripper_motion::motion ALIAS gripper_motion)
target_include_directories(gripper_motion
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
target_link_libraries(gripper_motion PUBLIC gripper_hal_kernel PRIVATE gripper_hal_warnings)
target_compile_features(gripper_motion PUBLIC cxx_std_17)
set_target_properties(gripper_motion PROPERTIES POSITION_INDEPENDENT_CODE ON)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다.
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR GRIPPER_MOTION_BUILD_TESTS)
  enable_testing()
  add_executable(gripper_motion_fsm_test test/gripper_fsm_test.cpp)
  target_link_libraries(gripper_motion_fsm_test PRIVATE gripper_motion gripper_hal_warnings)
  add_test(NAME gripper_motion_fsm_test COMMAND gripper_motion_fsm_test)
endif()

install(DIRECTORY include/ DESTINATION include)
install(TARGETS gripper_motion EXPORT gripper_motionTargets)
install(EXPORT gripper_motionTargets
  FILE gripper_motionTargets.cmake
  NAMESPACE gripper_motion::
  DESTINATION share/gripper_motion/cmake)
# export set 단독 소비를 위한 Config 래퍼(gripper_hal 의존 전이).
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/gripper_motionConfig.cmake"
"include(CMakeFindDependencyMacro)\nfind_dependency(gripper_hal CONFIG)\ninclude(\"\${CMAKE_CURRENT_LIST_DIR}/gripper_motionTargets.cmake\")\n")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/gripper_motionConfig.cmake" DESTINATION share/gripper_motion/cmake)
