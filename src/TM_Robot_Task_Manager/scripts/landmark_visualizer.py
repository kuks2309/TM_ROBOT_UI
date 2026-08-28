#!/usr/bin/env python3
import sys
import threading
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Polygon

LANDMARK_SIZE = 40.0

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = SCRIPT_DIR.parent
UI_DIR = PACKAGE_DIR / "ui"
DATA_DIR = PACKAGE_DIR / "data"

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QFileDialog,
    QMessageBox, QTableWidgetItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5 import uic

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Float32MultiArray
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    print("[LandmarkVisualizer] ROS2 not available - running in offline mode")


def rotation_matrix_from_euler(rx, ry, rz):
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


class GraphWidget(QWidget):
    def __init__(self, parent=None, is_3d=False, compact=False):
        super().__init__(parent)
        self.is_3d = is_3d
        self.compact = compact
        self._xlim_orig = None
        self._ylim_orig = None
        self._zlim_orig = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.compact:
            self.figure = Figure(figsize=(3, 2.5), dpi=100)
        else:
            self.figure = Figure(figsize=(6, 5), dpi=100)

        self.canvas = FigureCanvas(self.figure)

        if self.is_3d:
            self.ax = self.figure.add_subplot(111, projection='3d')
        else:
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

        if self.is_3d:
            pass
        else:
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            xdata, ydata = event.xdata, event.ydata
            if xdata and ydata:
                new_xlim = [xdata - (xdata - xlim[0]) * scale,
                            xdata + (xlim[1] - xdata) * scale]
                new_ylim = [ydata - (ydata - ylim[0]) * scale,
                            ydata + (ylim[1] - ydata) * scale]
                self.ax.set_xlim(new_xlim)
                self.ax.set_ylim(new_ylim)
                self.canvas.draw_idle()

    def _on_double_click(self, event):
        if event.dblclick:
            self.reset_view()

    def save_original_limits(self):
        self._xlim_orig = self.ax.get_xlim()
        self._ylim_orig = self.ax.get_ylim()
        if self.is_3d:
            self._zlim_orig = self.ax.get_zlim()

    def reset_view(self):
        if self._xlim_orig and self._ylim_orig:
            self.ax.set_xlim(self._xlim_orig)
            self.ax.set_ylim(self._ylim_orig)
            if self.is_3d and self._zlim_orig:
                self.ax.set_zlim(self._zlim_orig)
            self.canvas.draw_idle()

    def clear(self):
        self.ax.clear()

    def draw(self):
        self.figure.tight_layout()
        self.canvas.draw()
        self.save_original_limits()


class ROS2Thread(threading.Thread):
    def __init__(self, node):
        super().__init__(daemon=True)
        self.node = node
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            rclpy.spin_once(self.node, timeout_sec=0.1)

    def stop(self):
        self._stop_event.set()


