# modbus_tcp — plain CMake (ADR-000: MBAP 클라이언트 pio_hal 승격, ROS-free를 빌드 사실로 강제)
cmake_minimum_required(VERSION 3.16)
project(modbus_tcp VERSION 0.1.0 LANGUAGES CXX)

option(MODBUS_TCP_SANITIZE_THREAD "Build with ThreadSanitizer (debt-014① isLinkUp 교차관측 게이트)" OFF)

add_library(modbus_tcp_warnings INTERFACE)
target_compile_options(modbus_tcp_warnings INTERFACE
  -Wall -Wextra -Wpedantic
  -Werror=return-type -Werror=switch
  -Werror=maybe-uninitialized -Werror=implicit-fallthrough)

# ── 구현 라이브러리 (MBAP 프레이밍 + FC3/FC6 동기 클라이언트) ──
add_library(modbus_tcp_impl STATIC src/mbap_client.cpp)
add_library(modbus_tcp::impl ALIAS modbus_tcp_impl)
target_include_directories(modbus_tcp_impl PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(modbus_tcp_impl PUBLIC cxx_std_17)
target_link_libraries(modbus_tcp_impl PRIVATE modbus_tcp_warnings)
set_target_properties(modbus_tcp_impl PROPERTIES POSITION_INDEPENDENT_CODE ON)

if(MODBUS_TCP_SANITIZE_THREAD)
  target_compile_options(modbus_tcp_impl PUBLIC -fsanitize=thread -fno-omit-frame-pointer -g -O1)
  target_link_options(modbus_tcp_impl PUBLIC -fsanitize=thread)
endif()

install(DIRECTORY include/ DESTINATION include)
install(TARGETS modbus_tcp_impl modbus_tcp_warnings EXPORT modbus_tcpTargets)
install(EXPORT modbus_tcpTargets
  FILE modbus_tcpConfig.cmake
  NAMESPACE modbus_tcp::
  DESTINATION share/modbus_tcp/cmake)

include(CTest)
if(BUILD_TESTING)
  find_package(GTest QUIET)
  if(GTest_FOUND)
    find_package(Threads REQUIRED)  # mock 서버 fixture의 accept 스레드(테스트 전용 — 운영 코드는 무스레드)
    foreach(t mbap_client_test mbap_client_fault_test mbap_link_state_tsan_test mock_gl9089_server_test)
      add_executable(modbus_tcp_${t} test/${t}.cpp)
      target_link_libraries(modbus_tcp_${t}
        PRIVATE modbus_tcp_impl modbus_tcp_warnings GTest::gtest GTest::gtest_main Threads::Threads)
      add_test(NAME modbus_tcp_${t} COMMAND modbus_tcp_${t})
    endforeach()
  else()
    message(WARNING "modbus_tcp: GTest 미발견 — 단위테스트 제외. TSan 게이트(checks/)는 GTest 필요")
  endif()
endif()
