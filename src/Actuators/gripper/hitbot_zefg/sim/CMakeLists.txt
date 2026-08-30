# hitbot_zefg_sim — plain CMake (ROS-free). ZefgPlant 결정론 플랜트(SIL, ADR-005 단계④-2).
#
# 배치: 회사 폴더 승인 골격 hal·motion·sim 3형제(ADR-005 D1, smc_lecp6 와 대칭).
# checks/gripper-io-single-master.sh 는 sim/(SIL 슬레이브 플랜트)의 modbus_rtu 소비를
# 검증 자산으로 면제한다(단계④-2 fix wave 정밀화 — 런타임 쓰기 마스터는 hal/ 만).
cmake_minimum_required(VERSION 3.16)
project(hitbot_zefg_sim VERSION 0.1.0 LANGUAGES CXX)

# 형제 hal 소비(가드) — hal 이 modbus_rtu(impl+sim 타깃)를 형제 경로로 끌어온다.
if(NOT TARGET hitbot_zefg_hal)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../hal" "${CMAKE_CURRENT_BINARY_DIR}/hitbot_zefg_hal")
endif()

add_library(hitbot_zefg_sim STATIC src/zefg_plant.cpp)
add_library(hitbot_zefg::sim ALIAS hitbot_zefg_sim)
set_target_properties(hitbot_zefg_sim PROPERTIES EXPORT_NAME sim POSITION_INDEPENDENT_CODE ON)
target_include_directories(hitbot_zefg_sim
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
# hal·modbus_rtu_sim 은 add_subdirectory 소비(형제 프로젝트) — BUILD_INTERFACE 한정 전파
# (hitbot_zefg_hal 의 modbus_rtu_impl 과 동일 판단).
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

# install(TARGETS/EXPORT/DIRECTORY) 없음 — add_subdirectory 소비 전용 확정(ADR-005 Consequences
# 각주, 단계④ 최종 리뷰 F8).