class LandmarkVisualizerWindow(QMainWindow):
    tcp_updated = pyqtSignal(list)
    joint_updated = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.data = None
        self.selected_row = -1
        self.graph_widgets = {}

        self.ros_node = None
        self.ros_thread = None
        self.current_tcp = None
        self.current_joints = None

        self.setup_ui()
        self.setup_graphs()
        self.setup_connections()

        self.tcp_updated.connect(self._on_tcp_updated)
        self.joint_updated.connect(self._on_joint_updated)

    def setup_ui(self):
        self.setWindowTitle("TM Landmark Visualizer")
        self.setMinimumSize(1200, 800)

        ui_path = UI_DIR / "landmark_visualizer.ui"
        uic.loadUi(str(ui_path), self)

    def setup_graphs(self):
        graph_configs = [
            ('widget_view3D', True, False),
            ('widget_viewXY', False, False),
            ('widget_viewXZ', False, False),
            ('widget_viewYZ', False, False),
        ]

        for widget_name, is_3d, compact in graph_configs:
            self._replace_widget(widget_name, is_3d, compact)

        overview_configs = [
            ('widget_overviewXY', False, True),
            ('widget_overviewXZ', False, True),
            ('widget_overviewYZ', False, True),
            ('widget_overview3D', True, True),
        ]

        for widget_name, is_3d, compact in overview_configs:
            self._replace_widget(widget_name, is_3d, compact)

    def _replace_widget(self, widget_name: str, is_3d: bool, compact: bool):
        old_widget = getattr(self, widget_name, None)
        if not old_widget:
            return

        parent = old_widget.parent()
        layout = parent.layout()
        index = layout.indexOf(old_widget)

        if hasattr(layout, 'getItemPosition'):
            row, col, _, _ = layout.getItemPosition(index)
            layout.removeWidget(old_widget)
            old_widget.deleteLater()
            new_widget = GraphWidget(is_3d=is_3d, compact=compact)
            layout.addWidget(new_widget, row, col)
        else:
            layout.removeWidget(old_widget)
            old_widget.deleteLater()
            new_widget = GraphWidget(is_3d=is_3d, compact=compact)
            layout.insertWidget(index, new_widget)

        self.graph_widgets[widget_name] = new_widget

    def setup_connections(self):
        self.pushButton_openCSV.clicked.connect(self.open_csv)
        self.pushButton_recentFile.clicked.connect(self.open_recent_file)

        self.pushButton_connectROS.clicked.connect(self.toggle_ros_connection)

        self.tableWidget_data.itemSelectionChanged.connect(self.on_row_selected)

        self.checkBox_showRobotTCP.stateChanged.connect(self.update_graphs)

        self.action_openCSV.triggered.connect(self.open_csv)
        self.action_exportImage.triggered.connect(self.export_image)
        self.action_exit.triggered.connect(self.close)
        self.action_resetView.triggered.connect(self.reset_all_views)
        self.action_zoomFit.triggered.connect(self.zoom_fit)

    def open_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "CSV 파일 열기", str(DATA_DIR),
            "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            self.load_csv(file_path)

    def open_recent_file(self):
        csv_files = sorted(DATA_DIR.glob("precision_test_*.csv"), reverse=True)
        if csv_files:
            self.load_csv(str(csv_files[0]))
        else:
            QMessageBox.information(self, "알림", "테스트 파일이 없습니다.")

    def load_csv(self, file_path: str):
        try:
            df = pd.read_csv(file_path)

            stats_idx = df[df.iloc[:, 0].astype(str).str.contains('통계', na=False)].index
            if len(stats_idx) > 0:
                df = df.iloc[:stats_idx[0]]

            df = df.dropna(subset=['No.'])
            df = df[df['No.'].apply(lambda x: str(x).isdigit())]

            numeric_cols = ['X (mm)', 'Y (mm)', 'Z (mm)', 'Rx (deg)', 'Ry (deg)', 'Rz (deg)']
            tcp_cols = ['TCP_X (mm)', 'TCP_Y (mm)', 'TCP_Z (mm)', 'TCP_Rx (deg)', 'TCP_Ry (deg)', 'TCP_Rz (deg)']

            for col in numeric_cols + tcp_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            self.data = df
            self.label_fileName.setText(f"{Path(file_path).name} ({len(df)}개)")
            self.label_fileName.setStyleSheet("color: black; font-style: normal;")

            self.update_table()
            self.update_graphs()

        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 로드 실패:\n{str(e)}")

    def update_table(self):
        if self.data is None:
            return

        table = self.tableWidget_data
        table.setRowCount(len(self.data))

        columns = ['No.', 'X (mm)', 'Y (mm)', 'Z (mm)', 'Rx (deg)', 'Ry (deg)', 'Rz (deg)']

        for row_idx, (_, row) in enumerate(self.data.iterrows()):
            for col_idx, col in enumerate(columns):
                if col in self.data.columns:
                    value = row[col]
                    if isinstance(value, float):
                        text = f"{value:.2f}"
                    else:
                        text = str(value)
                else:
                    text = "-"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, col_idx, item)

        table.resizeColumnsToContents()

    def on_row_selected(self):
        selected = self.tableWidget_data.selectedItems()
        if not selected:
            self.selected_row = -1
            self.label_selectedInfo.setText("선택: -")
            return

        self.selected_row = selected[0].row()
        self.label_selectedInfo.setText(f"선택: #{self.selected_row + 1}")

        if self.data is not None and self.selected_row < len(self.data):
            row = self.data.iloc[self.selected_row]

            landmark_text = f"Landmark: X={row.get('X (mm)', 0):.3f} Y={row.get('Y (mm)', 0):.3f} Z={row.get('Z (mm)', 0):.3f}"
            landmark_text += f" Rx={row.get('Rx (deg)', 0):.2f} Ry={row.get('Ry (deg)', 0):.2f} Rz={row.get('Rz (deg)', 0):.2f}"
            self.label_selectedLandmark.setText(landmark_text)

            tcp_x = row.get('TCP_X (mm)', 0)
            tcp_y = row.get('TCP_Y (mm)', 0)
            tcp_z = row.get('TCP_Z (mm)', 0)
            if pd.notna(tcp_x):
                tcp_text = f"TCP: X={tcp_x:.3f} Y={tcp_y:.3f} Z={tcp_z:.3f}"
            else:
                tcp_text = "TCP: (데이터 없음)"
            self.label_selectedTCP.setText(tcp_text)

        self.update_graphs()

    def update_graphs(self):
        show_tcp = self.checkBox_showRobotTCP.isChecked()

        selected_point = None
        if self.data is not None and self.selected_row >= 0 and self.selected_row < len(self.data):
            row = self.data.iloc[self.selected_row]
            selected_point = {
                'x': row.get('X (mm)', 0),
                'y': row.get('Y (mm)', 0),
                'z': row.get('Z (mm)', 0),
                'rx': row.get('Rx (deg)', 0),
                'ry': row.get('Ry (deg)', 0),
                'rz': row.get('Rz (deg)', 0),
            }

        self._update_3d_graph('widget_view3D', selected_point, show_tcp)
        self._update_3d_graph('widget_overview3D', selected_point, show_tcp)

        self._update_2d_graph('widget_viewXY', 'widget_overviewXY',
                              selected_point, 'x', 'y', 'X (mm)', 'Y (mm)', 'XY Plane (Top)', show_tcp, 'xy')
        self._update_2d_graph('widget_viewXZ', 'widget_overviewXZ',
                              selected_point, 'x', 'z', 'X (mm)', 'Z (mm)', 'XZ Plane (Front)', show_tcp, 'xz')
        self._update_2d_graph('widget_viewYZ', 'widget_overviewYZ',
                              selected_point, 'y', 'z', 'Y (mm)', 'Z (mm)', 'YZ Plane (Side)', show_tcp, 'yz')

    def _update_3d_graph(self, widget_name, selected_point, show_tcp):
        if widget_name not in self.graph_widgets:
            return

        graph = self.graph_widgets[widget_name]
        graph.clear()
        ax = graph.ax

        if selected_point:
            corners = get_landmark_corners(
                selected_point['x'], selected_point['y'], selected_point['z'],
                selected_point['rx'], selected_point['ry'], selected_point['rz']
            )
            verts = [list(zip(corners[:, 0], corners[:, 1], corners[:, 2]))]
            poly = Poly3DCollection(verts, alpha=0.7, facecolor='red', edgecolor='black', linewidths=2)
            ax.add_collection3d(poly)

            ax.scatter([selected_point['x']], [selected_point['y']], [selected_point['z']],
                       c='darkred', marker='o', s=50, label='Landmark')

            center = np.array([selected_point['x'], selected_point['y'], selected_point['z']])
            margin = LANDMARK_SIZE * 2
            ax.set_xlim(center[0] - margin, center[0] + margin)
            ax.set_ylim(center[1] - margin, center[1] + margin)
            ax.set_zlim(center[2] - margin, center[2] + margin)

        if show_tcp and self.current_tcp:
            ax.scatter([self.current_tcp[0]], [self.current_tcp[1]], [self.current_tcp[2]],
                       c='orange', marker='^', s=150, label='현재 TCP')

        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Z (mm)')
        ax.set_title('3D View')
        ax.set_box_aspect([1, 1, 1])

        if selected_point or (show_tcp and self.current_tcp):
            ax.legend(loc='upper left', fontsize=8)

        graph.draw()

    def _update_2d_graph(self, main_widget, overview_widget, selected_point,
                         key_x, key_y, xlabel, ylabel, title, show_tcp, plane):
        axis_map = {'x': 0, 'y': 1, 'z': 2}
        idx_x = axis_map[key_x]
        idx_y = axis_map[key_y]

        for widget_name in [main_widget, overview_widget]:
            if widget_name not in self.graph_widgets:
                continue

            graph = self.graph_widgets[widget_name]
            graph.clear()
            ax = graph.ax

            if selected_point:
                corners = get_landmark_corners(
                    selected_point['x'], selected_point['y'], selected_point['z'],
                    selected_point['rx'], selected_point['ry'], selected_point['rz']
                )
                corners_2d = corners[:, [idx_x, idx_y]]
                poly = Polygon(corners_2d, closed=True, alpha=0.7,
                               facecolor='red', edgecolor='black', linewidth=2, label='Landmark')
                ax.add_patch(poly)

                ax.scatter([selected_point[key_x]], [selected_point[key_y]],
                           c='darkred', marker='o', s=50)

            if show_tcp and self.current_tcp:
                if plane == 'xy':
                    ax.scatter([self.current_tcp[0]], [self.current_tcp[1]],
                               c='orange', marker='^', s=100, label='현재 TCP')
                elif plane == 'xz':
                    ax.scatter([self.current_tcp[0]], [self.current_tcp[2]],
                               c='orange', marker='^', s=100, label='현재 TCP')
                elif plane == 'yz':
                    ax.scatter([self.current_tcp[1]], [self.current_tcp[2]],
                               c='orange', marker='^', s=100, label='현재 TCP')

            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            ax.set_aspect('equal', adjustable='datalim')
            ax.grid(True, alpha=0.3)
            ax.autoscale_view()

            if selected_point or (show_tcp and self.current_tcp):
                ax.legend(loc='upper left', fontsize=8)

            graph.draw()

    def toggle_ros_connection(self):
        if not ROS2_AVAILABLE:
            QMessageBox.warning(self, "경고", "ROS2가 설치되어 있지 않습니다.")
            self.pushButton_connectROS.setChecked(False)
            return

        if self.pushButton_connectROS.isChecked():
            self.connect_ros()
        else:
            self.disconnect_ros()

    def connect_ros(self):
        try:
            if not rclpy.ok():
                rclpy.init()

            self.ros_node = rclpy.create_node('landmark_visualizer')

            self.ros_node.create_subscription(
                Float32MultiArray,
                '/tm_robot/tcp_pose',
                self._tcp_callback,
                10
            )

            self.ros_node.create_subscription(
                JointState,
                '/joint_states',
                self._joint_callback,
                10
            )

            self.ros_thread = ROS2Thread(self.ros_node)
            self.ros_thread.start()

            self.label_rosStatus.setText("연결됨")
            self.label_rosStatus.setStyleSheet("color: green;")
            self.pushButton_connectROS.setText("연결 해제")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"ROS2 연결 실패:\n{str(e)}")
            self.pushButton_connectROS.setChecked(False)

    def disconnect_ros(self):
        if self.ros_thread:
            self.ros_thread.stop()
            self.ros_thread.join(timeout=1.0)
            self.ros_thread = None

        if self.ros_node:
            self.ros_node.destroy_node()
            self.ros_node = None

        self.label_rosStatus.setText("연결 안됨")
        self.label_rosStatus.setStyleSheet("color: #999;")
        self.pushButton_connectROS.setText("ROS2 연결")
        self.label_tcpPose.setText("TCP: -")
        self.label_jointState.setText("Joints: -")

    def _tcp_callback(self, msg):
        if len(msg.data) >= 6:
            self.tcp_updated.emit(list(msg.data[:6]))

    def _joint_callback(self, msg):
        if msg.position:
            self.joint_updated.emit(list(msg.position))

    def _on_tcp_updated(self, tcp: list):
        self.current_tcp = tcp
        self.label_tcpPose.setText(f"TCP: X={tcp[0]:.1f} Y={tcp[1]:.1f} Z={tcp[2]:.1f}")
        if self.checkBox_showRobotTCP.isChecked():
            self.update_graphs()

    def _on_joint_updated(self, joints: list):
        self.current_joints = joints
        joints_str = " ".join([f"{j:.1f}" for j in joints[:6]])
        self.label_jointState.setText(f"Joints: {joints_str}")

    def reset_all_views(self):
        for widget in self.graph_widgets.values():
            widget.reset_view()

    def zoom_fit(self):
        self.update_graphs()

    def export_image(self):
        if self.data is None and self.current_tcp is None:
            QMessageBox.warning(self, "경고", "표시할 데이터가 없습니다.")
            return

        dir_path = QFileDialog.getExistingDirectory(self, "저장 폴더 선택")
        if dir_path:
            for name, widget in self.graph_widgets.items():
                if 'overview' not in name:
                    file_path = Path(dir_path) / f"{name}.png"
                    widget.figure.savefig(str(file_path), dpi=150, bbox_inches='tight')
            QMessageBox.information(self, "완료", f"그래프가 {dir_path}에 저장되었습니다.")

    def closeEvent(self, event):
        self.disconnect_ros()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = LandmarkVisualizerWindow()
    window.show()

    if len(sys.argv) > 1:
        window.load_csv(sys.argv[1])

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
