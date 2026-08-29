import os
import re
import time
import math
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Tuple

import rclpy
import yaml
import numpy as np
from scipy.spatial.transform import Rotation

from . import paths
from .recipe_manager import Recipe, Job, RecipeManager
from .macros import MacroContext, run_macro
from tm_task_manager.tools.landmark_parser import parse_tm_landmark_to_dict
from tm_task_manager.tools.landmark_frame import (
    FRAME_MODE_RZ_ONLY,
    FRAME_MODES,
    TOOL_OFFSET_6DOF_KEYS,
    apply_tool_offset_6dof,
    pose_from_landmark_frame,
    pose_in_landmark_frame,
    tool_offset_6dof_from_poses,
)
from tm_task_manager.tools.jig_plane_calculator import (
    JigPlaneCalculator,
    Mark,
    TOOL_OFFSET_KEYS,
    apply_tool_offset,
    average_landmarks_from_files,
    plane_normal_from_pose,
    pose_from_plane_frame,
    signed_point_to_plane_distance,
    tcp_pose_for_plane_normal,
    tool_offset_from_poses,
)
from tm_task_manager.tools.jig_plate_validator import JigPlateValidator
from .services.landmark_analyzer import LandmarkAnalyzer
from .services.decomposed_move_planner import (
    build_decomposed_tcp_waypoints,
    DECOMPOSED_MIN_STEP_MM,
    DECOMPOSED_MIN_STEP_DEG,
)


POSE_KEEP_MIN_SEGMENT_MM = 0.1

POSE_KEEP_DECEL_ZONE_MM = 40.0
POSE_KEEP_DECEL_VELOCITY = 10.0
POSE_KEEP_DECEL_MARGIN_MM = 5.0

PLANE_ALIGN_MAX_TILT_DEG = 30.0
PLANE_ALIGN_MAX_DIAGONAL_DIFF_MM = 10.0
PLANE_ALIGN_MIN_ROTATION_DEG = 0.01


class ExecutionState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


