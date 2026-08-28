cmake_minimum_required(VERSION 3.8)
project(tc_msgs)


# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()


# find dependencies
find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

set(msg_files
  "msg/Command.msg"
  "msg/AmrAlarm.msg"
  "msg/AlarmState.msg"
  "msg/AmrJog.msg"
  "msg/AmrStatusForSafety.msg"
  "msg/SafetyStatus.msg"
  "msg/AmrTask.msg"
  "msg/Io.msg"
  "msg/IoControl.msg"
  "msg/TopicResponse.msg"
  "msg/TopicRequest.msg"
  "msg/TaskInfo.msg"
  "msg/DrawerStatus.msg"
  "msg/RoboteqQry.msg"
  "msg/DrawerJog.msg"
  "msg/ScenarioInfo.msg"
  "msg/CobotStatus.msg"
)

set(srv_files
  "srv/Navigate.srv"
  "srv/DrawerCommand.srv"
  "srv/DrawerSetting.srv"
  "srv/CobotGuiCommand.srv"
  "srv/CobotTestCommand.srv"
  "srv/GripperCommand.srv"
  "srv/RoboteqCmd.srv"
  "srv/ArucoMarkers.srv"
  "srv/Io.srv"
  "srv/Lidar.srv"

  "srv/HpioIdCmd.srv"
  "srv/HpioConfig.srv"
  "srv/HpioStatus.srv"
  "srv/PioTimeoutSetting.srv"

  "srv/CycleTest.srv"
  "srv/ArucoMarkerCheck.srv"
  
  "srv/Emo.srv"
  "srv/Reset.srv"
  "srv/Relocation.srv"

  "srv/DistanceCommand.srv"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  DEPENDENCIES builtin_interfaces std_msgs geometry_msgs
  ADD_LINTER_TESTS
)

ament_export_dependencies(rosidl_default_runtime)

ament_package()
