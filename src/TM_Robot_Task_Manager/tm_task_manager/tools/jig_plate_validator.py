#!/usr/bin/env python3
"""지그 플레이트 4점 무결성 검사기 + 독립 실행 GUI (mm/deg).

검증 코어(JigPlateValidator)는 plate_pose_dataset 등 헤드리스 사용처도 쓰지만,
모듈 상단에서 PyQt5·matplotlib 를 무조건 import 하므로 그 사용처도 GUI
의존성이 연쇄 로드된다.
"""
import sys
import os
import math
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import yaml
import numpy as np

try:
    from .. import paths
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import paths

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QVBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5 import uic

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

try:
    import matplotlib.font_manager as fm
    korean_fonts = [f.name for f in fm.fontManager.ttflist if 'Noto Sans CJK' in f.name or 'NanumGothic' in f.name]
    if korean_fonts:
        plt.rcParams['font.family'] = korean_fonts[0]
    else:
        plt.rcParams['font.family'] = 'DejaVu Sans'
except Exception:
    plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

LANDMARK_SIZE = 40.0


def rotation_matrix_from_euler(rx, ry, rz):
    """오일러 각(deg)에서 Rz@Ry@Rx 합성 3x3 회전행렬을 만든다."""
    rx, ry, rz = np.radians(rx), np.radians(ry), np.radians(rz)

    Rx = np.array([[1, 0, 0],
                   [0, np.cos(rx), -np.sin(rx)],
                   [0, np.sin(rx), np.cos(rx)]])

    Ry = np.array([[np.cos(ry), 0, np.sin(ry)],
                   [0, 1, 0],
                   [-np.sin(ry), 0, np.cos(ry)]])

    Rz = np.array([[np.cos(rz), -np.sin(rz), 0],
                   [np.sin(rz), np.cos(rz), 0],
                   [0, 0, 1]])

    return Rz @ Ry @ Rx


def get_landmark_corners(x, y, z, rx, ry, rz, size=LANDMARK_SIZE):
    """랜드마크 정사각형(size mm)의 4꼭짓점 월드 좌표 (4,3) 배열 — 3D 표시용."""
    half = size / 2.0
    corners_local = np.array([
        [-half, -half, 0],
        [half, -half, 0],
        [half, half, 0],
        [-half, half, 0]
    ])

    R = rotation_matrix_from_euler(rx, ry, rz)
    corners_rotated = corners_local @ R.T

    corners_world = corners_rotated + np.array([x, y, z])

    return corners_world


@dataclass
class Mark:
    """마크 한 점의 6축 측정값 (x/y/z mm, rx/ry/rz deg)."""
    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float


@dataclass
class ValidationResult:
    """검사 항목 하나의 결과 (측정값·허용값·합격 여부)."""
    name: str
    value: float
    threshold: float
    unit: str
    passed: bool

    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"  {self.name}: {self.value:.2f}{self.unit} (허용: ±{self.threshold}{self.unit}) {status}"


