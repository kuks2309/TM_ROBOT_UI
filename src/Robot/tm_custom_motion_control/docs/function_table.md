# src/Robot/tm_custom_motion_control — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/Robot/tm_custom_motion_control/include/tm_custom_motion_control/gripper_control.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 6 | `GripperControl::isOpen` (inline) | - | `bool` | is_open_ | include/tm_custom_motion_control/gripper_control.hpp:50 |
| 7 | `GripperControl::setOpenPin` (inline) | `pin` | void | 핀 변경 | gripper_control.hpp:52 |
| 8 | `GripperControl::setClosePin` (inline) | `pin` | void | 핀 변경 | gripper_control.hpp:53 |
| 9 | `GripperControl::setModule` (inline) | `module` | void | 모듈 변경 | gripper_control.hpp:54 |

## src/Robot/tm_custom_motion_control/include/tm_custom_motion_control/motion_control.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 11 | `MotionControl::setDefaultVelocityPTP` (inline) | `velocity` | void | 기본 PTP 속도 설정 | include/tm_custom_motion_control/motion_control.hpp:77 |
| 12 | `MotionControl::setDefaultVelocityLinear` (inline) | `velocity` | void | 기본 선형 속도 설정 | motion_control.hpp:78 |
| 13 | `MotionControl::setDefaultAccTime` (inline) | `acc_time` | void | 기본 가속시간 설정 | motion_control.hpp:79 |
| 14 | `MotionControl::setDefaultBlend` (inline) | `blend` | void | 기본 블렌드 설정 | motion_control.hpp:80 |

## src/Robot/tm_custom_motion_control/include/tm_custom_motion_control/robot_client.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 17 | `RobotClient::isConnected` (inline) | - | `bool` | connected_ 반환 | include/tm_custom_motion_control/robot_client.hpp:63 |

## src/Robot/tm_custom_motion_control/launch/driver.launch.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `generate_launch_description` | - | LaunchDescription | config_file 인자 선언만 (노드 없음) | src/Robot/tm_custom_motion_control/launch/driver.launch.py:10 |

## src/Robot/tm_custom_motion_control/launch/motion_control.launch.py

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 2 | `generate_launch_description` | - | LaunchDescription | 인자 7종 + motion_control_node 기동 | src/Robot/tm_custom_motion_control/launch/motion_control.launch.py:8 |

## src/Robot/tm_custom_motion_control/src/gripper_control.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `GripperControl::GripperControl` | `client, open_pin=0, close_pin=1, module=CONTROL_BOX` | - | 핀·모듈 보관 | src/Robot/tm_custom_motion_control/src/gripper_control.cpp:6 |
| 2 | `GripperControl::open` | - | `bool` | close OFF → open ON, is_open_=true | gripper_control.cpp:19 |
| 3 | `GripperControl::close` | - | `bool` | open OFF → close ON, is_open_=false | gripper_control.cpp:42 |
| 4 | `GripperControl::setPosition` | `position: float` | `bool` | ANALOG_OUT(open_pin_) 출력 | gripper_control.cpp:64 |
| 5 | `GripperControl::release` | - | `bool` | 양핀 OFF | gripper_control.cpp:73 |

## src/Robot/tm_custom_motion_control/src/motion_control.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `MotionControl::MotionControl` | `client: shared_ptr<RobotClient>` | - | 클라이언트 보관 | src/Robot/tm_custom_motion_control/src/motion_control.cpp:8 |
| 2 | `MotionControl::moveJoint` | `joints(6), velocity=-1, acc_time=-1, blend=-1, fine_goal=false` | `bool` | PTP_J setPositions | motion_control.cpp:13 |
| 3 | `MotionControl::moveTCP` | `pose(6), …` | `bool` | PTP_T setPositions | motion_control.cpp:33 |
| 4 | `MotionControl::moveLinear` | `pose(6), …` | `bool` | LINE_T setPositions | motion_control.cpp:53 |
| 5 | `MotionControl::moveCircular` | `via_point, end_point, velocity=100, arc_angle=0` | `bool` | `Circle("CAP",…)` 스크립트 | motion_control.cpp:73 |
| 6 | `MotionControl::moveHome` | - | `bool` | `QueueTag(1)`+`PTP("JPP",0…)` 스크립트 | motion_control.cpp:100 |
| 7 | `MotionControl::stop` | - | `bool` | `StopAndClearBuffer()` | motion_control.cpp:107 |
| 8 | `MotionControl::pause` | - | `bool` | `Pause()` | motion_control.cpp:112 |
| 9 | `MotionControl::resume` | - | `bool` | `Resume()` | motion_control.cpp:117 |
| 10 | `MotionControl::setSpeed` | `speed_percentage: int` | `bool` | `ChangeSpeedOverride(n)` | motion_control.cpp:122 |

