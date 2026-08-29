# modbus_rtu — plain CMake (ADR-005 D2: RS485 RTU 마스터 공용 계층, ROS-free 를 빌드 사실로 강제)
cmake_minimum_required(VERSION 3.16)
project(modbus_rtu VERSION 0.1.0 LANGUAGES CXX)

add_library(modbus_rtu_warnings INTERFACE)
target_compile_options(modbus_rtu_warnings INTERFACE
  -Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch
  -Werror=maybe-uninitialized -Werror=implicit-fallthrough)

add_library(modbus_rtu_impl STATIC src/rtu_frame.cpp src/rtu_client.cpp)
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

include(CTest)
if(BUILD_TESTING)
  find_package(GTest QUIET)
  if(GTest_FOUND)
    foreach(t rtu_frame_test rtu_client_test)
      add_executable(modbus_rtu_${t} test/${t}.cpp)
      target_link_libraries(modbus_rtu_${t}
        PRIVATE modbus_rtu_impl modbus_rtu_warnings GTest::gtest GTest::gtest_main)
      add_test(NAME modbus_rtu_${t} COMMAND modbus_rtu_${t})
    endforeach()
    target_include_directories(modbus_rtu_rtu_client_test PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/sim)
  else()
    message(WARNING "modbus_rtu: GTest 미발견 — 단위테스트 제외")
  endif()
endif()
