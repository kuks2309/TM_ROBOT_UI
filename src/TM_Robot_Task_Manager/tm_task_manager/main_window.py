"""애플리케이션 진입점 — TaskManagerNode(rclpy 노드)와 MainWindow(PyQt5 GUI)를 조립한다.

ROS 실행 모델은 별도 spin 스레드 없이 Qt QTimer(10ms)로 spin_once 를 폴링하는 방식이다.
"""
import math
import os
import time
from PyQt5.QtWidgets import (
    QMainWindow, QMessageBox, QTableWidgetItem, QFileDialog, QListWidgetItem, QApplication
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5 import uic

import rclpy
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory
from sensor_msgs.msg import Image, JointState
from geometry_msgs.msg import PoseStamped
from std_srvs.srv import Trigger
from cv_bridge import CvBridge

from . import paths
from .recipe_manager import RecipeManager, Recipe, Job
from .services.image_frame_cache import ImageFrameCache
from .job_executor import JobExecutor, ExecutionState
from .robot_connection import RobotConnectionManager, ConnectionState
from .global_variable_script import GlobalVariableScript
from .services.vision_manager import VisionManager
from .services.config_manager import ConfigManager
from .services.network_manager import NetworkManager
from .services.teaching_service import TeachingService
from .services.jog_service import JogService
from .services.command_gate import CommandGate
from .services.offset_preset_service import OffsetPresetService
from .services.image_processing_service import ImageProcessingService
from .services.tm_landmark_align_service import LandmarkAlignService
from .services.coordinate_system_manager import CoordinateSystemManager
from .services.camera_calibration_service import CameraCalibrationService
from .services.image_capture_service import ImageCaptureService
from .services.robot_motion_service import RobotMotionService, is_tm_joint_state
from .services.joystick_service import JoystickService
from .services.io_control_service import IOControlService
from .services.magazine_state_service import MagazineStateService
from .services.gripper_override_service import GripperOverrideService
from .services.ai_detection_service import AIDetectionService
from .services.coordinate_transformer import CoordinateTransformer, estimate_motion_timeout_s
from .services.vision_origin_check_service import VisionOriginCheckService
from tm_msgs.srv import SetPositions, AskItem, SendScript, SetIO

try:
    from rclpy.action import ActionClient as _SmcActionClient
    from gripper_ros.action import GripperCommand as _SmcGripperCommand
    _SMC_GRIPPER_AVAILABLE = True
except ImportError:
    _SMC_GRIPPER_AVAILABLE = False

try:
    from tc_msgs.srv import GripperCommand as _SchunkGripperCommand, DistanceCommand as _DistanceCommand
    _TC_MSGS_AVAILABLE = True
except ImportError:
    _TC_MSGS_AVAILABLE = False

from .tabs import (
    TaskEditTab, VisionTab, RunMonitorTab,
    SettingsTab, GlobalVariablesTab, PrecisionTestTab, HandEyeTestTab,
    PS2JoystickTestTab, KeyboardControlTab, IOControlTab, AIDetectionTab, PalletTeachTab
)


class TaskManagerNode(Node):
    """tm_driver 토픽 구독·서비스 클라이언트와 안전 가드를 보유한 rclpy 노드."""

    def __init__(self):
        super().__init__('tm_task_manager_node')

        paths.log_resolved(self.get_logger())

        self.bridge = CvBridge()

        self.motion_service = RobotMotionService()

        self.image_callback = None
        self.pose_callback = None
        self.joint_position_callback = None

        self.image_sub = None
        self.pose_sub = None

        self.joint_state_sub = self.create_subscription(
            JointState,
            'joint_states',
            self._on_joint_state,
            10
        )
        self.tool_pose_sub = self.create_subscription(
            PoseStamped,
            'tool_pose',
            self._on_tool_pose,
            10
        )
        from tm_msgs.msg import FeedbackState, SctResponse
        self.feedback_sub = self.create_subscription(
            FeedbackState,
            '/feedback_states',
            self._on_feedback_state,
            10
        )

        self.current_techman_image = None
        self.waiting_for_techman_image = False

        self.techman_image_cache = ImageFrameCache()

        self.techman_image_sub = self.create_subscription(
            Image,
            'techman_image',
            self._on_techman_image,
            10
        )
        self.get_logger().info('techman_image 영구 구독 생성 완료')

        self.set_positions_client = self.create_client(SetPositions, 'set_positions')

        self.ask_item_client = self.create_client(AskItem, 'ask_item')
        self.send_script_client = self.create_client(SendScript, 'send_script')

        self.set_io_client = self.create_client(SetIO, 'set_io')

        if _SMC_GRIPPER_AVAILABLE:
            self.gripper_action_client = _SmcActionClient(self, _SmcGripperCommand, '/gripper_node/command')
            self.get_logger().info('SMC 그리퍼 액션 클라이언트 생성 (/gripper_node/command)')
        else:
            self.gripper_action_client = None
            self.get_logger().warn('gripper_ros 미소싱 — SMC 그리퍼 태스크 비활성')

        if _TC_MSGS_AVAILABLE:
            self.schunk_gripper_client = self.create_client(_SchunkGripperCommand, 'gripper_command')
            self.distance_client = self.create_client(_DistanceCommand, 'distance_command')
            self.get_logger().info('SCHUNK 그리퍼·거리센서 클라이언트 생성 (/gripper_command, /distance_command)')
        else:
            self.schunk_gripper_client = None
            self.distance_client = None
            self.get_logger().warn('tc_msgs 미소싱 — SCHUNK 그리퍼·거리센서 태스크 비활성')

        self.io_control_service = None
        self.magazine_state_service = None

        self._init_safety_guard()

        self.get_logger().info('Task Manager Node initialized')

    def _init_safety_guard(self):
        """안전 구역 가드 배선 — 사전 검사(MotionGuard)·실시간 감시(BoundaryMonitor)·정지(RobotStopService).

        모든 모션은 self.motion_gateway 를 지나야 가드가 적용된다 — 새 모션 경로도 여기를 거치게 한다.
        """
        from .safety import safety_area as sa
        from .safety.boundary_monitor import BoundaryMonitor
        from .safety.motion_guard import MotionGuard
        from .safety.joint_guard import JointGuard
        from .services.motion_gateway import MotionGateway
        from .services.robot_stop_service import RobotStopService

        def log(message):
            self.get_logger().warn(message)

        area = sa.load_area()
        self.safety_guard = MotionGuard(area, log_callback=log)
        self.robot_stop_service = RobotStopService(self, log_callback=log)
        self.boundary_monitor = BoundaryMonitor(
            area,
            sample_fn=lambda: self.motion_service.current_tcp_pose,
            stop_fn=self.robot_stop_service.stop,
            log_callback=log,
        )
        self.motion_gateway = MotionGateway(
            self.safety_guard,
            tcp_pose_fn=lambda: self.motion_service.current_tcp_pose,
            monitor=self.boundary_monitor,
            log_callback=log,
        )
        self.safety_area_config = area
        self.joint_guard = JointGuard(
            area, stop_fn=self.robot_stop_service.stop, log_callback=log)
        if sa.joint_limits_enabled(area):
            jl_ok, jl_reason = sa.validate_joint_limits(area)
            if jl_ok:
                jl = sa.joint_limits_config(area)
                self.get_logger().info(
                    f"[조인트한계] 활성 — margin {jl.get('margin_deg')}°, "
                    f"auto_stop {jl.get('auto_stop')}")
            else:
                self.get_logger().error(f'[조인트한계] 설정이 올바르지 않습니다 — {jl_reason}')
        else:
            self.get_logger().warn('[조인트한계] 비활성 — 조인트 범위 검사 없이 동작합니다')

        if sa.is_enabled(area):
            ok, reason = sa.validate_area(area)
            if ok:
                self.get_logger().info(
                    f"[안전구역] 활성 — 허용 {len(area.get('allowed_boxes') or [])}개, "
                    f"금지 {len(area.get('keep_out_boxes') or [])}개, "
                    f"확장 {sa.keep_out_inflation_mm(area):.0f}mm")
            else:
                self.get_logger().error(f'[안전구역] 설정이 올바르지 않습니다 — {reason}')
        else:
            self.get_logger().warn(
                f'[안전구역] 비활성 — 구역 제약 없이 동작합니다 ({sa.config_path()})')

    def reload_safety_area(self):
        """안전 구역 설정을 다시 읽어 가드·감시기에 반영한다.

        Returns:
            (ok, reason).
        """
        from .safety import safety_area as sa

        area = self.safety_guard.reload()
        self.boundary_monitor.set_area(area)
        if not sa.is_enabled(area):
            return True, '안전 구역 비활성 — 제약 없음'
        return sa.validate_area(area)


    @property
    def current_joint_position(self):
        return self.motion_service.current_joint_position

    @property
    def current_tcp_pose(self):
        return self.motion_service.current_tcp_pose

    @property
    def current_base_name(self):
        return self.motion_service.current_base_name

    @current_base_name.setter
    def current_base_name(self, value):
        self.motion_service.current_base_name = value

    @property
    def robot_moving(self):
        return self.motion_service.is_moving

    @property
    def target_position(self):
        return self.motion_service.target_position

    @target_position.setter
    def target_position(self, value):
        self.motion_service.target_position = value

    @property
    def last_position_error(self):
        return self.motion_service.last_position_error

    @property
    def last_rotation_error(self):
        return self.motion_service.last_rotation_error

    @property
    def last_joint_error(self):
        return self.motion_service.last_joint_error


    def _on_joint_state(self, msg):
        """TM 로봇의 조인트 상태만 골라 motion_service 에 반영하고 UI 콜백을 부른다."""
        if is_tm_joint_state(msg.name, msg.position):
            self.motion_service.update_joint_state(list(msg.position[:6]))
            guard = getattr(self, 'joint_guard', None)
            if guard is not None:
                guard.update(self.current_joint_position)
            if self.joint_position_callback:
                self.joint_position_callback(self.current_joint_position)

    def _on_tool_pose(self, msg):
        pose = msg.pose
        self.motion_service.update_tcp_pose(
            pose.position.x, pose.position.y, pose.position.z,
            pose.orientation.x, pose.orientation.y,
            pose.orientation.z, pose.orientation.w
        )

    def _on_feedback_state(self, msg):
        """속도·SCT 연결 여부·IO 상태를 각 서비스 캐시에 반영한다."""
        tcp_speed = list(msg.tcp_speed) if msg.tcp_speed else []
        joint_vel = list(msg.joint_vel) if msg.joint_vel else []
        self.motion_service.update_feedback_state(tcp_speed, joint_vel)

        self.is_sct_connected = msg.is_sct_connected

        if hasattr(self, 'io_control_service') and self.io_control_service:
            cb_di = list(msg.cb_digital_input) if msg.cb_digital_input else []
            cb_do = list(msg.cb_digital_output) if msg.cb_digital_output else []
            ee_di = list(msg.ee_digital_input) if msg.ee_digital_input else []
            ee_do = list(msg.ee_digital_output) if msg.ee_digital_output else []
            cb_ai = list(msg.cb_analog_input) if hasattr(msg, 'cb_analog_input') and msg.cb_analog_input else None
            ee_ai = list(msg.ee_analog_input) if hasattr(msg, 'ee_analog_input') and msg.ee_analog_input else None
            self.io_control_service.update_io_state(cb_di, cb_do, ee_di, ee_do, cb_ai, ee_ai)
        else:
            if not hasattr(self, '_io_debug_logged'):
                self._io_debug_logged = True
                print(f"[DEBUG] io_control_service not set on TaskManagerNode")

    def _on_techman_image(self, msg):
        # 대기 여부와 무관하게 항상 캐시에 보관 — 소비자는 자기 기준 시퀀스 이후 프레임만 골라 간다.
        self.techman_image_cache.push(msg)

        if self.waiting_for_techman_image:
            self.current_techman_image = msg
            self.waiting_for_techman_image = False
            self.get_logger().info('techman_image 수신 완료')

    def start_techman_image_subscription(self):
        """촬영 대기를 연다 — 반환한 기준 시퀀스보다 뒤에 도착한 프레임만 이번 요청의 것으로 본다."""
        self.waiting_for_techman_image = True
        self.current_techman_image = None
        baseline = self.techman_image_cache.baseline()
        self.get_logger().info('techman_image 수신 대기 시작 (기준 seq=%d)' % baseline)
        return baseline

    def wait_techman_image(self, baseline, timeout_sec,
                           should_stop=None, spin=False):
        """baseline 이후에 도착한 techman_image 프레임을 기다린다.

        Args:
            baseline: start_techman_image_subscription 이 돌려준 기준 시퀀스.
            timeout_sec: 대기 한도 (s).
            should_stop: True 를 돌려주면 대기를 중단하는 콜백.
            spin: 자체 실행기가 없는 호출부가 직접 콜백을 돌려야 할 때 True.

        Returns:
            (msg, error) — msg 가 None 이면 error 에 사유가 담긴다.
        """
        on_poll = None
        if spin:
            def on_poll():
                rclpy.spin_once(self, timeout_sec=0.05)

        msg, err = self.techman_image_cache.wait_after(
            baseline, timeout_sec, should_stop=should_stop, on_poll=on_poll)
        if msg is not None:
            self.current_techman_image = msg
            self.waiting_for_techman_image = False
        return msg, err

    def _check_motion_complete(self):
        return self.motion_service.check_motion_complete()

    def _motion_kind_of(self, motion_type):
        """SetPositions.motion_type 상수 → 안전 가드가 쓰는 모션 종류 문자열."""
        from .safety import motion_guard as mg

        if motion_type == SetPositions.Request.LINE_T:
            return mg.MOTION_LINE
        if motion_type == SetPositions.Request.PTP_T:
            return mg.MOTION_PTP_TCP
        if motion_type == SetPositions.Request.PTP_J:
            return mg.MOTION_PTP_JOINT
        return f'set_positions({motion_type})'

    def _log_motion_command(self, kind, positions, velocity):
        """이동 명령의 좌표계·실측 TCP·목표를 진단 로그로 남긴다 — 로그가 모션을 막지 않도록 예외는 삼킨다."""
        import math
        from .safety import motion_guard as mg

        try:
            cur = self.motion_service.current_tcp_pose
            cur_txt = ('[' + ', '.join(f'{v:.2f}' for v in cur[:6]) + ']'
                       if cur and len(cur) >= 6 else 'None')

            if len(positions) >= 6:
                # 서비스 단위(m/rad) → 표시 단위(mm/deg) 환산
                if kind == mg.MOTION_PTP_JOINT:
                    target = [math.degrees(v) for v in positions[:6]]
                else:
                    target = [positions[0] * 1000.0, positions[1] * 1000.0, positions[2] * 1000.0,
                              math.degrees(positions[3]), math.degrees(positions[4]),
                              math.degrees(positions[5])]
                target_txt = '[' + ', '.join(f'{v:.2f}' for v in target) + ']'
            else:
                target_txt = str(list(positions))

            self.get_logger().info(
                f'[모션] {kind} base={self.motion_service.current_base_name} '
                f'vel={velocity} cur={cur_txt} target={target_txt}'
            )
        except Exception as e:
            self.get_logger().warn(f'[모션] 진단 로그 실패: {e}')

    def _call_set_positions(self, motion_type, positions, velocity, acc_time, blend_percentage=0, fine_goal=False):
        """안전 게이트웨이를 경유하는 set_positions — 판정에서 거부되면 명령을 보내지 않는다.

        positions 는 m·rad 단위이므로 가드에 넘길 목표는 mm 로 환산한다.
        """
        from .safety import motion_guard as mg
        from .safety import safety_area as sa

        kind = self._motion_kind_of(motion_type)
        self._log_motion_command(kind, positions, velocity)
        target_mm = None
        if kind == mg.MOTION_LINE and len(positions) >= 3:
            target_mm = [float(positions[i]) * 1000.0 for i in range(3)]

        area = getattr(self, 'safety_area_config', None)
        if kind == mg.MOTION_PTP_JOINT and area is not None and len(positions) >= 6:
            targets_deg = [math.degrees(float(p)) for p in positions[:6]]
            jl_ok, jl_reason = sa.check_joints(area, targets_deg)
            if not jl_ok:
                self.get_logger().warn(f'[조인트한계] 목표 거부 — {jl_reason}')
                return False, f'[조인트한계] 목표 거부 — {jl_reason}'

        return self.motion_gateway.send(
            kind,
            lambda: self._send_set_positions(
                motion_type, positions, velocity, acc_time, blend_percentage, fine_goal),
            target_mm=target_mm,
            label='set_positions',
        )

    def _send_set_positions(self, motion_type, positions, velocity, acc_time, blend_percentage=0, fine_goal=False):
        """set_positions 를 호출하고 완료를 폴링한다 (한도는 거리·속도 기반 동적, 완료 판정 3회 연속이면 성공)."""
        if not self.set_positions_client.wait_for_service(timeout_sec=1.0):
            return False, "TM Driver set_positions 서비스를 사용할 수 없습니다"

        request = SetPositions.Request()
        request.motion_type = motion_type
        request.positions = positions
        request.velocity = CoordinateTransformer.velocity_percent_to_service(motion_type, velocity)
        request.acc_time = acc_time
        request.blend_percentage = blend_percentage
        request.fine_goal = fine_goal

        future = self.set_positions_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)

        if future.result() is not None:
            if future.result().ok:
                import time
                if motion_type == SetPositions.Request.PTP_J:
                    kind = 'joint'
                elif motion_type == SetPositions.Request.LINE_T:
                    kind = 'line'
                else:
                    kind = 'tcp'
                timeout = estimate_motion_timeout_s(
                    kind, positions, velocity,
                    current_tcp_mm_deg=self.motion_service.current_tcp_pose,
                    current_joint_deg=self.motion_service.current_joint_position)
                self.get_logger().info(f'[모션] 완료 대기 한도 {timeout:.0f}s ({kind}, vel={velocity}%)')
                start_time = time.time()

                self.motion_service.target_position = positions.copy()

                stable_count = 0
                stable_threshold = 3

                while time.time() - start_time < timeout:
                    rclpy.spin_once(self, timeout_sec=0.1)

                    if self._check_motion_complete():
                        stable_count += 1
                        if stable_count >= stable_threshold:
                            error_msg = self.motion_service.get_motion_complete_message()
                            self.motion_service.clear_motion_state()
                            return True, error_msg
                    else:
                        stable_count = 0

                    time.sleep(0.05)

                self.motion_service.clear_motion_state()
                return False, f"이동 완료 확인 타임아웃 ({timeout:.0f}s 한도)"
            else:
                error_detail = getattr(future.result(), 'msg', '알 수 없는 오류')
                return False, f"이동 실패: 로봇이 명령을 거부함 ({error_detail})"
        else:
            return False, "서비스 호출 타임아웃"


    def start_subscriptions(self):
        """Vision 탭 라이브용 techman_image·aruco/pose 구독을 생성한다 (이미 있으면 유지)."""
        if self.image_sub is None:
            self.image_sub = self.create_subscription(
                Image,
                'techman_image',
                self._on_image,
                10
            )
            self.get_logger().info('Subscribed to techman_image')

        if self.pose_sub is None:
            self.pose_sub = self.create_subscription(
                PoseStamped,
                'aruco/pose',
                self._on_pose,
                10
            )
            self.get_logger().info('Subscribed to aruco/pose')

    def stop_subscriptions(self):
        """start_subscriptions 로 만든 구독을 해제한다."""
        if self.image_sub is not None:
            self.destroy_subscription(self.image_sub)
            self.image_sub = None
            self.get_logger().info('Unsubscribed from techman_image')

        if self.pose_sub is not None:
            self.destroy_subscription(self.pose_sub)
            self.pose_sub = None
            self.get_logger().info('Unsubscribed from aruco/pose')

    def _on_image(self, msg):
        if self.image_callback:
            try:
                cv_image = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
                self.image_callback(cv_image)
            except Exception as e:
                self.get_logger().error(f'Image conversion error: {e}')

    def _on_pose(self, msg):
        if self.pose_callback:
            self.pose_callback(msg)


