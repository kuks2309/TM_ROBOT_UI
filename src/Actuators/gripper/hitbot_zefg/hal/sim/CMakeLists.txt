# hitbot_zefg_sim — plain CMake (ROS-free). ZefgPlant 결정론 플랜트(SIL, ADR-005 단계④-2).
#
# 배치가 hal/ 하위인 이유: checks/gripper-io-single-master.sh 는 modbus 심볼·modbus_rtu 빌드
# 의존을 벤더 `hal/` 경로에만 면제한다(ADR-005 D4). 플랜트는 같은 RTU 버스의 슬레이브 모형으로
# modbus_rtu 를 소비하므로 hal 경계 안(독립 sim 하위 패키지)에 둔다 — 게이트 완화 없이 구조로 준수.
cmake_minimum_required(VERSION 3.16)
project(hitbot_zefg_sim VERSION 0.1.0 LANGUAGES CXX)

# 부모 hal 소비(가드) — hal 이 modbus_rtu(impl+sim 타깃)를 형제 경로로 끌어온다.
if(NOT TARGET hitbot_zefg_hal)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/.." "${CMAKE_CURRENT_BINARY_DIR}/hitbot_zefg_hal")
endif()

add_library(hitbot_zefg_sim STATIC src/zefg_plant.cpp)
add_library(hitbot_zefg::sim ALIAS hitbot_zefg_sim)
set_target_properties(hitbot_zefg_sim PROPERTIES EXPORT_NAME sim POSITION_INDEPENDENT_CODE ON)
target_include_directories(hitbot_zefg_sim
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
# hal·modbus_rtu_sim 은 add_subdirectory 소비(형제 프로젝트, 별도 install export)라 install(EXPORT)
# 대상에 넣지 않는다 — BUILD_INTERFACE 한정 전파(hitbot_zefg_hal 의 modbus_rtu_impl 선례와 동일 판단).
target_link_libraries(hitbot_zefg_sim
  PUBLIC $<BUILD_INTERFACE:hitbot_zefg_hal> $<BUILD_INTERFACE:modbus_rtu_sim>
  PRIVATE $<BUILD_INTERFACE:hitbot_zefg_hal_warnings>)
target_compile_features(hitbot_zefg_sim PUBLIC cxx_std_17)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다(중복 등록 방지, hal/modbus_rtu 선례).
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR HITBOT_ZEFG_SIM_BUILD_TESTS)
  enable_testing()
  find_package(GTest QUIET)
  if(GTest_FOUND)
    find_package(Threads REQUIRED)
    add_executable(hitbot_zefg_plant_test test/zefg_plant_test.cpp)
    target_link_libraries(hitbot_zefg_plant_test
      PRIVATE hitbot_zefg_sim hitbot_zefg_hal hitbot_zefg_hal_warnings
              GTest::gtest GTest::gtest_main Threads::Threads)
    add_test(NAME hitbot_zefg_plant_test COMMAND hitbot_zefg_plant_test)
  else()
    message(WARNING "hitbot_zefg_sim: GTest 미발견 — 단위테스트 제외")
  endif()
endif()

install(DIRECTORY include/ DESTINATION include)
install(TARGETS hitbot_zefg_sim EXPORT hitbot_zefg_simTargets)
install(EXPORT hitbot_zefg_simTargets
  FILE hitbot_zefg_simTargets.cmake
  NAMESPACE hitbot_zefg::
  DESTINATION share/hitbot_zefg_sim/cmake)
