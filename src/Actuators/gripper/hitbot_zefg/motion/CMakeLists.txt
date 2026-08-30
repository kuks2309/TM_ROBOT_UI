# hitbot_zefg_motion — plain CMake (ROS-free). ZefgSequencer FSM(ADR-005 단계④-3).
#
# 통신은 형제 hal(ZefgHal)만 소비한다 — 단일 쓰기 마스터 게이트(checks/gripper-io-single-master.sh)
# 가 motion/src·include·본 파일에서 하위 버스 심볼을 차단하므로, 링크는 전부 hal 타깃 경유다.
# 테스트만 형제 sim 플랜트를 직접 조립한다(motion/test/ 는 게이트 면제 경로).
cmake_minimum_required(VERSION 3.16)
project(hitbot_zefg_motion VERSION 0.1.0 LANGUAGES CXX)

# 형제 hal 소비(가드) — hal 이 하위 통신 패키지(impl+sim 타깃)를 형제 경로로 끌어온다.
if(NOT TARGET hitbot_zefg_hal)
  add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../hal" "${CMAKE_CURRENT_BINARY_DIR}/hitbot_zefg_hal")
endif()

add_library(hitbot_zefg_motion STATIC src/zefg_sequencer.cpp)
add_library(hitbot_zefg::motion ALIAS hitbot_zefg_motion)
set_target_properties(hitbot_zefg_motion PROPERTIES EXPORT_NAME motion POSITION_INDEPENDENT_CODE ON)
target_include_directories(hitbot_zefg_motion
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
# hal·warnings 는 add_subdirectory 소비(형제 프로젝트) — BUILD_INTERFACE 한정 전파
# (hitbot_zefg_sim 과 동일 판단).
target_link_libraries(hitbot_zefg_motion
  PUBLIC $<BUILD_INTERFACE:hitbot_zefg_hal>
  PRIVATE $<BUILD_INTERFACE:hitbot_zefg_hal_warnings>)
target_compile_features(hitbot_zefg_motion PUBLIC cxx_std_17)

# 소비자가 add_subdirectory 로 넣을 때는 시험을 등록하지 않는다(중복 등록 방지, hal/sim 선례).
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR OR HITBOT_ZEFG_MOTION_BUILD_TESTS)
  enable_testing()
  find_package(GTest QUIET)
  if(GTest_FOUND)
    find_package(Threads REQUIRED)
    if(NOT TARGET hitbot_zefg_sim)
      add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../sim" "${CMAKE_CURRENT_BINARY_DIR}/hitbot_zefg_sim")
    endif()
    # SIL 조립 테스트 — 목 링크·클라이언트 헤더 경로는 hitbot_zefg_sim·hitbot_zefg_hal 이
    # BUILD_INTERFACE 로 전이 제공한다(본 파일은 하위 통신 타깃을 직접 명명하지 않는다).
    add_executable(hitbot_zefg_sequencer_test test/zefg_sequencer_test.cpp)
    target_link_libraries(hitbot_zefg_sequencer_test
      PRIVATE hitbot_zefg_motion hitbot_zefg_sim hitbot_zefg_hal hitbot_zefg_hal_warnings
              GTest::gtest GTest::gtest_main Threads::Threads)
    add_test(NAME hitbot_zefg_sequencer_test COMMAND hitbot_zefg_sequencer_test)
  else()
    message(WARNING "hitbot_zefg_motion: GTest 미발견 — 단위테스트 제외")
  endif()
endif()

# install(TARGETS/EXPORT/DIRECTORY) 없음 — add_subdirectory 소비 전용 확정(ADR-005 Consequences
# 각주, 단계④ 최종 리뷰 F8).
