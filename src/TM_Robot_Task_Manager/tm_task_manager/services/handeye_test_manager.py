"""Hand-Eye 정밀도 테스트 오케스트레이터 — 그리드 이동·스캔·통계·CSV (mm/deg)."""
import os
import csv
from datetime import datetime
from typing import List, Dict, Any, Tuple, Callable, Optional

import numpy as np


class HandEyeTestManager:
    """기준 자세 주변 XYZ 그리드를 지그재그 순회하며 랜드마크를 반복 측정한다.

    위치별 Y/Ry 산포는 측정 반복성, 위치 간 평균 편차(range)는 Hand-Eye
    캘리브레이션 오차의 지표다. 측정 루프의 스레딩·반복 구동은 탭 소관.
    """

    def __init__(
        self,
        job_executor=None,
        vision_manager=None,
        log_callback: Callable[[str], None] = None
    ):
        self.job_executor = job_executor
        self.vision_manager = vision_manager
        self._log_callback = log_callback

        self.test_positions: List[Dict[str, float]] = []

        self.measurements: List[Dict[str, Any]] = []

        self.is_running = False
        self.current_position_index = 0
        self.current_repeat_index = 0
        self.repeat_count = 3
        self.scan_delay_sec = 0.5

        self.on_measurement_complete: Optional[Callable[[Dict], None]] = None
        self.on_test_complete: Optional[Callable[[], None]] = None
        self.on_progress_update: Optional[Callable[[int, int], None]] = None

    def _log(self, message: str):
        if self._log_callback:
            self._log_callback(message)


    def generate_positions(
        self,
        base_position: Dict[str, float],
        x_step: float, x_count: int,
        y_step: float, y_count: int,
        z_step: float, z_count: int
    ) -> List[Dict[str, float]]:
        """기준 자세 주변 측정 그리드를 만든다.

        XY 는 ±count 대칭 오프셋(총 2·count+1 개), Z 는 0 부터 위로 count 개 층.
        자세(rx/ry/rz)는 기준값 그대로 유지한다.
        """
        self.test_positions.clear()

        x_offsets = self._generate_xy_offsets(x_step, x_count)
        y_offsets = self._generate_xy_offsets(y_step, y_count)
        z_offsets = self._generate_z_offsets(z_step, z_count)

        for z_off in z_offsets:
            xy_positions = self._generate_zigzag_xy(base_position, x_offsets, y_offsets, z_off)
            self.test_positions.extend(xy_positions)

        x_total = 2 * x_count + 1
        y_total = 2 * y_count + 1
        self._log(f"측정 위치 {len(self.test_positions)}개 생성 완료 ({x_total}x{y_total}x{z_count})")
        return self.test_positions

    def _generate_xy_offsets(self, step: float, count: int) -> List[float]:
        offsets = []
        for i in range(-count, count + 1):
            offsets.append(i * step)
        return offsets

    def _generate_z_offsets(self, step: float, count: int) -> List[float]:
        offsets = []
        for i in range(count):
            offsets.append(i * step)
        return offsets

    def _generate_zigzag_xy(self, base_position: Dict[str, float],
                           x_offsets: List[float], y_offsets: List[float],
                           z_off: float) -> List[Dict[str, float]]:
        """X 열마다 Y 방향을 번갈아 뒤집는 지그재그 순회 — 이동 거리 최소화."""
        positions = []

        for i, x_off in enumerate(x_offsets):
            if i % 2 == 0:
                y_order = y_offsets
            else:
                y_order = list(reversed(y_offsets))

            for y_off in y_order:
                pos = {
                    'x': base_position['x'] + x_off,
                    'y': base_position['y'] + y_off,
                    'z': base_position['z'] + z_off,
                    'rx': base_position['rx'],
                    'ry': base_position['ry'],
                    'rz': base_position['rz']
                }
                positions.append(pos)

        return positions

    def add_position(self, position: Dict[str, float]):
        self.test_positions.append(position)

    def remove_position(self, index: int):
        if 0 <= index < len(self.test_positions):
            del self.test_positions[index]

    def clear_positions(self):
        self.test_positions.clear()

    def get_positions(self) -> List[Dict[str, float]]:
        return self.test_positions


    def save_positions(self, filename: str) -> bool:
        if not self.test_positions:
            return False

        try:
            import yaml
            with open(filename, 'w') as f:
                yaml.dump({'positions': self.test_positions}, f, default_flow_style=False)
            self._log(f"위치 목록 저장 완료: {filename}")
            return True
        except Exception as e:
            self._log(f"위치 목록 저장 실패: {e}")
            return False

    def load_positions(self, filename: str) -> bool:
        try:
            import yaml
            with open(filename, 'r') as f:
                data = yaml.safe_load(f)
                if 'positions' in data:
                    self.test_positions = data['positions']
                    self._log(f"위치 목록 불러오기 완료: {len(self.test_positions)}개")
                    return True
            return False
        except Exception as e:
            self._log(f"위치 목록 불러오기 실패: {e}")
            return False


    def start_test(self, repeat_count: int = 3, scan_delay_sec: float = 0.5) -> Tuple[bool, str]:
        """실행 상태를 초기화하고 테스트를 시작 상태로 만든다 (실제 루프는 탭이 돌린다)."""
        if not self.test_positions:
            return False, "측정 위치가 없습니다"

        if not self.vision_manager:
            return False, "VisionManager가 초기화되지 않았습니다"

        if not self.job_executor:
            return False, "JobExecutor가 초기화되지 않았습니다"

        self.is_running = True
        self.current_position_index = 0
        self.current_repeat_index = 0
        self.repeat_count = repeat_count
        self.scan_delay_sec = scan_delay_sec
        self.measurements.clear()

        self._log(f"Hand-Eye 테스트 시작: {len(self.test_positions)}개 위치 x {repeat_count}회 반복")
        return True, "테스트 시작"

    def stop_test(self):
        self.is_running = False
        self._log("Hand-Eye 테스트 중지됨")

    def reset_test(self):
        self.measurements.clear()
        self.current_position_index = 0
        self.current_repeat_index = 0
        self.is_running = False
        self._log("테스트 결과 초기화 완료")

    def run_single_measurement(self) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """1스텝 수행: 위치 이동 → 랜드마크 스캔 → TCP 기록 → 인덱스 전진.

        스캔 실패 건도 lm_* 를 0.0 으로 채워 기록된다(success 필드로 구분) —
        통계 집계 시 success 필터 없이는 0 값이 섞인다.
        """
        if not self.is_running:
            return False, None, "테스트가 실행 중이 아닙니다"

        if self.current_position_index >= len(self.test_positions):
            self.is_running = False
            if self.on_test_complete:
                self.on_test_complete()
            return False, None, "모든 측정 완료"

        pos = self.test_positions[self.current_position_index]

        success, msg = self._move_to_position(pos)
        if not success:
            return False, None, f"위치 이동 실패: {msg}"

        scan_success, result = self._execute_landmark_scan()

        tcp = self._get_current_tcp()

        measurement = {
            'position_index': self.current_position_index + 1,
            'repeat_index': self.current_repeat_index + 1,
            'success': scan_success,
            'lm_x': result['x'] if scan_success else 0.0,
            'lm_y': result['y'] if scan_success else 0.0,
            'lm_z': result['z'] if scan_success else 0.0,
            'lm_rx': result['rx'] if scan_success else 0.0,
            'lm_ry': result['ry'] if scan_success else 0.0,
            'lm_rz': result['rz'] if scan_success else 0.0,
            'tcp_x': tcp[0],
            'tcp_y': tcp[1],
            'tcp_z': tcp[2],
            'tcp_rx': tcp[3],
            'tcp_ry': tcp[4],
            'tcp_rz': tcp[5],
            'timestamp': datetime.now().strftime("%H:%M:%S")
        }
        self.measurements.append(measurement)

        if not scan_success:
            self._log(f"Landmark 스캔 실패 (위치 {self.current_position_index + 1})")

        if self.on_measurement_complete:
            self.on_measurement_complete(measurement)

        if self.on_progress_update:
            current = len(self.measurements)
            total = len(self.test_positions) * self.repeat_count
            self.on_progress_update(current, total)

        self._advance_to_next()

        return True, measurement, "측정 완료"

    def _move_to_position(self, pos: Dict[str, float]) -> Tuple[bool, str]:
        """가드 검사 후 TMflow 스크립트 채널로 Line("CPP") 이동을 보낸다.

        send_script 클라이언트는 루트 노드 차용, 응답 대기는 호출 스레드
        spin(최대 30s). 응답 ok 는 스크립트 수리까지만 보증하므로 도달은
        고정 sleep(2.0s)으로 가정한다 — 저속·장거리에서는 미도달 상태로
        다음 단계(스캔)에 들어갈 수 있다.
        """
        if not self.job_executor:
            return False, "JobExecutor가 없습니다"

        ros_node = self.job_executor.ros_node
        if not ros_node:
            return False, "ROS 노드가 없습니다"

        from tm_msgs.srv import SendScript
        import rclpy

        send_script_client = getattr(ros_node, 'send_script_client', None)
        if not send_script_client:
            return False, "send_script 클라이언트가 없습니다"

        if not send_script_client.wait_for_service(timeout_sec=1.0):
            return False, "send_script 서비스를 사용할 수 없습니다"

        gateway = getattr(ros_node, 'motion_gateway', None)
        if gateway is not None:
            decision = gateway.check(
                'line', target_mm=[pos['x'], pos['y'], pos['z']], label='HandEye Line')
            if not decision.allowed:
                self._log(f"[안전구역] 핸드아이 이동 거부 — {decision.reason}")
                return False, decision.reason

        velocity = 50
        script = f'Line("CPP", {pos["x"]}, {pos["y"]}, {pos["z"]}, {pos["rx"]}, {pos["ry"]}, {pos["rz"]}, {velocity}, 200, 0, true)'

        request = SendScript.Request()
        request.id = "gv"
        request.script = script

        self._log(f"이동 중: ({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f})")

        future = send_script_client.call_async(request)
        rclpy.spin_until_future_complete(ros_node, future, timeout_sec=30.0)

        if future.result() is not None and future.result().ok:
            import time
            time.sleep(2.0)
            self._log(f"이동 완료: ({pos['x']:.1f}, {pos['y']:.1f}, {pos['z']:.1f})")
            return True, "이동 완료"
        else:
            return False, "Line CPP 명령 실패"

    def _execute_landmark_scan(self) -> Tuple[bool, Dict[str, float]]:
        """vision_manager 로 스캔·읽기 — 미검출·실패는 (False, 0 pose)."""
        empty_result = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0}

        if not self.vision_manager:
            return False, empty_result

        success, msg = self.vision_manager.execute_tm_landmark_scan(
            wait_time=self.scan_delay_sec,
            pause_ethernet=False
        )

        if not success:
            return False, empty_result

        read_success, result = self.vision_manager.execute_tm_landmark_read()

        if read_success and isinstance(result, dict):
            if result.get('detected', False):
                return True, result
            else:
                return False, result
        else:
            return False, empty_result

    def get_current_tcp(self) -> List[float]:
        """현재 TCP [x..rz] (mm/deg) — 읽을 수 없으면 0 벡터."""
        if self.job_executor and self.job_executor.ros_node:
            tcp = self.job_executor.ros_node.current_tcp_pose
            if tcp:
                return list(tcp)
        return [0.0] * 6

    def _get_current_tcp(self) -> List[float]:
        return self.get_current_tcp()

    def _advance_to_next(self):
        """위치 인덱스 전진 — 한 바퀴 돌면 반복 인덱스를 올리고 처음 위치로."""
        self.current_position_index += 1

        if self.current_position_index >= len(self.test_positions):
            self.current_position_index = 0
            self.current_repeat_index += 1

    def is_test_complete(self) -> bool:
        return self.current_repeat_index >= self.repeat_count

    def get_total_measurements(self) -> int:
        return len(self.test_positions) * self.repeat_count


    def calculate_statistics(self) -> Dict[str, Any]:
        """위치별 Y/Ry 평균·표준편차(ddof=1)와 위치 간 range 를 계산한다.

        success 필터 없이 전 측정을 집계하므로 스캔 실패의 0 기록도 포함된다.
        """
        if not self.measurements:
            return {}

        position_groups = {}
        for m in self.measurements:
            pos_idx = m['position_index']
            if pos_idx not in position_groups:
                position_groups[pos_idx] = []
            position_groups[pos_idx].append(m)

        position_stats = {}
        position_means_y = []
        position_means_ry = []

        for pos_idx in sorted(position_groups.keys()):
            group = position_groups[pos_idx]
            y_values = [m['lm_y'] for m in group]
            ry_values = [m['lm_ry'] for m in group]

            y_mean = float(np.mean(y_values))
            y_std = float(np.std(y_values, ddof=1)) if len(y_values) > 1 else 0.0
            ry_mean = float(np.mean(ry_values))
            ry_std = float(np.std(ry_values, ddof=1)) if len(ry_values) > 1 else 0.0

            position_stats[pos_idx] = {
                'y_mean': y_mean,
                'y_std': y_std,
                'ry_mean': ry_mean,
                'ry_std': ry_std
            }

            position_means_y.append(y_mean)
            position_means_ry.append(ry_mean)

        y_range = max(position_means_y) - min(position_means_y) if len(position_means_y) > 1 else 0.0
        ry_range = max(position_means_ry) - min(position_means_ry) if len(position_means_ry) > 1 else 0.0

        return {
            'position_stats': position_stats,
            'y_range': y_range,
            'ry_range': ry_range
        }

    def format_statistics_text(self) -> str:
        stats = self.calculate_statistics()
        if not stats:
            return "측정 데이터가 없습니다"

        text = "=== 위치별 Landmark 통계 ===\n\n"

        for pos_idx, s in stats['position_stats'].items():
            text += f"위치 {pos_idx}: Y mean={s['y_mean']:.3f} std={s['y_std']:.3f}  "
            text += f"Ry mean={s['ry_mean']:.3f} std={s['ry_std']:.3f}\n"

        if stats['y_range'] > 0 or stats['ry_range'] > 0:
            text += "\n" + "=" * 50 + "\n"
            text += f"위치간 Y 편차 (max-min): {stats['y_range']:.3f} mm (Hand-Eye 오차)\n"
            text += f"위치간 Ry 편차 (max-min): {stats['ry_range']:.3f} deg (Hand-Eye 오차)\n"

        return text


    def export_to_csv(self, filename: str) -> bool:
        if not self.measurements:
            return False

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                writer.writerow([
                    'No.', 'Pos', 'Lm_X', 'Lm_Y', 'Lm_Z', 'Lm_Rx', 'Lm_Ry', 'Lm_Rz',
                    'TCP_X', 'TCP_Y', 'TCP_Z', 'TCP_Rx', 'TCP_Ry', 'TCP_Rz', 'Time'
                ])

                for i, m in enumerate(self.measurements, 1):
                    writer.writerow([
                        i, m['position_index'],
                        m['lm_x'], m['lm_y'], m['lm_z'],
                        m['lm_rx'], m['lm_ry'], m['lm_rz'],
                        m['tcp_x'], m['tcp_y'], m['tcp_z'],
                        m['tcp_rx'], m['tcp_ry'], m['tcp_rz'],
                        m['timestamp']
                    ])

            self._log(f"CSV 저장 완료: {filename}")
            return True
        except Exception as e:
            self._log(f"CSV 저장 실패: {e}")
            return False

    def get_default_csv_path(self) -> str:
        """소스 트리의 data/<날짜>/ 아래 저장 경로를 만든다.

        install/build 경로 문자열 분해로 워크스페이스를 역산한다 — 경로에
        'install'/'build' 단어가 들어 있는 환경에서는 오동작할 수 있다.
        """
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        datetime_str = now.strftime('%Y%m%d_%H%M%S')

        pkg_dir = os.path.dirname(__file__)
        if 'install' in pkg_dir:
            ws_dir = pkg_dir.split('/install')[0]
            data_dir = os.path.join(ws_dir, 'src', 'TM_Robot_Task_Manager', 'data', date_str)
        elif 'build' in pkg_dir:
            ws_dir = pkg_dir.split('/build')[0]
            data_dir = os.path.join(ws_dir, 'src', 'TM_Robot_Task_Manager', 'data', date_str)
        else:
            data_dir = os.path.join(pkg_dir, '..', 'data', date_str)

        data_dir = os.path.abspath(data_dir)
        os.makedirs(data_dir, exist_ok=True)

        return os.path.join(data_dir, f"handeye_test_{datetime_str}.csv")

    def get_measurements(self) -> List[Dict[str, Any]]:
        return self.measurements
