# modbus_rtu — plain CMake (ADR-005 D2: RS485 RTU 마스터 공용 계층, ROS-free 를 빌드 사실로 강제)
cmake_minimum_required(VERSION 3.16)
project(modbus_rtu VERSION 0.1.0 LANGUAGES CXX)

add_library(modbus_rtu_warnings INTERFACE)
target_compile_options(modbus_rtu_warnings INTERFACE
  -Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch
  -Werror=maybe-uninitialized -Werror=implicit-fallthrough)

add_library(modbus_rtu_impl STATIC src/rtu_frame.cpp src/rtu_client.cpp src/serial_port.cpp)
add_library(modbus_rtu::impl ALIAS modbus_rtu_impl)
target_include_directories(modbus_rtu_impl PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(modbus_rtu_impl PUBLIC cxx_std_17)
target_link_libraries(modbus_rtu_impl PRIVATE modbus_rtu_warnings)
set_target_properties(modbus_rtu_impl PROPERTIES POSITION_INDEPENDENT_CODE ON)

install(DIRECTORY include/ DESTINATION include)
install(TARGETS modbus_rtu_impl modbus_rtu_warnings EXPORT modbus_rtuTargets)
install(EXPORT modbus_rtuTargets
  FILE modbus_rtuConfig.cmake
  NAMESPACE modbus_rtu::
  DESTINATION share/modbus_rtu/cmake)

# H0 스모크 도구 — GTest 무관, 항상 빌드(Task 4 Step 3). 읽기 전용(readHoldingRegisters 1회) —
# 쓰기 API 는 이 도구에서 절대 호출하지 않는다(H0 규율).
add_executable(modbus_rtu_h0_smoke tools/rtu_h0_smoke.cpp)
target_link_libraries(modbus_rtu_h0_smoke PRIVATE modbus_rtu_impl modbus_rtu_warnings)

include(CTest)
if(BUILD_TESTING)
  find_package(GTest QUIET)
  if(GTest_FOUND)
    find_package(Threads REQUIRED)
    foreach(t rtu_frame_test rtu_client_test serial_port_test)
      add_executable(modbus_rtu_${t} test/${t}.cpp)
      target_link_libraries(modbus_rtu_${t}
        PRIVATE modbus_rtu_impl modbus_rtu_warnings GTest::gtest GTest::gtest_main)
      add_test(NAME modbus_rtu_${t} COMMAND modbus_rtu_${t})
    endforeach()
    target_include_directories(modbus_rtu_rtu_client_test PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/sim)
    # openpty(<pty.h>) 는 glibc 에서 libutil 에 있다(util 링크). RtuClientOverPty 는 별도 스레드로
    # pty 마스터를 구동하므로 Threads 도 필요.
    target_link_libraries(modbus_rtu_serial_port_test PRIVATE util Threads::Threads)
  else()
    message(WARNING "modbus_rtu: GTest 미발견 — 단위테스트 제외")
  endif()
endif()
