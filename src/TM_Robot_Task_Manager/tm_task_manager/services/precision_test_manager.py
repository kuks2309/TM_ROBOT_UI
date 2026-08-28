import numpy as np
from typing import List, Dict, Tuple, Optional, Callable, Any
from datetime import datetime


class MeasurementData:
    def __init__(self, x: float, y: float, z: float, rx: float, ry: float, rz: float,
                 tcp_x: float = 0.0, tcp_y: float = 0.0, tcp_z: float = 0.0,
                 tcp_rx: float = 0.0, tcp_ry: float = 0.0, tcp_rz: float = 0.0,
                 timestamp: str = None):
        self.x = x
        self.y = y
        self.z = z
        self.rx = rx
        self.ry = ry
        self.rz = rz
        self.tcp_x = tcp_x
        self.tcp_y = tcp_y
        self.tcp_z = tcp_z
        self.tcp_rx = tcp_rx
        self.tcp_ry = tcp_ry
        self.tcp_rz = tcp_rz
        self.timestamp = timestamp or datetime.now().strftime("%H:%M:%S")

    def to_dict(self) -> Dict[str, any]:
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'rx': self.rx,
            'ry': self.ry,
            'rz': self.rz,
            'tcp_x': self.tcp_x,
            'tcp_y': self.tcp_y,
            'tcp_z': self.tcp_z,
            'tcp_rx': self.tcp_rx,
            'tcp_ry': self.tcp_ry,
            'tcp_rz': self.tcp_rz,
            'timestamp': self.timestamp
        }


class Statistics:
    def __init__(self):
        self.mean_x = 0.0
        self.mean_y = 0.0
        self.mean_z = 0.0
        self.mean_rx = 0.0
        self.mean_ry = 0.0
        self.mean_rz = 0.0

        self.std_x = 0.0
        self.std_y = 0.0
        self.std_z = 0.0
        self.std_rx = 0.0
        self.std_ry = 0.0
        self.std_rz = 0.0

        self.sigma3_x = 0.0
        self.sigma3_y = 0.0
        self.sigma3_z = 0.0
        self.sigma3_rx = 0.0
        self.sigma3_ry = 0.0
        self.sigma3_rz = 0.0