## src/Robot/tm_custom_motion_control/src/motion_control_node.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `MotionControlNode::MotionControlNode` | - | - | 파라미터 9종 declare | src/Robot/tm_custom_motion_control/src/motion_control_node.cpp:25 |
| 2 | `MotionControlNode::initialize` | - | void | client/motion/gripper 조립, 서비스 13·구독 3 생성 | motion_control_node.cpp:44 |
| 3 | `MotionControlNode::moveJointCallback` | `req/res: SetPositions` | void | moveJoint 위임 | motion_control_node.cpp:143 |
| 4 | `MotionControlNode::moveLinearCallback` | `req/res: SetPositions` | void | moveLinear 위임 | motion_control_node.cpp:156 |
| 5 | `MotionControlNode::moveTCPCallback` | `req/res: SetPositions` | void | moveTCP 위임 + 성공 로그 | motion_control_node.cpp:169 |
| 6 | `MotionControlNode::goHomeCallback` | `req/res: Trigger` | void | home_position 파라미터로 moveJoint | motion_control_node.cpp:188 |
| 7 | `MotionControlNode::goTMflowHomeCallback` | `req/res: Trigger` | void | moveHome (TMflow 홈) | motion_control_node.cpp:212 |
| 8 | `MotionControlNode::getJointPositionCallback` | `req/res: Trigger` | void | 조인트 6값 CSV 응답 | motion_control_node.cpp:228 |
| 9 | `MotionControlNode::getTCPPoseCallback` | `req/res: Trigger` | void | TCP 6값 CSV 응답 | motion_control_node.cpp:251 |
| 10 | `MotionControlNode::gripperCmdCallback` | `msg: Bool` | void | true=open / false=close | motion_control_node.cpp:274 |
| 11 | `MotionControlNode::stopCmdCallback` | `msg: Bool` | void | true 시 motion_->stop | motion_control_node.cpp:286 |
| 12 | `MotionControlNode::speedOverrideCallback` | `msg: Int32` | void | ChangeSpeedOverride | motion_control_node.cpp:295 |
| 13 | `MotionControlNode::getToolListCallback` | `req/res: Trigger` | void | 공구 목록 CSV 응답 | motion_control_node.cpp:303 |
| 14 | `MotionControlNode::getToolInfoCallback` | `req/res: Trigger` | void | 공구 정보 JSON 문자열 응답 | motion_control_node.cpp:326 |
| 15 | `MotionControlNode::changeToolCallback` | `req/res: Trigger` | void | current_tool_name 파라미터로 ChangeTool | motion_control_node.cpp:356 |
| 16 | `MotionControlNode::setTCPCallback` | `req/res: SetPositions` | void | positions(6) 검증 후 setTCP | motion_control_node.cpp:382 |
| 17 | `MotionControlNode::setPayloadCallback` | `req/res: SetPositions` | void | positions(≥4)=mass+cog 로 setPayload | motion_control_node.cpp:402 |
| 18 | `MotionControlNode::testConnectionCallback` | `req/res: Trigger` | void | 서비스 가용+조인트 조회로 연결 진단 JSON | motion_control_node.cpp:424 |
| 19 | `main` | `argc, argv` | `int` | init → 노드 생성 → initialize → spin | motion_control_node.cpp:491 |

## src/Robot/tm_custom_motion_control/src/robot_client.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | `RobotClient::RobotClient` | `node: Node::SharedPtr` | - | 클라이언트 5종 생성 | src/Robot/tm_custom_motion_control/src/robot_client.cpp:7 |
| 2 | `RobotClient::waitForService<T>` (template, private) | `client, service_name, timeout_sec` | `bool` | 단일 서비스 대기 | robot_client.cpp:18 |
| 3 | `RobotClient::waitForServices` | `timeout_sec=5.0` | `bool` | 5종 순차 대기 | robot_client.cpp:31 |
| 4 | `RobotClient::connect` | `server_type=1, timeout=1.0` | `bool` | ConnectTM 호출(10s spin 대기) | robot_client.cpp:51 |
| 5 | `RobotClient::disconnect` | - | `bool` | ConnectTM connect=false (5s) | robot_client.cpp:79 |
| 6 | `RobotClient::setPositions` | `motion_type, positions, velocity, acc_time, blend_percentage, fine_goal` | `bool` | set_positions 호출(30s) | robot_client.cpp:100 |
| 7 | `RobotClient::setIO` | `module, type, pin, state` | `bool` | set_io 호출(5s) | robot_client.cpp:126 |
| 8 | `RobotClient::sendScript` | `script, script_id="tm_script"` | `bool` | send_script 호출(10s) | robot_client.cpp:144 |
| 9 | `RobotClient::askSta` | `subcmd, subdata, response_data&` | `bool` | ask_sta 호출(5s), subdata 회수 | robot_client.cpp:160 |
| 10 | `RobotClient::getCurrentJointPositions` | `positions&` | `bool` | askSta("00") CSV→6개 double | robot_client.cpp:181 |
| 11 | `RobotClient::getCurrentTCPPose` | `pose&` | `bool` | askSta("01") CSV→6개 double | robot_client.cpp:201 |
| 12 | `RobotClient::getCurrentToolInfo` | `tool_name&, tcp&, mass&, cog&` | `bool` | askSta("02"/"01"/"03") 조합 — tcp 는 항상 0 | robot_client.cpp:222 |
| 13 | `RobotClient::setTCP` | `tcp: vector<double>(6)` | `bool` | `ChangeTCP(...)` 스크립트 전송 | robot_client.cpp:275 |
| 14 | `RobotClient::setPayload` | `mass, cog(3)` | `bool` | `ChangeLoad(...)` 스크립트 전송 | robot_client.cpp:298 |
| 15 | `RobotClient::changeTool` | `tool_name` | `bool` | `ChangeTool("...")` 스크립트 전송 | robot_client.cpp:321 |
| 16 | `RobotClient::getToolList` | `tool_names&` | `bool` | 기본 2종 + askSta("04") CSV 파싱, 항상 true | robot_client.cpp:335 |
