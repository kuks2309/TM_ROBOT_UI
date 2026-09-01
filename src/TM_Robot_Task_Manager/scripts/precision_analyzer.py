#!/usr/bin/env python3
"""정밀 반복 테스트 CSV(precision_test_*.csv)의 6축 mean·σ·3σ·range 통계와 산점/회전 그래프를 표시하는 PyQt5 오프라인 분석기.

실행: python3 scripts/precision_analyzer.py [csv경로] — load_from_manager 로 메모리 내 측정 리스트도 수용.
"""
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = SCRIPT_DIR.parent
UI_DIR = PACKAGE_DIR / "ui"
DATA_DIR = PACKAGE_DIR / "data"

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFileDialog,
    QMessageBox, QTableWidgetItem
)
from PyQt5.QtCore import Qt
from PyQt5 import uic

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


class ZoomableGraphWidget(QWidget):
    """휠 줌·더블클릭 시 저장된 초기 축 범위로 복원되는 matplotlib 캔버스 위젯."""

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
            self.figure = Figure(figsize=(3, 2.5), dpi=100)
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


class PrecisionAnalyzer:
    """정밀 테스트 데이터의 축별 통계 산출 유틸리티."""

    @staticmethod
    def calculate_statistics(data: pd.DataFrame) -> dict:
        """6축(X/Y/Z[mm], Rx/Ry/Rz[deg]) 각각의 mean/std/3sigma/min/max/range 를 계산한다."""
        columns = ['X (mm)', 'Y (mm)', 'Z (mm)', 'Rx (deg)', 'Ry (deg)', 'Rz (deg)']
        stats = {}

        for col in columns:
            if col in data.columns:
                values = data[col].dropna()
                stats[col] = {
                    'mean': values.mean(),
                    'std': values.std(),
                    '3sigma': 3 * values.std(),
                    'min': values.min(),
                    'max': values.max(),
                    'range': values.max() - values.min()
                }

        return stats