class PrecisionTestManager:
    def __init__(self):
        self.measurements: List[MeasurementData] = []
        self.statistics = Statistics()
        self.is_running = False
        self.test_mode = 'static'
        self.total_iterations = 50
        self.current_iteration = 0

        self.job_executor = None
        self.ros_node = None
        self.recipe = None

        self.on_log: Optional[Callable[[str], None]] = None
        self.on_measurement_added: Optional[Callable[[], None]] = None
        self.on_test_completed: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_request_next_iteration: Optional[Callable[[], None]] = None

    def _log(self, message: str):
        if self.on_log:
            self.on_log(message)

    def reset(self):
        self.measurements.clear()
        self.statistics = Statistics()
        self.current_iteration = 0
        self.is_running = False

    def add_measurement(self, x: float, y: float, z: float, rx: float, ry: float, rz: float,
                        tcp_x: float = 0.0, tcp_y: float = 0.0, tcp_z: float = 0.0,
                        tcp_rx: float = 0.0, tcp_ry: float = 0.0, tcp_rz: float = 0.0):
        measurement = MeasurementData(x, y, z, rx, ry, rz, tcp_x, tcp_y, tcp_z, tcp_rx, tcp_ry, tcp_rz)
        self.measurements.append(measurement)
        self.current_iteration = len(self.measurements)

        self._update_statistics()

    def _update_statistics(self):
        if len(self.measurements) == 0:
            return

        x_data = [m.x for m in self.measurements]
        y_data = [m.y for m in self.measurements]
        z_data = [m.z for m in self.measurements]
        rx_data = [m.rx for m in self.measurements]
        ry_data = [m.ry for m in self.measurements]
        rz_data = [m.rz for m in self.measurements]

        self.statistics.mean_x = np.mean(x_data)
        self.statistics.mean_y = np.mean(y_data)
        self.statistics.mean_z = np.mean(z_data)
        self.statistics.mean_rx = np.mean(rx_data)
        self.statistics.mean_ry = np.mean(ry_data)
        self.statistics.mean_rz = np.mean(rz_data)

        if len(self.measurements) > 1:
            self.statistics.std_x = np.std(x_data, ddof=1)
            self.statistics.std_y = np.std(y_data, ddof=1)
            self.statistics.std_z = np.std(z_data, ddof=1)
            self.statistics.std_rx = np.std(rx_data, ddof=1)
            self.statistics.std_ry = np.std(ry_data, ddof=1)
            self.statistics.std_rz = np.std(rz_data, ddof=1)

            self.statistics.sigma3_x = 3 * self.statistics.std_x
            self.statistics.sigma3_y = 3 * self.statistics.std_y
            self.statistics.sigma3_z = 3 * self.statistics.std_z
            self.statistics.sigma3_rx = 3 * self.statistics.std_rx
            self.statistics.sigma3_ry = 3 * self.statistics.std_ry
            self.statistics.sigma3_rz = 3 * self.statistics.std_rz

    def get_statistics(self) -> Statistics:
        return self.statistics

    def get_measurements_as_arrays(self) -> Dict[str, List[float]]:
        return {
            'x': [m.x for m in self.measurements],
            'y': [m.y for m in self.measurements],
            'z': [m.z for m in self.measurements],
            'rx': [m.rx for m in self.measurements],
            'ry': [m.ry for m in self.measurements],
            'rz': [m.rz for m in self.measurements]
        }

    def export_to_csv(self, filepath: str) -> bool:
        try:
            import csv

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                writer.writerow([
                    'No.',
                    'X (mm)', 'Y (mm)', 'Z (mm)', 'Rx (deg)', 'Ry (deg)', 'Rz (deg)',
                    'TCP_X (mm)', 'TCP_Y (mm)', 'TCP_Z (mm)', 'TCP_Rx (deg)', 'TCP_Ry (deg)', 'TCP_Rz (deg)',
                    '시간'
                ])

                for i, m in enumerate(self.measurements, 1):
                    writer.writerow([
                        i,
                        m.x, m.y, m.z, m.rx, m.ry, m.rz,
                        m.tcp_x, m.tcp_y, m.tcp_z, m.tcp_rx, m.tcp_ry, m.tcp_rz,
                        m.timestamp
                    ])

                writer.writerow([])
                writer.writerow(['통계 (Landmark)'])
                writer.writerow(['', 'X', 'Y', 'Z', 'Rx', 'Ry', 'Rz'])
                writer.writerow(['평균 (μ)',
                               f'{self.statistics.mean_x:.4f}',
                               f'{self.statistics.mean_y:.4f}',
                               f'{self.statistics.mean_z:.4f}',
                               f'{self.statistics.mean_rx:.4f}',
                               f'{self.statistics.mean_ry:.4f}',
                               f'{self.statistics.mean_rz:.4f}'])
                writer.writerow(['표준편차 (σ)',
                               f'{self.statistics.std_x:.4f}',
                               f'{self.statistics.std_y:.4f}',
                               f'{self.statistics.std_z:.4f}',
                               f'{self.statistics.std_rx:.4f}',
                               f'{self.statistics.std_ry:.4f}',
                               f'{self.statistics.std_rz:.4f}'])
                writer.writerow(['3σ 범위',
                               f'±{self.statistics.sigma3_x:.4f}',
                               f'±{self.statistics.sigma3_y:.4f}',
                               f'±{self.statistics.sigma3_z:.4f}',
                               f'±{self.statistics.sigma3_rx:.4f}',
                               f'±{self.statistics.sigma3_ry:.4f}',
                               f'±{self.statistics.sigma3_rz:.4f}'])

            return True

        except Exception as e:
            print(f"CSV 내보내기 오류: {e}")
            return False

    def get_progress_percentage(self) -> float:
        if self.total_iterations == 0:
            return 0.0
        return (self.current_iteration / self.total_iterations) * 100.0


    def start_dynamic_test(self, recipe, job_executor, ros_node) -> Tuple[bool, str]:
        if not recipe or not recipe.jobs:
            return False, "동적 테스트를 위해 Recipe를 먼저 로드해주세요."

        has_measure_end = any(
            job.type == 'measure_point' and job.params.get('point_type') == 'end'
            for job in recipe.jobs
        )

        if not has_measure_end:
            return False, "Recipe에 측정점(end 타입)이 없습니다.\nRecipe에 '측정점' Job을 추가하고 point_type을 'end'로 설정해주세요."

        self.recipe = recipe
        self.job_executor = job_executor
        self.ros_node = ros_node

        self.is_running = True
        self._log(f"동적 테스트 시작: {self.total_iterations}회 반복")

        self.run_next_iteration()

        return True, "동적 테스트 시작됨"

    def run_next_iteration(self):
        if not self.is_running:
            self._finish_test()
            return

        if self.current_iteration >= self.total_iterations:
            self._finish_test()
            return

        self._log(f"동적 테스트 반복 {self.current_iteration + 1}/{self.total_iterations}")

        self.job_executor.on_measure_point = self.on_measure_point_reached

        self.job_executor.on_state_changed = self._on_executor_state_changed

        self.job_executor.load_recipe(self.recipe)
        self.job_executor.run()

    def _on_executor_state_changed(self, state):
        from ..job_executor import ExecutionState
        self._log(f"[DEBUG] Executor state changed: {state}")
        if state == ExecutionState.COMPLETED:
            self._log(f"[DEBUG] Recipe 완료, on_recipe_completed 호출")
            self.on_recipe_completed()

    def on_measure_point_reached(self):
        if not self.ros_node:
            self._log("ROS 노드가 없습니다")
            return

        tcp = getattr(self.ros_node, 'current_tcp_pose', None)
        if tcp and len(tcp) >= 6:
            self.add_measurement(tcp[0], tcp[1], tcp[2], tcp[3], tcp[4], tcp[5])
            self._log(f"측정 완료: X={tcp[0]:.3f}, Y={tcp[1]:.3f}, Z={tcp[2]:.3f}")

            if self.on_measurement_added:
                self.on_measurement_added()
        else:
            self._log("TCP 위치를 읽을 수 없습니다")

    def on_recipe_completed(self):
        if not self.is_running:
            self._finish_test()
            return

        if self.current_iteration >= self.total_iterations:
            self._finish_test()
            return

        if self.on_request_next_iteration:
            self.on_request_next_iteration()

    def _finish_test(self):
        self.is_running = False
        self._log(f"정밀도 테스트 완료: 총 {self.current_iteration}회 측정")

        if self.on_test_completed:
            self.on_test_completed()