class MainWindow(QMainWindow):
    """메인 창 — 서비스 객체들과 12개 탭을 조립하고 QTimer 로 ROS 를 폴링한다."""

    def __init__(self, ros_node=None):
        super().__init__()

        self.ros_node = ros_node

        self.connection_manager = None
        if self.ros_node:
            self.connection_manager = RobotConnectionManager(self.ros_node)

        self.gv_manager = None
        if self.ros_node:
            self.gv_manager = GlobalVariableScript(self.ros_node)

        package_share = get_package_share_directory('tm_task_manager')
        ui_path = os.path.join(package_share, 'ui', 'main_window.ui')
        uic.loadUi(ui_path, self)

        self.vision_manager = VisionManager(gv_manager=self.gv_manager, ros_node=self.ros_node)

        if self.ros_node:
            self.ros_node.vision_manager = self.vision_manager

        self.config_manager = ConfigManager()

        self.calib_service = CameraCalibrationService(ros_node=self.ros_node)
        self.calib_service.status_changed.connect(self._on_calib_status_changed)
        self.calib_service.chessboard_detected.connect(self._on_chessboard_detected)
        self.calib_service.image_captured.connect(self._on_calib_image_captured)
        self.calib_service.calibration_completed.connect(self._on_calibration_completed)
        self.calib_service.calibration_saved.connect(self._on_calibration_saved)
        self.calib_service.error_occurred.connect(self._log)

        self.current_camera_image = None
        self.captured_image = None
        self.image_processing_service = ImageProcessingService()
        self.image_processing_service.processing_error.connect(self._log)

        self.image_capture_service = ImageCaptureService(
            ros_node=self.ros_node,
            gv_manager=self.gv_manager
        )
        self.image_capture_service.image_captured.connect(self._on_image_captured)
        self.image_capture_service.capture_status.connect(self._log)
        self.image_capture_service.capture_error.connect(self._on_capture_error)

        self.teaching_service = TeachingService(ros_node=self.ros_node)
        self.teaching_service.position_taught.connect(self._on_position_taught)
        self.teaching_service.jog_completed.connect(lambda msg: self._log(msg))
        self.teaching_service.move_completed.connect(lambda success, msg: self._log(msg))

        self.command_gate = CommandGate(log_callback=self._log)
        self.offset_preset_service = OffsetPresetService()

        self.jog_service = JogService(
            ros_node=self.ros_node,
            teaching_service=self.teaching_service,
            move_callback=self._move_to_position,
            command_gate=self.command_gate
        )
        self.jog_service.jog_failed.connect(self._log)

        self.landmark_align_service = LandmarkAlignService(
            ros_node=self.ros_node,
            log_callback=self._log,
            gv_manager=self.gv_manager
        )

        self.coordinate_system_manager = CoordinateSystemManager(
            config_manager=self.config_manager,
            log_callback=self._log,
            ros_node=self.ros_node
        )

        joystick_config_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'joystick_config.yaml'
        )
        self.joystick_service = JoystickService(joystick_config_path)

        self.io_control_service = IOControlService(ros_node=self.ros_node)

        self.ros_node.io_control_service = self.io_control_service

        self.magazine_state_service = MagazineStateService(ros_node=self.ros_node)

        self.gripper_override_service = GripperOverrideService(self.ros_node, log_callback=self._log)
        self.ros_node.magazine_state_service = self.magazine_state_service

        self.ai_detection_service = AIDetectionService()


        self.recipe_manager = RecipeManager()
        self.recipe_manager.new_recipe("새 Recipe")

        self.job_executor = JobExecutor(ros_node=self.ros_node, vision_manager=self.vision_manager, ai_detection_service=self.ai_detection_service)
        self.vision_origin_check_service = VisionOriginCheckService(
            config_manager=self.config_manager,
            log_callback=self._log
        )

        self.job_executor.on_log = self._log
        self.job_executor.coordinate_system_manager = self.coordinate_system_manager
        self.job_executor.vision_origin_check_service = self.vision_origin_check_service
        self.job_executor.on_origin_check_alarm = self._on_origin_check_alarm
        self.job_executor.on_plate_rect_alarm = self._on_plate_rect_alarm

        self.task_edit_tab = TaskEditTab(self)
        self.vision_tab = VisionTab(self)
        self.run_monitor_tab = RunMonitorTab(self)
        self.settings_tab = SettingsTab(self)
        self.global_variables_tab = GlobalVariablesTab(self)
        self.precision_test_tab = PrecisionTestTab(self)
        self.handeye_test_tab = HandEyeTestTab(self)
        self.ps2_joystick_test_tab = PS2JoystickTestTab(self)
        self.keyboard_control_tab = KeyboardControlTab(self)
        self.io_control_tab = IOControlTab(self)
        self.ai_detection_tab = AIDetectionTab(self)
        self.pallet_teach_tab = PalletTeachTab(self)

        self._init_ui()

        self._connect_signals()

        if self.ros_node:
            self.ros_node.image_callback = self.vision_tab.update_camera_image
            self.ros_node.pose_callback = self.vision_tab.update_tag_pose
            self.ros_node.joint_position_callback = self._update_joint_display

        self.current_joint_position = None
        self.current_tcp_pose = None

        self.ros_timer = QTimer()
        self.ros_timer.timeout.connect(self._spin_ros)
        self.ros_timer.start(10)

        self.robot_status_timer = QTimer()
        self.robot_status_timer.timeout.connect(self._update_robot_status_display)
        self.robot_status_timer.start(100)

    def _spin_ros(self):
        """10ms 주기 QTimer — rclpy 콜백을 Qt 메인 스레드에서 비차단(spin_once timeout 0)으로 처리한다."""
        if self.ros_node and rclpy.ok():
            try:
                rclpy.spin_once(self.ros_node, timeout_sec=0)
            except (KeyboardInterrupt, Exception):
                self.close()

    def _connect_signals(self):
        self.actionNew.triggered.connect(self._on_new)
        self.actionOpen.triggered.connect(self._on_open)
        self.actionSave.triggered.connect(self._on_save)
        self.actionSaveAs.triggered.connect(self._on_save_as)
        self.actionExit.triggered.connect(self.close)
        self.actionAbout.triggered.connect(self._on_about)

        self.actionStop.triggered.connect(self._on_emergency_stop)
        self.actionEmergencyStop.triggered.connect(self._on_emergency_stop)

        self.pushButton_detectChessboard.clicked.connect(self._on_detect_chessboard)
        self.pushButton_captureCalibImage.clicked.connect(self._on_capture_calib_image)
        self.pushButton_runCalibration.clicked.connect(self._on_run_calibration)
        self.pushButton_saveCalibration.clicked.connect(self._on_save_calibration)

        self.pushButton_startCamera.clicked.connect(self._on_start_camera)
        self.pushButton_stopCamera.clicked.connect(self._on_stop_camera)
        self.pushButton_imageCapture.clicked.connect(self._on_image_capture)
        self.pushButton_imageSave.clicked.connect(self._on_image_save)

        self.task_edit_tab.connect_signals()
        self.vision_tab.connect_signals()
        self.run_monitor_tab.connect_signals()
        self.settings_tab.connect_signals()
        self.global_variables_tab.connect_signals()
        self.io_control_tab.connect_signals()
        self.ai_detection_tab.connect_signals()

    def _init_ui(self):
        self._init_ip_display()

        self._update_recent_files_menu()

        self.actionConnect.setEnabled(True)
        self.actionDisconnect.setEnabled(False)

        from PyQt5.QtWidgets import QLabel

        self.label_statusBar_connection = QLabel("연결: -")
        self.label_statusBar_connection.setStyleSheet("padding-right: 20px;")
        self.statusBar().addPermanentWidget(self.label_statusBar_connection)

        self.label_statusBar_coordinate = QLabel("좌표계: -")
        self.label_statusBar_coordinate.setStyleSheet("padding-right: 10px;")
        self.statusBar().addPermanentWidget(self.label_statusBar_coordinate)

        self.task_edit_tab.init_ui()
        self.vision_tab.init_ui()
        self.run_monitor_tab.init_ui()
        self.settings_tab.init_ui()
        self.global_variables_tab.init_ui()
        self.precision_test_tab.init_ui()
        self.handeye_test_tab.init_ui()
        self.ps2_joystick_test_tab.init_ui()
        self.keyboard_control_tab.init_ui()
        self.io_control_tab.init_ui()
        self.ai_detection_tab.init_ui()
        self.pallet_teach_tab.init_ui()

    def _init_ip_display(self):
        pc_ip = self._get_local_ip()
        self.lineEdit_pcIp.setText(pc_ip)

        robot_ip = self._load_robot_ip_from_config()
        if robot_ip:
            self.lineEdit_robotIp.setText(robot_ip)

        self.lineEdit_robotIp.editingFinished.connect(self._on_robot_ip_changed)

        self.pushButton_findRobotIp.clicked.connect(self._on_find_robot_ip)
        self.pushButton_refreshPcIp.clicked.connect(self._on_refresh_pc_ip)

    def _get_all_network_interfaces(self):
        return NetworkManager.get_all_network_interfaces()

    def _get_local_ip(self):
        return NetworkManager.get_local_ip(preferred_wired=True)

    def _load_robot_ip_from_config(self):
        return self.config_manager.get_robot_ip()

    def _on_robot_ip_changed(self):
        robot_ip = self.lineEdit_robotIp.text().strip()
        if robot_ip:
            self._save_robot_ip_to_config(robot_ip)
            self._log(f"Robot IP 저장됨: {robot_ip}")

    def _save_robot_ip_to_config(self, ip):
        try:
            self.config_manager.set_robot_ip(ip)
        except Exception as e:
            self._log(f"Robot IP 저장 실패: {e}")

    def _on_find_robot_ip(self):
        """백그라운드 스레드로 로봇 IP(5890/5891 포트)를 스캔하고 QTimer 로 완료를 폴링한다."""
        import threading

        self._log("TM 로봇 IP 검색 중...")
        self.pushButton_findRobotIp.setEnabled(False)
        self.pushButton_findRobotIp.setText("...")

        self._scan_result = []
        self._scan_done = False

        def scan_thread():
            local_ip = self._get_local_ip()
            self._scan_result = NetworkManager.scan_for_robot(
                local_ip=local_ip,
                ports=[5890, 5891],
                timeout=0.1
            )
            self._scan_done = True

        def check_scan_complete():
            if self._scan_done:
                self._scan_check_timer.stop()
                self._on_scan_complete()

        self._scan_check_timer = QTimer()
        self._scan_check_timer.timeout.connect(check_scan_complete)
        self._scan_check_timer.start(100)

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()

    def _on_scan_complete(self):
        self.pushButton_findRobotIp.setEnabled(True)
        self.pushButton_findRobotIp.setText("찾기")

        if self._scan_result:
            self.lineEdit_robotIp.setText(self._scan_result[0])
            self._save_robot_ip_to_config(self._scan_result[0])
            self._log(f"TM 로봇 발견: {', '.join(self._scan_result)}")
        else:
            self._log("TM 로봇을 찾을 수 없습니다")

    def _on_refresh_pc_ip(self):
        from PyQt5.QtWidgets import QInputDialog

        interfaces = self._get_all_network_interfaces()

        if not interfaces:
            self._log("사용 가능한 네트워크 인터페이스가 없습니다")
            return

        options = [iface['display'] for iface in interfaces]

        selected, ok = QInputDialog.getItem(
            self,
            "네트워크 인터페이스 선택",
            "사용할 네트워크 인터페이스를 선택하세요:",
            options,
            0,
            False
        )

        if ok and selected:
            for iface in interfaces:
                if iface['display'] == selected:
                    self.lineEdit_pcIp.setText(iface['ip'])
                    self._log(f"PC IP 설정: {iface['display']}")
                    break
        else:
            pc_ip = self._get_local_ip()
            self.lineEdit_pcIp.setText(pc_ip)
            self._log(f"PC IP 자동 설정: {pc_ip}")


    def _on_position_taught(self, taught_data: dict):
        motion_type = taught_data['motion_type']
        positions = taught_data['positions']
        unit = taught_data['unit']

        self._log(f"{motion_type.upper()} 위치 티칭: {positions} ({unit})")

    def _on_new(self):
        if self.recipe_manager.current_recipe and self.recipe_manager.current_recipe.jobs:
            reply = QMessageBox.question(
                self, "새 Recipe",
                "현재 Recipe를 저장하지 않고 새로 만드시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.recipe_manager.new_recipe("새 Recipe")
        self._update_task_sequence()
        self._log("새 Recipe 생성됨")
        self.setWindowTitle("TM Task Manager - 새 Recipe")

    def _on_open(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Recipe 열기",
            self.recipe_manager.recipe_dir,
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )

        if file_path:
            try:
                self.recipe_manager.load_recipe(file_path)
                self._update_task_sequence()
                recipe = self.recipe_manager.current_recipe
                self._log(f"Recipe 로드됨: {recipe.name} ({len(recipe.jobs)}개 Task)")
                file_name = os.path.basename(file_path)
                self.setWindowTitle(f"TM Task Manager - {file_name}")

                self._update_recent_files_menu()

                self.precision_test_tab._update_precision_recipe_label()
            except Exception as e:
                QMessageBox.warning(self, "오류", f"Recipe 로드 실패:\n{e}")
                self._log(f"Recipe 로드 실패: {e}")

    def _update_recipe_reference(self, recipe):
        """scan 잡이 있는 레시피 저장 시 tm_jig_landmark 기준점을 recipe.reference 에 기록한다."""
        has_scan = any(job.type == 'scan_tm_landmark' for job in recipe.jobs)
        if not has_scan:
            return

        landmark = None
        source = None

        if self.job_executor and getattr(self.job_executor, 'tm_landmark_pose', None):
            pose = self.job_executor.tm_landmark_pose
            if any(pose.get(k, 0.0) != 0.0 for k in ['x', 'y', 'z']):
                landmark = pose
                source = 'tm_landmark_pose'

        if landmark is None:
            scan_data = self.coordinate_system_manager.get_scan_data('jig_landmark')
            if scan_data and scan_data.get('landmark'):
                lm = scan_data['landmark']
                if any(lm.get(k, 0.0) != 0.0 for k in ['x', 'y', 'z']):
                    landmark = lm
                    source = 'coordinate_system_manager'

        if landmark:
            if recipe.reference is None:
                recipe.reference = {}
            recipe.reference['tm_jig_landmark'] = {
                'X': landmark['x'], 'Y': landmark['y'], 'Z': landmark['z'],
                'Rx': landmark['rx'], 'Ry': landmark['ry'], 'Rz': landmark['rz']
            }
            self._log(f"Recipe reference 저장 ({source}): jig_landmark X={landmark['x']:.2f}, Y={landmark['y']:.2f}, Z={landmark['z']:.2f}")

    def _on_save(self):
        recipe = self.recipe_manager.current_recipe
        if recipe is None:
            return

        if recipe.file_path:
            try:
                self._update_recipe_reference(recipe)
                self.recipe_manager.save_recipe()
                self._log(f"Recipe 저장됨: {recipe.file_path}")

                self._update_recent_files_menu()
            except Exception as e:
                QMessageBox.warning(self, "오류", f"저장 실패:\n{e}")
        else:
            self._on_save_as()

    def _on_save_as(self):
        recipe = self.recipe_manager.current_recipe
        if recipe is None:
            return

        default_name = recipe.name.replace(" ", "_") + ".yaml"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Recipe 저장",
            os.path.join(self.recipe_manager.recipe_dir, default_name),
            "YAML Files (*.yaml);;All Files (*)"
        )

        if file_path:
            if not file_path.endswith('.yaml'):
                file_path += '.yaml'
            try:
                self._update_recipe_reference(recipe)
                self.recipe_manager.save_recipe(file_path=file_path)
                self._log(f"Recipe 저장됨: {file_path}")
                file_name = os.path.basename(file_path)
                self.setWindowTitle(f"TM Task Manager - {file_name}")

                self._update_recent_files_menu()
            except Exception as e:
                QMessageBox.warning(self, "오류", f"저장 실패:\n{e}")
                self._log(f"저장 실패: {e}")


    def _on_about(self):
        QMessageBox.about(self, "About", "TM Task Manager v0.1\n\nAR 태그 기반 팔레트 픽업 작업 관리")


    def _on_emergency_stop(self):
        self.job_executor.stop()
        self._log("비상 정지!")


    def _on_origin_check_alarm(self, result):
        """기준점 편차 초과 시 축별 편차(mm/deg)와 허용범위를 담은 크리티컬 다이얼로그를 띄운다."""
        axis_lines = "\n".join(
            f"  {axis.upper()}: {result.deltas[axis]:+.3f}"
            f"{' mm' if axis in ('x', 'y', 'z') else ' deg'}"
            f"{'   ← 허용범위 초과' if axis in result.failed_axes else ''}"
            for axis in ('x', 'y', 'z', 'rx', 'ry', 'rz')
        )
        QMessageBox.critical(
            self,
            "기준점 확인 실패 — 로봇 교정 필요",
            f"측정된 기준점이 학습값과 다릅니다.\n"
            f"허용범위 초과 축: {', '.join(result.failed_axes)}\n\n"
            f"축별 편차 (측정 - 기준)\n{axis_lines}\n\n"
            f"허용범위: XYZ {result.tolerance['xyz']:.3f} mm / "
            f"RxRyRz {result.tolerance['rpy']:.3f} deg\n\n"
            f"실행을 중단했습니다. 로봇 교정 여부를 점검하세요."
        )


    def _on_plate_rect_alarm(self, payload):
        """직사각형 검증 실패 시 저장/중단 선택을 작업자에게 묻는다.

        Returns:
            True 면 저장하고 계속, False 면 중단.
        """
        results = payload['results']
        distances = payload['distances']

        check_lines = "\n".join(
            f"  {'X' if not r.passed else 'O'} {r.name}: "
            f"{r.value:.3f}{r.unit}   (상한 {r.threshold:.3f}{r.unit})"
            for r in results
        )
        dist_lines = "\n".join(f"  {name} = {value:.3f} mm"
                               for name, value in distances.items())

        reply = QMessageBox.warning(
            self,
            "Plate 직사각형 검증 실패 — 작업자 확인 필요",
            f"4 Landmark 배치가 허용 범위를 벗어났습니다.\n\n"
            f"검증 항목\n{check_lines}\n\n"
            f"실측 길이\n{dist_lines}\n\n"
            f"마커 장착 상태와 스캔 결과를 확인하십시오.\n"
            f"이대로 저장하고 계속하시겠습니까?",
            QMessageBox.Save | QMessageBox.Abort,
            QMessageBox.Abort
        )
        return reply == QMessageBox.Save


    def _update_joint_display(self, joint_positions):
        self.current_joint_position = joint_positions


    def _update_robot_status_display(self):
        if self.ros_node:
            if self.ros_node.current_joint_position:
                self.current_joint_position = self.ros_node.current_joint_position
            if self.ros_node.current_tcp_pose:
                self.current_tcp_pose = self.ros_node.current_tcp_pose

        if self.current_joint_position and len(self.current_joint_position) >= 6:
            self.lineEdit_j1.setText(f"{self.current_joint_position[0]:.2f}")
            self.lineEdit_j2.setText(f"{self.current_joint_position[1]:.2f}")
            self.lineEdit_j3.setText(f"{self.current_joint_position[2]:.2f}")
            self.lineEdit_j4.setText(f"{self.current_joint_position[3]:.2f}")
            self.lineEdit_j5.setText(f"{self.current_joint_position[4]:.2f}")
            self.lineEdit_j6.setText(f"{self.current_joint_position[5]:.2f}")

        if self.current_tcp_pose and len(self.current_tcp_pose) >= 6:
            self.lineEdit_tcpX.setText(f"{self.current_tcp_pose[0]:.2f}")
            self.lineEdit_tcpY.setText(f"{self.current_tcp_pose[1]:.2f}")
            self.lineEdit_tcpZ.setText(f"{self.current_tcp_pose[2]:.2f}")
            self.lineEdit_tcpRx.setText(f"{self.current_tcp_pose[3]:.2f}")
            self.lineEdit_tcpRy.setText(f"{self.current_tcp_pose[4]:.2f}")
            self.lineEdit_tcpRz.setText(f"{self.current_tcp_pose[5]:.2f}")


    def _on_start_camera(self):
        if getattr(self, '_camera_live_timer', None) and self._camera_live_timer.isActive():
            self._log("카메라 라이브 뷰가 이미 실행 중입니다")
            return
        if getattr(self, '_camera_live_timer', None) is None:
            self._camera_live_timer = QTimer(self)
            self._camera_live_timer.timeout.connect(self._on_camera_live_tick)
        self._camera_live_timer.start(500)
        self._log("카메라 라이브 뷰 시작 (최대 속도, 정지 버튼으로 종료)")
        self._on_camera_live_tick()

    def _on_camera_live_tick(self):
        if self.image_capture_service.is_capturing:
            return
        self.image_capture_service.capture_image(timeout_sec=15.0)

    def _on_stop_camera(self):
        if getattr(self, '_camera_live_timer', None) and self._camera_live_timer.isActive():
            self._camera_live_timer.stop()
            self._log("카메라 라이브 뷰 정지")
        else:
            self._log("카메라 라이브 뷰가 실행 중이 아닙니다")

    def _on_capture_error(self, msg: str):
        self._log(msg)
        timer = getattr(self, '_camera_live_timer', None)
        if timer and timer.isActive():
            timer.stop()
            self._log("캡처 실패 — 라이브 뷰를 정지했습니다 (로봇 반복 트리거 방지)")

    def _on_image_capture(self):
        self.image_capture_service.capture_image(timeout_sec=15.0)

    def _on_image_captured(self, cv_image):
        self.captured_image = cv_image
        self.current_camera_image = cv_image
        self.vision_tab.update_camera_image(cv_image)
        self._log("Image Capture 완료")

    def _on_image_save(self):
        if not hasattr(self, 'captured_image') or self.captured_image is None:
            self._log("저장할 이미지가 없습니다. 먼저 Image Capture를 실행하세요.")
            return

        self._save_captured_image(self.captured_image)

    def _save_captured_image(self, cv_image):
        """캡처 이미지를 data/images/<날짜>/ 에 PNG 로 저장한다 (실패 시 None)."""
        import cv2
        from datetime import datetime

        base_path = str(paths.DATA_DIR / 'images')
        date_folder = datetime.now().strftime('%Y%m%d')
        save_dir = os.path.join(base_path, date_folder)

        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%H%M%S_%f')[:-3]
        filename = f"capture_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)

        # cv2.imwrite 는 실패해도 예외 없이 False 만 돌려주므로 반환값을 반드시 확인한다.
        if not cv2.imwrite(filepath, cv_image):
            self._log(f"이미지 저장 실패 (경로·권한·형식 확인): {filepath}")
            return None
        self._log(f"이미지 저장: {filepath}")
        return filepath


    def _on_detect_chessboard(self):
        self.calib_service.detect_chessboard()

    def _on_capture_calib_image(self):
        self.calib_service.capture_image()

    def _on_run_calibration(self):
        self.calib_service.run_calibration()

    def _on_save_calibration(self):
        self.calib_service.save_calibration()


    def _on_calib_status_changed(self, status: str):
        self.label_calibrationStatus.setText(status)

    def _on_chessboard_detected(self, success: bool, message: str):
        if success:
            self._log(f"Chessboard 인식: {message}")
        else:
            self._log(f"Chessboard 인식 실패: {message}")

    def _on_calib_image_captured(self, success: bool, message: str, count: int):
        self.label_capturedCount.setText(f"캡처된 이미지: {count}")
        if success:
            self._log(f"캘리브레이션 이미지 캡처: {message}")
        else:
            self._log(f"이미지 캡처 실패: {message}")

    def _on_calibration_completed(self, success: bool, message: str):
        if success:
            self._log(f"캘리브레이션 성공:\n{message}")
        else:
            self._log(f"캘리브레이션 실패: {message}")

    def _on_calibration_saved(self, success: bool, message: str):
        if success:
            self._log(f"캘리브레이션 결과 저장: {message}")
        else:
            self._log(f"저장 실패: {message}")


    def _move_to_position(self, motion_type, positions, velocity, acc_time, blend_percentage=0, fine_goal=False):
        """jog/teaching 서비스용 이동 콜백 — ros_node 의 안전 게이트 경유 호출로 위임한다."""
        if not self.ros_node:
            return False, "ROS 노드 없음"

        return self.ros_node._call_set_positions(
            motion_type,
            positions,
            velocity,
            acc_time,
            blend_percentage,
            fine_goal
        )


    def _update_task_sequence(self):
        self.listWidget_taskSequence.clear()
        recipe = self.recipe_manager.current_recipe
        if recipe:
            for job in recipe.jobs:
                display_name = getattr(job, 'caption', '') or job.name
                item_text = f"{job.id}. [{job.type}] {display_name}"
                item = QListWidgetItem(item_text)
                self.listWidget_taskSequence.addItem(item)


    @property
    def current_tcp_orientation(self):
        return self.coordinate_system_manager.get_current_tcp_orientation()

    # 로그 스타일 테이블: (kind, 마크, 전경색, 배경색, 트리거 키워드)
    LOG_STYLES = (
        ('fail', '✕', '#b00020', '#fdecea',
         ('실패', '오류', '[거부]', '[중단]', '[ERROR]', '초과', '타임아웃', '불가',
          '기대는')),
        ('warn', '▲', '#8a6100', '#fff6e0',
         ('[경고]', '[알람]', '건너뜀', '건너뜁니다', '생략', '주의', '무시')),
        ('ok', '✔', '#0b6b2f', '#e8f6ec',
         ('통과', '일치')),
    )

    LOG_PREMARKS = ('✅', '❌', '⚠️', '⚠', '✓', '✗')

    def _log_style_for(self, message, kind=None):
        """명시 kind 또는 메시지 키워드로 로그 스타일(마크·전경·배경)을 정한다 (해당 없으면 None)."""
        if kind is not None:
            if kind == 'plain':
                return None
            for key, mark, fg, bg, _needles in self.LOG_STYLES:
                if key == kind:
                    return mark, fg, bg
            return None
        for _kind, mark, fg, bg, needles in self.LOG_STYLES:
            if any(needle in message for needle in needles):
                return mark, fg, bg
        return None

    def _strip_log_premark(self, message):
        """메시지 선두의 이모지 마크를 제거한다 — 스타일 마크와의 중복 표시 방지."""
        text = message.lstrip()
        for mark in self.LOG_PREMARKS:
            if text.startswith(mark):
                return text[len(mark):].lstrip()
        return message

    def _log(self, message, kind=None):
        """타임스탬프 로그 출력 — 스타일 대상이면 HTML 색상을 입힌다.

        마지막 processEvents 호출로 동기 잡 실행 중에도 GUI 이벤트가 처리된다 —
        실행 중 정지 버튼이 동작하는 경로이므로 제거 시 대체 수단이 필요하다.
        """
        from datetime import datetime
        from html import escape
        from PyQt5.QtGui import QTextCharFormat
        from PyQt5.QtWidgets import QApplication

        timestamp = datetime.now().strftime("%H:%M:%S")
        style = self._log_style_for(message, kind)

        if style is None:
            self.textEdit_log.append(f"[{timestamp}] {message}")
        else:
            mark, fg, bg = style
            body = escape(self._strip_log_premark(message)).replace('\n', '<br>')
            self.textEdit_log.append('')
            cursor = self.textEdit_log.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertHtml(
                f'<span style="color:{fg}; background-color:{bg}; font-weight:bold;">'
                f'[{timestamp}] {mark} {body}</span>'
            )
            cursor.setCharFormat(QTextCharFormat())
            self.textEdit_log.setTextCursor(cursor)
            self.textEdit_log.setCurrentCharFormat(QTextCharFormat())

        self.textEdit_log.ensureCursorVisible()
        QApplication.processEvents()


    def _update_recent_files_menu(self):
        self.menuRecentFiles.clear()

        recent_files = self.recipe_manager.get_recent_files()

        if not recent_files:
            action = self.menuRecentFiles.addAction("(최근 파일 없음)")
            action.setEnabled(False)
        else:
            for i, file_path in enumerate(recent_files):
                file_name = os.path.basename(file_path)
                action_text = f"{i+1}. {file_name}"
                action = self.menuRecentFiles.addAction(action_text)
                action.setData(file_path)
                action.triggered.connect(lambda checked, path=file_path: self._open_recent_file(path))

    def _open_recent_file(self, file_path):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "오류", f"파일을 찾을 수 없습니다:\n{file_path}")
            self.recipe_manager.remove_from_recent_files(file_path)
            self._update_recent_files_menu()
            return

        try:
            self.recipe_manager.load_recipe(file_path)
            self._update_task_sequence()
            recipe = self.recipe_manager.current_recipe
            self._log(f"Recipe 로드됨: {recipe.name} ({len(recipe.jobs)}개 Task)")
            file_name = os.path.basename(file_path)
            self.setWindowTitle(f"TM Task Manager - {file_name}")

            self._update_recent_files_menu()

            self.precision_test_tab._update_precision_recipe_label()
        except Exception as e:
            QMessageBox.warning(self, "오류", f"Recipe 로드 실패:\n{e}")
            self._log(f"Recipe 로드 실패: {e}")


    def closeEvent(self, event):
        """종료 정리 — 타이머 정지·구독 해제·TF 정지 후 카메라 브리지 프로세스를 정리한다."""
        import subprocess

        self.ros_timer.stop()
        self.robot_status_timer.stop()
        if getattr(self, '_camera_live_timer', None):
            self._camera_live_timer.stop()
        if self.ros_node:
            self.ros_node.stop_subscriptions()

        if self.coordinate_system_manager:
            self.coordinate_system_manager.stop_tf_publishing()

        if self.connection_manager and self.connection_manager.is_connected():
            self.connection_manager.disconnect()

        try:
            subprocess.run(['pkill', '-f', 'tm_camera_bridge'],
                         timeout=1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

        try:
            subprocess.run(['pkill', '-f', 'camera_calibration_node'],
                         timeout=1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

        event.accept()


def main():
    """진입점 — rclpy 초기화 → TaskManagerNode → QApplication → MainWindow → 이벤트 루프."""
    import sys
    from PyQt5.QtWidgets import QApplication

    rclpy.init(args=sys.argv)

    ros_node = TaskManagerNode()

    app = QApplication(sys.argv)

    window = MainWindow(ros_node=ros_node)
    window.show()

    exit_code = app.exec_()

    ros_node.destroy_node()
    rclpy.shutdown()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