class JobExecutor:
    def __init__(self, ros_node=None, vision_manager=None, ai_detection_service=None):
        self.ros_node = ros_node
        self.state = ExecutionState.IDLE
        self.current_recipe: Optional[Recipe] = None
        self.current_job_index = 0

        self.on_state_changed: Optional[Callable[[ExecutionState], None]] = None
        self.on_job_started: Optional[Callable[[int, Job], None]] = None
        self.on_job_completed: Optional[Callable[[int, Job, bool], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None
        self.on_measure_point: Optional[Callable[[], None]] = None
        self.on_origin_check_alarm: Optional[Callable[[Any], None]] = None
        self.on_plate_rect_alarm: Optional[Callable[[Any], bool]] = None

        self.detected_ar_pose: Optional[Dict[str, float]] = None

        self.detected_landmark_pose: Optional[Dict[str, float]] = None

        self.detected_plate_pose: Optional[Dict[str, float]] = None
        self.measured_plane_distance: Optional[float] = None

        self.jig_landmark_results: Dict[int, Dict[str, float]] = {}
        self.saved_poses: Dict[str, List[float]] = {}

        self.vision_manager = vision_manager

        self.ai_detection_service = ai_detection_service

        self.tm_transform_matrix: Optional[np.ndarray] = None
        self.tm_landmark_pose: Optional[Dict[str, float]] = None

        self.coordinate_system_manager = None

        self.vision_origin_check_service = None

        self.macro_blackboard: Dict[str, Any] = {}

        self.recipe_mode: str = 'execution'

        self._stop_requested = False

        self._direction = 1

    def _log(self, message: str):
        if self.on_log:
            self.on_log(message)

    @property
    def last_origin_check_result(self):
        return self.macro_blackboard.get('origin_check_result')

    def _macro_context(self) -> MacroContext:
        return MacroContext(self, self.macro_blackboard)

    def _run_macro_sequence(self, job: Job, macro_defs: List[Dict[str, Any]]) -> bool:
        ctx = self._macro_context()

        for index, macro_def in enumerate(macro_defs, start=1):
            name = macro_def.get('use')
            if not name:
                self._log(f"[오류] {job.type} 의 {index}번 매크로 정의에 'use' 가 없습니다")
                return False

            params = dict(job.params)
            for macro_param, job_param in (macro_def.get('bind') or {}).items():
                if job_param in job.params:
                    params[macro_param] = job.params[job_param]

            if len(macro_defs) > 1:
                self._log(f"[매크로 {index}/{len(macro_defs)}] {name}")

            result = run_macro(name, ctx, params)
            if not result.ok:
                self._log(f"[오류] 매크로 '{name}' 실패: {result.message}")
                return False

        return True

    def _wait_for_listen_node(self, timeout: float = 10.0) -> bool:
        import time
        import rclpy

        if not self.ros_node:
            return False

        start_time = time.time()
        check_interval = 0.1

        while time.time() - start_time < timeout:
            rclpy.spin_once(self.ros_node, timeout_sec=check_interval)

            if hasattr(self.ros_node, 'is_sct_connected') and self.ros_node.is_sct_connected:
                elapsed = time.time() - start_time
                self._log(f"Listen Node 연결 확인 ({elapsed:.2f}초 대기)")
                return True

        return False

    def _set_state(self, state: ExecutionState):
        self.state = state
        if self.on_state_changed:
            self.on_state_changed(state)

    def load_recipe(self, recipe: Recipe):
        self.current_recipe = recipe
        self.current_job_index = 0
        self._set_state(ExecutionState.IDLE)

    def run(self):
        return self.run_from(0)

    def run_from(self, start_index: int = 0):
        if self.current_recipe is None:
            self._log("실행할 Recipe가 없습니다")
            return False

        if not self.current_recipe.jobs:
            self._log("Recipe에 Job이 없습니다")
            return False

        if start_index < 0 or start_index >= len(self.current_recipe.jobs):
            self._log(f"잘못된 시작 인덱스: {start_index} (총 {len(self.current_recipe.jobs)}개)")
            return False

        self._stop_requested = False
        self._direction = 1
        self.macro_blackboard.clear()
        self._set_state(ExecutionState.RUNNING)
        self.current_job_index = start_index

        if start_index > 0:
            self._log(f"Task {start_index + 1}번부터 실행 시작")

        return self._execute_next_job()

    def run_reverse_from(self, start_index: int):
        if self.current_recipe is None:
            self._log("실행할 Recipe가 없습니다")
            return False

        if not self.current_recipe.jobs:
            self._log("Recipe에 Job이 없습니다")
            return False

        if start_index < 0 or start_index >= len(self.current_recipe.jobs):
            self._log(f"잘못된 시작 인덱스: {start_index} (총 {len(self.current_recipe.jobs)}개)")
            return False

        self._stop_requested = False
        self._direction = -1
        self._set_state(ExecutionState.RUNNING)
        self.current_job_index = start_index

        self._log(f"Task {start_index + 1}번부터 역순 실행 (→ 1번)")

        return self._execute_next_job()

    def pause(self):
        if self.state == ExecutionState.RUNNING:
            self._set_state(ExecutionState.PAUSED)
            self._log("실행 일시정지됨")

    def resume(self):
        if self.state == ExecutionState.PAUSED:
            self._set_state(ExecutionState.RUNNING)
            self._log("실행 재개됨")
            return self._execute_next_job()
        return False

    def stop(self):
        self._stop_requested = True
        self._set_state(ExecutionState.STOPPED)
        self.current_job_index = 0
        self._log("실행 정지됨")

    def step(self):
        if self.current_recipe is None:
            self._log("실행할 Recipe가 없습니다")
            return False

        if self.current_job_index >= len(self.current_recipe.jobs):
            self._log("모든 Job이 완료되었습니다")
            return False

        self._set_state(ExecutionState.RUNNING)
        success = self._execute_current_job()
        self._set_state(ExecutionState.PAUSED)
        return success

    def _execute_next_job(self) -> bool:
        if self.state != ExecutionState.RUNNING:
            return False

        if self._direction == 1:
            if self.current_job_index >= len(self.current_recipe.jobs):
                self._set_state(ExecutionState.COMPLETED)
                self._log("Recipe 실행 완료")
                return True
        else:
            if self.current_job_index < 0:
                self._set_state(ExecutionState.COMPLETED)
                self._log("역순 실행 완료")
                return True

        return self._execute_current_job()

    def _execute_current_job(self) -> bool:
        job = self.current_recipe.jobs[self.current_job_index]

        if self.on_job_started:
            self.on_job_started(self.current_job_index, job)

        try:
            success = self._execute_job(job)

            if self.on_job_completed:
                self.on_job_completed(self.current_job_index, job, success)

            if success:
                self._log(f"✓ Job 완료: {job.name}")
                self.current_job_index += self._direction

                if self.state == ExecutionState.RUNNING:
                    import time
                    time.sleep(0.1)
                    return self._execute_next_job()
            else:
                self._log(f"✗ Job 실패: {job.name}")
                self._set_state(ExecutionState.ERROR)
                return False

        except Exception as e:
            self._log(f"[ERROR] Job 실행 오류: {e}")
            import traceback
            self._log(f"[ERROR] Traceback: {traceback.format_exc()}")
            self._set_state(ExecutionState.ERROR)
            if self.on_job_completed:
                self.on_job_completed(self.current_job_index, job, False)
            return False

        return True


    def _create_transform_matrix(self, pose: Dict[str, float]) -> np.ndarray:
        x, y, z = pose['X'], pose['Y'], pose['Z']
        rx, ry, rz = pose['Rx'], pose['Ry'], pose['Rz']

        r = Rotation.from_euler('ZYX', [rz, ry, rx], degrees=True)
        R = r.as_matrix()

        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = [x, y, z]

        return T

    def _extract_pose(self, T: np.ndarray) -> Dict[str, float]:
        x, y, z = T[:3, 3]

        R = T[:3, :3]
        r = Rotation.from_matrix(R)
        rz, ry, rx = r.as_euler('ZYX', degrees=True)

        return {
            'X': float(x),
            'Y': float(y),
            'Z': float(z),
            'Rx': float(rx),
            'Ry': float(ry),
            'Rz': float(rz)
        }

    def _transform_relative_to_absolute(self, rel_pose: Dict[str, float]) -> Dict[str, float]:
        if self.tm_transform_matrix is None:
            return rel_pose

        T_rel = self._create_transform_matrix(rel_pose)
        T_abs = self.tm_transform_matrix @ T_rel
        return self._extract_pose(T_abs)


    def _convert_to_robot_positions(self, motion_type: str,
                                     x: float, y: float, z: float,
                                     rx: float, ry: float, rz: float) -> List[float]:
        if motion_type == 'joint':
            return [
                x * math.pi / 180.0,
                y * math.pi / 180.0,
                z * math.pi / 180.0,
                rx * math.pi / 180.0,
                ry * math.pi / 180.0,
                rz * math.pi / 180.0
            ]
        else:
            return [
                x / 1000.0,
                y / 1000.0,
                z / 1000.0,
                rx * math.pi / 180.0,
                ry * math.pi / 180.0,
                rz * math.pi / 180.0
            ]

    def _move_to_position(self, motion_type: str,
                          x: float, y: float, z: float,
                          rx: float, ry: float, rz: float,
                          velocity: float,
                          decomposed_tcp: bool = False) -> Tuple[bool, str]:
        if not self.ros_node:
            return False, "ROS2 노드가 없습니다"

        if decomposed_tcp:
            if motion_type == 'joint':
                self._log("[decomposed_tcp] joint 모드는 축 분해 불가 — 단일 PTP_J로 실행합니다")
            else:
                return self._move_to_position_decomposed(x, y, z, rx, ry, rz, velocity)

        from tm_msgs.srv import SetPositions

        positions = self._convert_to_robot_positions(motion_type, x, y, z, rx, ry, rz)

        if motion_type == 'joint':
            motion_mode = SetPositions.Request.PTP_J
        else:
            motion_mode = SetPositions.Request.PTP_T

        return self.ros_node._call_set_positions(
            motion_mode,
            positions,
            velocity=velocity,
            acc_time=0.2
        )

    def _build_decomposed_tcp_waypoints(self, current_pose: List[float],
                                        target: List[float]) -> Tuple[List[Tuple[str, List[float]]], str]:
        return build_decomposed_tcp_waypoints(current_pose, target)

    def _move_to_position_decomposed(self, x: float, y: float, z: float,
                                     rx: float, ry: float, rz: float,
                                     velocity: float) -> Tuple[bool, str]:
        if not self.ros_node.current_tcp_pose or len(self.ros_node.current_tcp_pose) < 6:
            return False, "현재 TCP 위치를 알 수 없어 축 분해 이동을 할 수 없습니다"

        waypoints, order_label = self._build_decomposed_tcp_waypoints(
            list(self.ros_node.current_tcp_pose[:6]), [x, y, z, rx, ry, rz]
        )

        if not waypoints:
            return True, "축 분해 이동: 이동량이 없어 현재 위치를 유지합니다"

        from tm_msgs.srv import SetPositions

        total = len(waypoints)
        self._log(f"[decomposed_tcp] {order_label} 순서로 {total}단계 직선(LINE_T) 분해 이동 "
                  f"({' → '.join(label for label, _ in waypoints)})")

        for step_no, (label, wp) in enumerate(waypoints, start=1):
            if self._stop_requested:
                return False, f"축 분해 이동 중단됨 ({step_no}/{total} {label} 실행 전)"

            self._log(f"  [{step_no}/{total}] {label}: X={wp[0]:.2f}, Y={wp[1]:.2f}, Z={wp[2]:.2f}, "
                      f"Rx={wp[3]:.2f}, Ry={wp[4]:.2f}, Rz={wp[5]:.2f}")

            positions = self._convert_to_robot_positions('tcp', wp[0], wp[1], wp[2], wp[3], wp[4], wp[5])
            success, msg = self.ros_node._call_set_positions(
                SetPositions.Request.LINE_T,
                positions,
                velocity=velocity,
                acc_time=0.2
            )

            if not success:
                return False, f"축 분해 이동 {step_no}/{total} {label} 실패: {msg}"

        return True, f"축 분해 이동 완료 ({order_label}, {total}단계)"

    def _move_to_position_line(self, motion_type: str,
                                x: float, y: float, z: float,
                                rx: float, ry: float, rz: float,
                                velocity: float) -> Tuple[bool, str]:
        if not self.ros_node:
            return False, "ROS2 노드가 없습니다"

        from tm_msgs.srv import SetPositions

        positions = self._convert_to_robot_positions('tcp', x, y, z, rx, ry, rz)

        return self.ros_node._call_set_positions(
            SetPositions.Request.LINE_T,
            positions,
            velocity=velocity,
            acc_time=0.2
        )

    def _execute_job(self, job: Job) -> bool:
        job_type = job.type

        macro_defs = RecipeManager.JOB_TYPES.get(job_type, {}).get('macros')
        if macro_defs:
            return self._run_macro_sequence(job, macro_defs)

        if job_type == 'recipe_info':
            self.recipe_mode = job.params.get('mode', 'execution')
            desc = job.params.get('description', '')
            mode_label = '티칭 (TCP 자세 유지)' if self.recipe_mode == 'teaching' else '실행'
            self._log(f"[Recipe 모드: {mode_label}] {desc}")
            return True
        elif job_type == 'go_home':
            return self._exec_go_home(job)
        elif job_type == 'move_to_point':
            return self._exec_move_to_point(job)
        elif job_type == 'move_linear':
            return self._exec_move_linear(job)
        elif job_type == 'line_move_to_point':
            return self._exec_line_move_to_point(job)
        elif job_type == 'pose_keep_move_to_point':
            return self._exec_pose_keep_move_to_point(job)
        elif job_type == 'move_to_ar_offset':
            return self._exec_move_to_ar_offset(job)
        elif job_type == 'scan_tm_landmark':
            return self._exec_scan_tm_landmark(job)
        elif job_type == 'find_landmark':
            return self._exec_find_landmark(job)
        elif job_type == 'scan_tm_landmark_jig':
            return self._exec_scan_tm_landmark_jig(job)
        elif job_type == 'scan_align_tm_landmark':
            return self._exec_scan_tm_landmark(job)
        elif job_type == 'scan_ar_tag':
            return self._exec_scan_ar_tag(job)
        elif job_type == 'wait_for_detection':
            return self._exec_wait_for_detection(job)
        elif job_type == 'save_landmark_pose':
            return self._exec_save_landmark_pose(job)
        elif job_type == 'move_to_landmark_pose':
            return self._exec_move_to_landmark_pose(job)
        elif job_type == 'move_to_jig_landmark':
            return self._exec_move_to_jig_landmark(job)
        elif job_type == 'calculate_plate_pose':
            return self._exec_calculate_plate_pose(job)
        elif job_type == 'load_plate_pose':
            return self._exec_load_plate_pose(job)
        elif job_type == 'align_to_plane_normal':
            return self._exec_align_to_plane_normal(job)
        elif job_type == 'move_to_plane_pose':
            return self._exec_move_to_plane_pose(job)
        elif job_type == 'save_pose':
            return self._exec_save_pose(job)
        elif job_type == 'move_to_saved_pose':
            return self._exec_move_to_saved_pose(job)
        elif job_type == 'move_to_named_position':
            return self._exec_move_to_named_position(job)
        elif job_type == 'measure_plane_distance':
            return self._exec_measure_plane_distance(job)
        elif job_type == 'generate_runtime':
            return self._exec_generate_runtime(job)
        elif job_type == 'vision_process':
            return self._exec_vision_process(job)
        elif job_type == 'gripper_open':
            return self._exec_gripper_open(job)
        elif job_type == 'gripper_close':
            return self._exec_gripper_close(job)
        elif job_type == 'gripper_home':
            return self._exec_gripper_home(job)
        elif job_type == 'schunk_grip':
            return self._exec_schunk_gripper(job, 1)
        elif job_type == 'schunk_release':
            return self._exec_schunk_gripper(job, 2)
        elif job_type == 'schunk_home':
            return self._exec_schunk_gripper(job, 3)
        elif job_type == 'read_distance':
            return self._exec_read_distance(job)
        elif job_type == 'smc_grip':
            return self._exec_smc_grip(job)
        elif job_type == 'smc_release':
            return self._exec_smc_release(job)
        elif job_type == 'smc_home':
            return self._exec_smc_home(job)
        elif job_type == 'check_magazine':
            return self._exec_check_magazine(job)
        elif job_type == 'read_digital_io':
            return self._exec_read_digital_io(job)
        elif job_type == 'write_digital_io':
            return self._exec_write_digital_io(job)
        elif job_type == 'read_analog_io':
            return self._exec_read_analog_io(job)
        elif job_type == 'align_to_ar_tag':
            return self._exec_align_to_ar_tag(job)
        elif job_type == 'move_to_ar_center':
            return self._exec_move_to_ar_center(job)
        elif job_type == 'align_tm_landmark':
            return self._exec_align_tm_landmark(job)
        elif job_type == 'sdc_tcp_base':
            return self._exec_sdc_tcp_base(job)
        elif job_type == 'sdc_palette_tcp_align':
            return self._exec_sdc_palette_tcp_align(job)
        elif job_type == 'measure_point':
            return self._exec_measure_point(job)
        elif job_type == 'ai_inspection':
            return self._exec_ai_inspection(job)
        else:
            self._log(f"알 수 없는 Job 타입: {job_type}")
            return False


    def _exec_go_home(self, job: Job) -> bool:
        params = job.params

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase가 아닙니다: {current_base}")
                self._log("[경고] go_home은 RobotBase 좌표계에서 실행해야 합니다!")
                return False

        motion_type = params.get('motion_type', 'tcp')
        x = params.get('X', 0.0)
        y = params.get('Y', -30.0)
        z = params.get('Z', 120.0)
        rx = params.get('Rx', 0.0)
        ry = params.get('Ry', 90.0)
        rz = params.get('Rz', 0.0)
        velocity = params.get('velocity', 20.0)
        decomposed_tcp = params.get('decomposed_tcp', False)

        success, msg = self._move_to_position(motion_type, x, y, z, rx, ry, rz, velocity,
                                              decomposed_tcp=decomposed_tcp)

        if success:
            self._log(msg)
        else:
            self._log(f"HOME 이동 실패: {msg}")

        return success

    def _exec_move_to_point(self, job: Job) -> bool:
        params = job.params

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase가 아닙니다: {current_base}")
                self._log("[경고] move_to_point는 RobotBase 좌표계에서 실행해야 합니다!")
                return False

        motion_type = params.get('motion_type', 'tcp')
        coordinate_mode = getattr(job, 'coordinate_mode', 'absolute')
        x = params.get('X', 0.0)
        y = params.get('Y', 0.0)
        z = params.get('Z', 0.0)
        rx = params.get('Rx', 0.0)
        ry = params.get('Ry', 0.0)
        rz = params.get('Rz', 0.0)
        velocity = params.get('velocity', 25.0)

        if coordinate_mode == 'relative':
            if self.tm_transform_matrix is None:
                self._log("[경고] TM Landmark 기준점이 없습니다. scan_tm_landmark를 먼저 실행하세요.")
                return False

            if self.recipe_mode == 'teaching':
                master_rx, master_ry, master_rz = rx, ry, rz
                rel_pose = {'X': x, 'Y': y, 'Z': z, 'Rx': 0.0, 'Ry': 0.0, 'Rz': 0.0}
                abs_pose = self._transform_relative_to_absolute(rel_pose)

                self._log(f"[좌표 변환-Teaching] 위치만 변환: ({x:.2f}, {y:.2f}, {z:.2f}) → "
                          f"({abs_pose['X']:.2f}, {abs_pose['Y']:.2f}, {abs_pose['Z']:.2f})")
                self._log(f"[좌표 변환-Teaching] TCP 자세 유지: Rx={master_rx:.2f}, Ry={master_ry:.2f}, Rz={master_rz:.2f}")

                x = abs_pose['X']
                y = abs_pose['Y']
                z = abs_pose['Z']
                rx = master_rx
                ry = master_ry
                rz = master_rz
            else:
                rel_pose = {'X': x, 'Y': y, 'Z': z, 'Rx': rx, 'Ry': ry, 'Rz': rz}
                abs_pose = self._transform_relative_to_absolute(rel_pose)

                self._log(f"[좌표 변환] 상대 → 절대: ({x:.2f}, {y:.2f}, {z:.2f}) → "
                          f"({abs_pose['X']:.2f}, {abs_pose['Y']:.2f}, {abs_pose['Z']:.2f})")

                x = abs_pose['X']
                y = abs_pose['Y']
                z = abs_pose['Z']
                rx = abs_pose['Rx']
                ry = abs_pose['Ry']
                rz = abs_pose['Rz']

        tcp_before = None
        if self.ros_node and self.ros_node.current_tcp_pose and len(self.ros_node.current_tcp_pose) >= 6:
            tcp_before = list(self.ros_node.current_tcp_pose[:6])

        decomposed_tcp = params.get('decomposed_tcp', False)

        success, msg = self._move_to_position(motion_type, x, y, z, rx, ry, rz, velocity,
                                              decomposed_tcp=decomposed_tcp)

        if success:
            self._log(msg)
            self._verify_move_position(job, x, y, z, rx, ry, rz, tcp_before)
        else:
            self._log(f"포인트 이동 실패: {msg}")

        return success

    def _verify_move_position(self, job, target_x, target_y, target_z, target_rx, target_ry, target_rz, tcp_before):
        if not self.ros_node or not self.ros_node.current_tcp_pose or len(self.ros_node.current_tcp_pose) < 6:
            return

        tcp_after = self.ros_node.current_tcp_pose[:6]
        actual_x, actual_y, actual_z = tcp_after[0], tcp_after[1], tcp_after[2]
        actual_rx, actual_ry, actual_rz = tcp_after[3], tcp_after[4], tcp_after[5]

        dx = abs(actual_x - target_x)
        dy = abs(actual_y - target_y)
        dz = abs(actual_z - target_z)
        max_pos_err = max(dx, dy, dz)

        caption = job.caption if job.caption else job.name

        if max_pos_err > 1.0:
            self._log(f"[검증] {caption}: 위치 오차 dX={dx:.2f} dY={dy:.2f} dZ={dz:.2f}mm (max={max_pos_err:.2f}mm)")
        else:
            self._log(f"[검증] {caption}: 위치 OK (오차 {max_pos_err:.2f}mm)")

    def _exec_move_linear(self, job: Job) -> bool:
        params = job.params if hasattr(job, 'params') else job
        offset_x = params.get('offset X', 0.0)
        offset_y = params.get('offset Y', 0.0)
        offset_z = params.get('offset Z', 0.0)
        velocity_mm_s = params.get('velocity', 50.0)

        if not self.ros_node:
            self._log("ROS2 노드가 없습니다")
            return False

        self._log(f"직선 이동(Move_Line): 오프셋({offset_x:.1f}, {offset_y:.1f}, {offset_z:.1f})mm, 속도 {velocity_mm_s:.1f} mm/s")

        from tm_msgs.srv import SendScript

        send_script_client = getattr(self.ros_node, 'send_script_client', None)
        if not send_script_client:
            self._log("send_script 클라이언트가 없습니다")
            return False

        if not send_script_client.wait_for_service(timeout_sec=1.0):
            self._log("send_script 서비스를 사용할 수 없습니다")
            return False

        vel = int(velocity_mm_s)
        script = f'Move_Line("TPP", {offset_x}, {offset_y}, {offset_z}, 0, 0, 0, {vel}, 200, 0, true)'

        gateway = getattr(self.ros_node, 'motion_gateway', None)
        if gateway is not None:
            decision = gateway.check(
                'line_relative', offset_mm=[offset_x, offset_y, offset_z], label='Move_Line')
            if not decision.allowed:
                self._log(f"[안전구역] 직선 이동 거부 — {decision.reason}")
                return False

        request = SendScript.Request()
        request.id = "gv"
        request.script = script

        self._log(f"Script: {script}")

        future = send_script_client.call_async(request)
        rclpy.spin_until_future_complete(self.ros_node, future, timeout_sec=10.0)

        if future.result() is None or not future.result().ok:
            self._log("직선 이동 실패: 스크립트 전송 실패")
            return False

        import time

        motion_service = self.ros_node.motion_service
        timeout = 30.0
        start_time = time.time()

        motion_started = False
        while time.time() - start_time < 2.0:
            rclpy.spin_once(self.ros_node, timeout_sec=0.1)
            if motion_service.is_moving:
                motion_started = True
                break
            time.sleep(0.05)

        if not motion_started:
            time.sleep(0.3)
            rclpy.spin_once(self.ros_node, timeout_sec=0.1)

        stable_count = 0
        stable_threshold = 5

        while time.time() - start_time < timeout:
            rclpy.spin_once(self.ros_node, timeout_sec=0.1)

            if not motion_service.is_moving:
                stable_count += 1
                if stable_count >= stable_threshold:
                    self._log("직선 이동 완료")
                    return True
            else:
                stable_count = 0

            time.sleep(0.05)

        self._log("직선 이동 실패: 이동 완료 확인 타임아웃")
        return False

    def _exec_line_move_to_point(self, job: Job) -> bool:
        params = job.params

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase가 아닙니다: {current_base}")
                return False

        coordinate_mode = getattr(job, 'coordinate_mode', 'absolute')
        x = params.get('X', 0.0)
        y = params.get('Y', 0.0)
        z = params.get('Z', 0.0)
        rx = params.get('Rx', 0.0)
        ry = params.get('Ry', 0.0)
        rz = params.get('Rz', 0.0)
        velocity = params.get('velocity', 25.0)

        if x == 0.0 and y == 0.0 and z == 0.0 and rx == 0.0 and ry == 0.0 and rz == 0.0:
            self._log("[경고] 기준 좌표가 모두 0입니다. '현재위치 입력' 버튼으로 기준위치를 설정해 주세요.")
            return False

        offset_x = params.get('offset X', 0.0)
        offset_y = params.get('offset Y', 0.0)
        offset_z = params.get('offset Z', 0.0)

        if coordinate_mode == 'relative':
            if self.tm_transform_matrix is None:
                self._log("[경고] TM Landmark 기준점이 없습니다. scan_tm_landmark를 먼저 실행하세요.")
                return False

            if self.recipe_mode == 'teaching':
                master_rx, master_ry, master_rz = rx, ry, rz
                rel_pose = {'X': x, 'Y': y, 'Z': z, 'Rx': 0.0, 'Ry': 0.0, 'Rz': 0.0}
                abs_pose = self._transform_relative_to_absolute(rel_pose)

                self._log(f"[좌표 변환-Teaching] 위치만 변환: ({x:.2f}, {y:.2f}, {z:.2f}) → "
                          f"({abs_pose['X']:.2f}, {abs_pose['Y']:.2f}, {abs_pose['Z']:.2f})")

                x = abs_pose['X']
                y = abs_pose['Y']
                z = abs_pose['Z']
                rx = master_rx
                ry = master_ry
                rz = master_rz
            else:
                rel_pose = {'X': x, 'Y': y, 'Z': z, 'Rx': rx, 'Ry': ry, 'Rz': rz}
                abs_pose = self._transform_relative_to_absolute(rel_pose)

                self._log(f"[좌표 변환] 상대 → 절대: ({x:.2f}, {y:.2f}, {z:.2f}) → "
                          f"({abs_pose['X']:.2f}, {abs_pose['Y']:.2f}, {abs_pose['Z']:.2f})")

                x = abs_pose['X']
                y = abs_pose['Y']
                z = abs_pose['Z']
                rx = abs_pose['Rx']
                ry = abs_pose['Ry']
                rz = abs_pose['Rz']

        x += offset_x
        y += offset_y
        z += offset_z

        if offset_x != 0.0 or offset_y != 0.0 or offset_z != 0.0:
            self._log(f"오프셋 적용: ({offset_x:+.2f}, {offset_y:+.2f}, {offset_z:+.2f})mm")

        self._log(f"직선 이동(LINE_T): ({x:.2f}, {y:.2f}, {z:.2f})mm, "
                  f"({rx:.2f}, {ry:.2f}, {rz:.2f})°, 속도 {velocity}%")

        tcp_before = None
        if self.ros_node and self.ros_node.current_tcp_pose and len(self.ros_node.current_tcp_pose) >= 6:
            tcp_before = list(self.ros_node.current_tcp_pose[:6])

        success, msg = self._move_to_position_line('tcp', x, y, z, rx, ry, rz, velocity)

        if success:
            self._log(msg)
            self._verify_move_position(job, x, y, z, rx, ry, rz, tcp_before)
        else:
            self._log(f"직선 이동 실패: {msg}")

        return success

    def _build_descent_segments(self, x: float, y: float, from_z: float, to_z: float,
                                velocity: float, decel_zone_mm: float,
                                decel_velocity: float) -> List[Tuple[str, float, float, float, float]]:
        if decel_zone_mm <= 0.0 or velocity <= decel_velocity:
            return [('Z 하강', x, y, to_z, velocity)]

        if abs(to_z - from_z) > decel_zone_mm + POSE_KEEP_DECEL_MARGIN_MM:
            return [
                ('Z 하강', x, y, to_z + decel_zone_mm, velocity),
                ('Z 하강(감속 진입)', x, y, to_z, decel_velocity),
            ]

        return [('Z 하강(저속)', x, y, to_z, decel_velocity)]

    def _build_straight_segments(self, cur_x: float, cur_y: float, cur_z: float,
                                 target_x: float, target_y: float, target_z: float,
                                 velocity: float, decel_zone_mm: float,
                                 decel_velocity: float
                                 ) -> List[Tuple[str, float, float, float, float]]:
        dz = target_z - cur_z
        descending = dz < 0.0
        damping_on = descending and decel_zone_mm > 0.0 and velocity > decel_velocity

        if damping_on and abs(dz) > decel_zone_mm + POSE_KEEP_DECEL_MARGIN_MM:
            ratio = (abs(dz) - decel_zone_mm) / abs(dz)
            return [
                ('직선 하강', cur_x + (target_x - cur_x) * ratio,
                 cur_y + (target_y - cur_y) * ratio, cur_z + dz * ratio, velocity),
                ('직선 하강(감속 진입)', target_x, target_y, target_z, decel_velocity),
            ]

        if damping_on:
            return [('직선 하강(저속)', target_x, target_y, target_z, decel_velocity)]

        label = '직선 하강' if descending else '직선 상승'
        return [(label, target_x, target_y, target_z, velocity)]

    def _build_pose_keep_segments(self, tcp_before: List[float],
                                  target_x: float, target_y: float, target_z: float,
                                  velocity: float, decel_zone_mm: float = 0.0,
                                  decel_velocity: float = POSE_KEEP_DECEL_VELOCITY,
                                  straight: bool = False
                                  ) -> List[Tuple[str, float, float, float, float]]:
        cur_x, cur_y, cur_z = tcp_before[0], tcp_before[1], tcp_before[2]
        dz = target_z - cur_z
        dxy = math.hypot(target_x - cur_x, target_y - cur_y)
        xy_moves = dxy >= POSE_KEEP_MIN_SEGMENT_MM

        segments: List[Tuple[str, float, float, float, float]] = []

        if straight:
            if math.hypot(dxy, dz) < POSE_KEEP_MIN_SEGMENT_MM:
                return segments
            return self._build_straight_segments(
                cur_x, cur_y, cur_z, target_x, target_y, target_z,
                velocity, decel_zone_mm, decel_velocity
            )

        if abs(dz) < POSE_KEEP_MIN_SEGMENT_MM:
            if xy_moves:
                segments.append(('XY 이동', target_x, target_y, target_z, velocity))
        elif dz > 0:
            segments.append(('Z 상승', cur_x, cur_y, target_z, velocity))
            if xy_moves:
                segments.append(('XY 이동', target_x, target_y, target_z, velocity))
        else:
            if xy_moves:
                segments.append(('XY 이동', target_x, target_y, cur_z, velocity))
            segments.extend(self._build_descent_segments(
                target_x, target_y, cur_z, target_z,
                velocity, decel_zone_mm, decel_velocity
            ))

        return segments

    def _log_orientation_deviation(self, label: str, lock_rx: float,
                                   lock_ry: float, lock_rz: float) -> Optional[float]:
        if not self.ros_node or not self.ros_node.current_tcp_pose \
                or len(self.ros_node.current_tcp_pose) < 6:
            self._log(f"[자세검증] {label}: TCP 포즈 미수신 — 편차 측정 불가")
            return None

        motion_service = getattr(self.ros_node, 'motion_service', None)
        angle_diff = getattr(motion_service, '_angle_difference_deg', None)
        if angle_diff is None:
            self._log(f"[자세검증] {label}: 각도 비교 기능 없음 — 편차 측정 불가")
            return None

        tcp_now = self.ros_node.current_tcp_pose[:6]
        d_rx = angle_diff(lock_rx, tcp_now[3])
        d_ry = angle_diff(lock_ry, tcp_now[4])
        d_rz = angle_diff(lock_rz, tcp_now[5])
        max_dev = max(d_rx, d_ry, d_rz)

        self._log(f"[자세검증] {label}: 종점 자세 편차 dRx={d_rx:.3f} dRy={d_ry:.3f} "
                  f"dRz={d_rz:.3f}° (max={max_dev:.3f}°)")
        return max_dev

    def _exec_pose_keep_move_to_point(self, job: Job) -> bool:
        params = job.params

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase가 아닙니다: {current_base}")
                self._log("[경고] pose_keep_move_to_point는 RobotBase 좌표계에서 실행해야 합니다!")
                return False

        x = params.get('X', 0.0)
        y = params.get('Y', 0.0)
        z = params.get('Z', 0.0)
        velocity = params.get('velocity', 10.0)
        decel_zone_mm = params.get('decel_zone_mm', POSE_KEEP_DECEL_ZONE_MM)
        decel_velocity = params.get('decel_velocity', POSE_KEEP_DECEL_VELOCITY)

        if x == 0.0 and y == 0.0 and z == 0.0:
            self._log("[경고] 목표 좌표가 모두 0입니다. '현재위치 입력' 버튼으로 목표위치를 설정해 주세요.")
            return False

        coordinate_mode = getattr(job, 'coordinate_mode', 'absolute')
        if coordinate_mode == 'relative':
            if self.tm_transform_matrix is None:
                self._log("[경고] TM Landmark 기준점이 없습니다. scan_tm_landmark를 먼저 실행하세요.")
                return False

            rel_pose = {'X': x, 'Y': y, 'Z': z, 'Rx': 0.0, 'Ry': 0.0, 'Rz': 0.0}
            abs_pose = self._transform_relative_to_absolute(rel_pose)
            self._log(f"[좌표 변환-자세유지] 위치만 변환: ({x:.2f}, {y:.2f}, {z:.2f}) → "
                      f"({abs_pose['X']:.2f}, {abs_pose['Y']:.2f}, {abs_pose['Z']:.2f})")
            x = abs_pose['X']
            y = abs_pose['Y']
            z = abs_pose['Z']

        offset_x = params.get('offset X', 0.0)
        offset_y = params.get('offset Y', 0.0)
        offset_z = params.get('offset Z', 0.0)
        x += offset_x
        y += offset_y
        z += offset_z

        if offset_x != 0.0 or offset_y != 0.0 or offset_z != 0.0:
            self._log(f"오프셋 적용: ({offset_x:+.2f}, {offset_y:+.2f}, {offset_z:+.2f})mm")

        if not self.ros_node or not self.ros_node.current_tcp_pose \
                or len(self.ros_node.current_tcp_pose) < 6:
            self._log("자세유지 이동 실패: 현재 TCP 위치를 읽을 수 없습니다 (로봇 상태 미수신)")
            return False

        tcp_before = list(self.ros_node.current_tcp_pose[:6])
        lock_rx, lock_ry, lock_rz = tcp_before[3], tcp_before[4], tcp_before[5]

        segments = self._build_pose_keep_segments(
            tcp_before, x, y, z, velocity, decel_zone_mm, decel_velocity
        )
        if not segments:
            self._log(f"자세유지 이동: 이동량이 {POSE_KEEP_MIN_SEGMENT_MM}mm 미만 — 이동 생략")
            return True

        decel_note = (f"하강 감속 {decel_zone_mm:.0f}mm@{decel_velocity:.0f}%"
                      if decel_zone_mm > 0 else "하강 감속 없음")
        self._log(f"자세유지 이동(LINE_T): 목표({x:.2f}, {y:.2f}, {z:.2f})mm, "
                  f"자세 고정(Rx={lock_rx:.2f}, Ry={lock_ry:.2f}, Rz={lock_rz:.2f})°, "
                  f"구간 {len(segments)}개, 속도 {velocity}%, {decel_note}")

        for idx, (label, seg_x, seg_y, seg_z, seg_vel) in enumerate(segments, start=1):
            self._log(f"[{idx}/{len(segments)}] {label} → "
                      f"({seg_x:.2f}, {seg_y:.2f}, {seg_z:.2f})mm, 속도 {seg_vel}%")

            success, msg = self._move_to_position_line(
                'tcp', seg_x, seg_y, seg_z, lock_rx, lock_ry, lock_rz, seg_vel
            )

            if not success:
                self._log(f"자세유지 이동 실패({label}): {msg}")
                self._log("[중단] 이후 구간을 실행하지 않습니다 (PTP 대체 없음 — 자세 보존 우선)")
                return False

            self._log(msg)
            self._log_orientation_deviation(f"{idx}/{len(segments)} {label}",
                                            lock_rx, lock_ry, lock_rz)

        self._verify_move_position(job, x, y, z, lock_rx, lock_ry, lock_rz, tcp_before)
        return True

    def _exec_move_to_ar_offset(self, job: Job) -> bool:
        params = job.params
        if self.detected_ar_pose is None:
            self._log("AR 태그 위치가 없습니다. scan_ar_tag를 먼저 실행하세요.")
            return False

        offset = params.get('offset', {'x': 0.0, 'y': 0.0, 'z': 0.0})
        velocity = params.get('velocity', 50.0)

        target_x = self.detected_ar_pose.get('x', 0) + offset.get('x', 0)
        target_y = self.detected_ar_pose.get('y', 0) + offset.get('y', 0)
        target_z = self.detected_ar_pose.get('z', 0) + offset.get('z', 0)

        self._log(f"Move to AR offset: target=({target_x}, {target_y}, {target_z}), vel={velocity}")
        return True

    def _exec_scan_ar_tag(self, job: Job) -> bool:
        params = job.params
        target_id = params.get('target_id', 0)
        timeout = params.get('timeout', 5.0)
        delay = params.get('delay', 0.5)

        self._log(f"Scanning AR tag ID={target_id}, timeout={timeout}s, delay={delay}s")

        start_time = time.time()
        target_id_str = str(target_id)

        while (time.time() - start_time) < timeout:
            tag_data = self.vision_manager.get_tag(target_id_str) if self.vision_manager else None
            if tag_data:
                self.detected_ar_pose = {
                    'x': tag_data['x'],
                    'y': tag_data['y'],
                    'z': tag_data['z'],
                    'pose': tag_data['pose']
                }
                self._log(f"AR tag {target_id} detected at ({tag_data['x']:.3f}, {tag_data['y']:.3f}, {tag_data['z']:.3f})")

                if not self.vision_manager.write_variable('g_robot_command', 2):
                    self._log("g_robot_command=2 설정 실패")
                    return False

                self._log(f"Delay {delay}s before ScriptExit()")
                time.sleep(delay)

                if not self.vision_manager.send_script_exit():
                    self._log("ScriptExit() 발행 실패")
                    return False

                self._log("scan_ar_tag 완료 - TM Flow 동작 시작")
                return True

            time.sleep(0.1)

        self._log(f"AR tag {target_id} not detected within {timeout}s timeout")
        return False

    def _exec_wait_for_detection(self, job: Job) -> bool:
        params = job.params
        target_id = params.get('target_id', 0)
        timeout = params.get('timeout', 10.0)

        self._log(f"Waiting for AR tag ID={target_id}, timeout={timeout}s")
        return True

    def _exec_gripper_open(self, job: Job) -> bool:
        params = job.params
        delay = params.get('delay', 0.5)

        self._log(f"Gripper open (g_robot_command=10), delay={delay}s")

        if not self.vision_manager:
            self._log("VisionManager가 초기화되지 않았습니다")
            return False

        if not self.vision_manager.write_variable('g_robot_command', 10):
            self._log("g_robot_command=10 설정 실패")
            return False

        time.sleep(delay)
        return True

    def _exec_gripper_close(self, job: Job) -> bool:
        params = job.params
        delay = params.get('delay', 0.5)

        self._log(f"Gripper close (g_robot_command=9), delay={delay}s")

        if not self.vision_manager:
            self._log("VisionManager가 초기화되지 않았습니다")
            return False

        if not self.vision_manager.write_variable('g_robot_command', 9):
            self._log("g_robot_command=9 설정 실패")
            return False

        time.sleep(delay)
        return True

    def _exec_gripper_home(self, job: Job) -> bool:
        params = job.params
        delay = params.get('delay', 0.5)

        self._log(f"Gripper home (g_robot_command=11), delay={delay}s")

        if not self.vision_manager:
            self._log("VisionManager가 초기화되지 않았습니다")
            return False

        if not self.vision_manager.write_variable('g_robot_command', 11):
            self._log("g_robot_command=11 설정 실패")
            return False

        time.sleep(delay)
        return True

    def _exec_smc_grip(self, job: Job) -> bool:
        return self._exec_smc_gripper(job, 'grip')

    def _exec_smc_release(self, job: Job) -> bool:
        return self._exec_smc_gripper(job, 'release')

    def _exec_smc_home(self, job: Job) -> bool:
        return self._exec_smc_gripper(job, 'home')

    def _exec_smc_gripper(self, job: Job, profile: str) -> bool:
        timeout = float(job.params.get('timeout', 30.0))

        if not self.ros_node:
            self._log("[SMC 그리퍼] ROS2 노드가 없습니다")
            return False

        client = getattr(self.ros_node, 'gripper_action_client', None)
        if client is None:
            self._log("[SMC 그리퍼] gripper 액션 클라이언트가 없습니다 (gripper_ros 미빌드/미소싱)")
            return False

        try:
            from gripper_ros.action import GripperCommand
        except ImportError:
            self._log("[SMC 그리퍼] gripper_ros.action.GripperCommand import 실패")
            return False

        if not client.wait_for_server(timeout_sec=3.0):
            self._log("[SMC 그리퍼] gripper_node 액션 서버 없음 (미기동/미활성)")
            return False

        goal = GripperCommand.Goal()
        goal.command = GripperCommand.Goal.COMMAND_PROFILE
        goal.profile = profile
        goal.step = 0
        goal.bypass_interlock = bool(job.params.get('bypass_interlock', False))

        self._log(f"[SMC 그리퍼] {profile} 명령 전송")
        send_future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.ros_node, send_future, timeout_sec=5.0)
        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            self._log(f"[SMC 그리퍼] {profile} goal 거부됨 (인터록/상태 미충족)")
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self.ros_node, result_future, timeout_sec=timeout)
        if not result_future.done():
            self._log(f"[SMC 그리퍼] {profile} 결과 타임아웃 ({timeout}s)")
            return False

        result = result_future.result().result
        if result.result_code == 0:
            self._log(f"[SMC 그리퍼] {profile} 완료 (result_code=0)")
            return True

        if bool(job.params.get('verify_skip', False)) and result.result_code == 10:
            self._log(f"[SMC 그리퍼] {profile} verify_skip — INP 미도달(허공 파지)을 성공 처리 (result_code=10)")
            return True

        self._log(f"[SMC 그리퍼] {profile} 실패 result_code={result.result_code} msg={result.message}")
        return False

    def _exec_schunk_gripper(self, job: Job, command: int) -> bool:
        timeout = float(job.params.get('timeout', 15.0))
        names = {1: 'grip', 2: 'release', 3: 'home'}
        label = names.get(command, str(command))

        if not self.ros_node:
            self._log("[SCHUNK 그리퍼] ROS2 노드가 없습니다")
            return False
        client = getattr(self.ros_node, 'schunk_gripper_client', None)
        if client is None:
            self._log("[SCHUNK 그리퍼] gripper_command 클라이언트가 없습니다 (tc_msgs 미소싱)")
            return False
        try:
            from tc_msgs.srv import GripperCommand
        except ImportError:
            self._log("[SCHUNK 그리퍼] tc_msgs.srv.GripperCommand import 실패")
            return False
        if not client.wait_for_service(timeout_sec=3.0):
            self._log("[SCHUNK 그리퍼] /gripper_command 서비스 없음 (tc_end_effector 미기동)")
            return False

        req = GripperCommand.Request()
        req.command = int(command)
        self._log(f"[SCHUNK 그리퍼] {label}(command={command}) 전송")
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self.ros_node, future, timeout_sec=timeout)
        if not future.done():
            self._log(f"[SCHUNK 그리퍼] {label} 응답 타임아웃")
            return False
        res = future.result()
        if res is not None and getattr(res, 'received', False):
            self._log(f"[SCHUNK 그리퍼] {label} 수신 확인(received=True)")
            return True
        self._log(f"[SCHUNK 그리퍼] {label} 실패(received=False/None)")
        return False

    def _exec_read_distance(self, job: Job) -> bool:
        timeout = float(job.params.get('timeout', 5.0))
        command = int(job.params.get('command', 0))

        if not self.ros_node:
            self._log("[거리센서] ROS2 노드가 없습니다")
            return False
        client = getattr(self.ros_node, 'distance_client', None)
        if client is None:
            self._log("[거리센서] distance_command 클라이언트가 없습니다 (tc_msgs 미소싱)")
            return False
        try:
            from tc_msgs.srv import DistanceCommand
        except ImportError:
            self._log("[거리센서] tc_msgs.srv.DistanceCommand import 실패")
            return False
        if not client.wait_for_service(timeout_sec=3.0):
            self._log("[거리센서] /distance_command 서비스 없음")
            return False

        req = DistanceCommand.Request()
        req.command = command
        future = client.call_async(req)
        rclpy.spin_until_future_complete(self.ros_node, future, timeout_sec=timeout)
        if not future.done():
            self._log("[거리센서] 응답 타임아웃")
            return False
        res = future.result()
        if res is None:
            self._log("[거리센서] 응답 없음")
            return False
        self._log(f"[거리센서] detected={res.detected} sensor1={res.distance_sensor_one:.3f} "
                  f"sensor2={res.distance_sensor_two:.3f}")
        return True

    def _exec_read_digital_io(self, job: Job) -> bool:
        params = job.params
        di_name = params.get('di_name', 'Ctrl_DI0')

        self._log(f"[DI READ] {di_name} 읽기 시작")

        if not self.vision_manager or not self.vision_manager.gv_manager:
            self._log("[DI READ] GlobalVariable Manager가 없습니다")
            return False

        success, value = self.vision_manager.gv_manager.read_variable(di_name)
        if success:
            self._log(f"[DI READ] {di_name} = {value}")
            return True
        else:
            self._log(f"[DI READ] {di_name} 읽기 실패: {value}")
            return False

    def _exec_check_magazine(self, job: Job) -> bool:
        params = job.params
        try:
            slot = int(params.get('slot', 0))
        except (TypeError, ValueError):
            self._log(f"[매거진] slot 값이 숫자가 아닙니다: {params.get('slot')!r}")
            return False
        expect_present = str(params.get('expect', 'present')).lower() != 'empty'
        try:
            timeout = float(params.get('timeout', 3.0))
        except (TypeError, ValueError):
            timeout = 3.0

        service = getattr(self.ros_node, 'magazine_state_service', None)
        if service is None or not getattr(service, 'available', False):
            self._log("[매거진] magazine_detect 미소싱 — 재고를 확인할 수 없습니다")
            return False
        if not 0 <= slot < service.SLOT_COUNT:
            self._log(f"[매거진] 슬롯 번호가 범위 밖입니다: {slot} (0~{service.SLOT_COUNT - 1})")
            return False

        deadline = time.time() + timeout
        while service.slot_present(slot) is None and time.time() < deadline:
            time.sleep(0.05)

        actual = service.slot_present(slot)
        name = service.slot_name(slot)
        if actual is None:
            self._log(f"[매거진] 슬롯 {slot}({name}) 판정 불가 — io_resp 미수신/끊김 ({timeout}s 대기)")
            return False

        want = "매거진 있음" if expect_present else "비어 있음"
        got = "매거진 있음" if actual else "비어 있음"
        if actual == expect_present:
            self._log(f"[매거진] 슬롯 {slot}({name}) {got} — 기대와 일치")
            return True

        self._log(f"[매거진] 슬롯 {slot}({name}) {got} — 기대는 {want} 입니다")
        return self._handle_magazine_mismatch(params)

    def _handle_magazine_mismatch(self, params: Dict[str, Any]) -> bool:
        mode = str(params.get('on_mismatch', 'stop')).lower()

        if mode == 'ignore':
            self._log("[매거진] on_mismatch=ignore — 무시하고 그대로 진행합니다")
            return True

        if mode != 'skip':
            if mode != 'stop':
                self._log(f"[매거진] on_mismatch 값을 알 수 없습니다({mode!r}) — stop 으로 처리합니다")
            self._log("[매거진] on_mismatch=stop — 레시피를 정지합니다")
            return False

        try:
            skip_count = int(params.get('skip_count', 0))
        except (TypeError, ValueError):
            self._log(f"[매거진] skip_count 가 숫자가 아닙니다({params.get('skip_count')!r}) — 정지합니다")
            return False

        if skip_count < 0:
            self._log(f"[매거진] skip_count 가 음수입니다({skip_count}) — 정지합니다")
            return False

        if getattr(self, '_direction', 1) != 1:
            self._log("[매거진] 역순 실행 중에는 skip 을 적용하지 않습니다 — 정지합니다")
            return False

        if skip_count == 0:
            self._log("[매거진] on_mismatch=skip 이지만 skip_count=0 — 건너뛸 잡이 없어 그대로 진행합니다")
            return True

        total = len(self.current_recipe.jobs) if self.current_recipe else 0
        target = self.current_job_index + skip_count
        if total and target >= total:
            self._log(f"[매거진] on_mismatch=skip — 남은 잡({total - self.current_job_index - 1}개)이 "
                      f"skip_count({skip_count})보다 적어 레시피 끝으로 이동합니다")
            self.current_job_index = total - 1
            return True

        self.current_job_index = target
        self._log(f"[매거진] on_mismatch=skip — 다음 {skip_count}개 잡을 건너뜁니다 "
                  f"(다음 실행: index {target + 1})")
        return True

    def _exec_write_digital_io(self, job: Job) -> bool:
        params = job.params
        do_name = params.get('do_name', 'Ctrl_DO0')
        state_str = params.get('state', 'ON')

        self._log(f"[DO WRITE] {do_name} = {state_str}")

        if not self.ros_node:
            self._log("[DO WRITE] ROS2 노드가 없습니다")
            return False

        set_io_client = getattr(self.ros_node, 'set_io_client', None)
        if not set_io_client:
            self._log("[DO WRITE] set_io 클라이언트가 없습니다")
            return False

        if not set_io_client.wait_for_service(timeout_sec=2.0):
            self._log("[DO WRITE] set_io 서비스를 사용할 수 없습니다")
            return False

        from tm_msgs.srv import SetIO

        if do_name.startswith('Ctrl_DO'):
            module = 0
            pin = int(do_name.replace('Ctrl_DO', ''))
        elif do_name.startswith('End_DO'):
            module = 1
            pin = int(do_name.replace('End_DO', ''))
        else:
            self._log(f"[DO WRITE] 알 수 없는 DO 이름: {do_name}")
            return False

        state = 1.0 if state_str == 'ON' else 0.0

        request = SetIO.Request()
        request.module = module
        request.type = 1
        request.pin = pin
        request.state = state

        self._log(f"[DO WRITE] module={module}, type=1(DO), pin={pin}, state={state}")

        future = set_io_client.call_async(request)
        rclpy.spin_until_future_complete(self.ros_node, future, timeout_sec=5.0)

        if not future.done():
            self._log("[DO WRITE] 서비스 호출 타임아웃")
            return False

        if future.result() is not None and future.result().ok:
            self._log(f"[DO WRITE] {do_name} = {state_str} 설정 완료")
            return True
        else:
            self._log(f"[DO WRITE] {do_name} 설정 실패")
            return False

    def _exec_read_analog_io(self, job: Job) -> bool:
        params = job.params
        ai_name = params.get('ai_name', 'Ctrl_AI0')

        self._log(f"[AI READ] {ai_name} 읽기 시작")

        io_service = getattr(self.ros_node, 'io_control_service', None)
        if io_service:
            success, value, msg = io_service.read_analog_input(ai_name)
            if success:
                self._log(f"[AI READ] {msg}")
                return True
            else:
                self._log(f"[AI READ] 실패: {msg}")
                return False

        if not self.vision_manager or not self.vision_manager.gv_manager:
            self._log("[AI READ] IOControlService 및 GlobalVariable Manager가 없습니다")
            return False

        success, value = self.vision_manager.gv_manager.read_variable(ai_name)
        if success:
            self._log(f"[AI READ] {ai_name} = {value}")
            return True
        else:
            self._log(f"[AI READ] {ai_name} 읽기 실패: {value}")
            return False

    def _exec_align_to_ar_tag(self, job: Job) -> bool:
        params = job.params
        if self.detected_ar_pose is None:
            self._log("AR 태그 위치가 없습니다. scan_ar_tag를 먼저 실행하세요.")
            return False

        target_id = params.get('target_id', 0)
        approach_distance = params.get('approach_distance', 100.0)
        velocity = params.get('velocity', 30.0)
        align_axis = params.get('align_axis', 'z')

        ar_x = self.detected_ar_pose.get('x', 0)
        ar_y = self.detected_ar_pose.get('y', 0)
        ar_z = self.detected_ar_pose.get('z', 0)

        ar_rx = self.detected_ar_pose.get('rx', 0)
        ar_ry = self.detected_ar_pose.get('ry', 0)
        ar_rz = self.detected_ar_pose.get('rz', 0)


        target_x = ar_x
        target_y = ar_y
        target_z = ar_z + approach_distance

        target_rx = 180.0 + ar_rx
        target_ry = ar_ry
        target_rz = ar_rz

        self._log(f"AR 태그 정렬: 위치=({target_x:.1f}, {target_y:.1f}, {target_z:.1f}), "
                  f"자세=({target_rx:.1f}, {target_ry:.1f}, {target_rz:.1f}), vel={velocity}")

        if self.ros_node:
            pass

        return True

    def _exec_move_to_ar_center(self, job: Job) -> bool:
        params = job.params
        if self.detected_ar_pose is None:
            self._log("AR 태그 위치가 없습니다. scan_ar_tag를 먼저 실행하세요.")
            return False

        z_offset = params.get('z_offset', 0.0)
        velocity = params.get('velocity', 20.0)

        ar_x = self.detected_ar_pose.get('x', 0)
        ar_y = self.detected_ar_pose.get('y', 0)
        ar_z = self.detected_ar_pose.get('z', 0)

        target_x = ar_x
        target_y = ar_y
        target_z = ar_z + z_offset

        self._log(f"AR 태그 중심 이동: ({target_x:.1f}, {target_y:.1f}, {target_z:.1f}), vel={velocity}")

        if self.ros_node:
            pass

        return True

    def _exec_align_tm_landmark(self, job: Job) -> bool:
        params = job.params
        if self.detected_landmark_pose is None:
            self._log("Landmark 위치가 없습니다. scan_tm_landmark를 먼저 실행하세요.")
            return False

        if not self.ros_node:
            self._log("ROS2 노드가 없습니다")
            return False

        if not self.ros_node.current_tcp_pose or len(self.ros_node.current_tcp_pose) < 6:
            self._log("현재 TCP 위치를 알 수 없습니다")
            return False

        velocity = params.get('velocity', 10.0)
        wait_time = params.get('wait_after_command', 0.5)

        current_x = self.ros_node.current_tcp_pose[0]
        current_y = self.ros_node.current_tcp_pose[1]
        current_z = self.ros_node.current_tcp_pose[2]

        landmark_rx = self.detected_landmark_pose.get('rx', 0)
        landmark_ry = self.detected_landmark_pose.get('ry', 0)
        landmark_rz = self.detected_landmark_pose.get('rz', 0)

        self._log(f"TM Landmark 정렬:")
        self._log(f"  현재 위치: X={current_x:.2f}, Y={current_y:.2f}, Z={current_z:.2f}")
        self._log(f"  목표 자세: Rx={landmark_rx:.2f}, Ry={landmark_ry:.2f}, Rz={landmark_rz:.2f}")

        from tm_msgs.srv import SetPositions

        gateway = getattr(self.ros_node, 'motion_gateway', None)
        if gateway is not None:
            decision = gateway.check('ptp_tcp', label='align_tm_landmark')
            if not decision.allowed:
                self._log(f"[안전구역] Landmark 정렬 거부 — {decision.reason}")
                return False

        client = self.ros_node.create_client(SetPositions, 'set_positions')
        if not client.wait_for_service(timeout_sec=2.0):
            self._log("set_positions 서비스를 찾을 수 없습니다")
            return False

        request = SetPositions.Request()
        request.motion_type = 2
        request.positions = [current_x, current_y, current_z, landmark_rx, landmark_ry, landmark_rz]
        from .services.coordinate_transformer import CoordinateTransformer
        request.velocity = CoordinateTransformer.velocity_percent_to_service(2, velocity)
        request.acc_time = 0.2
        request.blend_percentage = 0
        request.fine_goal = True

        future = client.call_async(request)

        timeout = 10.0
        start_time = time.time()
        while not future.done():
            if time.time() - start_time > timeout:
                self._log("set_positions 서비스 타임아웃")
                return False
            time.sleep(0.1)

        result = future.result()
        if not result.ok:
            self._log(f"set_positions 실패")
            return False

        self._log(f"대기 중 ({wait_time}초)...")
        time.sleep(wait_time)
        self._log("align_tm_landmark 완료")
        return True

    def _exec_sdc_tcp_base(self, job: Job) -> bool:
        from .services.config_manager import ConfigManager

        params = job.params
        velocity = params.get('velocity', 10.0)
        wait_time = params.get('wait_after_command', 0.5)

        entry = ConfigManager().get_position('sdc_tcp_base')
        if not entry:
            self._log("[오류] positions.yaml 에 sdc_tcp_base 자세가 없습니다")
            return False

        values = list(entry.get('values') or [])
        if len(values) != 3:
            self._log(f"[오류] sdc_tcp_base 의 values 는 rx,ry,rz 3개여야 합니다: {values}")
            return False

        target_rx, target_ry, target_rz = (float(v) for v in values)

        if not self.ros_node:
            self._log("ROS2 노드가 없습니다")
            return False

        if not self.ros_node.current_tcp_pose or len(self.ros_node.current_tcp_pose) < 6:
            self._log("현재 TCP 위치를 알 수 없습니다")
            return False

        current_x, current_y, current_z = self.ros_node.current_tcp_pose[:3]

        self._log("sdc_tcp_base 위치: 위치 유지, 자세만 변경")
        self._log(f"  현재 위치: X={current_x:.2f}, Y={current_y:.2f}, Z={current_z:.2f}")
        self._log(f"  목표 자세: Rx={target_rx:.2f}, Ry={target_ry:.2f}, Rz={target_rz:.2f}")

        success, msg = self._move_to_position_line(
            'tcp', current_x, current_y, current_z,
            target_rx, target_ry, target_rz, velocity)
        if not success:
            self._log(f"sdc_tcp_base 실패: {msg}")
            return False

        self._log(msg)
        if wait_time > 0:
            time.sleep(wait_time)
        self._log("sdc_tcp_base 완료")
        return True

    def _exec_sdc_palette_tcp_align(self, job: Job) -> bool:
        from .services.config_manager import ConfigManager

        params = job.params
        velocity = params.get('velocity', 10.0)
        wait_time = params.get('wait_after_command', 0.5)

        if self.detected_landmark_pose is None:
            self._log("Landmark 위치가 없습니다. scan_tm_landmark를 먼저 실행하세요.")
            return False

        entry = ConfigManager().get_position('sdc_palette_tcp_align')
        if not entry:
            self._log("[오류] positions.yaml 에 sdc_palette_tcp_align 항목이 없습니다")
            return False

        offsets = list(entry.get('values') or [])
        if len(offsets) != 3:
            self._log(f"[오류] sdc_palette_tcp_align 의 values 는 rx,ry,rz offset 3개여야 합니다: {offsets}")
            return False

        marker_rx = float(self.detected_landmark_pose.get('rx', 0))
        marker_ry = float(self.detected_landmark_pose.get('ry', 0))
        marker_rz = float(self.detected_landmark_pose.get('rz', 0))

        # 마커와 수직: 근사식(-rx,+ry,-rz + offset) 자세의 Z축을 마커 법선에
        # 정확히 일치시키는 최소 회전을 합성(스냅) — 법선 주위 회전(카메라
        # 보상 ry offset 포함)은 유지된다. 오일러 성분 근사만으로는 마커가
        # 축에서 벗어난 만큼(예: rx -87.9) 법선 오차로 새어 지그 진입 공차
        # (~0.4°)를 초과한다.
        R_marker = Rotation.from_euler(
            'ZYX', [marker_rz, marker_ry, marker_rx], degrees=True).as_matrix()
        R_approx = Rotation.from_euler(
            'ZYX', [-marker_rz + float(offsets[2]),
                    marker_ry + float(offsets[1]),
                    -marker_rx + float(offsets[0])], degrees=True).as_matrix()
        z_marker = R_marker[:, 2]
        z_approx = R_approx[:, 2]
        axis = np.cross(z_approx, z_marker)
        sin_a = float(np.linalg.norm(axis))
        cos_a = float(np.dot(z_approx, z_marker))
        if sin_a > 1e-12:
            snap = Rotation.from_rotvec(
                axis / sin_a * math.atan2(sin_a, cos_a)).as_matrix()
        else:
            snap = np.eye(3)
        rz_t, ry_t, rx_t = Rotation.from_matrix(
            snap @ R_approx).as_euler('ZYX', degrees=True)
        target_rx, target_ry, target_rz = float(rx_t), float(ry_t), float(rz_t)

        if not self.ros_node:
            self._log("ROS2 노드가 없습니다")
            return False

        if not self.ros_node.current_tcp_pose or len(self.ros_node.current_tcp_pose) < 6:
            self._log("현재 TCP 위치를 알 수 없습니다")
            return False

        current_x, current_y, current_z = self.ros_node.current_tcp_pose[:3]

        self._log("sdc_palette_tcp_align: 위치 유지, 자세를 마커 수직으로")
        self._log(f"  마커 자세: Rx={marker_rx:.2f}, Ry={marker_ry:.2f}, Rz={marker_rz:.2f}")
        self._log(f"  목표 자세: Rx={target_rx:.2f}, Ry={target_ry:.2f}, Rz={target_rz:.2f}")

        success, msg = self._move_to_position_line(
            'tcp', current_x, current_y, current_z,
            target_rx, target_ry, target_rz, velocity)
        if not success:
            self._log(f"sdc_palette_tcp_align 실패: {msg}")
            return False

        self._log(msg)
        if wait_time > 0:
            time.sleep(wait_time)
        self._log("sdc_palette_tcp_align 완료")
        return True

    def _exec_find_landmark(self, job: Job) -> bool:
        params = job.params
        grid_step = params.get('grid_step', 30.0)
        grid_size = params.get('grid_size', 3)
        scan_timeout_ms = params.get('scan_timeout', 500)
        scan_timeout = scan_timeout_ms / 1000.0
        velocity = params.get('velocity', 30.0)
        on_found = params.get('on_found', 'store_position')
        on_not_found = params.get('on_not_found', 'abort')

        if not self.vision_manager:
            self._log("VisionManager가 없습니다")
            return False

        if not self.ros_node:
            self._log("ROS2 노드가 없습니다")
            return False

        if not self.ros_node.current_tcp_pose or len(self.ros_node.current_tcp_pose) < 6:
            self._log("현재 TCP 위치를 알 수 없습니다")
            return False

        base_x = self.ros_node.current_tcp_pose[0]
        base_y = self.ros_node.current_tcp_pose[1]
        base_z = self.ros_node.current_tcp_pose[2]
        base_rx = self.ros_node.current_tcp_pose[3]
        base_ry = self.ros_node.current_tcp_pose[4]
        base_rz = self.ros_node.current_tcp_pose[5]

        self._log(f"Landmark 검색 시작: 기준점=({base_x:.1f}, {base_y:.1f}, {base_z:.1f}), "
                  f"격자={grid_size}x{grid_size}, 간격={grid_step}mm")

        if grid_size == 3:
            GRID_ORDER = [
                (0, 0),
                (0, 1),
                (-1, 0),
                (1, 0),
                (0, -1),
                (-1, 1),
                (1, 1),
                (-1, -1),
                (1, -1),
            ]
        elif grid_size == 5:
            GRID_ORDER = [
                (0, 0),
                (0, 1), (-1, 0), (1, 0), (0, -1),
                (-1, 1), (1, 1), (-1, -1), (1, -1),
                (0, 2), (-2, 0), (2, 0), (0, -2),
                (-1, 2), (1, 2), (-2, 1), (2, 1),
                (-2, -1), (2, -1), (-1, -2), (1, -2),
                (-2, 2), (2, 2), (-2, -2), (2, -2),
            ]
        else:
            GRID_ORDER = [(0, 0)]

        found = False
        found_position = None

        for idx, (dx, dy) in enumerate(GRID_ORDER):
            target_x = base_x + dx * grid_step
            target_y = base_y + dy * grid_step

            grid_num = idx + 1
            self._log(f"[{grid_num}/{len(GRID_ORDER)}] 위치 탐색: ({target_x:.1f}, {target_y:.1f}, {base_z:.1f})")

            if idx > 0:
                success, msg = self._move_to_position(
                    'tcp', target_x, target_y, base_z,
                    base_rx, base_ry, base_rz, velocity
                )
                if not success:
                    self._log(f"이동 실패: {msg}")
                    continue

                time.sleep(0.2)

            scan_success, scan_msg = self.vision_manager.execute_tm_landmark_scan(
                scan_timeout, pause_ethernet=False
            )

            if scan_success:
                read_success, result = self.vision_manager.execute_tm_landmark_read()
                if read_success and isinstance(result, dict) and result.get('detected', False):
                    found = True
                    found_position = {
                        'search_x': target_x,
                        'search_y': target_y,
                        'search_z': base_z,
                        'landmark': result
                    }
                    self._log(f"✓ Landmark 발견! 위치 ({grid_num}): "
                              f"X={result['x']:.2f}, Y={result['y']:.2f}, Z={result['z']:.2f}")
                    break

            self._log(f"  위치 ({grid_num}): 미검출")

        if found:
            self.detected_landmark_pose = found_position['landmark']

            if on_found == 'move_and_scan':
                lm = found_position['landmark']
                self._log(f"Landmark 위치로 이동 후 정밀 스캔...")

                success, msg = self._move_to_position(
                    'tcp', lm['x'], lm['y'], base_z,
                    base_rx, base_ry, base_rz, velocity
                )
                if success:
                    time.sleep(0.3)
                    scan_success, scan_msg = self.vision_manager.execute_tm_landmark_scan(
                        scan_timeout, pause_ethernet=False
                    )
                    if scan_success:
                        read_success, result = self.vision_manager.execute_tm_landmark_read()
                        if read_success and isinstance(result, dict):
                            self.detected_landmark_pose = result
                            self._log(f"정밀 스캔 완료: X={result['x']:.2f}, Y={result['y']:.2f}, Z={result['z']:.2f}")

            self._log(f"find_landmark 완료 - Landmark 발견됨")
            return True
        else:
            self._log(f"✗ 모든 위치 탐색 완료 - Landmark 미발견")

            self._log("원위치로 복귀 중...")
            self._move_to_position('tcp', base_x, base_y, base_z,
                                   base_rx, base_ry, base_rz, velocity)

            if on_not_found == 'abort':
                self._log("find_landmark 실패 - 작업 중단")
                return False
            elif on_not_found == 'continue':
                self._log("find_landmark 실패 - 다음 작업 계속")
                return True
            else:
                self._log("find_landmark 실패 - 사용자 확인 필요")
                return False

    def scan_landmark_averaged(self, repeat_count: int, outlier_method: str, wait_time: float,
                                jig_number: Optional[int] = None,
                                analysis_target: str = 'xyz') -> Tuple[Optional[Dict[str, float]],
                                                                       Optional[Dict[str, Any]]]:
        analyzer = LandmarkAnalyzer()
        label = "TM Landmark" if jig_number is None else f"Jig{jig_number}"

        self._log(f"{label} 스캔 시작 (반복: {repeat_count}회, outlier: {outlier_method}, target: {analysis_target})")

        for i in range(repeat_count):
            if repeat_count > 1:
                self._log(f"{label} 스캔 [{i+1}/{repeat_count}]")

            if jig_number is None:
                success, msg = self.vision_manager.execute_tm_landmark_scan(wait_time, pause_ethernet=False)
            else:
                success, msg = self.vision_manager.execute_tm_landmark_jig_scan(
                    jig_number, wait_time, pause_ethernet=False
                )
            self._log(msg)

            if not success:
                self._log(f"스캔 실패 ({i+1}회차)")
                continue

            if jig_number is None:
                read_success, result = self.vision_manager.execute_tm_landmark_read()
            else:
                read_success, result = self.vision_manager.execute_tm_landmark_jig_read(jig_number)

            if not read_success:
                self._log(f"측정 {i+1}: 변수 읽기 실패 — {result}")
            elif not isinstance(result, dict):
                self._log(f"측정 {i+1}: 결과 형식 오류 — {result}")
            elif not result.get('detected', False):
                detect_var = ('g_tm_landmark_detect' if jig_number is None
                              else f'g_jig_landmark{jig_number}_detect')
                self._log(f"측정 {i+1}: 미검출 ({detect_var} 가 true/=1 아님) — "
                          f"읽힌 좌표 X={result['x']:.3f}, Y={result['y']:.3f}, "
                          f"Z={result['z']:.3f}, Rz={result['rz']:.3f}")
            else:
                analyzer.add_measurement(
                    result['x'], result['y'], result['z'],
                    result['rx'], result['ry'], result['rz']
                )
                self._log(f"측정 {i+1}: X={result['x']:.3f}, Y={result['y']:.3f}, Z={result['z']:.3f}")

        if len(analyzer.measurements) == 0:
            self._log(f"[오류] 유효한 측정값 없음 - 최소 1회 이상 성공 필요")
            return None, None

        analysis = analyzer.analyze(method=outlier_method, target=analysis_target)
        self._log(f"분석 완료: 원본 {analysis['count_original']}개, outlier 제거 후 {analysis['count_after_outlier']}개")

        final_pose = analyzer.get_final_pose(method=outlier_method, target=analysis_target)
        self._log(f"표준편차: X={analysis['std']['x']:.4f}, Y={analysis['std']['y']:.4f}, Z={analysis['std']['z']:.4f}")

        return final_pose, analysis

    def _exec_scan_tm_landmark(self, job: Job) -> bool:
        params = job.params
        wait_time_ms = params.get('wait_after_command', 100)
        wait_time = wait_time_ms / 1000.0
        repeat_count = params.get('repeat_count', 1)
        outlier_method = params.get('outlier_method', 'none')
        analysis_target = params.get('analysis_target', 'xyz')

        if not self.vision_manager:
            self._log("VisionManager가 없습니다")
            return False

        final_pose, analysis = self.scan_landmark_averaged(
            repeat_count, outlier_method, wait_time, analysis_target=analysis_target
        )
        if final_pose is None:
            return False

        self.detected_landmark_pose = final_pose

        self.tm_landmark_pose = self.detected_landmark_pose.copy()
        pose_upper = {
            'X': self.detected_landmark_pose['x'],
            'Y': self.detected_landmark_pose['y'],
            'Z': self.detected_landmark_pose['z'],
            'Rx': self.detected_landmark_pose['rx'],
            'Ry': self.detected_landmark_pose['ry'],
            'Rz': self.detected_landmark_pose['rz']
        }
        self.tm_transform_matrix = self._create_transform_matrix(pose_upper)

        self._log(f"TM Landmark 최종 좌표: X={final_pose['x']:.3f}, Y={final_pose['y']:.3f}, Z={final_pose['z']:.3f}")
        self._log(f"scan_tm_landmark 완료 ({analysis['count_after_outlier']}개 유효 측정)")

        if self.coordinate_system_manager:
            try:
                self.coordinate_system_manager.set_single_landmark_scan(
                    'jig_landmark', final_pose, final_pose
                )
                self._log(f"jig_landmark 좌표계 자동 저장 완료")
            except Exception as e:
                self._log(f"jig_landmark 좌표계 저장 실패: {e}")

        return True

    def _exec_scan_tm_landmark_jig(self, job: Job) -> bool:
        params = job.params
        jig_number = params.get('jig_number', 1)
        wait_time_ms = params.get('wait_after_command', 100)
        wait_time = wait_time_ms / 1000.0
        repeat_count = params.get('repeat_count', 1)
        outlier_method = params.get('outlier_method', 'none')
        analysis_target = params.get('analysis_target', 'xyz')

        if not self.vision_manager:
            self._log("VisionManager가 없습니다")
            return False

        final_pose, analysis = self.scan_landmark_averaged(
            repeat_count, outlier_method, wait_time,
            jig_number=jig_number, analysis_target=analysis_target
        )
        if final_pose is None:
            return False

        final_pose = dict(final_pose)
        final_pose['measured_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        self.jig_landmark_results[jig_number] = final_pose

        self._log(f"Jig{jig_number} 최종 좌표: X={final_pose['x']:.3f}, Y={final_pose['y']:.3f}, Z={final_pose['z']:.3f}")
        self._log(f"scan_tm_landmark_jig{jig_number} 완료")
        return True

    def vision_origin_check(self, repeat_count: int = 5, outlier_method: str = 'iqr',
                            move_to_reference: bool = True, velocity: float = 20.0,
                            wait_after_command: int = 100) -> bool:
        self.macro_blackboard.pop('origin_check_result', None)
        result = run_macro('vision_origin_check', self._macro_context(), {
            'move_to_reference': move_to_reference,
            'velocity': velocity,
            'repeat_count': repeat_count,
            'outlier_method': outlier_method,
            'wait_after_command': wait_after_command,
        })
        if not result.ok:
            self._log(f"[오류] {result.message}")
        return result.ok

    def _exec_move_to_jig_landmark(self, job: Job) -> bool:
        params = job.params

        self._log("[프로토타입] move_to_jig_landmark 실행 — 검증 전 기능입니다")

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase가 아닙니다: {current_base}")
                self._log("[경고] move_to_jig_landmark 는 RobotBase 좌표계에서 실행해야 합니다!")
                return False

        jig_number = params.get('jig_number', 1)
        if jig_number < 1 or jig_number > 4:
            self._log(f"[거부] 잘못된 Jig 번호: {jig_number} (1~4만 가능)")
            return False

        landmark = self.jig_landmark_results.get(jig_number)
        if not landmark:
            self._log(f"Jig{jig_number} 스캔 결과 없음 - scan_tm_landmark_jig 를 먼저 실행하세요")
            return False

        if not landmark.get('detected', False):
            self._log(f"Jig{jig_number} 미검출 - 이동 불가")
            return False

        if not self.ros_node or not self.ros_node.current_tcp_pose \
                or len(self.ros_node.current_tcp_pose) < 6:
            self._log("Jig Landmark 이동 실패: 현재 TCP 위치를 읽을 수 없습니다 (로봇 상태 미수신)")
            return False

        offset = params.get('offset', {}) or {}
        offset_x = offset.get('x', 0.0)
        offset_y = offset.get('y', 0.0)
        offset_z = offset.get('z', 0.0)
        velocity = params.get('velocity', 20.0)
        decomposed_tcp = params.get('decomposed_tcp', True)

        target_x = landmark['x'] + offset_x
        target_y = landmark['y'] + offset_y
        target_z = landmark['z'] + offset_z

        tcp_before = list(self.ros_node.current_tcp_pose[:6])
        rx, ry, rz = tcp_before[3], tcp_before[4], tcp_before[5]

        self._log(f"[프로토타입] Jig{jig_number} 기준 이동:")
        self._log(f"  Landmark: X={landmark['x']:.2f}, Y={landmark['y']:.2f}, Z={landmark['z']:.2f}")
        self._log(f"  오프셋: ({offset_x:.2f}, {offset_y:.2f}, {offset_z:.2f})mm")
        self._log(f"  목표 위치: ({target_x:.2f}, {target_y:.2f}, {target_z:.2f})mm")
        self._log(f"  TCP 자세 유지: Rx={rx:.2f}, Ry={ry:.2f}, Rz={rz:.2f}")

        success, msg = self._move_to_position('tcp', target_x, target_y, target_z,
                                              rx, ry, rz, velocity,
                                              decomposed_tcp=decomposed_tcp)

        if success:
            self._log(msg)
            self._log(f"[프로토타입] move_to_jig_landmark (Jig{jig_number}) 완료")
        else:
            self._log(f"Jig Landmark 이동 실패: {msg}")

        return success

    def _exec_calculate_plate_pose(self, job: Job) -> bool:
        params = job.params
        if not self.vision_manager:
            self._log("VisionManager가 없습니다")
            return False

        landmarks = []
        for i in range(1, 5):
            if i not in self.jig_landmark_results:
                self._log(f"Jig{i} landmark 스캔 결과 없음 - scan_tm_landmark_jig 실행 필요")
                return False
            result = self.jig_landmark_results[i]
            if not result.get('detected', False):
                self._log(f"Jig{i} landmark 미검출 - 계산 불가")
                return False
            landmarks.append(result)
            self._log(f"Jig{i}: X={result['x']:.2f}, Y={result['y']:.2f}, Z={result['z']:.2f}")

        calc = JigPlaneCalculator()
        if not calc.load_from_dicts(landmarks):
            self._log("Landmark 데이터 로드 실패")
            return False

        plate_pose = calc.to_dict()
        if plate_pose is None:
            self._log("Plate pose 계산 실패")
            return False

        self.detected_plate_pose = plate_pose
        self._log(f"Plate Pose 계산 완료:")
        self._log(f"  X={plate_pose['x']:.3f}, Y={plate_pose['y']:.3f}, Z={plate_pose['z']:.3f}")
        self._log(f"  Rx={plate_pose['rx']:.3f}, Ry={plate_pose['ry']:.3f}, Rz={plate_pose['rz']:.3f}")

        if not self._confirm_plate_rectangle(landmarks, params):
            return False

        save_path = str(params.get('save_path', '') or '').strip()
        if save_path:
            operator = str(params.get('operator', '') or '').strip()
            if not operator:
                self._log("[경고] 작업자 이름이 비어 있습니다 — operator 없이 저장합니다")
            if not self._save_plate_pose(save_path, plate_pose, landmarks, job, operator):
                return False

        return True

    def _confirm_plate_rectangle(self, landmarks: List[Dict[str, float]],
                                 params: Dict[str, Any], blocking: bool = True) -> bool:
        if not bool(params.get('rect_guard_enabled', True)):
            return True

        validator = JigPlateValidator()
        if not validator.load_from_dicts(landmarks):
            self._log("[경고] 직사각형 검증용 Landmark 로드 실패 — 검증을 건너뜁니다")
            return True

        validator.TOLERANCE_SIDE_DIFF = float(params.get('max_side_diff_mm', 1.0))
        validator.TOLERANCE_DIAGONAL_DIFF = float(params.get('max_diagonal_diff_mm', 1.5))
        validator.TOLERANCE_ANGLE = float(params.get('max_angle_error_deg', 1.0))

        results = validator.check_rectangle()
        if not results:
            self._log("[경고] 직사각형 검증 결과 없음 — 검증을 건너뜁니다")
            return True

        failed = [r for r in results if not r.passed]
        if not failed:
            self._log("직사각형 검증 통과 — " + ", ".join(
                f"{r.name} {r.value:.3f}{r.unit}" for r in results))
            return True

        head = "[알람]" if blocking else "[경고]"
        self._log(f"{head} 직사각형 검증 실패 — 4 Landmark 배치가 허용 범위를 벗어났습니다")
        for r in results:
            self._log(f"  {'❌' if not r.passed else '✅'} {r.name}: "
                      f"{r.value:.3f}{r.unit} (상한 {r.threshold:.3f}{r.unit})")

        if not blocking:
            self._log("[경고] 실행 단계이므로 중단하지 않고 계속합니다 — 배치는 캘리브레이션에서 확인하세요")
            return True

        if self.on_plate_rect_alarm is None:
            self._log("[중단] 확인 콜백이 없어 저장하지 않고 중단합니다")
            return False

        distances = validator.get_side_lengths()
        approved = bool(self.on_plate_rect_alarm({
            'results': results,
            'failed': failed,
            'distances': distances,
        }))
        self._log("작업자 확인: " + ("저장하고 계속" if approved else "중단"))
        return approved

    def _resolve_plate_pose_files(self, source_path: str, file_prefix: str,
                                  average_count: int) -> List[Path]:
        target = Path(source_path)
        if not target.is_absolute():
            target = paths.PACKAGE_ROOT / target

        if target.is_file():
            return [target]

        if not target.is_dir():
            return []

        pattern = f"{file_prefix}*.yaml" if file_prefix else "*.yaml"
        files = sorted((f for f in target.glob(pattern) if f.is_file()), reverse=True)
        if average_count > 0:
            files = files[:average_count]
        return files

    def _exec_load_plate_pose(self, job: Job) -> bool:
        params = job.params
        source_path = str(params.get('source_path', '') or '').strip()
        if not source_path:
            self._log("[오류] source_path 가 비어 있습니다 — 불러올 파일/폴더를 지정하세요")
            return False

        file_prefix = str(params.get('file_prefix', '') or '').strip()
        average_count = int(params.get('average_count', 1))

        files = self._resolve_plate_pose_files(source_path, file_prefix, average_count)
        if not files:
            self._log(f"[오류] 불러올 plate_pose 파일이 없습니다 (source_path={source_path}, "
                      f"prefix={file_prefix or '없음'})")
            return False

        averaged, used, skipped = average_landmarks_from_files(files)
        for path, reason in skipped:
            self._log(f"[경고] 건너뜁니다 — {path.name}: {reason}")
        for path in used:
            self._log(f"  불러옴: {path.name}")

        if averaged is None:
            self._log("[오류] 유효한 plate_pose 파일이 없습니다 (jig1~4 필요)")
            return False
        loaded = len(used)

        calc = JigPlaneCalculator()
        if not calc.load_from_dicts(averaged):
            self._log("[오류] 평균 랜드마크 로드 실패")
            return False

        plate_pose = calc.to_dict()
        if plate_pose is None:
            self._log("[오류] 평균 랜드마크로 Plate Pose 계산 실패")
            return False

        self.jig_landmark_results = {i + 1: dict(averaged[i]) for i in range(4)}
        self.detected_plate_pose = plate_pose

        self._log(f"Plate Pose 불러오기 완료 ({loaded}개 파일 평균):")
        self._log(f"  X={plate_pose['x']:.3f}, Y={plate_pose['y']:.3f}, Z={plate_pose['z']:.3f}")
        self._log(f"  Rx={plate_pose['rx']:.3f}, Ry={plate_pose['ry']:.3f}, Rz={plate_pose['rz']:.3f}")

        return self._confirm_plate_rectangle(averaged, params, blocking=False)

    def _plate_pose_file_name(self, job: Job, saved_at: str) -> str:
        parts = []
        if self.current_recipe is not None and self.current_recipe.file_path:
            parts.append(Path(self.current_recipe.file_path).stem)
        caption = (getattr(job, 'caption', '') or '').strip()
        parts.append(caption if caption else f"{job.type}_{job.id}")
        parts.append(saved_at)

        name = '_'.join(p for p in parts if p)
        name = re.sub(r'[^0-9A-Za-z가-힣._-]', '_', name)
        return f"{name}.yaml"

    def _save_plate_pose(self, save_dir: str, plate_pose: Dict[str, float],
                         landmarks: List[Dict[str, Any]], job: Job,
                         operator: str = '') -> bool:
        now = time.localtime()
        directory = Path(save_dir)
        if not directory.is_absolute():
            directory = paths.PACKAGE_ROOT / directory
        target = directory / self._plate_pose_file_name(
            job, time.strftime('%Y%m%d_%H%M%S', now))

        recipe_name = (Path(self.current_recipe.file_path).stem
                       if self.current_recipe is not None and self.current_recipe.file_path
                       else None)

        data = {
            'operator': operator or None,
            'recipe': recipe_name,
            'task_caption': (getattr(job, 'caption', '') or '').strip() or None,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S', now),
            'plate_pose': {k: round(float(plate_pose[k]), 3)
                           for k in ('x', 'y', 'z', 'rx', 'ry', 'rz')},
            'landmarks': {
                f'jig{i}': dict(
                    {k: round(float(mark[k]), 3)
                     for k in ('x', 'y', 'z', 'rx', 'ry', 'rz')},
                    measured_at=mark.get('measured_at')
                )
                for i, mark in enumerate(landmarks, start=1)
            },
        }

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        except OSError as e:
            self._log(f"[오류] Plate Pose 저장 실패: {target} ({e})")
            return False

        self._log(f"Plate Pose 저장 완료: {target}")
        return True

    LANDMARK_POSE_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')

    def _exec_save_landmark_pose(self, job: Job) -> bool:
        params = job.params

        pose = self.tm_landmark_pose
        if not pose:
            self._log("[오류] Landmark 좌표가 없습니다 — scan_tm_landmark 를 먼저 실행하세요")
            return False

        missing = [k for k in self.LANDMARK_POSE_KEYS if k not in pose]
        if missing:
            self._log(f"[오류] Landmark 좌표에 빠진 값이 있습니다: {missing}")
            return False

        save_path = str(params.get('save_path', '') or '').strip()
        if not save_path:
            self._log("[오류] save_path 가 비어 있습니다 — 저장할 폴더를 지정하세요")
            return False

        operator = str(params.get('operator', '') or '').strip()
        if not operator:
            self._log("[경고] 작업자 이름이 비어 있습니다 — operator 없이 저장합니다")

        return self._save_landmark_pose(save_path, pose, job, operator)

    def _save_landmark_pose(self, save_dir: str, pose: Dict[str, float],
                            job: Job, operator: str = '') -> bool:
        now = time.localtime()
        directory = Path(save_dir)
        if not directory.is_absolute():
            directory = paths.PACKAGE_ROOT / directory
        target = directory / self._plate_pose_file_name(
            job, time.strftime('%Y%m%d_%H%M%S', now))

        recipe_name = (Path(self.current_recipe.file_path).stem
                       if self.current_recipe is not None and self.current_recipe.file_path
                       else None)

        data = {
            'operator': operator or None,
            'recipe': recipe_name,
            'task_caption': (getattr(job, 'caption', '') or '').strip() or None,
            'saved_at': time.strftime('%Y-%m-%d %H:%M:%S', now),
            'landmark': {k: round(float(pose[k]), 3)
                         for k in self.LANDMARK_POSE_KEYS},
        }

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        except OSError as e:
            self._log(f"[오류] Landmark 좌표 저장 실패: {target} ({e})")
            return False

        self._log(f"Landmark 좌표 저장 완료: {target}")
        return True

    LANDMARK_FRAME_OFFSET_KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')

    def _landmark_pose_age_min(self, path, data: Dict[str, Any]):
        raw = str(data.get('saved_at', '') or '').strip()
        if raw:
            try:
                return (time.time() - time.mktime(
                    time.strptime(raw, '%Y-%m-%d %H:%M:%S'))) / 60.0
            except ValueError:
                self._log(f"[경고] saved_at 형식을 읽지 못했습니다: {Path(path).name} ({raw!r}) "
                          f"— 파일 수정시각으로 대신 판정합니다")
        try:
            return (time.time() - Path(path).stat().st_mtime) / 60.0
        except OSError:
            return None

    def _load_landmark_pose_from_files(self, params: Dict[str, Any]):
        source_path = str(params.get('source_path', '') or '').strip()
        if not source_path:
            return None, "source_path 가 비어 있습니다 (landmark_source=file)"

        files = self._resolve_plate_pose_files(
            source_path,
            str(params.get('file_prefix', '') or '').strip(),
            int(params.get('average_count', 1)),
        )
        if not files:
            return None, (f"불러올 landmark_pose 파일이 없습니다 "
                          f"(source_path={source_path}, file_prefix={params.get('file_prefix')!r})")

        try:
            max_age_min = float(params.get('max_age_min', 0.0) or 0.0)
        except (TypeError, ValueError):
            return None, (f"max_age_min 이 숫자가 아닙니다: {params.get('max_age_min')!r} "
                          f"(분 단위, 0 이하면 무제한)")

        poses, skipped, stale = [], [], []
        for path in files:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
            except (OSError, yaml.YAMLError) as e:
                skipped.append(f"{Path(path).name}({e})")
                continue
            mark = data.get('landmark') or {}
            if not all(k in mark for k in self.LANDMARK_POSE_KEYS):
                skipped.append(f"{Path(path).name}(landmark 불완전)")
                continue
            if max_age_min > 0:
                age_min = self._landmark_pose_age_min(path, data)
                if age_min is None:
                    return None, (f"{Path(path).name} 의 저장시각을 읽지 못해 유효시간을 "
                                  f"확인할 수 없습니다 (max_age_min={max_age_min:g}분)")
                if age_min > max_age_min:
                    stale.append(f"{Path(path).name}({age_min:.1f}분 전)")
                    continue
            poses.append([float(mark[k]) for k in self.LANDMARK_POSE_KEYS])

        if skipped:
            self._log(f"[경고] landmark_pose 파일 {len(skipped)}개 건너뜀: {', '.join(skipped)}")
        if stale:
            return None, (f"landmark_pose 저장본이 유효시간 {max_age_min:g}분을 넘었습니다: "
                          f"{', '.join(stale)} — 마커를 다시 스캔·저장하세요")
        if not poses:
            return None, f"유효한 landmark_pose 파일이 없습니다 ({len(files)}개 확인)"

        averaged = np.mean(np.array(poses, dtype=float), axis=0)
        pose = dict(zip(self.LANDMARK_POSE_KEYS, (float(v) for v in averaged)))
        return pose, f"landmark_pose {len(poses)}개 파일 평균 사용"

    def _landmark_frame_inputs(self, params: Dict[str, Any]):
        source = str(params.get('landmark_source', 'latest_scan') or 'latest_scan')
        if source not in ('latest_scan', 'file'):
            return None, f"알 수 없는 landmark_source: {source!r} (가능: ['latest_scan', 'file'])"

        if source == 'file':
            landmark, message = self._load_landmark_pose_from_files(params)
            if landmark is None:
                return None, message
            self._log(message)
        else:
            landmark = self.tm_landmark_pose
            if not landmark:
                return None, "Landmark 좌표가 없습니다 — scan_tm_landmark 를 먼저 실행하세요"
            missing = [k for k in self.LANDMARK_POSE_KEYS if k not in landmark]
            if missing:
                return None, f"Landmark 좌표에 빠진 값이 있습니다: {missing}"

        frame_mode = str(params.get('frame_mode', FRAME_MODE_RZ_ONLY) or FRAME_MODE_RZ_ONLY)
        if frame_mode not in FRAME_MODES:
            return None, f"알 수 없는 frame_mode: {frame_mode!r} (가능: {list(FRAME_MODES)})"

        relative = {k: float(params.get(f'offset_{k}', 0.0))
                    for k in self.LANDMARK_FRAME_OFFSET_KEYS}
        return (landmark, frame_mode, relative), ""

    def _landmark_frame_target(self, params: Dict[str, Any]):
        parsed, reason = self._landmark_frame_inputs(params)
        if parsed is None:
            return None, reason
        landmark, frame_mode, relative = parsed

        max_radius_mm = float(params.get('max_radius_mm', 0.0))
        radius = math.sqrt(relative['x'] ** 2 + relative['y'] ** 2 + relative['z'] ** 2)
        if max_radius_mm > 0 and radius > max_radius_mm:
            return None, f"마커 기준 거리 {radius:.2f}mm > 상한 {max_radius_mm:.2f}mm"

        target = pose_from_landmark_frame(landmark, relative, frame_mode)
        tool_offset = {k: float(params.get(f'tool_offset_{k}', 0.0))
                       for k in TOOL_OFFSET_6DOF_KEYS}
        if any(abs(v) > 0 for v in tool_offset.values()):
            target = apply_tool_offset_6dof(target, tool_offset)
            self._log(f"  그리퍼 오차 반영: x={tool_offset['x']:.2f}, y={tool_offset['y']:.2f}, "
                      f"z={tool_offset['z']:.2f}mm, rx={tool_offset['rx']:.2f}, "
                      f"ry={tool_offset['ry']:.2f}, rz={tool_offset['rz']:.2f}°")

        self._log(f"마커 좌표계 이동 [{frame_mode}]: 상대 "
                  f"(x={relative['x']:.3f}, y={relative['y']:.3f}, z={relative['z']:.3f})mm, "
                  f"(rx={relative['rx']:.3f}, ry={relative['ry']:.3f}, rz={relative['rz']:.3f})°")
        self._log(f"  마커 X={landmark['x']:.3f}, Y={landmark['y']:.3f}, Z={landmark['z']:.3f}, "
                  f"Rz={landmark['rz']:.3f}")
        return target, ""

    def _exec_move_to_landmark_pose(self, job: Job) -> bool:
        params = job.params

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase 가 아닙니다: {current_base}")
                self._log("[경고] move_to_landmark_pose 는 RobotBase 좌표계에서 실행해야 합니다!")
                return False

        target, reason = self._landmark_frame_target(params)
        if target is None:
            self._log(f"[거부] {reason}")
            return False

        return self._move_pose_keep(
            "마커 좌표계 이동", target,
            params.get('velocity', 10.0),
            params.get('decel_zone_mm', POSE_KEEP_DECEL_ZONE_MM),
            params.get('decel_velocity', POSE_KEEP_DECEL_VELOCITY),
        )

    def estimate_landmark_frame_target(self, params: Dict[str, Any]):
        parsed, reason = self._landmark_frame_inputs(params)
        if parsed is None:
            return None, f"[오류] {reason}"
        landmark, frame_mode, _ = parsed

        tcp = self._read_tcp_or_log("마커 좌표계 목표 역산")
        if tcp is None:
            return None, "[오류] 현재 TCP 를 읽지 못했습니다"

        pose = dict(zip(self.LANDMARK_POSE_KEYS, tcp[:6]))
        offset = pose_in_landmark_frame(landmark, pose, frame_mode)
        return offset, (
            f"마커 좌표계 목표 역산 [{frame_mode}]: "
            f"x={offset['x']:.3f}, y={offset['y']:.3f}, z={offset['z']:.3f}, "
            f"rx={offset['rx']:.3f}, ry={offset['ry']:.3f}, rz={offset['rz']:.3f}")

    def estimate_landmark_frame_tool_offset(self, params: Dict[str, Any]):
        zeroed = dict(params)
        for key in TOOL_OFFSET_6DOF_KEYS:
            zeroed[f'tool_offset_{key}'] = 0.0

        target, reason = self._landmark_frame_target(zeroed)
        if target is None:
            return None, f"[오류] {reason}"

        tcp = self._read_tcp_or_log("그리퍼 오차 역산")
        if tcp is None:
            return None, "[오류] 현재 TCP 를 읽지 못했습니다"

        actual = dict(zip(self.LANDMARK_POSE_KEYS, tcp[:6]))
        offset = tool_offset_6dof_from_poses(target, actual)

        return offset, (
            f"그리퍼 오차 추산: x={offset['x']:.2f}, y={offset['y']:.2f}, z={offset['z']:.2f}mm, "
            f"rx={offset['rx']:.2f}, ry={offset['ry']:.2f}, rz={offset['rz']:.2f}°")

    def _plane_normal_tilt_deg(self, plate_pose: Dict[str, float]) -> float:
        normal = plane_normal_from_pose(plate_pose)
        cos_tilt = float(np.clip(np.dot(normal, np.array([0.0, 0.0, 1.0])), -1.0, 1.0))
        return math.degrees(math.acos(cos_tilt))

    def _check_landmark_diagonal_diff(self, max_diff_mm: float) -> Tuple[bool, str]:
        marks = []
        for i in range(1, 5):
            result = self.jig_landmark_results.get(i)
            if not result:
                return False, f"Jig{i} 스캔 결과가 없어 배치 검증 불가 — scan_tm_landmark_jig 를 먼저 실행하세요"
            marks.append(Mark(
                x=result['x'], y=result['y'], z=result['z'],
                rx=result['rx'], ry=result['ry'], rz=result['rz']
            ))

        calc = JigPlaneCalculator()
        if not calc.load_from_marks(marks):
            return False, "Landmark 4개 로드 실패 — 배치 검증 불가"

        distances = calc.calculate_distance_matrix()
        if distances is None:
            return False, "거리 행렬 계산 실패 — 배치 검증 불가"

        diff = abs(distances['d_1_4'] - distances['d_2_3'])
        if diff > max_diff_mm:
            return False, (
                f"[거부] 대각선 길이 차 {diff:.2f}mm > 상한 {max_diff_mm:.2f}mm "
                f"(d_1_4={distances['d_1_4']:.2f}, d_2_3={distances['d_2_3']:.2f}) "
                f"— 마크 배치 순서(1 좌하/2 좌상/3 우하/4 우상) 또는 검출을 확인하세요"
            )
        return True, f"배치 검증 통과 (대각선 차 {diff:.2f}mm ≤ {max_diff_mm:.2f}mm)"

    def _read_tcp_or_log(self, what: str) -> Optional[List[float]]:
        if not self.ros_node or not self.ros_node.current_tcp_pose \
                or len(self.ros_node.current_tcp_pose) < 6:
            self._log(f"{what} 실패: 현재 TCP 위치를 읽을 수 없습니다 (로봇 상태 미수신)")
            return None
        return list(self.ros_node.current_tcp_pose[:6])

    def _move_pose_keep(self, label: str, target: Dict[str, float], velocity: float,
                        decel_zone_mm: float, decel_velocity: float,
                        straight: bool = False) -> bool:
        tcp_before = self._read_tcp_or_log(label)
        if tcp_before is None:
            return False

        target_rx, target_ry, target_rz = target['rx'], target['ry'], target['rz']
        self._log(f"{label}: 목표 위치 ({target['x']:.2f}, {target['y']:.2f}, "
                  f"{target['z']:.2f})mm, 자세 (Rx={target_rx:.2f}, Ry={target_ry:.2f}, "
                  f"Rz={target_rz:.2f})°, 속도 {velocity}%")

        motion_service = getattr(self.ros_node, 'motion_service', None)
        angle_diff = getattr(motion_service, '_angle_difference_deg', None)
        rotation_needed = True
        if angle_diff is not None:
            max_gap = max(
                angle_diff(target_rx, tcp_before[3]),
                angle_diff(target_ry, tcp_before[4]),
                angle_diff(target_rz, tcp_before[5]),
            )
            rotation_needed = max_gap >= PLANE_ALIGN_MIN_ROTATION_DEG
            if not rotation_needed:
                self._log(f"[1/2] 자세 정렬 생략 — 이미 정렬됨 (최대 편차 {max_gap:.4f}°)")

        if rotation_needed:
            self._log(f"[1/2] 제자리 자세 정렬 (위치 고정)")
            success, msg = self._move_to_position_line(
                'tcp', tcp_before[0], tcp_before[1], tcp_before[2],
                target_rx, target_ry, target_rz, velocity
            )
            if not success:
                self._log(f"자세 정렬 실패: {msg}")
                self._log("[중단] 접근 단계를 실행하지 않습니다 (PTP 대체 없음)")
                return False
            self._log(msg)
            self._log_orientation_deviation("1/2 자세 정렬", target_rx, target_ry, target_rz)

        tcp_aligned = [tcp_before[0], tcp_before[1], tcp_before[2],
                       target_rx, target_ry, target_rz]
        segments = self._build_pose_keep_segments(
            tcp_aligned, target['x'], target['y'], target['z'],
            velocity, decel_zone_mm, decel_velocity, straight
        )
        if not segments:
            self._log(f"[2/2] 접근 생략 — 이동량이 {POSE_KEEP_MIN_SEGMENT_MM}mm 미만")
            return True

        self._log(f"[2/2] 자세 유지 접근: 구간 {len(segments)}개")
        for idx, (seg_label, seg_x, seg_y, seg_z, seg_vel) in enumerate(segments, start=1):
            self._log(f"  [{idx}/{len(segments)}] {seg_label} → "
                      f"({seg_x:.2f}, {seg_y:.2f}, {seg_z:.2f})mm, 속도 {seg_vel}%")
            success, msg = self._move_to_position_line(
                'tcp', seg_x, seg_y, seg_z, target_rx, target_ry, target_rz, seg_vel
            )
            if not success:
                self._log(f"접근 실패({seg_label}): {msg}")
                self._log("[중단] 이후 구간을 실행하지 않습니다 (PTP 대체 없음)")
                return False
            self._log(msg)

        self._log_orientation_deviation(f"{label} 종점", target_rx, target_ry, target_rz)
        return True

    def _exec_save_pose(self, job: Job) -> bool:
        key = str(job.params.get('key', 'start') or 'start').strip()
        tcp = self._read_tcp_or_log(f"자세 저장({key})")
        if tcp is None:
            return False

        self.saved_poses[key] = tcp
        self._log(f"자세 저장 [{key}]: X={tcp[0]:.3f}, Y={tcp[1]:.3f}, Z={tcp[2]:.3f}, "
                  f"Rx={tcp[3]:.3f}, Ry={tcp[4]:.3f}, Rz={tcp[5]:.3f}")
        return True

    def _exec_move_to_saved_pose(self, job: Job) -> bool:
        params = job.params
        key = str(params.get('key', 'start') or 'start').strip()

        tcp = self.saved_poses.get(key)
        if tcp is None:
            self._log(f"[오류] 저장된 자세가 없습니다 [{key}] — save_pose 를 먼저 실행하세요")
            return False

        target = {'x': tcp[0], 'y': tcp[1], 'z': tcp[2],
                  'rx': tcp[3], 'ry': tcp[4], 'rz': tcp[5]}
        return self._move_pose_keep(
            f"저장 자세 복귀 [{key}]", target,
            params.get('velocity', 10.0),
            params.get('decel_zone_mm', POSE_KEEP_DECEL_ZONE_MM),
            params.get('decel_velocity', POSE_KEEP_DECEL_VELOCITY),
        )

    def _exec_move_to_named_position(self, job: Job) -> bool:
        from .services.config_manager import ConfigManager

        params = job.params
        name = str(params.get('name', '') or '').strip()
        if not name:
            self._log("[오류] 자세 이름(name)이 비어 있습니다")
            return False

        entry = ConfigManager().get_position(name)
        if not entry:
            self._log(f"[오류] positions.yaml 에 등록된 자세가 없습니다 [{name}]")
            return False

        values = list(entry.get('values') or [])
        if len(values) < 6:
            self._log(f"[오류] 자세 [{name}] 의 values 는 6개여야 합니다: {values}")
            return False

        # type: joint → 관절각(deg) PTP_J, tcp → TCP 6값(mm/deg) PTP_T
        motion_type = 'joint' if str(entry.get('type', 'joint')) == 'joint' else 'tcp'
        velocity = float(params.get('velocity', 10.0))

        success, msg = self._move_to_position(
            motion_type, values[0], values[1], values[2],
            values[3], values[4], values[5], velocity)
        self._log(f"등록 자세 이동 [{name}] ({motion_type}): {msg}")
        return success

    def _exec_move_to_plane_pose(self, job: Job) -> bool:
        params = job.params

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase 가 아닙니다: {current_base}")
                self._log("[경고] move_to_plane_pose 는 RobotBase 좌표계에서 실행해야 합니다!")
                return False

        if self.detected_plate_pose is None:
            self._log("평면 pose 가 없습니다. calculate_plate_pose 또는 "
                      "load_plate_pose 를 먼저 실행하세요.")
            return False

        relative = {
            'x': float(params.get('offset_x', 0.0)),
            'y': float(params.get('offset_y', 0.0)),
            'z': float(params.get('offset_z', 150.0)),
            'rx': float(params.get('offset_rx', 180.0)),
            'ry': float(params.get('offset_ry', 0.0)),
            'rz': float(params.get('offset_rz', 0.0)),
        }
        if relative['z'] <= 0:
            self._log(f"[거부] offset_z 는 양수여야 합니다 — 평면 아래로 이동 금지 "
                      f"(입력: {relative['z']})")
            return False

        max_tilt_deg = params.get('max_tilt_deg', PLANE_ALIGN_MAX_TILT_DEG)
        tilt_deg = self._plane_normal_tilt_deg(self.detected_plate_pose)
        if tilt_deg > max_tilt_deg:
            self._log(f"[거부] 평면 법선 기울기 {tilt_deg:.2f}° > 상한 {max_tilt_deg:.2f}°")
            return False

        max_radius_mm = float(params.get('max_radius_mm', 200.0))
        radius = math.hypot(relative['x'], relative['y'])
        if max_radius_mm > 0 and radius > max_radius_mm:
            self._log(f"[거부] 평면상 중심 거리 {radius:.2f}mm > 상한 {max_radius_mm:.2f}mm "
                      f"— 팔레트 밖으로 나가는 목표입니다")
            return False

        target = pose_from_plane_frame(self.detected_plate_pose, relative)
        self._log(f"평면 좌표계 이동: 상대 (x={relative['x']:.3f}, y={relative['y']:.3f}, "
                  f"z={relative['z']:.3f})mm, rz={relative['rz']:.3f}° "
                  f"(법선 기울기 {tilt_deg:.2f}°)")

        return self._move_pose_keep(
            "평면 좌표계 이동", target,
            params.get('velocity', 10.0),
            params.get('decel_zone_mm', POSE_KEEP_DECEL_ZONE_MM),
            params.get('decel_velocity', POSE_KEEP_DECEL_VELOCITY),
            bool(params.get('straight_path', False)),
        )

    def _plane_align_base_target(self, params: dict):
        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase가 아닙니다: {current_base}")
                self._log("[경고] align_to_plane_normal 은 RobotBase 좌표계에서 실행해야 합니다!")
                return None, None, None

        if self.detected_plate_pose is None:
            self._log("평면 pose가 없습니다. calculate_plate_pose 를 먼저 실행하세요.")
            return None, None, None

        standoff_mm = params.get('standoff_mm', 150.0)
        rz_mode = params.get('rz_mode', 'keep')
        max_tilt_deg = params.get('max_tilt_deg', PLANE_ALIGN_MAX_TILT_DEG)
        max_diagonal_diff_mm = params.get('max_diagonal_diff_mm',
                                          PLANE_ALIGN_MAX_DIAGONAL_DIFF_MM)

        if standoff_mm <= 0:
            self._log(f"[거부] standoff_mm 은 양수여야 합니다 (입력: {standoff_mm})")
            return None, None, None

        layout_ok, layout_msg = self._check_landmark_diagonal_diff(max_diagonal_diff_mm)
        self._log(layout_msg)
        if not layout_ok:
            return None, None, None

        tilt_deg = self._plane_normal_tilt_deg(self.detected_plate_pose)
        if tilt_deg > max_tilt_deg:
            self._log(f"[거부] 평면 법선 기울기 {tilt_deg:.2f}° > 상한 {max_tilt_deg:.2f}°")
            self._log("[확인] 스캔 오류이거나 법선이 뒤집혔을 수 있습니다 "
                      "(마크 배치 순서: 1 좌하 / 2 좌상 / 3 우하 / 4 우상)")
            return None, None, None

        if not self.ros_node or not self.ros_node.current_tcp_pose \
                or len(self.ros_node.current_tcp_pose) < 6:
            self._log("평면 수직 정렬 실패: 현재 TCP 위치를 읽을 수 없습니다 (로봇 상태 미수신)")
            return None, None, None

        tcp_before = list(self.ros_node.current_tcp_pose[:6])

        try:
            target = tcp_pose_for_plane_normal(
                self.detected_plate_pose, standoff_mm, rz_mode, tcp_before
            )
        except ValueError as e:
            self._log(f"[거부] 목표 자세 계산 실패: {e}")
            return None, None, None

        return target, tcp_before, tilt_deg

    @staticmethod
    def _plane_align_tool_offset(params: dict) -> dict:
        return {
            key: float(params.get(f'offset_{key}', 0.0) or 0.0)
            for key in TOOL_OFFSET_KEYS
        }

    def estimate_plane_align_tool_offset(self, params: dict):
        zeroed = dict(params)
        for key in TOOL_OFFSET_KEYS:
            zeroed[f'offset_{key}'] = 0.0

        target, tcp_before, _ = self._plane_align_base_target(zeroed)
        if target is None:
            return None, "오차 추산 실패 — 위 로그의 사유를 확인하세요"

        actual = {
            'x': tcp_before[0], 'y': tcp_before[1], 'z': tcp_before[2],
            'rx': tcp_before[3], 'ry': tcp_before[4], 'rz': tcp_before[5],
        }
        offset, z_ignored = tool_offset_from_poses(target, actual)

        message = (
            f"그리퍼 오차 추산: x={offset['x']:.2f}, y={offset['y']:.2f}mm, "
            f"rx={offset['rx']:.2f}, ry={offset['ry']:.2f}, rz={offset['rz']:.2f}°"
        )
        if abs(z_ignored) >= 0.01:
            message += (f" (공구 Z 방향 차이 {z_ignored:.2f}mm 는 오차로 넣지 않음 "
                        f"— standoff_mm 으로 조정하세요)")

        return offset, message

    def _exec_align_to_plane_normal(self, job: Job) -> bool:
        params = job.params

        velocity = params.get('velocity', 10.0)
        rz_mode = params.get('rz_mode', 'keep')
        standoff_mm = params.get('standoff_mm', 150.0)
        decel_zone_mm = params.get('decel_zone_mm', POSE_KEEP_DECEL_ZONE_MM)
        decel_velocity = params.get('decel_velocity', POSE_KEEP_DECEL_VELOCITY)

        target, tcp_before, tilt_deg = self._plane_align_base_target(params)
        if target is None:
            return False

        offset = self._plane_align_tool_offset(params)
        if any(abs(v) > 0.0 for v in offset.values()):
            target = apply_tool_offset(target, offset)
            self._log(f"그리퍼 오차 적용(공구 좌표계): x={offset['x']:.2f}, "
                      f"y={offset['y']:.2f}mm, rx={offset['rx']:.2f}, "
                      f"ry={offset['ry']:.2f}, rz={offset['rz']:.2f}°")

        target_rx, target_ry, target_rz = target['rx'], target['ry'], target['rz']
        self._log(f"평면 수직 정렬: 법선 기울기 {tilt_deg:.2f}°, standoff {standoff_mm:.1f}mm, "
                  f"rz_mode={rz_mode}, 속도 {velocity}%")
        self._log(f"  목표 위치: ({target['x']:.2f}, {target['y']:.2f}, {target['z']:.2f})mm")
        self._log(f"  목표 자세: (Rx={target_rx:.2f}, Ry={target_ry:.2f}, Rz={target_rz:.2f})°")

        motion_service = getattr(self.ros_node, 'motion_service', None)
        angle_diff = getattr(motion_service, '_angle_difference_deg', None)
        rotation_needed = True
        if angle_diff is not None:
            max_gap = max(
                angle_diff(target_rx, tcp_before[3]),
                angle_diff(target_ry, tcp_before[4]),
                angle_diff(target_rz, tcp_before[5]),
            )
            rotation_needed = max_gap >= PLANE_ALIGN_MIN_ROTATION_DEG
            if not rotation_needed:
                self._log(f"[1/2] 자세 정렬 생략 — 이미 정렬됨 (최대 편차 {max_gap:.4f}°)")

        if rotation_needed:
            self._log(f"[1/2] 제자리 자세 정렬 (위치 고정) → "
                      f"Rx={target_rx:.2f}, Ry={target_ry:.2f}, Rz={target_rz:.2f}°")
            success, msg = self._move_to_position_line(
                'tcp', tcp_before[0], tcp_before[1], tcp_before[2],
                target_rx, target_ry, target_rz, velocity
            )
            if not success:
                self._log(f"자세 정렬 실패: {msg}")
                self._log("[중단] 접근 단계를 실행하지 않습니다 (PTP 대체 없음 — 정렬 보존 우선)")
                return False
            self._log(msg)
            self._log_orientation_deviation("1/2 자세 정렬", target_rx, target_ry, target_rz)

        tcp_aligned = [tcp_before[0], tcp_before[1], tcp_before[2],
                       target_rx, target_ry, target_rz]
        segments = self._build_pose_keep_segments(
            tcp_aligned, target['x'], target['y'], target['z'],
            velocity, decel_zone_mm, decel_velocity
        )
        if not segments:
            self._log(f"[2/2] 접근 생략 — 이동량이 {POSE_KEEP_MIN_SEGMENT_MM}mm 미만")
            return True

        self._log(f"[2/2] 자세 유지 접근: 구간 {len(segments)}개")
        for idx, (label, seg_x, seg_y, seg_z, seg_vel) in enumerate(segments, start=1):
            self._log(f"  [{idx}/{len(segments)}] {label} → "
                      f"({seg_x:.2f}, {seg_y:.2f}, {seg_z:.2f})mm, 속도 {seg_vel}%")

            success, msg = self._move_to_position_line(
                'tcp', seg_x, seg_y, seg_z, target_rx, target_ry, target_rz, seg_vel
            )
            if not success:
                self._log(f"접근 실패({label}): {msg}")
                self._log("[중단] 이후 구간을 실행하지 않습니다 (PTP 대체 없음)")
                return False

            self._log(msg)
            self._log_orientation_deviation(f"2/2 {idx}/{len(segments)} {label}",
                                            target_rx, target_ry, target_rz)

        self._log("align_to_plane_normal 완료")
        return True

    def _exec_measure_plane_distance(self, job: Job) -> bool:
        if self.detected_plate_pose is None:
            self._log("평면 pose가 없습니다. calculate_plate_pose 를 먼저 실행하세요.")
            return False

        if not self.ros_node or not self.ros_node.current_tcp_pose \
                or len(self.ros_node.current_tcp_pose) < 6:
            self._log("평면 거리 측정 실패: 현재 TCP 위치를 읽을 수 없습니다 (로봇 상태 미수신)")
            return False

        tcp = list(self.ros_node.current_tcp_pose[:6])
        distance = signed_point_to_plane_distance((tcp[0], tcp[1], tcp[2]),
                                                  self.detected_plate_pose)
        self.measured_plane_distance = distance

        normal = plane_normal_from_pose(self.detected_plate_pose)
        tool_z = self._create_transform_matrix({
            'X': tcp[0], 'Y': tcp[1], 'Z': tcp[2],
            'Rx': tcp[3], 'Ry': tcp[4], 'Rz': tcp[5],
        })[:3, 2]
        cos_angle = float(np.clip(np.dot(tool_z, -normal), -1.0, 1.0))
        alignment_deg = math.degrees(math.acos(cos_angle))
        tilt_deg = self._plane_normal_tilt_deg(self.detected_plate_pose)

        side = "법선 방향 쪽" if distance >= 0 else "법선 반대쪽"
        self._log(f"평면 거리 측정: {distance:+.3f}mm ({side}, |거리| {abs(distance):.3f}mm)")
        self._log(f"  수직 정렬 편차: {alignment_deg:.3f}° "
                  f"(0°=Tool Z가 평면을 정확히 향함)")
        self._log(f"  평면 법선 기울기(base +Z 기준): {tilt_deg:.3f}°")
        self._log(f"  현재 TCP: ({tcp[0]:.2f}, {tcp[1]:.2f}, {tcp[2]:.2f})mm")
        if distance < 0:
            self._log("[확인] 거리가 음수입니다 — 법선이 뒤집혔거나 TCP 가 평면 반대편에 있습니다. "
                      "실이동 전 마크 배치 순서를 확인하세요.")
        return True

    def _exec_generate_runtime(self, job: Job) -> bool:
        params = job.params

        if self.current_recipe is None or not self.current_recipe.file_path:
            self._log("[ERROR] 현재 로드된 Recipe가 없습니다")
            return False

        master_file = self.current_recipe.file_path

        if '_runtime' in master_file:
            self._log("[ERROR] 이미 Runtime YAML 파일입니다")
            return False

        output_suffix = params.get('output_suffix', '_runtime')
        from pathlib import Path
        master_path = Path(master_file)
        output_file = str(master_path.parent / f"{master_path.stem}{output_suffix}{master_path.suffix}")

        import os
        import sys

        use_jig_plate = params.get('use_jig_plate_file', True)
        jig_plate_file = None

        pkg_dir = os.path.dirname(__file__)
        if 'install' in pkg_dir or 'build' in pkg_dir:
            ws_dir = pkg_dir.split('/install')[0].split('/build')[0]
            tools_dir = os.path.join(ws_dir, 'src', 'TM_Robot_Task_Manager', 'tools')
        else:
            tools_dir = os.path.join(pkg_dir, '..', 'tools')

        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        if use_jig_plate:
            from convert_to_runtime import find_latest_jig_plate_file
            jig_plate_file = find_latest_jig_plate_file()
            if jig_plate_file:
                self._log(f"Jig Plate 파일 사용: {jig_plate_file}")
            else:
                self._log("Jig Plate 파일 미발견 - 마스터 파일 기준점 사용")

        from convert_to_runtime import (RecipeConverter, find_latest_runtime_job_config,
                                        find_latest_landmark_pose_file)
        runtime_job_config = find_latest_runtime_job_config()
        if runtime_job_config:
            self._log(f"Runtime Job 설정 파일: {runtime_job_config}")
        landmark_pose_file = find_latest_landmark_pose_file()
        if landmark_pose_file:
            self._log(f"Landmark Pose 파일: {landmark_pose_file}")
        converter = RecipeConverter(
            jig_plate_file=jig_plate_file,
            runtime_job_config=runtime_job_config,
            landmark_pose_file=landmark_pose_file
        )

        self._log(f"Runtime YAML 생성 시작: {master_file} -> {output_file}")
        success = converter.convert_to_relative(master_file, output_file)

        if success:
            self._log(f"Runtime YAML 생성 완료: {output_file}")
        else:
            self._log(f"[ERROR] Runtime YAML 생성 실패")

        return success

    def _read_and_store_landmark_result(self) -> bool:
        if not self.ros_node:
            return False

        from tm_msgs.srv import AskItem
        client = self.ros_node.ask_item_client

        if not client.wait_for_service(timeout_sec=1.0):
            return False

        request = AskItem.Request()
        request.id = "gv"
        request.item = 'g_tm_landmark_detect'
        request.wait_time = 0.2

        try:
            future = client.call_async(request)
            rclpy.spin_until_future_complete(self.ros_node, future, timeout_sec=5.0)

            landmark_detected = False
            if future.result() is not None and future.result().ok:
                detect_val = future.result().value
                if detect_val:
                    detect_val_lower = detect_val.lower()
                    landmark_detected = 'true' in detect_val_lower or '=1' in detect_val_lower

            if not landmark_detected:
                self._log("Landmark 검출 실패 (g_tm_landmark_detect=false)")
                return False

            request2 = AskItem.Request()
            request2.id = "gv"
            request2.item = 'g_TM_Landmark'
            request2.wait_time = 0.2

            future2 = client.call_async(request2)
            rclpy.spin_until_future_complete(self.ros_node, future2, timeout_sec=5.0)

            if future2.result() is None or not future2.result().ok:
                self._log("g_TM_Landmark 읽기 실패")
                return False

            landmark_val = future2.result().value
            success, result = parse_tm_landmark_to_dict(landmark_val, detected=landmark_detected)
            if not success:
                self._log(f"g_TM_Landmark {result}")
                return False

            self.detected_landmark_pose = result
            self._log(f"Landmark 저장: X={result['x']:.3f}, Y={result['y']:.3f}, Z={result['z']:.3f}, "
                      f"Rx={result['rx']:.3f}, Ry={result['ry']:.3f}, Rz={result['rz']:.3f}")
            return True

        except Exception as e:
            self._log(f"Landmark 결과 읽기 예외: {e}")
            return False

    def _exec_measure_point(self, job: Job) -> bool:
        params = job.params

        if self.ros_node:
            current_base = getattr(self.ros_node, 'current_base_name', 'RobotBase')
            if current_base and current_base != 'RobotBase':
                self._log(f"[경고] 현재 좌표계가 RobotBase가 아닙니다: {current_base}")
                self._log("[경고] measure_point는 RobotBase 좌표계에서 실행해야 합니다!")
                return False

        point_type = params.get('point_type', 'start')
        motion_type = params.get('motion_type', 'tcp')
        coordinate_mode = getattr(job, 'coordinate_mode', 'absolute')
        x = params.get('X', 0.0)
        y = params.get('Y', 0.0)
        z = params.get('Z', 0.0)
        rx = params.get('Rx', 0.0)
        ry = params.get('Ry', 0.0)
        rz = params.get('Rz', 0.0)
        velocity = params.get('velocity', 25.0)

        if coordinate_mode == 'relative':
            if self.tm_transform_matrix is None:
                self._log("[경고] TM Landmark 기준점이 없습니다. scan_tm_landmark를 먼저 실행하세요.")
                return False

            if self.recipe_mode == 'teaching':
                master_rx, master_ry, master_rz = rx, ry, rz
                rel_pose = {'X': x, 'Y': y, 'Z': z, 'Rx': 0.0, 'Ry': 0.0, 'Rz': 0.0}
                abs_pose = self._transform_relative_to_absolute(rel_pose)

                self._log(f"[좌표 변환-Teaching] 위치만 변환: ({x:.2f}, {y:.2f}, {z:.2f}) → "
                          f"({abs_pose['X']:.2f}, {abs_pose['Y']:.2f}, {abs_pose['Z']:.2f})")
                self._log(f"[좌표 변환-Teaching] TCP 자세 유지: Rx={master_rx:.2f}, Ry={master_ry:.2f}, Rz={master_rz:.2f}")

                x = abs_pose['X']
                y = abs_pose['Y']
                z = abs_pose['Z']
                rx = master_rx
                ry = master_ry
                rz = master_rz
            else:
                rel_pose = {'X': x, 'Y': y, 'Z': z, 'Rx': rx, 'Ry': ry, 'Rz': rz}
                abs_pose = self._transform_relative_to_absolute(rel_pose)

                self._log(f"[좌표 변환] 상대 → 절대: ({x:.2f}, {y:.2f}, {z:.2f}) → "
                          f"({abs_pose['X']:.2f}, {abs_pose['Y']:.2f}, {abs_pose['Z']:.2f})")

                x = abs_pose['X']
                y = abs_pose['Y']
                z = abs_pose['Z']
                rx = abs_pose['Rx']
                ry = abs_pose['Ry']
                rz = abs_pose['Rz']

        point_type_names = {'start': '시작', 'waypoint': '경유', 'end': '측정'}
        point_name = point_type_names.get(point_type, point_type)

        self._log(f"측정점 이동 ({point_name}): {motion_type.upper()}")

        success, msg = self._move_to_position(motion_type, x, y, z, rx, ry, rz, velocity)

        if success:
            self._log(msg)

            if point_type == 'end' and hasattr(self, 'on_measure_point'):
                if self.on_measure_point:
                    self.on_measure_point()
        else:
            self._log(f"측정점 이동 실패: {msg}")

        return success

    def _exec_vision_process(self, job: Job) -> bool:
        import cv2
        import numpy as np
        from datetime import datetime
        from pathlib import Path

        params = job.params
        plugin_name = params.get('plugin', '')
        input_source = params.get('input_source', 'camera')
        input_path = params.get('input_path', '')
        input_variable = params.get('input_variable', '')
        plugin_params = params.get('plugin_params', {})
        output_variable = params.get('output_variable', 'vision_result')
        save_image = params.get('save_image', False)
        save_path = params.get('save_path', '')

        self._log(f"[Vision] 영상처리 시작: plugin={plugin_name}")

        try:
            from services.vision_plugin_manager import get_vision_plugin_manager
            plugin_manager = get_vision_plugin_manager()
            plugin = plugin_manager.get_plugin(plugin_name)

            if plugin is None:
                available = plugin_manager.get_available_plugins()
                self._log(f"[Vision] 플러그인을 찾을 수 없음: {plugin_name}")
                self._log(f"[Vision] 사용 가능한 플러그인: {available}")
                return False
        except Exception as e:
            self._log(f"[Vision] 플러그인 로드 실패: {e}")
            return False

        image = None
        try:
            if input_source == 'camera':
                self._log("[Vision] 카메라 캡처 (미구현 - 테스트 이미지 사용)")
                image = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(image, "Test Image", (200, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            elif input_source == 'file':
                if not input_path:
                    self._log("[Vision] 입력 파일 경로가 지정되지 않음")
                    return False
                image = cv2.imread(input_path)
                if image is None:
                    self._log(f"[Vision] 이미지 파일을 읽을 수 없음: {input_path}")
                    return False
                self._log(f"[Vision] 파일 로드: {input_path}")

            elif input_source == 'variable':
                if not input_variable:
                    self._log("[Vision] 입력 변수명이 지정되지 않음")
                    return False
                image = self.runtime_vars.get(input_variable)
                if image is None:
                    self._log(f"[Vision] 변수에서 이미지를 찾을 수 없음: {input_variable}")
                    return False
                self._log(f"[Vision] 변수 로드: {input_variable}")

            else:
                self._log(f"[Vision] 알 수 없는 입력 소스: {input_source}")
                return False

        except Exception as e:
            self._log(f"[Vision] 이미지 취득 실패: {e}")
            return False

        try:
            self._log(f"[Vision] 플러그인 실행: {plugin_name}")
            result = plugin.process(image, plugin_params)

            if not result.get('success', False):
                self._log(f"[Vision] 플러그인 실행 실패: {result.get('message', 'Unknown error')}")
                return False

            self._log(f"[Vision] 플러그인 완료: {result.get('message', '')}")

        except Exception as e:
            self._log(f"[Vision] 플러그인 실행 중 오류: {e}")
            return False

        try:
            self.runtime_vars[output_variable] = result
            self._log(f"[Vision] 결과 저장: {output_variable}")

            if save_image and 'result_image' in result:
                result_image = result['result_image']
                if result_image is not None:
                    if not save_path:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        save_path = f"/tmp/vision_{plugin_name}_{timestamp}.png"

                    cv2.imwrite(save_path, result_image)
                    self._log(f"[Vision] 이미지 저장: {save_path}")

            if 'data' in result:
                self._log(f"[Vision] 결과 데이터: {result['data']}")

        except Exception as e:
            self._log(f"[Vision] 결과 저장 중 오류: {e}")
            return False

        return True

    def _exec_ai_inspection(self, job: Job) -> bool:
        import time

        params = job.params
        detection_task = params.get('detection_task', 'jig_latch')
        runtime = params.get('runtime', 'pc')
        confidence = params.get('confidence_threshold', 0.5)
        timeout_ms = params.get('timeout', 5000)
        wait_ms = params.get('wait_after_command', 100)

        self._log(f"[AI] 검사 시작: task={detection_task}, runtime={runtime}, conf={confidence}")

        if not self.ai_detection_service:
            self._log("[AI] AIDetectionService가 없습니다")
            return False

        models = self.ai_detection_service.get_available_models(task=detection_task, runtime=runtime)
        if not models:
            self._log(f"[AI] 모델을 찾을 수 없음: task={detection_task}, runtime={runtime}")
            return False

        model_path = models[0][1]
        for name, path in models:
            if name.startswith('best'):
                model_path = path
                break

        self._log(f"[AI] 모델 로드: {os.path.basename(model_path)}")
        if not self.ai_detection_service.load_model(model_path):
            self._log("[AI] 모델 로드 실패")
            return False

        self.ai_detection_service.set_confidence_threshold(confidence)
        angle_threshold = params.get('angle_threshold', 15.0)
        self.ai_detection_service.set_angle_threshold(angle_threshold)

        if not self.vision_manager or not self.vision_manager.gv_manager:
            self._log("[AI] VisionManager/GV Manager가 없습니다")
            return False

        if not self.ros_node:
            self._log("[AI] ROS2 노드가 없습니다")
            return False

        baseline = self.ros_node.start_techman_image_subscription()

        if not self.vision_manager.write_variable('g_robot_command', 3):
            self._log("[AI] g_robot_command=3 전송 실패")
            return False

        if not self.vision_manager.send_script_exit():
            self._log("[AI] ScriptExit() 발행 실패")
            return False

        timeout_sec = timeout_ms / 1000.0
        msg, err = self.ros_node.wait_techman_image(
            baseline, timeout_sec,
            should_stop=lambda: self._stop_requested)
        if msg is None:
            self._log(f"[AI] {err}")
            return False

        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)

        try:
            from cv_bridge import CvBridge
            bridge = CvBridge()
            cv_image = bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self._log(f"[AI] 이미지 변환 오류: {e}")
            return False

        self._log(f"[AI] 이미지 캡처 완료: {cv_image.shape}")

        try:
            result = self.ai_detection_service.run_inference(cv_image)
            if not result:
                self._log("[AI] 추론 실패")
                return False
        except Exception as e:
            self._log(f"[AI] 추론 오류: {e}")
            return False

        self._log(f"[AI] 검사 완료: task={detection_task}")
        return True
