# remote_io_hal — plain CMake (ADR-001(remote_io): ROS-free를 빌드 사실로 강제, modbus_rtu/pio_hal 선례)
cmake_minimum_required(VERSION 3.16)
project(remote_io_hal VERSION 0.1.0 LANGUAGES CXX)

# ── 계약 커널(헤더 온리) — M0 동결 대상 ──
add_library(remote_io_hal_kernel INTERFACE)
add_library(remote_io_hal::kernel ALIAS remote_io_hal_kernel)
target_include_directories(remote_io_hal_kernel INTERFACE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(remote_io_hal_kernel INTERFACE cxx_std_17)

add_library(remote_io_hal_warnings INTERFACE)
target_compile_options(remote_io_hal_warnings INTERFACE
  -Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch
  -Werror=maybe-uninitialized -Werror=implicit-fallthrough)

# ── 구현 라이브러리 (M1: RemoteIoStationPort — comm::modbus_tcp 소비, 재구현 금지 debt-022) ──
# 설치본 우선(find_package), 미설치 시 소스트리 폴백(add_subdirectory) — pio_hal 선례.
if(NOT TARGET modbus_tcp_impl AND NOT TARGET modbus_tcp::impl)
  find_package(modbus_tcp CONFIG QUIET)
  if(NOT TARGET modbus_tcp::impl)
    # 공용 comm 트리는 대문자 Common 이 정본이다(사용자 확정). 소문자 common 도 병존하는
    # 트리가 있어 양쪽을 탐색한다 — 경로 하드코딩은 트리마다 구성 실패를 낸다.
    set(_rio_modbus_tcp "")
    foreach(_c "Common" "common")
      if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../../../${_c}/comm/modbus_tcp/CMakeLists.txt")
        set(_rio_modbus_tcp "${CMAKE_CURRENT_SOURCE_DIR}/../../../${_c}/comm/modbus_tcp")
        break()
      endif()
    endforeach()
    if(_rio_modbus_tcp STREQUAL "")
      message(FATAL_ERROR "remote_io_hal: comm/modbus_tcp 소스트리를 찾지 못했습니다 "
                          "(Common/ · common/ 둘 다 부재). 설치본이 있으면 find_package 경로를 주십시오.")
    endif()
    add_subdirectory("${_rio_modbus_tcp}" "${CMAKE_CURRENT_BINARY_DIR}/modbus_tcp")
  endif()
endif()

add_library(remote_io_hal_impl STATIC src/remote_io_station_port.cpp)
add_library(remote_io_hal::impl ALIAS remote_io_hal_impl)
target_link_libraries(remote_io_hal_impl PUBLIC remote_io_hal_kernel modbus_tcp::impl PRIVATE remote_io_hal_warnings)
set_target_properties(remote_io_hal_impl PROPERTIES POSITION_INDEPENDENT_CODE ON)

install(DIRECTORY include/ DESTINATION include)
install(TARGETS remote_io_hal_kernel remote_io_hal_warnings remote_io_hal_impl EXPORT remote_io_halTargets)
# Config 래퍼: modbus_tcp 의존을 find_dependency 로 전이(pio_halConfig 선례).
install(EXPORT remote_io_halTargets
  FILE remote_io_halTargets.cmake
  NAMESPACE remote_io_hal::
  DESTINATION share/remote_io_hal/cmake)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/remote_io_halConfig.cmake"
"include(CMakeFindDependencyMacro)\nfind_dependency(modbus_tcp CONFIG)\ninclude(\"\${CMAKE_CURRENT_LIST_DIR}/remote_io_halTargets.cmake\")\n")
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/remote_io_halConfig.cmake" DESTINATION share/remote_io_hal/cmake)

# 읽기 전용 HIL 프로브(FC3 판독만 — 리모트 실기용, 사용자 지시 2026-07-31 "읽기만 hil")
add_executable(remote_io_read_only_hil_probe test/read_only_hil_probe.cpp)
target_link_libraries(remote_io_read_only_hil_probe PRIVATE remote_io_hal_impl remote_io_hal_warnings)

# remote_io_gui 용 JSON 브리지(읽기 전용 — 쓰기 명령 미구현, M4 승인 후 추가)
add_executable(remote_io_bridge test/bridge_main.cpp)
target_link_libraries(remote_io_bridge PRIVATE remote_io_hal_impl remote_io_hal_warnings)

include(CTest)
if(BUILD_TESTING)
  add_executable(remote_io_hal_smoke_test test/smoke_test.cpp)
  target_link_libraries(remote_io_hal_smoke_test PRIVATE remote_io_hal_kernel remote_io_hal_warnings)
  add_test(NAME remote_io_hal_smoke_test COMMAND remote_io_hal_smoke_test)

  find_package(GTest QUIET)
  if(GTest_FOUND)
    find_package(Threads REQUIRED)  # mock 서버 fixture accept 스레드(테스트 전용 — 운영 코드 무스레드)
    # 위 구성 단계에서 해결한 소스트리를 재사용한다(Common/ · common/ 병존 대응).
    set(MODBUS_TCP_TEST_INC "")
    foreach(_c "Common" "common")
      if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../../../${_c}/comm/modbus_tcp/test")
        set(MODBUS_TCP_TEST_INC "${CMAKE_CURRENT_SOURCE_DIR}/../../../${_c}/comm/modbus_tcp/test")
        break()
      endif()
    endforeach()
    add_executable(remote_io_hal_remote_io_station_port_test test/remote_io_station_port_test.cpp)
    target_include_directories(remote_io_hal_remote_io_station_port_test PRIVATE "${MODBUS_TCP_TEST_INC}")
    target_link_libraries(remote_io_hal_remote_io_station_port_test
      PRIVATE remote_io_hal_impl remote_io_hal_warnings GTest::gtest GTest::gtest_main Threads::Threads)
    add_test(NAME remote_io_hal_remote_io_station_port_test COMMAND remote_io_hal_remote_io_station_port_test)
  else()
    message(WARNING "remote_io_hal: GTest 미발견 — 단위테스트 제외(스모크만)")
  endif()
endif()