class MainWindow(QMainWindow):
    """CSV/메모리 데이터 로드→통계→테이블·그래프 갱신과 CSV/PNG 내보내기를 담당하는 메인 창."""

    def __init__(self):
        super().__init__()
        self.data = None
        self.stats = None
        self.graph_widgets = {}
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """ui/precision_analyzer.ui 를 로드해 중앙 위젯으로 얹고 그래프 위젯을 치환한다."""
        self.setWindowTitle("Precision Test Analyzer")
        self.setMinimumSize(1000, 700)

        ui_path = UI_DIR / "precision_analyzer.ui"

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        self.ui = QWidget()
        uic.loadUi(str(ui_path), self.ui)
        main_layout.addWidget(self.ui)

        self.setup_graphs()

    def setup_graphs(self):
        """.ui 의 placeholder 를 ZoomableGraphWidget 으로 교체한다(개요4·상세3·회전3)."""
        overview_graphs = [
            ('widget_overviewXY', 'X-Y'),
            ('widget_overviewYZ', 'Y-Z'),
            ('widget_overviewZX', 'Z-X'),
            ('widget_overviewRotation', 'Rotation')
        ]

        for widget_name, title in overview_graphs:
            self._replace_widget(widget_name, title, compact=True)

        detail_graphs = [
            ('widget_graphXY', 'X-Y Position'),
            ('widget_graphYZ', 'Y-Z Position'),
            ('widget_graphZX', 'Z-X Position'),
        ]

        for widget_name, title in detail_graphs:
            self._replace_widget(widget_name, title, compact=False)

        rotation_graphs = [
            ('widget_graphRx', 'Rx'),
            ('widget_graphRy', 'Ry'),
            ('widget_graphRz', 'Rz'),
        ]

        for widget_name, title in rotation_graphs:
            self._replace_widget(widget_name, title, compact=False)

    def _replace_widget(self, widget_name: str, title: str, compact: bool):
        old_widget = getattr(self.ui, widget_name)
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
        """버튼 시그널을 슬롯에 연결한다."""
        self.ui.pushButton_openFile.clicked.connect(self.open_csv_file)
        self.ui.pushButton_recentFile.clicked.connect(self.open_recent_file)
        self.ui.pushButton_exportCSV.clicked.connect(self.export_csv)
        self.ui.pushButton_saveGraphs.clicked.connect(self.save_graphs)

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
        """data/ 의 최신 precision_test_*.csv 를 찾아 로드한다."""
        csv_files = sorted(DATA_DIR.glob("precision_test_*.csv"), reverse=True)

        if csv_files:
            self.load_csv(str(csv_files[0]))
        else:
            QMessageBox.information(self, "알림", "테스트 파일이 없습니다.")

    def load_csv(self, file_path: str):
        """CSV 를 로드해 하단 통계 요약부를 잘라내고 수치 변환·통계 산출 후 전체 갱신한다."""
        try:
            df = pd.read_csv(file_path)

            # 정밀 테스트 CSV 는 데이터 뒤에 '통계' 요약 행이 붙으므로 그 앞까지만 사용한다.
            stats_idx = df[df.iloc[:, 0].astype(str).str.contains('통계', na=False)].index
            if len(stats_idx) > 0:
                df = df.iloc[:stats_idx[0]]

            df = df.dropna(subset=['No.'])
            df = df[df['No.'].apply(lambda x: str(x).isdigit())]

            landmark_cols = ['X (mm)', 'Y (mm)', 'Z (mm)', 'Rx (deg)', 'Ry (deg)', 'Rz (deg)']
            for col in landmark_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            tcp_cols = ['TCP_X (mm)', 'TCP_Y (mm)', 'TCP_Z (mm)', 'TCP_Rx (deg)', 'TCP_Ry (deg)', 'TCP_Rz (deg)']
            for col in tcp_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            self.data = df
            self.stats = PrecisionAnalyzer.calculate_statistics(df)
            self.ui.label_fileName.setText(f"{Path(file_path).name} ({len(df)}개 데이터)")
            self.update_all()

        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 로드 실패:\n{str(e)}")

    def update_all(self):
        """테이블·개요 통계·상세 통계·그래프를 일괄 갱신한다."""
        if self.data is None:
            return

        self.update_table()
        self.update_overview_stats()
        self.update_detail_stats()
        self.update_graphs()

    def update_table(self):
        """랜드마크·TCP·시간 14컬럼 데이터 테이블을 채운다."""
        table = self.ui.tableWidget_data
        table.setRowCount(len(self.data))

        columns = [
            'No.', 'X (mm)', 'Y (mm)', 'Z (mm)', 'Rx (deg)', 'Ry (deg)', 'Rz (deg)',
            'TCP_X (mm)', 'TCP_Y (mm)', 'TCP_Z (mm)', 'TCP_Rx (deg)', 'TCP_Ry (deg)', 'TCP_Rz (deg)',
            '시간'
        ]

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

    def update_overview_stats(self):
        """축별 μ/σ 와 3σ 라벨을 갱신한다."""
        s = self.stats

        self.ui.label_xValue.setText(f"μ={s['X (mm)']['mean']:.4f}  σ={s['X (mm)']['std']:.4f}")
        self.ui.label_yValue.setText(f"μ={s['Y (mm)']['mean']:.4f}  σ={s['Y (mm)']['std']:.4f}")
        self.ui.label_zValue.setText(f"μ={s['Z (mm)']['mean']:.4f}  σ={s['Z (mm)']['std']:.4f}")

        self.ui.label_rxValue.setText(f"μ={s['Rx (deg)']['mean']:.4f}  σ={s['Rx (deg)']['std']:.4f}")
        self.ui.label_ryValue.setText(f"μ={s['Ry (deg)']['mean']:.4f}  σ={s['Ry (deg)']['std']:.4f}")
        self.ui.label_rzValue.setText(f"μ={s['Rz (deg)']['mean']:.4f}  σ={s['Rz (deg)']['std']:.4f}")

        self.ui.label_3sigmaPos.setText(
            f"X: ±{s['X (mm)']['3sigma']:.4f} / Y: ±{s['Y (mm)']['3sigma']:.4f} / Z: ±{s['Z (mm)']['3sigma']:.4f}"
        )
        self.ui.label_3sigmaRot.setText(
            f"Rx: ±{s['Rx (deg)']['3sigma']:.4f} / Ry: ±{s['Ry (deg)']['3sigma']:.4f} / Rz: ±{s['Rz (deg)']['3sigma']:.4f}"
        )

    def update_detail_stats(self):
        """평면(XY/YZ/ZX)·회전 탭의 상세 통계 라벨을 갱신한다."""
        s = self.stats

        self.ui.label_xyStatsX.setText(
            f"X: μ={s['X (mm)']['mean']:.4f}, σ={s['X (mm)']['std']:.4f}, 3σ=±{s['X (mm)']['3sigma']:.4f}, range={s['X (mm)']['range']:.4f}"
        )
        self.ui.label_xyStatsY.setText(
            f"Y: μ={s['Y (mm)']['mean']:.4f}, σ={s['Y (mm)']['std']:.4f}, 3σ=±{s['Y (mm)']['3sigma']:.4f}, range={s['Y (mm)']['range']:.4f}"
        )

        self.ui.label_yzStatsY.setText(
            f"Y: μ={s['Y (mm)']['mean']:.4f}, σ={s['Y (mm)']['std']:.4f}, 3σ=±{s['Y (mm)']['3sigma']:.4f}, range={s['Y (mm)']['range']:.4f}"
        )
        self.ui.label_yzStatsZ.setText(
            f"Z: μ={s['Z (mm)']['mean']:.4f}, σ={s['Z (mm)']['std']:.4f}, 3σ=±{s['Z (mm)']['3sigma']:.4f}, range={s['Z (mm)']['range']:.4f}"
        )

        self.ui.label_zxStatsX.setText(
            f"X: μ={s['X (mm)']['mean']:.4f}, σ={s['X (mm)']['std']:.4f}, 3σ=±{s['X (mm)']['3sigma']:.4f}, range={s['X (mm)']['range']:.4f}"
        )
        self.ui.label_zxStatsZ.setText(
            f"Z: μ={s['Z (mm)']['mean']:.4f}, σ={s['Z (mm)']['std']:.4f}, 3σ=±{s['Z (mm)']['3sigma']:.4f}, range={s['Z (mm)']['range']:.4f}"
        )

        self.ui.label_rotStatsRx.setText(
            f"Rx: μ={s['Rx (deg)']['mean']:.4f}, σ={s['Rx (deg)']['std']:.4f}, 3σ=±{s['Rx (deg)']['3sigma']:.4f}"
        )
        self.ui.label_rotStatsRy.setText(
            f"Ry: μ={s['Ry (deg)']['mean']:.4f}, σ={s['Ry (deg)']['std']:.4f}, 3σ=±{s['Ry (deg)']['3sigma']:.4f}"
        )
        self.ui.label_rotStatsRz.setText(
            f"Rz: μ={s['Rz (deg)']['mean']:.4f}, σ={s['Rz (deg)']['std']:.4f}, 3σ=±{s['Rz (deg)']['3sigma']:.4f}"
        )

    def update_graphs(self):
        """XY/YZ/ZX 산점도(개요+상세)와 회전 추이 그래프를 갱신한다."""
        if self.data is None:
            return

        x = self.data['X (mm)'].values
        y = self.data['Y (mm)'].values
        z = self.data['Z (mm)'].values
        rx = self.data['Rx (deg)'].values
        ry = self.data['Ry (deg)'].values
        rz = self.data['Rz (deg)'].values

        for widget_name in ['widget_overviewXY', 'widget_graphXY']:
            graph = self.graph_widgets[widget_name]
            graph.clear()
            graph.ax.scatter(x, y, c='blue', alpha=0.6, s=20)
            graph.ax.axhline(y=np.mean(y), color='r', linestyle='--', alpha=0.5)
            graph.ax.axvline(x=np.mean(x), color='r', linestyle='--', alpha=0.5)
            graph.ax.set_xlabel('X (mm)')
            graph.ax.set_ylabel('Y (mm)')
            graph.ax.set_title('X-Y Position')
            graph.ax.grid(True, alpha=0.3)
            graph.set_equal_aspect()
            graph.draw()

        for widget_name in ['widget_overviewYZ', 'widget_graphYZ']:
            graph = self.graph_widgets[widget_name]
            graph.clear()
            graph.ax.scatter(y, z, c='green', alpha=0.6, s=20)
            graph.ax.axhline(y=np.mean(z), color='r', linestyle='--', alpha=0.5)
            graph.ax.axvline(x=np.mean(y), color='r', linestyle='--', alpha=0.5)
            graph.ax.set_xlabel('Y (mm)')
            graph.ax.set_ylabel('Z (mm)')
            graph.ax.set_title('Y-Z Position')
            graph.ax.grid(True, alpha=0.3)
            graph.set_equal_aspect()
            graph.draw()

        for widget_name in ['widget_overviewZX', 'widget_graphZX']:
            graph = self.graph_widgets[widget_name]
            graph.clear()
            graph.ax.scatter(x, z, c='orange', alpha=0.6, s=20)
            graph.ax.axhline(y=np.mean(z), color='r', linestyle='--', alpha=0.5)
            graph.ax.axvline(x=np.mean(x), color='r', linestyle='--', alpha=0.5)
            graph.ax.set_xlabel('X (mm)')
            graph.ax.set_ylabel('Z (mm)')
            graph.ax.set_title('X-Z Position')
            graph.ax.grid(True, alpha=0.3)
            graph.set_equal_aspect()
            graph.draw()

        graph = self.graph_widgets['widget_overviewRotation']
        graph.clear()
        indices = np.arange(len(rx))
        graph.ax.plot(indices, rx, 'r-', label='Rx', alpha=0.7)
        graph.ax.plot(indices, ry, 'g-', label='Ry', alpha=0.7)
        # Rz 는 ±180° 부근 값이라 +180 시프트해 Rx/Ry 와 같은 축 범위에서 비교한다.
        graph.ax.plot(indices, rz + 180, 'b-', label='Rz+180', alpha=0.7)
        graph.ax.set_xlabel('Sample')
        graph.ax.set_ylabel('Angle (deg)')
        graph.ax.set_title('Rotation')
        graph.ax.legend(loc='upper right', fontsize=8)
        graph.ax.grid(True, alpha=0.3)
        graph.draw()

        graph_rx = self.graph_widgets['widget_graphRx']
        graph_rx.clear()
        rx_mean, rx_std = np.mean(rx), np.std(rx)
        graph_rx.ax.plot(indices, rx, 'r-', linewidth=1.5)
        graph_rx.ax.axhline(y=rx_mean, color='b', linestyle='--', alpha=0.7, label=f'mean={rx_mean:.4f}')
        graph_rx.ax.axhspan(rx_mean - rx_std, rx_mean + rx_std, alpha=0.2, color='blue', label=f'±σ={rx_std:.4f}')
        graph_rx.ax.set_xlabel('Sample')
        graph_rx.ax.set_ylabel('Rx (deg)')
        graph_rx.ax.set_title('Rx')
        graph_rx.ax.legend(loc='upper right', fontsize=8)
        graph_rx.ax.grid(True, alpha=0.3)
        graph_rx.draw()

        graph_ry = self.graph_widgets['widget_graphRy']
        graph_ry.clear()
        ry_mean, ry_std = np.mean(ry), np.std(ry)
        graph_ry.ax.plot(indices, ry, 'g-', linewidth=1.5)
        graph_ry.ax.axhline(y=ry_mean, color='b', linestyle='--', alpha=0.7, label=f'mean={ry_mean:.4f}')
        graph_ry.ax.axhspan(ry_mean - ry_std, ry_mean + ry_std, alpha=0.2, color='blue', label=f'±σ={ry_std:.4f}')
        graph_ry.ax.set_xlabel('Sample')
        graph_ry.ax.set_ylabel('Ry (deg)')
        graph_ry.ax.set_title('Ry')
        graph_ry.ax.legend(loc='upper right', fontsize=8)
        graph_ry.ax.grid(True, alpha=0.3)
        graph_ry.draw()

        graph_rz = self.graph_widgets['widget_graphRz']
        graph_rz.clear()
        rz_mean, rz_std = np.mean(rz), np.std(rz)
        graph_rz.ax.plot(indices, rz, 'b-', linewidth=1.5)
        graph_rz.ax.axhline(y=rz_mean, color='r', linestyle='--', alpha=0.7, label=f'mean={rz_mean:.4f}')
        graph_rz.ax.axhspan(rz_mean - rz_std, rz_mean + rz_std, alpha=0.2, color='red', label=f'±σ={rz_std:.4f}')
        graph_rz.ax.set_xlabel('Sample')
        graph_rz.ax.set_ylabel('Rz (deg)')
        graph_rz.ax.set_title('Rz')
        graph_rz.ax.legend(loc='upper right', fontsize=8)
        graph_rz.ax.grid(True, alpha=0.3)
        graph_rz.draw()

    def export_csv(self):
        """현재 데이터를 CSV 로 재저장한다."""
        if self.data is None:
            QMessageBox.warning(self, "경고", "내보낼 데이터가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "CSV 내보내기",
            "",
            "CSV Files (*.csv)"
        )

        if file_path:
            self.data.to_csv(file_path, index=False)
            QMessageBox.information(self, "완료", f"저장됨: {file_path}")

    def save_graphs(self):
        """상세 6개 그래프를 PNG 로 저장한다."""
        if self.data is None:
            QMessageBox.warning(self, "경고", "저장할 그래프가 없습니다.")
            return

        dir_path = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")

        if dir_path:
            detail_graphs = ['widget_graphXY', 'widget_graphYZ', 'widget_graphZX',
                           'widget_graphRx', 'widget_graphRy', 'widget_graphRz']
            for name in detail_graphs:
                widget = self.graph_widgets[name]
                file_path = os.path.join(dir_path, f"{name.replace('widget_graph', '')}.png")
                widget.figure.savefig(file_path, dpi=150, bbox_inches='tight')
            QMessageBox.information(self, "완료", f"그래프가 {dir_path}에 저장되었습니다.")

    def load_from_manager(self, manager):
        """CSV 파일 없이 매니저의 메모리 측정 리스트(measurements)를 DataFrame 으로 받아 갱신한다."""
        if not manager.measurements:
            QMessageBox.warning(self, "경고", "측정 데이터가 없습니다.")
            return

        data_list = []
        for i, m in enumerate(manager.measurements, 1):
            data_list.append({
                'No.': i,
                'X (mm)': m.x,
                'Y (mm)': m.y,
                'Z (mm)': m.z,
                'Rx (deg)': m.rx,
                'Ry (deg)': m.ry,
                'Rz (deg)': m.rz,
                '시간': m.timestamp
            })

        self.data = pd.DataFrame(data_list)
        self.stats = PrecisionAnalyzer.calculate_statistics(self.data)
        self.ui.label_fileName.setText(f"메모리 데이터 ({len(self.data)}개)")
        self.update_all()


def main():
    """앱을 기동하고 argv[1] 이 있으면 해당 CSV 를 자동 로드한다."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        window.load_csv(sys.argv[1])

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