class JigPlateValidator:
    """4점 마크의 기하 무결성(직사각·평행도·Z 편차)을 검사한다.

    마크 순서 계약은 JigPlaneCalculator 와 동일: 1=좌하, 2=좌상, 3=우하, 4=우상.
    """

    # 허용값 — 변/대각 차 mm, 각도 deg
    TOLERANCE_SIDE_DIFF = 1.0
    TOLERANCE_DIAGONAL_DIFF = 1.0
    TOLERANCE_ANGLE = 0.5
    TOLERANCE_PARALLELISM = 1.0
    TOLERANCE_Z_DEVIATION = 1.0

    def __init__(self):
        self.marks: List[Mark] = []
        self.jig_landmark: Optional[Mark] = None
        self.results: List[ValidationResult] = []

    def load_from_yaml(self, yaml_path: str) -> bool:
        """positions.yaml 형식에서 jig_landmark(선택)와 jig_plate 4점을 읽는다."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            coord_defs = data.get('coordinate_definitions', {})

            jig_landmark_data = coord_defs.get('jig_landmark', {})
            if jig_landmark_data:
                scan_data = jig_landmark_data.get('scan_data', {})
                landmark_pose = scan_data.get('landmark', {})
                if landmark_pose:
                    self.jig_landmark = Mark(
                        x=landmark_pose.get('x', 0),
                        y=landmark_pose.get('y', 0),
                        z=landmark_pose.get('z', 0),
                        rx=landmark_pose.get('rx', 0),
                        ry=landmark_pose.get('ry', 0),
                        rz=landmark_pose.get('rz', 0)
                    )
                else:
                    self.jig_landmark = None

            jig_plate_data = coord_defs.get('jig_plate', {})
            scan_data = jig_plate_data.get('scan_data', [])

            self.marks = []
            for item in scan_data:
                landmark = item.get('landmark', {})
                self.marks.append(Mark(
                    x=landmark.get('x', 0),
                    y=landmark.get('y', 0),
                    z=landmark.get('z', 0),
                    rx=landmark.get('rx', 0),
                    ry=landmark.get('ry', 0),
                    rz=landmark.get('rz', 0)
                ))

            return len(self.marks) == 4

        except Exception as e:
            print(f"YAML 로드 오류: {e}")
            return False

    def load_from_dicts(self, mark_dicts: List[Dict[str, float]]) -> bool:
        """dict 4개로 마크를 로드한다 (jig_landmark 는 비운다)."""
        if len(mark_dicts) != 4:
            print(f"4개의 mark가 필요합니다 (입력: {len(mark_dicts)}개)")
            return False

        self.marks = [
            Mark(x=d['x'], y=d['y'], z=d['z'],
                 rx=d.get('rx', 0.0), ry=d.get('ry', 0.0), rz=d.get('rz', 0.0))
            for d in mark_dicts
        ]
        self.jig_landmark = None
        self.results = []
        return True

    def get_side_lengths(self) -> Dict[str, float]:
        """변 4개 + 대각 2개 거리(mm) dict."""
        if len(self.marks) != 4:
            return {}

        m = self.marks
        return {
            'jig1-jig3': self._distance(m[0], m[2]),
            'jig2-jig4': self._distance(m[1], m[3]),
            'jig1-jig2': self._distance(m[0], m[1]),
            'jig3-jig4': self._distance(m[2], m[3]),
            'jig1-jig4': self._distance(m[0], m[3]),
            'jig2-jig3': self._distance(m[1], m[2]),
        }

    def _distance(self, m1: Mark, m2: Mark) -> float:
        return math.sqrt(
            (m2.x - m1.x)**2 +
            (m2.y - m1.y)**2 +
            (m2.z - m1.z)**2
        )

    def _angle_between_vectors(self, v1: Tuple[float, float, float],
                                v2: Tuple[float, float, float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a**2 for a in v1))
        mag2 = math.sqrt(sum(a**2 for a in v2))

        if mag1 == 0 or mag2 == 0:
            return 0

        cos_angle = dot / (mag1 * mag2)
        cos_angle = max(-1, min(1, cos_angle))
        return math.degrees(math.acos(cos_angle))

    def check_rectangle(self) -> List[ValidationResult]:
        """대향변 차·대각선 차(mm)·직각 오차(deg)로 직사각형 여부를 검사한다."""
        results = []
        m = self.marks

        if len(m) != 4:
            return results

        side_bottom = self._distance(m[0], m[2])
        side_top = self._distance(m[1], m[3])
        side_left = self._distance(m[0], m[1])
        side_right = self._distance(m[2], m[3])

        diff_horizontal = abs(side_bottom - side_top)
        diff_vertical = abs(side_left - side_right)

        results.append(ValidationResult(
            name="대향변(수평) 차이",
            value=diff_horizontal,
            threshold=self.TOLERANCE_SIDE_DIFF,
            unit="mm",
            passed=diff_horizontal <= self.TOLERANCE_SIDE_DIFF
        ))

        results.append(ValidationResult(
            name="대향변(수직) 차이",
            value=diff_vertical,
            threshold=self.TOLERANCE_SIDE_DIFF,
            unit="mm",
            passed=diff_vertical <= self.TOLERANCE_SIDE_DIFF
        ))

        diag1 = self._distance(m[0], m[3])
        diag2 = self._distance(m[1], m[2])
        diag_diff = abs(diag1 - diag2)

        results.append(ValidationResult(
            name="대각선 차이",
            value=diag_diff,
            threshold=self.TOLERANCE_DIAGONAL_DIFF,
            unit="mm",
            passed=diag_diff <= self.TOLERANCE_DIAGONAL_DIFF
        ))

        v1 = (m[2].x - m[0].x, m[2].y - m[0].y, m[2].z - m[0].z)
        v2 = (m[1].x - m[0].x, m[1].y - m[0].y, m[1].z - m[0].z)
        angle = self._angle_between_vectors(v1, v2)
        angle_error = abs(90.0 - angle)

        results.append(ValidationResult(
            name="직각 오차",
            value=angle_error,
            threshold=self.TOLERANCE_ANGLE,
            unit="°",
            passed=angle_error <= self.TOLERANCE_ANGLE
        ))

        return results

    def check_plane_parallelism(self) -> List[ValidationResult]:
        """jig_landmark 대비 마크들의 Ry 최대 편차(deg) — 기준 랜드마크 없으면 빈 목록."""
        results = []
        m = self.marks

        if len(m) != 4 or self.jig_landmark is None:
            return results

        ry_values = [mark.ry for mark in m]
        ry_landmark = self.jig_landmark.ry

        ry_max_diff = max(abs(ry - ry_landmark) for ry in ry_values)

        results.append(ValidationResult(
            name="평면 평행도 (Ry)",
            value=ry_max_diff,
            threshold=self.TOLERANCE_PARALLELISM,
            unit="°",
            passed=ry_max_diff <= self.TOLERANCE_PARALLELISM
        ))

        return results

    def check_z_consistency(self) -> List[ValidationResult]:
        """마크 Z 의 평균 대비 최대 편차(mm)를 검사한다."""
        results = []

        if len(self.marks) != 4:
            return results

        z_values = [m.z for m in self.marks]
        z_mean = sum(z_values) / len(z_values)
        z_max_deviation = max(abs(z - z_mean) for z in z_values)

        results.append(ValidationResult(
            name="Z 높이 편차",
            value=z_max_deviation,
            threshold=self.TOLERANCE_Z_DEVIATION,
            unit="mm",
            passed=z_max_deviation <= self.TOLERANCE_Z_DEVIATION
        ))

        return results

    def run_validation(self) -> str:
        """전 검사를 수행해 results 를 채우고 텍스트 리포트를 돌려준다."""
        from datetime import datetime
        self.results = []

        report_lines = []
        report_lines.append("=" * 50)
        report_lines.append("     Jig Plate 무결성 검사 결과")
        report_lines.append(f"     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 50)
        report_lines.append("")

        report_lines.append("[Mark 좌표]")
        for i, m in enumerate(self.marks, 1):
            report_lines.append(f"  Mark {i}: ({m.x:.2f}, {m.y:.2f}, {m.z:.2f}) Rx={m.rx:.2f}, Ry={m.ry:.2f}, Rz={m.rz:.2f}")
        report_lines.append("")

        if len(self.marks) == 4:
            m = self.marks
            report_lines.append("[변 길이]")
            report_lines.append(f"  하단 (1→3): {self._distance(m[0], m[2]):.2f}mm")
            report_lines.append(f"  상단 (2→4): {self._distance(m[1], m[3]):.2f}mm")
            report_lines.append(f"  좌측 (1→2): {self._distance(m[0], m[1]):.2f}mm")
            report_lines.append(f"  우측 (3→4): {self._distance(m[2], m[3]):.2f}mm")
            report_lines.append("")

        report_lines.append("[직사각형 검사]")
        rect_results = self.check_rectangle()
        self.results.extend(rect_results)
        for r in rect_results:
            report_lines.append(str(r))
        report_lines.append("")

        report_lines.append("[평행도 검사]")
        para_results = self.check_plane_parallelism()
        self.results.extend(para_results)
        for r in para_results:
            report_lines.append(str(r))
        report_lines.append("")

        report_lines.append("[Z 높이 검사]")
        z_results = self.check_z_consistency()
        self.results.extend(z_results)
        for r in z_results:
            report_lines.append(str(r))
        report_lines.append("")

        all_passed = all(r.passed for r in self.results)
        failed_count = sum(1 for r in self.results if not r.passed)

        report_lines.append("=" * 50)
        if all_passed:
            report_lines.append("  [최종 결과] ✅ PASS - 모든 검사 통과")
        else:
            report_lines.append(f"  [최종 결과] ❌ FAIL - {failed_count}개 항목 불합격")
        report_lines.append("=" * 50)

        return "\n".join(report_lines)

    def calculate_center(self) -> Optional[Mark]:
        """4점 산술 평균 중심 pose.

        rx 만 ±180° 랩어라운드를 보정한다 (마크가 대개 rx 180° 근방이라 부호가
        갈리기 때문) — ry·rz 는 단순 산술 평균.
        """
        if len(self.marks) != 4:
            return None

        x = sum(m.x for m in self.marks) / 4
        y = sum(m.y for m in self.marks) / 4
        z = sum(m.z for m in self.marks) / 4

        rx_values = [m.rx for m in self.marks]
        if any(rx < -90 for rx in rx_values) and any(rx > 90 for rx in rx_values):
            rx_values = [rx + 360 if rx < 0 else rx for rx in rx_values]
        rx = sum(rx_values) / 4
        if rx > 180:
            rx -= 360

        ry = sum(m.ry for m in self.marks) / 4
        rz = sum(m.rz for m in self.marks) / 4

        return Mark(x=x, y=y, z=z, rx=rx, ry=ry, rz=rz)


class ValidatorWindow(QMainWindow):
    """단독 실행 GUI — yaml 로드→검사→2D/Z바/3D 시각화·리포트 저장."""

    def __init__(self):
        super().__init__()

        try:
            from ament_index_python.packages import get_package_share_directory
            package_share = get_package_share_directory('tm_task_manager')
            ui_path = Path(package_share) / "ui" / "jig_plate_validator.ui"
        except Exception:
            ui_path = Path(__file__).parent.parent.parent / "ui" / "jig_plate_validator.ui"
        uic.loadUi(str(ui_path), self)

        self.validator = JigPlateValidator()
        self.yaml_path = None

        self._setup_plots()

        self._connect_signals()

        self._try_load_default_yaml()

    def _setup_plots(self):
        self.fig_2d = Figure(figsize=(5, 4))
        self.canvas_2d = FigureCanvas(self.fig_2d)
        self.ax_2d = self.fig_2d.add_subplot(111)

        layout_2d = self.widget_2dPlot.layout()
        if layout_2d is None:
            layout_2d = QVBoxLayout(self.widget_2dPlot)
        layout_2d.addWidget(self.canvas_2d)

        self.fig_z = Figure(figsize=(5, 2))
        self.canvas_z = FigureCanvas(self.fig_z)
        self.ax_z = self.fig_z.add_subplot(111)

        layout_z = self.widget_zPlot.layout()
        if layout_z is None:
            layout_z = QVBoxLayout(self.widget_zPlot)
        layout_z.addWidget(self.canvas_z)

        self.fig_3d = Figure(figsize=(6, 5))
        self.canvas_3d = FigureCanvas(self.fig_3d)
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')

        layout_3d = self.widget_3dPlot.layout()
        if layout_3d is None:
            layout_3d = QVBoxLayout(self.widget_3dPlot)
        layout_3d.addWidget(self.canvas_3d)

    def _connect_signals(self):
        self.pushButton_loadYaml.clicked.connect(self._on_load_yaml)
        self.pushButton_runValidation.clicked.connect(self._on_run_validation)
        self.pushButton_saveReport.clicked.connect(self._on_save_report)

    def _get_jig_data_dir(self) -> Path:
        """data/jig_mark 의 최신 날짜 폴더 (없으면 config 폴더 폴백)."""
        src_data = Path(__file__).resolve()
        for _ in range(3):
            src_data = src_data.parent
        jig_dir = src_data / "data" / "jig_mark"
        if jig_dir.exists():
            date_dirs = sorted([d for d in jig_dir.iterdir() if d.is_dir()], reverse=True)
            if date_dirs:
                return date_dirs[0]
            return jig_dir
        return src_data / "config"

    def _try_load_default_yaml(self):
        data_dir = self._get_jig_data_dir()
        yaml_files = sorted(data_dir.glob("jig_plate_*.yaml"), reverse=True)
        if yaml_files:
            self._load_yaml(str(yaml_files[0]))
            return
        default_path = Path(paths.config("positions.yaml"))
        if default_path.exists():
            self._load_yaml(str(default_path))

    def _on_load_yaml(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "YAML 파일 선택",
            str(self._get_jig_data_dir()),
            "YAML Files (*.yaml *.yml)"
        )

        if file_path:
            self._load_yaml(file_path)

    def _load_yaml(self, file_path: str):
        if self.validator.load_from_yaml(file_path):
            self.yaml_path = file_path
            self.label_yamlPath.setText(f"YAML: {Path(file_path).name}")
            self.statusbar.showMessage(f"로드 완료: {file_path}")

            self._on_run_validation()
        else:
            QMessageBox.warning(self, "오류", "YAML 파일 로드 실패")

    def _on_run_validation(self):
        if not self.validator.marks:
            QMessageBox.warning(self, "오류", "먼저 YAML 파일을 로드하세요")
            return

        report = self.validator.run_validation()
        self.textEdit_results.setPlainText(report)

        self._update_2d_plot()
        self._update_z_plot()
        self._update_3d_plot()

        self.statusbar.showMessage("검사 완료")

    def _update_2d_plot(self):
        self.ax_2d.clear()

        m = self.validator.marks
        if len(m) != 4:
            return

        x_actual = [m[0].x, m[1].x, m[3].x, m[2].x, m[0].x]
        y_actual = [m[0].y, m[1].y, m[3].y, m[2].y, m[0].y]

        self.ax_2d.plot(x_actual, y_actual, 'b-o', linewidth=2, markersize=8, label='실제')

        for i, mark in enumerate(m, 1):
            self.ax_2d.annotate(f'{i}', (mark.x, mark.y),
                               textcoords="offset points", xytext=(5, 5),
                               fontsize=12, fontweight='bold')

        center = self.validator.calculate_center()
        if center:
            self.ax_2d.plot(center.x, center.y, 'g*', markersize=15, label='중심')

        avg_width = (self.validator._distance(m[0], m[2]) +
                     self.validator._distance(m[1], m[3])) / 2
        avg_height = (self.validator._distance(m[0], m[1]) +
                      self.validator._distance(m[2], m[3])) / 2

        x_ideal = [m[0].x, m[0].x, m[0].x + avg_width, m[0].x + avg_width, m[0].x]
        y_ideal = [m[0].y, m[0].y + avg_height, m[0].y + avg_height, m[0].y, m[0].y]
        self.ax_2d.plot(x_ideal, y_ideal, 'r--', linewidth=1, alpha=0.5, label='이상')

        self.ax_2d.set_xlabel('X (mm)')
        self.ax_2d.set_ylabel('Y (mm)')
        self.ax_2d.legend(loc='best')
        self.ax_2d.grid(True, alpha=0.3)
        self.ax_2d.set_aspect('equal')

        self.fig_2d.tight_layout()
        self.canvas_2d.draw()

    def _update_z_plot(self):
        self.ax_z.clear()

        m = self.validator.marks
        if len(m) != 4:
            return

        z_values = [mark.z for mark in m]
        z_mean = sum(z_values) / len(z_values)

        x_pos = [1, 2, 3, 4]
        colors = []
        for z in z_values:
            if abs(z - z_mean) <= self.validator.TOLERANCE_Z_DEVIATION:
                colors.append('green')
            else:
                colors.append('red')

        self.ax_z.bar(x_pos, z_values, color=colors, alpha=0.7)
        self.ax_z.axhline(y=z_mean, color='blue', linestyle='--', linewidth=2, label=f'평균: {z_mean:.2f}mm')

        self.ax_z.axhline(y=z_mean + self.validator.TOLERANCE_Z_DEVIATION,
                         color='orange', linestyle=':', alpha=0.5)
        self.ax_z.axhline(y=z_mean - self.validator.TOLERANCE_Z_DEVIATION,
                         color='orange', linestyle=':', alpha=0.5)

        self.ax_z.set_xlabel('Mark')
        self.ax_z.set_ylabel('Z (mm)')
        self.ax_z.set_xticks(x_pos)
        self.ax_z.legend(loc='best')
        self.ax_z.grid(True, alpha=0.3, axis='y')

        self.fig_z.tight_layout()
        self.canvas_z.draw()

    def _update_3d_plot(self):
        self.ax_3d.clear()

        if len(self.validator.marks) != 4:
            self.ax_3d.text(0.5, 0.5, 0.5, '4개 mark 필요\n(현재: {}개)'.format(len(self.validator.marks)),
                            ha='center', va='center', fontsize=12,
                            transform=self.ax_3d.transAxes)
            self.fig_3d.tight_layout()
            self.canvas_3d.draw()
            return

        m = self.validator.marks

        all_points = []

        if self.validator.jig_landmark:
            jl = self.validator.jig_landmark
            corners = get_landmark_corners(jl.x, jl.y, jl.z, jl.rx, jl.ry, jl.rz)
            verts = [list(zip(corners[:, 0], corners[:, 1], corners[:, 2]))]
            poly = Poly3DCollection(verts, alpha=0.7, facecolor='green', edgecolor='darkgreen', linewidths=2)
            self.ax_3d.add_collection3d(poly)

            self.ax_3d.scatter([jl.x], [jl.y], [jl.z], c='darkgreen', marker='o', s=50)

            R_jl = rotation_matrix_from_euler(jl.rx, jl.ry, jl.rz)
            normal_jl = R_jl @ np.array([0, 0, 1])
            arrow_len = 30.0
            self.ax_3d.quiver(jl.x, jl.y, jl.z,
                              normal_jl[0] * arrow_len, normal_jl[1] * arrow_len, normal_jl[2] * arrow_len,
                              color='darkgreen', arrow_length_ratio=0.15, linewidth=2)

            all_points.append([jl.x, jl.y, jl.z])
            all_points.extend(corners.tolist())

        arrow_len = 30.0
        for i, mark in enumerate(m, start=1):
            corners = get_landmark_corners(mark.x, mark.y, mark.z, mark.rx, mark.ry, mark.rz)
            verts = [list(zip(corners[:, 0], corners[:, 1], corners[:, 2]))]

            poly = Poly3DCollection(verts, alpha=0.5, facecolor='blue', edgecolor='darkblue', linewidths=1)
            self.ax_3d.add_collection3d(poly)

            self.ax_3d.scatter([mark.x], [mark.y], [mark.z], c='darkblue', marker='o', s=30)

            R_mk = rotation_matrix_from_euler(mark.rx, mark.ry, mark.rz)
            normal_mk = R_mk @ np.array([0, 0, 1])
            self.ax_3d.quiver(mark.x, mark.y, mark.z,
                              normal_mk[0] * arrow_len, normal_mk[1] * arrow_len, normal_mk[2] * arrow_len,
                              color='darkblue', arrow_length_ratio=0.15, linewidth=1.5)

            self.ax_3d.text(mark.x, mark.y, mark.z + 5, f'Mark {i}',
                            fontsize=10, ha='center', va='bottom')

            all_points.append([mark.x, mark.y, mark.z])
            all_points.extend(corners.tolist())

        if all_points:
            all_points = np.array(all_points)
            center = all_points.mean(axis=0)
            max_range = (all_points.max(axis=0) - all_points.min(axis=0)).max() / 2 + LANDMARK_SIZE

            self.ax_3d.set_xlim(center[0] - max_range, center[0] + max_range)
            self.ax_3d.set_ylim(center[1] - max_range, center[1] + max_range)
            self.ax_3d.set_zlim(center[2] - max_range, center[2] + max_range)

        self.ax_3d.set_xlabel('X (mm)')
        self.ax_3d.set_ylabel('Y (mm)')
        self.ax_3d.set_zlabel('Z (mm)')
        self.ax_3d.set_title('3D 랜드마크 시각화')

        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
        legend_elements = []
        if self.validator.jig_landmark:
            legend_elements.append(Patch(facecolor='green', edgecolor='darkgreen', alpha=0.7, label='Jig Landmark'))
        legend_elements.append(Patch(facecolor='blue', edgecolor='darkblue', alpha=0.5, label='Jig Plate Marks'))
        legend_elements.append(Line2D([0], [0], color='gray', linewidth=2,
                                      marker='>', markersize=5, label='Normal Vector'))
        if legend_elements:
            self.ax_3d.legend(handles=legend_elements, loc='upper left', fontsize=8)

        self.ax_3d.set_box_aspect([1, 1, 1])

        self.fig_3d.tight_layout()
        self.canvas_3d.draw()

    def _on_save_report(self):
        report_text = self.textEdit_results.toPlainText()
        if not report_text:
            QMessageBox.warning(self, "오류", "저장할 리포트가 없습니다")
            return

        now = datetime.now()
        date_folder = now.strftime("%Y%m%d")
        datetime_str = now.strftime("%Y%m%d_%H%M%S")

        report_dir = Path(__file__).parent.parent.parent.parent / "Report" / date_folder
        report_dir.mkdir(parents=True, exist_ok=True)

        default_filename = f"jig_plate_report_{datetime_str}.txt"
        default_path = report_dir / default_filename

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "리포트 저장",
            str(default_path),
            "Text Files (*.txt)"
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            self.statusbar.showMessage(f"리포트 저장 완료: {file_path}")


def main():
    """CLI: QApplication 기동 후 --config yaml 이 있으면 즉시 로드·검사한다."""
    parser = argparse.ArgumentParser(description='Jig Plate 무결성 검사기')
    parser.add_argument('--config', '-c', type=str, help='YAML 설정 파일 경로')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = ValidatorWindow()

    if args.config:
        window._load_yaml(args.config)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
