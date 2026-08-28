# gripper_hal — plain CMake (ROS-free 를 빌드 사실로 강제, drawer_hal 선례)
cmake_minimum_required(VERSION 3.16)
project(gripper_hal VERSION 0.2.0 LANGUAGES CXX)

# ── 계약 커널(헤더 온리) — M0 ──
add_library(gripper_hal_kernel INTERFACE)
add_library(gripper_hal::kernel ALIAS gripper_hal_kernel)
set_target_properties(gripper_hal_kernel PROPERTIES EXPORT_NAME kernel)
target_include_directories(gripper_hal_kernel INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(gripper_hal_kernel INTERFACE cxx_std_17)

add_library(gripper_hal_warnings INTERFACE)
set_target_properties(gripper_hal_warnings PROPERTIES EXPORT_NAME warnings)
target_compile_options(gripper_hal_warnings INTERFACE
  -Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch
  -Werror=maybe-uninitialized -Werror=implicit-fallthrough)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다(중복 등록 방지).
set(GRIPPER_HAL_REGISTER_TESTS OFF)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR GRIPPER_HAL_BUILD_TESTS)
  set(GRIPPER_HAL_REGISTER_TESTS ON)
  enable_testing()
  add_executable(gripper_hal_contract_check test/contract_check.cpp)
  target_link_libraries(gripper_hal_contract_check PRIVATE gripper_hal_kernel gripper_hal_warnings)
  add_test(NAME gripper_hal_contract_check COMMAND gripper_hal_contract_check)
endif()

# ── 구현 (M1): impl/remote_io — 스테이션 서비스 클라이언트 어댑터 ──
# 외부 의존 없음: ROS 결선은 IStationIoClient 구현으로 조립층이 주입한다.
add_library(gripper_hal_impl STATIC
  impl/src/signal_map.cpp
  impl/src/remote_io_command_port.cpp
  impl/src/remote_io_feedback_port.cpp
  impl/src/remote_io_magazine_port.cpp)
add_library(gripper_hal::impl ALIAS gripper_hal_impl)
set_target_properties(gripper_hal_impl PROPERTIES EXPORT_NAME impl POSITION_INDEPENDENT_CODE ON)
target_include_directories(gripper_hal_impl
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/impl/include>
    $<INSTALL_INTERFACE:include>)
target_link_libraries(gripper_hal_impl PUBLIC gripper_hal_kernel PRIVATE gripper_hal_warnings)

if(GRIPPER_HAL_REGISTER_TESTS)
  add_executable(gripper_hal_remote_io_ports_test test/remote_io_ports_test.cpp)
  target_link_libraries(gripper_hal_remote_io_ports_test PRIVATE gripper_hal_impl gripper_hal_warnings)
  add_test(NAME gripper_hal_remote_io_ports_test COMMAND gripper_hal_remote_io_ports_test)

  # ⟦CI:gripper-io-single-master⟧ 를 ctest 로도 돌린다 — 스크립트를 따로 호출하지 않는 CI 에서도 걸리게.
  add_test(NAME gripper_io_single_master
           COMMAND ${CMAKE_COMMAND} -E env bash "${CMAKE_CURRENT_SOURCE_DIR}/../checks/gripper-io-single-master.sh")
endif()

install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY impl/include/ DESTINATION include)
install(TARGETS gripper_hal_kernel gripper_hal_warnings gripper_hal_impl EXPORT gripper_halTargets)
install(EXPORT gripper_halTargets
  FILE gripper_halTargets.cmake
  NAMESPACE gripper_hal::
  DESTINATION share/gripper_hal/cmake)
