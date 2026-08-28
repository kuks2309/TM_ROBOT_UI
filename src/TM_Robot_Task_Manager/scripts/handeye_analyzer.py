#!/usr/bin/env python3
"""Hand-Eye 캘리브레이션 테스트 CSV(handeye_test_*.csv)의 반복정밀도(σ·3σ)·히트맵·상관을 표시하는 PyQt5 오프라인 분석기.

실행: python3 scripts/handeye_analyzer.py [csv경로] (ROS 불필요, 단독 데스크톱 앱)
"""
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = SCRIPT_DIR.parent
UI_DIR = PACKAGE_DIR / "ui"
DATA_DIR = PACKAGE_DIR / "data"

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFileDialog,
    QMessageBox, QTableWidgetItem
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5 import uic

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = ['DejaVu Sans', 'NanumGothic', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


class ZoomableGraphWidget(QWidget):
    """휠 줌(커서 기준)·더블클릭 원래 범위 복원을 지원하는 matplotlib 캔버스 위젯."""

    def __init__(self, parent=None, title="", compact=False):
        super().__init__(parent)
        self.title = title
        self.compact = compact
        self._xlim_orig = None
        self._ylim_orig = None
        self.setup_ui()

    def setup_ui(self):
        """Figure·캔버스·툴바를 구성하고 스크롤/클릭 이벤트를 연결한다."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.compact:
            self.figure = Figure(figsize=(3.5, 2.8), dpi=100)
        else:
            self.figure = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        self.toolbar = NavigationToolbar(self.canvas, self)
        if self.compact:
            self.toolbar.setVisible(False)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.canvas.mpl_connect('scroll_event', self._on_scroll)
        self.canvas.mpl_connect('button_press_event', self._on_double_click)

    def _on_scroll(self, event):
        if event.inaxes != self.ax:
            return

        scale_factor = 1.2
        if event.button == 'up':
            scale = 1 / scale_factor
        elif event.button == 'down':
            scale = scale_factor
        else:
            return

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return
        new_xlim = [xdata - (xdata - xlim[0]) * scale,
                    xdata + (xlim[1] - xdata) * scale]
        new_ylim = [ydata - (ydata - ylim[0]) * scale,
                    ydata + (ylim[1] - ydata) * scale]

        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.canvas.draw_idle()

    def _on_double_click(self, event):
        if event.dblclick and self._xlim_orig and self._ylim_orig:
            self.ax.set_xlim(self._xlim_orig)
            self.ax.set_ylim(self._ylim_orig)
            self.canvas.draw_idle()

    def save_original_limits(self):
        """현재 축 범위를 더블클릭 복원용 원본으로 저장한다."""
        self._xlim_orig = self.ax.get_xlim()
        self._ylim_orig = self.ax.get_ylim()

    def clear(self):
        self.ax.clear()

    def set_equal_aspect(self):
        self.ax.set_aspect('equal', adjustable='datalim')

    def draw(self):
        """레이아웃 정리 후 렌더링하고 축 범위를 원본으로 저장한다."""
        self.figure.tight_layout()
        self.canvas.draw()
        self.save_original_limits()


class HandEyeDataAnalyzer:
    """Hand-Eye 측정 DataFrame 에서 전체·위치별 통계(mm/deg)를 산출·보관한다."""

    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.position_stats = None
        self.overall_stats = None
        self._analyze()

    def _analyze(self):
        self._calculate_overall_stats()
        self._calculate_position_stats()

    def _normalize_angle(self, angles: pd.Series) -> pd.Series:
        result = angles.copy()

        # ±180° 경계에 걸친 각도열은 음수쪽을 +360° 시프트해 랩을 풀어야 σ 가 왜곡되지 않는다.
        if angles.max() - angles.min() > 180:
            result = angles.apply(lambda x: x + 360 if x < 0 else x)

        return result

    def _calculate_overall_stats(self):
        cols = {
            'Lm_X': 'Lm_X', 'Lm_Y': 'Lm_Y', 'Lm_Z': 'Lm_Z',
            'Lm_Rx': 'Lm_Rx', 'Lm_Ry': 'Lm_Ry', 'Lm_Rz': 'Lm_Rz'
        }

        self.overall_stats = {}
        for key, col in cols.items():
            if col in self.data.columns:
                values = self.data[col].dropna()

                if key == 'Lm_Rx':
                    values = self._normalize_angle(values)

                self.overall_stats[key] = {
                    'mean': values.mean(),
                    'std': values.std(),
                    '3sigma': 3 * values.std(),
                    'min': values.min(),
                    'max': values.max(),
                    'range': values.max() - values.min()
                }

    def _calculate_position_stats(self):
        if 'Pos' not in self.data.columns:
            return

        self.position_stats = []
        for pos in sorted(self.data['Pos'].unique()):
            pos_data = self.data[self.data['Pos'] == pos]

            stats = {
                'pos': int(pos),
                'count': len(pos_data),
                'tcp_x': pos_data['TCP_X'].mean() if 'TCP_X' in pos_data.columns else 0,
                'tcp_y': pos_data['TCP_Y'].mean() if 'TCP_Y' in pos_data.columns else 0,
                'tcp_z': pos_data['TCP_Z'].mean() if 'TCP_Z' in pos_data.columns else 0,
            }

            for col in ['Lm_X', 'Lm_Y', 'Lm_Z', 'Lm_Rx', 'Lm_Ry', 'Lm_Rz']:
                if col in pos_data.columns:
                    values = pos_data[col].dropna()
                    if col == 'Lm_Rx':
                        values = self._normalize_angle(values)
                    stats[f'{col}_std'] = values.std() if len(values) > 1 else 0
                    stats[f'{col}_mean'] = values.mean()

            self.position_stats.append(stats)

    def get_unique_positions(self) -> int:
        """측정 위치(Pos) 수를 반환한다."""
        if 'Pos' in self.data.columns:
            return self.data['Pos'].nunique()
        return 0

    def get_repeat_count(self) -> int:
        """위치당 반복 횟수(총 행수/위치수)를 반환한다."""
        if 'Pos' in self.data.columns:
            return int(len(self.data) / self.data['Pos'].nunique())
        return 0

    def get_success_rate(self) -> float:
        """성공률(%) — CSV 에 실패 판정 컬럼이 없어 100.0 고정값을 돌려준다."""
        return 100.0

    def get_z_levels(self) -> List[float]:
        """TCP_Z(mm)를 정수 반올림한 고유 높이 목록을 반환한다(히트맵 Z 필터용)."""
        if 'TCP_Z' in self.data.columns:
            return sorted(self.data['TCP_Z'].round(0).unique())
        return []


class MainWindow(QMainWindow):
    """CSV 로드→분석→요약·그래프·테이블 갱신과 리포트/PNG 내보내기를 담당하는 메인 창."""

    def __init__(self):
        super().__init__()
        self.data = None
        self.analyzer = None
        self.graph_widgets = {}
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """ui/handeye_analyzer.ui 를 로드해 중앙 위젯으로 얹고 그래프 위젯을 치환한다."""
        self.setWindowTitle("Hand-Eye Calibration Analyzer")
        self.setMinimumSize(1200, 800)

        ui_path = UI_DIR / "handeye_analyzer.ui"

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        self.ui = QWidget()
        uic.loadUi(str(ui_path), self.ui)
        main_layout.addWidget(self.ui)

        self.setup_graphs()

    def setup_graphs(self):
        """.ui 의 placeholder 위젯들을 ZoomableGraphWidget 으로 교체한다(개요4·히트맵·회전3·상관3)."""
        overview_graphs = [
            ('widget_overviewXY', 'Lm X-Y'),
            ('widget_overviewYZ', 'Lm Y-Z'),
            ('widget_overviewZX', 'Lm Z-X'),
            ('widget_overviewRotation', 'Rotation')
        ]

        for widget_name, title in overview_graphs:
            self._replace_widget(widget_name, title, compact=True)

        self._replace_widget('widget_heatmap', 'Heatmap', compact=False)

        rotation_graphs = [
            ('widget_graphRx', 'Lm_Rx'),
            ('widget_graphRy', 'Lm_Ry'),
            ('widget_graphRz', 'Lm_Rz'),
        ]

        for widget_name, title in rotation_graphs:
            self._replace_widget(widget_name, title, compact=False)

        corr_graphs = [
            ('widget_corrX', 'TCP_X vs Lm_X'),
            ('widget_corrY', 'TCP_Y vs Lm_Y'),
            ('widget_corrZ', 'TCP_Z vs Lm_Z'),
        ]

        for widget_name, title in corr_graphs:
            self._replace_widget(widget_name, title, compact=True)

    def _replace_widget(self, widget_name: str, title: str, compact: bool):
        old_widget = getattr(self.ui, widget_name, None)
        if old_widget is None:
            return

        parent = old_widget.parent()
        layout = parent.layout()

        index = layout.indexOf(old_widget)

        # grid 레이아웃은 (row, col) 자리를, box 레이아웃은 index 를 보존해야 배치가 유지된다.
        if hasattr(layout, 'getItemPosition'):
            row, col, _, _ = layout.getItemPosition(index)
            layout.removeWidget(old_widget)
            old_widget.deleteLater()

            new_widget = ZoomableGraphWidget(title=title, compact=compact)
            layout.addWidget(new_widget, row, col)
        else:
            layout.removeWidget(old_widget)
            old_widget.deleteLater()

            new_widget = ZoomableGraphWidget(title=title, compact=compact)
            layout.insertWidget(index, new_widget)

        self.graph_widgets[widget_name] = new_widget

    def setup_connections(self):
        """버튼·콤보박스 시그널을 슬롯에 연결한다."""
        self.ui.pushButton_openFile.clicked.connect(self.open_csv_file)
        self.ui.pushButton_recentFile.clicked.connect(self.open_recent_file)
        self.ui.pushButton_exportReport.clicked.connect(self.export_report)
        self.ui.pushButton_saveGraphs.clicked.connect(self.save_graphs)

        self.ui.comboBox_heatmapAxis.currentIndexChanged.connect(self.update_heatmap)
        self.ui.comboBox_zLevel.currentIndexChanged.connect(self.update_heatmap)

    def open_csv_file(self):
        """파일 다이얼로그로 CSV 를 선택해 로드한다."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "CSV 파일 열기",
            str(DATA_DIR),
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.load_csv(file_path)

    def open_recent_file(self):
        """data/ 의 날짜 폴더 중 최신에서 handeye_test_*.csv 를 찾아 로드한다."""
        csv_files = []
        for date_dir in sorted(DATA_DIR.glob("*"), reverse=True):
            if date_dir.is_dir():
                csv_files.extend(sorted(date_dir.glob("handeye_test_*.csv"), reverse=True))
                if csv_files:
                    break

        if csv_files:
            self.load_csv(str(csv_files[0]))
        else:
            QMessageBox.information(self, "알림", "Hand-Eye 테스트 파일이 없습니다.")

    def load_csv(self, file_path: str):
        """CSV 를 로드·검증(필수 컬럼)·수치 변환한 뒤 전체 뷰를 갱신한다."""
        try:
            df = pd.read_csv(file_path)

            required_cols = ['Pos', 'Lm_X', 'Lm_Y', 'Lm_Z']
            if not all(col in df.columns for col in required_cols):
                QMessageBox.warning(self, "경고",
                    "Hand-Eye 테스트 CSV 형식이 아닙니다.\n"
                    "필요한 컬럼: Pos, Lm_X, Lm_Y, Lm_Z")
                return

            numeric_cols = ['Lm_X', 'Lm_Y', 'Lm_Z', 'Lm_Rx', 'Lm_Ry', 'Lm_Rz',
                          'TCP_X', 'TCP_Y', 'TCP_Z', 'TCP_Rx', 'TCP_Ry', 'TCP_Rz']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            self.data = df
            self.analyzer = HandEyeDataAnalyzer(df)
            self.ui.label_fileName.setText(f"{Path(file_path).name} ({len(df)}개 데이터)")

            self._update_z_level_combo()

            self.update_all()

        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 로드 실패:\n{str(e)}")

    def _update_z_level_combo(self):
        combo = self.ui.comboBox_zLevel
        combo.clear()
        combo.addItem("전체")

        if self.analyzer:
            z_levels = self.analyzer.get_z_levels()
            for z in z_levels:
                combo.addItem(f"Z = {z:.1f}")

    def update_all(self):
        """요약·통계·그래프·테이블 8개 뷰를 일괄 갱신한다."""
        if self.data is None or self.analyzer is None:
            return

        self.update_summary()
        self.update_overview_stats()
        self.update_overview_graphs()
        self.update_position_table()
        self.update_heatmap()
        self.update_rotation_graphs()
        self.update_correlation_graphs()
        self.update_raw_data_table()

    def update_summary(self):
        total = len(self.data)
        positions = self.analyzer.get_unique_positions()
        repeats = self.analyzer.get_repeat_count()
        success_rate = self.analyzer.get_success_rate()

        self.ui.label_totalMeasurements.setText(f"총 측정: {total}회")
        self.ui.label_totalPositions.setText(f"위치: {positions}개")
        self.ui.label_repeatCount.setText(f"반복: {repeats}회")
        self.ui.label_successRate.setText(f"성공률: {success_rate:.1f}%")

    def update_overview_stats(self):
        s = self.analyzer.overall_stats

        self.ui.label_lmXValue.setText(f"σ={s['Lm_X']['std']:.4f}")
        self.ui.label_lmYValue.setText(f"σ={s['Lm_Y']['std']:.4f}")
        self.ui.label_lmZValue.setText(f"σ={s['Lm_Z']['std']:.4f}")

        self.ui.label_lmRxValue.setText(f"σ={s['Lm_Rx']['std']:.4f}")
        self.ui.label_lmRyValue.setText(f"σ={s['Lm_Ry']['std']:.4f}")
        self.ui.label_lmRzValue.setText(f"σ={s['Lm_Rz']['std']:.4f}")

        self.ui.label_3sigmaPos.setText(
            f"X: ±{s['Lm_X']['3sigma']:.3f} / Y: ±{s['Lm_Y']['3sigma']:.3f} / Z: ±{s['Lm_Z']['3sigma']:.3f}"
        )
        self.ui.label_3sigmaRot.setText(
            f"Rx: ±{s['Lm_Rx']['3sigma']:.3f} / Ry: ±{s['Lm_Ry']['3sigma']:.3f} / Rz: ±{s['Lm_Rz']['3sigma']:.3f}"
        )

        max_pos_std = max(s['Lm_X']['std'], s['Lm_Y']['std'], s['Lm_Z']['std'])
        max_rot_std = max(s['Lm_Rx']['std'], s['Lm_Ry']['std'], s['Lm_Rz']['std'])

        if max_pos_std < 0.3 and max_rot_std < 0.3:
            verdict = "우수 (Excellent)"
            color = "green"
        elif max_pos_std < 0.5 and max_rot_std < 0.5:
            verdict = "양호 (Good)"
            color = "blue"
        elif max_pos_std < 1.0 and max_rot_std < 1.0:
            verdict = "보통 (Fair)"
            color = "orange"
        else:
            verdict = "재검토 필요"
            color = "red"

        self.ui.label_verdict.setText(verdict)
        self.ui.label_verdict.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")

    def update_overview_graphs(self):
        if self.data is None:
            return

        valid_data = self.data.dropna(subset=['Lm_X', 'Lm_Y', 'Lm_Z'])

        lm_x = valid_data['Lm_X'].to_numpy()
        lm_y = valid_data['Lm_Y'].to_numpy()
        lm_z = valid_data['Lm_Z'].to_numpy()
        lm_rx = valid_data['Lm_Rx'].to_numpy()
        lm_ry = valid_data['Lm_Ry'].to_numpy()
        lm_rz = valid_data['Lm_Rz'].to_numpy()

        if 'Pos' in valid_data.columns:
            colors = valid_data['Pos'].to_numpy().astype(float)
        else:
            colors = 'blue'

        graph = self.graph_widgets.get('widget_overviewXY')
        if graph:
            graph.clear()
            scatter = graph.ax.scatter(lm_x, lm_y, c=colors, cmap='tab20', alpha=0.6, s=20)
            graph.ax.axhline(y=np.mean(lm_y), color='r', linestyle='--', alpha=0.5)
            graph.ax.axvline(x=np.mean(lm_x), color='r', linestyle='--', alpha=0.5)
            graph.ax.set_xlabel('Lm_X (mm)')
            graph.ax.set_ylabel('Lm_Y (mm)')
            graph.ax.set_title('Lm X-Y')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

        graph = self.graph_widgets.get('widget_overviewYZ')
        if graph:
            graph.clear()
            graph.ax.scatter(lm_y, lm_z, c=colors, cmap='tab20', alpha=0.6, s=20)
            graph.ax.axhline(y=np.mean(lm_z), color='r', linestyle='--', alpha=0.5)
            graph.ax.axvline(x=np.mean(lm_y), color='r', linestyle='--', alpha=0.5)
            graph.ax.set_xlabel('Lm_Y (mm)')
            graph.ax.set_ylabel('Lm_Z (mm)')
            graph.ax.set_title('Lm Y-Z')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

        graph = self.graph_widgets.get('widget_overviewZX')
        if graph:
            graph.clear()
            graph.ax.scatter(lm_x, lm_z, c=colors, cmap='tab20', alpha=0.6, s=20)
            graph.ax.axhline(y=np.mean(lm_z), color='r', linestyle='--', alpha=0.5)
            graph.ax.axvline(x=np.mean(lm_x), color='r', linestyle='--', alpha=0.5)
            graph.ax.set_xlabel('Lm_X (mm)')
            graph.ax.set_ylabel('Lm_Z (mm)')
            graph.ax.set_title('Lm X-Z')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

        graph = self.graph_widgets.get('widget_overviewRotation')
        if graph:
            graph.clear()
            indices = np.arange(len(lm_rx))
            graph.ax.plot(indices, lm_ry, 'g-', label='Ry', alpha=0.7, linewidth=1)
            graph.ax.plot(indices, lm_rz - 180, 'b-', label='Rz-180', alpha=0.7, linewidth=1)
            graph.ax.set_xlabel('Sample')
            graph.ax.set_ylabel('Angle (deg)')
            graph.ax.set_title('Rotation')
            graph.ax.legend(loc='upper right', fontsize=7)
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

    def update_position_table(self):
        if self.analyzer is None or self.analyzer.position_stats is None:
            return

        table = self.ui.tableWidget_positionStats
        stats = self.analyzer.position_stats

        table.setRowCount(len(stats))
        for i, s in enumerate(stats):
            table.setItem(i, 0, QTableWidgetItem(str(s['pos'])))
            table.setItem(i, 1, QTableWidgetItem(f"{s['tcp_x']:.1f}"))
            table.setItem(i, 2, QTableWidgetItem(f"{s['tcp_y']:.1f}"))
            table.setItem(i, 3, QTableWidgetItem(f"{s['tcp_z']:.1f}"))
            table.setItem(i, 4, QTableWidgetItem(f"{s.get('Lm_X_std', 0):.4f}"))
            table.setItem(i, 5, QTableWidgetItem(f"{s.get('Lm_Y_std', 0):.4f}"))
            table.setItem(i, 6, QTableWidgetItem(f"{s.get('Lm_Z_std', 0):.4f}"))
            table.setItem(i, 7, QTableWidgetItem(f"{s['count']}"))
            table.setItem(i, 8, QTableWidgetItem(f"{s['count']}"))

    def update_heatmap(self):
        if self.analyzer is None or self.analyzer.position_stats is None:
            return

        graph = self.graph_widgets.get('widget_heatmap')
        if not graph:
            return

        axis_map = {
            0: 'Lm_X_std', 1: 'Lm_Y_std', 2: 'Lm_Z_std',
            3: 'Lm_Rx_std', 4: 'Lm_Ry_std', 5: 'Lm_Rz_std'
        }
        axis_idx = self.ui.comboBox_heatmapAxis.currentIndex()
        axis_key = axis_map.get(axis_idx, 'Lm_X_std')

        z_idx = self.ui.comboBox_zLevel.currentIndex()
        z_levels = self.analyzer.get_z_levels()

        stats = self.analyzer.position_stats

        if z_idx > 0 and z_idx - 1 < len(z_levels):
            selected_z = z_levels[z_idx - 1]
            stats = [s for s in stats if abs(s['tcp_z'] - selected_z) < 1.0]

        if not stats:
            return

        tcp_x_vals = sorted(set(round(s['tcp_x'], 0) for s in stats))
        tcp_y_vals = sorted(set(round(s['tcp_y'], 0) for s in stats))

        heatmap_data = np.full((len(tcp_y_vals), len(tcp_x_vals)), np.nan)

        for s in stats:
            x_idx = tcp_x_vals.index(round(s['tcp_x'], 0))
            y_idx = tcp_y_vals.index(round(s['tcp_y'], 0))
            heatmap_data[y_idx, x_idx] = s.get(axis_key, 0)

        graph.clear()
        im = graph.ax.imshow(heatmap_data, cmap='RdYlGn_r', aspect='auto',
                            interpolation='nearest')
        graph.ax.set_xticks(range(len(tcp_x_vals)))
        graph.ax.set_yticks(range(len(tcp_y_vals)))
        graph.ax.set_xticklabels([f"{x:.0f}" for x in tcp_x_vals], fontsize=8)
        graph.ax.set_yticklabels([f"{y:.0f}" for y in tcp_y_vals], fontsize=8)
        graph.ax.set_xlabel('TCP_X (mm)')
        graph.ax.set_ylabel('TCP_Y (mm)')

        for i in range(len(tcp_y_vals)):
            for j in range(len(tcp_x_vals)):
                val = heatmap_data[i, j]
                if not np.isnan(val):
                    graph.ax.text(j, i, f"{val:.3f}", ha='center', va='center',
                                 fontsize=7, color='black')

        cbar = graph.figure.colorbar(im, ax=graph.ax)
        cbar.ax.tick_params(labelsize=8)

        graph.ax.set_title(f'{self.ui.comboBox_heatmapAxis.currentText()}')
        graph.draw()

    def update_rotation_graphs(self):
        if self.data is None:
            return

        s = self.analyzer.overall_stats

        graph = self.graph_widgets.get('widget_graphRx')
        if graph:
            lm_rx = self.analyzer._normalize_angle(self.data['Lm_Rx']).to_numpy()
            indices = np.arange(len(lm_rx))
            rx_mean, rx_std = s['Lm_Rx']['mean'], s['Lm_Rx']['std']

            graph.clear()
            graph.ax.plot(indices, lm_rx, 'r-', linewidth=1)
            graph.ax.axhline(y=rx_mean, color='b', linestyle='--', alpha=0.7)
            graph.ax.axhspan(rx_mean - rx_std, rx_mean + rx_std, alpha=0.2, color='blue')
            graph.ax.set_xlabel('Sample')
            graph.ax.set_ylabel('Lm_Rx (deg)')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

            self.ui.label_rotStatsRx.setText(
                f"Rx: mean={rx_mean:.4f}, std={rx_std:.4f}, range={s['Lm_Rx']['range']:.4f}"
            )

        graph = self.graph_widgets.get('widget_graphRy')
        if graph:
            lm_ry = self.data['Lm_Ry'].to_numpy()
            indices = np.arange(len(lm_ry))
            ry_mean, ry_std = s['Lm_Ry']['mean'], s['Lm_Ry']['std']

            graph.clear()
            graph.ax.plot(indices, lm_ry, 'g-', linewidth=1)
            graph.ax.axhline(y=ry_mean, color='b', linestyle='--', alpha=0.7)
            graph.ax.axhspan(ry_mean - ry_std, ry_mean + ry_std, alpha=0.2, color='blue')
            graph.ax.set_xlabel('Sample')
            graph.ax.set_ylabel('Lm_Ry (deg)')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

            self.ui.label_rotStatsRy.setText(
                f"Ry: mean={ry_mean:.4f}, std={ry_std:.4f}, range={s['Lm_Ry']['range']:.4f}"
            )

        graph = self.graph_widgets.get('widget_graphRz')
        if graph:
            lm_rz = self.data['Lm_Rz'].to_numpy()
            indices = np.arange(len(lm_rz))
            rz_mean, rz_std = s['Lm_Rz']['mean'], s['Lm_Rz']['std']

            graph.clear()
            graph.ax.plot(indices, lm_rz, 'b-', linewidth=1)
            graph.ax.axhline(y=rz_mean, color='r', linestyle='--', alpha=0.7)
            graph.ax.axhspan(rz_mean - rz_std, rz_mean + rz_std, alpha=0.2, color='red')
            graph.ax.set_xlabel('Sample')
            graph.ax.set_ylabel('Lm_Rz (deg)')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

            self.ui.label_rotStatsRz.setText(
                f"Rz: mean={rz_mean:.4f}, std={rz_std:.4f}, range={s['Lm_Rz']['range']:.4f}"
            )

    def update_correlation_graphs(self):
        if self.data is None:
            return

        valid_data = self.data.dropna(subset=['TCP_X', 'TCP_Y', 'TCP_Z', 'Lm_X', 'Lm_Y', 'Lm_Z'])

        graph = self.graph_widgets.get('widget_corrX')
        if graph and 'TCP_X' in valid_data.columns:
            tcp_x = valid_data['TCP_X'].to_numpy()
            lm_x = valid_data['Lm_X'].to_numpy()
            corr = np.corrcoef(tcp_x, lm_x)[0, 1]

            graph.clear()
            graph.ax.scatter(tcp_x, lm_x, alpha=0.5, s=15)
            graph.ax.set_xlabel('TCP_X (mm)')
            graph.ax.set_ylabel('Lm_X (mm)')
            graph.ax.set_title(f'r = {corr:.4f}')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

            self.ui.label_corrXValue.setText(f"r = {corr:.4f}")

        graph = self.graph_widgets.get('widget_corrY')
        if graph and 'TCP_Y' in valid_data.columns:
            tcp_y = valid_data['TCP_Y'].to_numpy()
            lm_y = valid_data['Lm_Y'].to_numpy()
            corr = np.corrcoef(tcp_y, lm_y)[0, 1]

            graph.clear()
            graph.ax.scatter(tcp_y, lm_y, alpha=0.5, s=15)
            graph.ax.set_xlabel('TCP_Y (mm)')
            graph.ax.set_ylabel('Lm_Y (mm)')
            graph.ax.set_title(f'r = {corr:.4f}')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

            self.ui.label_corrYValue.setText(f"r = {corr:.4f}")

        graph = self.graph_widgets.get('widget_corrZ')
        if graph and 'TCP_Z' in valid_data.columns:
            tcp_z = valid_data['TCP_Z'].to_numpy()
            lm_z = valid_data['Lm_Z'].to_numpy()
            corr = np.corrcoef(tcp_z, lm_z)[0, 1]

            graph.clear()
            graph.ax.scatter(tcp_z, lm_z, alpha=0.5, s=15)
            graph.ax.set_xlabel('TCP_Z (mm)')
            graph.ax.set_ylabel('Lm_Z (mm)')
            graph.ax.set_title(f'r = {corr:.4f}')
            graph.ax.grid(True, alpha=0.3)
            graph.draw()

            self.ui.label_corrZValue.setText(f"r = {corr:.4f}")

    def update_raw_data_table(self):
        if self.data is None:
            return

        table = self.ui.tableWidget_rawData
        table.setRowCount(len(self.data))

        columns = ['No.', 'Pos', 'Lm_X', 'Lm_Y', 'Lm_Z', 'Lm_Rx', 'Lm_Ry', 'Lm_Rz',
                  'TCP_X', 'TCP_Y', 'TCP_Z', 'TCP_Rx', 'TCP_Ry', 'TCP_Rz', 'Time']

        for row_idx, (_, row) in enumerate(self.data.iterrows()):
            for col_idx, col in enumerate(columns):
                if col in self.data.columns:
                    value = row[col]
                    if isinstance(value, float):
                        text = f"{value:.4f}"
                    else:
                        text = str(value)
                else:
                    text = "-"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, col_idx, item)

    def export_report(self):
        if self.data is None or self.analyzer is None:
            QMessageBox.warning(self, "경고", "내보낼 데이터가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "리포트 내보내기",
            str(DATA_DIR / "handeye_report.txt"),
            "Text Files (*.txt);;All Files (*)"
        )

        if not file_path:
            return

        s = self.analyzer.overall_stats
        lines = [
            "=" * 60,
            "Hand-Eye Calibration Analysis Report",
            "=" * 60,
            "",
            f"총 측정 횟수: {len(self.data)}",
            f"측정 위치 수: {self.analyzer.get_unique_positions()}",
            f"반복 횟수: {self.analyzer.get_repeat_count()}",
            "",
            "--- 반복정밀도 (Repeatability) ---",
            f"Lm_X: σ = {s['Lm_X']['std']:.4f} mm, 3σ = ±{s['Lm_X']['3sigma']:.4f} mm",
            f"Lm_Y: σ = {s['Lm_Y']['std']:.4f} mm, 3σ = ±{s['Lm_Y']['3sigma']:.4f} mm",
            f"Lm_Z: σ = {s['Lm_Z']['std']:.4f} mm, 3σ = ±{s['Lm_Z']['3sigma']:.4f} mm",
            "",
            f"Lm_Rx: σ = {s['Lm_Rx']['std']:.4f}°, 3σ = ±{s['Lm_Rx']['3sigma']:.4f}°",
            f"Lm_Ry: σ = {s['Lm_Ry']['std']:.4f}°, 3σ = ±{s['Lm_Ry']['3sigma']:.4f}°",
            f"Lm_Rz: σ = {s['Lm_Rz']['std']:.4f}°, 3σ = ±{s['Lm_Rz']['3sigma']:.4f}°",
            "",
            "--- 위치별 통계 ---",
        ]

        for ps in self.analyzer.position_stats:
            lines.append(
                f"Pos {ps['pos']:2d}: TCP({ps['tcp_x']:.1f}, {ps['tcp_y']:.1f}, {ps['tcp_z']:.1f}) "
                f"σ(X={ps.get('Lm_X_std', 0):.4f}, Y={ps.get('Lm_Y_std', 0):.4f}, Z={ps.get('Lm_Z_std', 0):.4f})"
            )

        lines.append("")
        lines.append("=" * 60)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        QMessageBox.information(self, "완료", f"리포트 저장됨: {file_path}")

    def save_graphs(self):
        if self.data is None:
            QMessageBox.warning(self, "경고", "저장할 그래프가 없습니다.")
            return

        dir_path = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")

        if dir_path:
            graphs_to_save = [
                'widget_overviewXY', 'widget_overviewYZ', 'widget_overviewZX',
                'widget_heatmap', 'widget_graphRx', 'widget_graphRy', 'widget_graphRz',
                'widget_corrX', 'widget_corrY', 'widget_corrZ'
            ]
            for name in graphs_to_save:
                widget = self.graph_widgets.get(name)
                if widget:
                    file_name = name.replace('widget_', '') + '.png'
                    file_path = os.path.join(dir_path, file_name)
                    widget.figure.savefig(file_path, dpi=150, bbox_inches='tight')

            QMessageBox.information(self, "완료", f"그래프가 {dir_path}에 저장되었습니다.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        window.load_csv(sys.argv[1])

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
