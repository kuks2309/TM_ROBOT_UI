# hitbot_zefg_hal — plain CMake (ROS-free, ADR-005 D3/D4: Z-EFG-C35 RTU 레지스터 계약 + 어댑터)
cmake_minimum_required(VERSION 3.16)
project(hitbot_zefg_hal VERSION 0.1.0 LANGUAGES CXX)

# modbus_rtu — 형제 경로(add_subdirectory 가드, modbus_rtu 선례). hal 위치에서
# src/Common/comm/modbus_rtu 까지 4단 상위(hal→hitbot_zefg→gripper→Actuators→src).
if(NOT TARGET modbus_rtu_impl)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../../../../Common/comm/modbus_rtu" "${CMAKE_CURRENT_BINARY_DIR}/modbus_rtu")
endif()

add_library(hitbot_zefg_hal_warnings INTERFACE)
target_compile_options(hitbot_zefg_hal_warnings INTERFACE
  -Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch
  -Werror=maybe-uninitialized -Werror=implicit-fallthrough)

add_library(hitbot_zefg_hal STATIC src/zefg_hal.cpp)
add_library(hitbot_zefg::hal ALIAS hitbot_zefg_hal)
set_target_properties(hitbot_zefg_hal PROPERTIES EXPORT_NAME hal POSITION_INDEPENDENT_CODE ON)
target_include_directories(hitbot_zefg_hal
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
# gripper_common(공용 타입)은 형제 패키지 — include 경로만 소비(타깃 링크·export 결합 없음, gripper_hal 선례).
target_include_directories(hitbot_zefg_hal
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/../../gripper_common/include>)
# modbus_rtu_impl 은 add_subdirectory 소비(형제 프로젝트, 별도 install export)라 install(EXPORT) 대상에
# 넣지 않는다 — BUILD_INTERFACE 로 한정해 본 빌드 트리 안에서만 전파(gripper_hal_kernel 의 "설치 export
# 는 add_subdirectory 소비 전용" 선례와 동일 판단).
target_link_libraries(hitbot_zefg_hal PUBLIC $<BUILD_INTERFACE:modbus_rtu_impl> PRIVATE hitbot_zefg_hal_warnings)
target_compile_features(hitbot_zefg_hal PUBLIC cxx_std_17)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다(중복 등록 방지, gripper_hal/modbus_rtu 선례).
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR HITBOT_ZEFG_HAL_BUILD_TESTS)
  enable_testing()
  find_package(GTest QUIET)
  if(GTest_FOUND)
    find_package(Threads REQUIRED)
    add_executable(hitbot_zefg_hal_test test/zefg_hal_test.cpp)
    target_link_libraries(hitbot_zefg_hal_test
      PRIVATE hitbot_zefg_hal modbus_rtu_sim hitbot_zefg_hal_warnings GTest::gtest GTest::gtest_main Threads::Threads)
    add_test(NAME hitbot_zefg_hal_test COMMAND hitbot_zefg_hal_test)
  else()
    message(WARNING "hitbot_zefg_hal: GTest 미발견 — 단위테스트 제외")
  endif()
endif()

# 실기 H0 스모크(관측·읽기 전용, tools/zefg_hal_h0_smoke.cpp) — 평시 SIL 빌드에서 제외(기본 OFF),
# 실기 검증 시 -DHITBOT_ZEFG_BUILD_TOOLS=ON 으로 빌드한다(리뷰 Minor — 소스만 있고 타깃이 없던 도구).
option(HITBOT_ZEFG_BUILD_TOOLS "Z-EFG-C35 실기 H0 스모크 도구 빌드" OFF)
if(HITBOT_ZEFG_BUILD_TOOLS)
  add_executable(zefg_hal_h0_smoke "${CMAKE_CURRENT_SOURCE_DIR}/../tools/zefg_hal_h0_smoke.cpp")
  target_link_libraries(zefg_hal_h0_smoke PRIVATE hitbot_zefg_hal modbus_rtu_impl hitbot_zefg_hal_warnings)
endif()

# install(TARGETS/EXPORT/DIRECTORY) 없음 — 본 패키지는 add_subdirectory 소비 전용으로 확정
# (ADR-005 Consequences 각주, 단계④ 최종 리뷰 F8: 소비자 없는 설치 export 는 광고하지 않는다).
