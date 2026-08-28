import os
from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QTableWidgetItem, QFileDialog, QMessageBox
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QBrush, QColor
from PyQt5 import uic

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

from .base_tab import BaseTab
from .. import paths


class PrecisionTestTab(BaseTab):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.precision_ui = None

        self.figure_xy = None
        self.canvas_xy = None
        self.ax_xy = None
        self.figure_yz = None
        self.canvas_yz = None
        self.ax_yz = None
        self.figure_zx = None
        self.canvas_zx = None
        self.ax_zx = None
        self.figure_rotation = None
        self.canvas_rotation = None
        self.ax_rotation = None

        self.plate_dataset = None
        self.figure_dataset = None
        self.canvas_dataset = None
        self.axes_dataset = {}
        self.figure_jig3d = None
        self.canvas_jig3d = None
        self.ax_jig3d = None

    def connect_signals(self):
        pass

    def init_ui(self):
        from ..services.precision_test_manager import PrecisionTestManager

        self.mw.precision_test_manager = PrecisionTestManager()

        ui_path = paths.ui('precision_test_tab.ui')
        self.precision_ui = uic.loadUi(ui_path)

        layout = QVBoxLayout(self.mw.tab_precisionTest)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.precision_ui)

        self.mw.precision_ui = self.precision_ui

        self._connect_precision_test_signals()

        self._init_precision_test_graphs()

        self.precision_ui.radioButton_staticTest.setChecked(True)
        self.precision_ui.widget_dynamicSettings.setEnabled(False)

        self._update_precision_recipe_label()

        self._init_plate_dataset_block()

    def _connect_precision_test_signals(self):
        ui = self.precision_ui

        ui.radioButton_staticTest.toggled.connect(self._on_test_mode_changed)
        ui.radioButton_dynamicTest.toggled.connect(self._on_test_mode_changed)

        ui.pushButton_startTest.clicked.connect(self._on_start_precision_test)
        ui.pushButton_stopTest.clicked.connect(self._on_stop_precision_test)
        ui.pushButton_resetTest.clicked.connect(self._on_reset_precision_test)

        ui.pushButton_exportCSV.clicked.connect(self._on_export_precision_csv)
        ui.pushButton_saveGraph.clicked.connect(self._on_save_precision_graph)
        ui.pushButton_precisionAnalyzer.clicked.connect(self._on_open_precision_analyzer)

    def _init_precision_test_graphs(self):
        ui = self.precision_ui

        self.figure_xy = Figure(figsize=(4, 3))
        self.canvas_xy = FigureCanvas(self.figure_xy)
        self.ax_xy = self.figure_xy.add_subplot(111)
        self.ax_xy.set_xlabel('X (mm)')
        self.ax_xy.set_ylabel('Y (mm)')
        self.ax_xy.set_title('X-Y Plane')
        self.ax_xy.grid(True)
        layout_xy = QVBoxLayout(ui.widget_graphXY)
        layout_xy.setContentsMargins(0, 0, 0, 0)
        layout_xy.addWidget(self.canvas_xy)

        self.figure_yz = Figure(figsize=(4, 3))
        self.canvas_yz = FigureCanvas(self.figure_yz)
        self.ax_yz = self.figure_yz.add_subplot(111)
        self.ax_yz.set_xlabel('Y (mm)')
        self.ax_yz.set_ylabel('Z (mm)')
        self.ax_yz.set_title('Y-Z Plane')
        self.ax_yz.grid(True)
        layout_yz = QVBoxLayout(ui.widget_graphYZ)
        layout_yz.setContentsMargins(0, 0, 0, 0)
        layout_yz.addWidget(self.canvas_yz)

        self.figure_zx = Figure(figsize=(4, 3))
        self.canvas_zx = FigureCanvas(self.figure_zx)
        self.ax_zx = self.figure_zx.add_subplot(111)
        self.ax_zx.set_xlabel('X (mm)')
        self.ax_zx.set_ylabel('Z (mm)')
        self.ax_zx.set_title('X-Z Plane')
        self.ax_zx.grid(True)
        layout_zx = QVBoxLayout(ui.widget_graphZX)
        layout_zx.setContentsMargins(0, 0, 0, 0)
        layout_zx.addWidget(self.canvas_zx)

        self.figure_rotation = Figure(figsize=(4, 3))
        self.canvas_rotation = FigureCanvas(self.figure_rotation)
        self.ax_rotation = self.figure_rotation.add_subplot(111)
        self.ax_rotation.set_xlabel('Rx (deg)')
        self.ax_rotation.set_ylabel('Rz (deg)')
        self.ax_rotation.set_title('Rotation Distribution')
        self.ax_rotation.grid(True)
        layout_rotation = QVBoxLayout(ui.widget_graphRotation)
        layout_rotation.setContentsMargins(0, 0, 0, 0)
        layout_rotation.addWidget(self.canvas_rotation)


    def _on_test_mode_changed(self):
        ui = self.precision_ui
        is_dynamic = ui.radioButton_dynamicTest.isChecked()
        ui.widget_dynamicSettings.setEnabled(is_dynamic)

        self.mw.precision_test_manager.test_mode = 'dynamic' if is_dynamic else 'static'

        if is_dynamic:
            self._update_precision_recipe_label()

    def _update_precision_recipe_label(self):
        ui = self.precision_ui
        recipe = self.recipe_manager.current_recipe

        if recipe and recipe.file_path:
            filename = os.path.basename(recipe.file_path)
            ui.label_currentRecipe.setText(filename)
            ui.label_currentRecipe.setStyleSheet("color: #333; font-weight: bold;")
        else:
            ui.label_currentRecipe.setText("(로드된 Recipe 없음)")
            ui.label_currentRecipe.setStyleSheet("color: #666; font-style: italic;")


    def _on_start_precision_test(self):
        ui = self.precision_ui
        manager = self.mw.precision_test_manager

        iterations = ui.spinBox_iterations.value()
        manager.total_iterations = iterations
        manager.is_running = True

        ui.pushButton_startTest.setEnabled(False)
        ui.pushButton_stopTest.setEnabled(True)
        ui.pushButton_resetTest.setEnabled(False)

        self._log(f"정밀도 테스트 시작: {iterations}회 반복")

        if manager.test_mode == 'static':
            self._run_static_precision_test()
        else:
            self._run_dynamic_precision_test()

    def _run_static_precision_test(self):
        manager = self.mw.precision_test_manager

        if manager.current_iteration >= manager.total_iterations:
            self._finish_precision_test()
            return

        wait_time = 0.5

        success, msg = self.vision_manager.execute_tm_landmark_scan(wait_time)

        if not success:
            self._log(f"스캔 오류: {msg}")
            self._handle_measurement_error(msg)
            return

        read_success, result = self.vision_manager.execute_tm_landmark_read()

        if read_success and isinstance(result, dict):
            tcp = self.mw.current_tcp_pose if self.mw.current_tcp_pose else [0, 0, 0, 0, 0, 0]

            manager.add_measurement(
                result['x'], result['y'], result['z'],
                result['rx'], result['ry'], result['rz'],
                tcp[0], tcp[1], tcp[2], tcp[3], tcp[4], tcp[5]
            )

            self._update_precision_test_ui()
            self._log(f"측정 완료: {manager.current_iteration}/{manager.total_iterations}")

            if manager.is_running:
                QTimer.singleShot(100, self._run_static_precision_test)
        else:
            error_msg = result if isinstance(result, str) else "결과 읽기 실패"
            self._log(f"측정 오류: {error_msg}")
            self._handle_measurement_error(error_msg)

    def _handle_measurement_error(self, error_msg: str):
        manager = self.mw.precision_test_manager

        reply = QMessageBox.question(
            self.mw,
            "측정 오류",
            f"{error_msg}\n계속 진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes and manager.is_running:
            QTimer.singleShot(100, self._run_static_precision_test)
        else:
            self._finish_precision_test()

    def _run_dynamic_precision_test(self):
        manager = self.mw.precision_test_manager
        recipe = self.recipe_manager.current_recipe

        manager.on_log = self._log
        manager.on_measurement_added = self._update_precision_test_ui
        manager.on_test_completed = self._on_precision_test_completed
        manager.on_request_next_iteration = self._on_request_next_iteration

        success, msg = manager.start_dynamic_test(recipe, self.job_executor, self.ros_node)

        if not success:
            QMessageBox.warning(self.mw, "오류", msg)
            self._finish_precision_test()

    def _on_precision_test_completed(self):
        self._finish_precision_test()

    def _on_request_next_iteration(self):
        QTimer.singleShot(500, self.mw.precision_test_manager.run_next_iteration)

    def _finish_precision_test(self):
        ui = self.precision_ui
        manager = self.mw.precision_test_manager

        manager.is_running = False

        ui.pushButton_startTest.setEnabled(True)
        ui.pushButton_stopTest.setEnabled(False)
        ui.pushButton_resetTest.setEnabled(True)

        self._log(f"정밀도 테스트 완료: 총 {manager.current_iteration}회 측정")
        self._update_precision_test_ui()

    def _on_stop_precision_test(self):
        ui = self.precision_ui
        self.mw.precision_test_manager.is_running = False

        ui.pushButton_startTest.setEnabled(True)
        ui.pushButton_stopTest.setEnabled(False)
        ui.pushButton_resetTest.setEnabled(True)

        self._log("정밀도 테스트 중지됨")

    def _on_reset_precision_test(self):
        self.mw.precision_test_manager.reset()
        self._update_precision_test_ui()
        self._log("정밀도 테스트 초기화 완료")


    def _on_export_precision_csv(self):
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
            data_dir = os.path.join(pkg_dir, '..', '..', 'data', date_str)

        data_dir = os.path.abspath(data_dir)
        os.makedirs(data_dir, exist_ok=True)

        default_filename = os.path.join(data_dir, f"precision_test_{datetime_str}.csv")

        filename, _ = QFileDialog.getSaveFileName(
            self.mw,
            "CSV 저장",
            default_filename,
            "CSV Files (*.csv)"
        )

        if filename:
            if self.mw.precision_test_manager.export_to_csv(filename):
                self._log(f"CSV 저장 완료: {filename}")
            else:
                self._log("CSV 저장 실패")

    def _on_save_precision_graph(self):
        if not self.mw.precision_test_manager.measurements:
            QMessageBox.warning(self.mw, "데이터 없음",
                              "저장할 그래프 데이터가 없습니다.\n먼저 정밀도 테스트를 수행하세요.")
            return

        default_name = os.path.join(
            os.path.expanduser("~"),
            f"precision_graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self.mw, "그래프 저장", default_name, "PNG Files (*.png)"
        )
        if not filename:
            return

        base, ext = os.path.splitext(filename)
        if not ext:
            ext = ".png"

        saved = []
        try:
            for plane, fig in (("XY", self.figure_xy),
                               ("YZ", self.figure_yz),
                               ("ZX", self.figure_zx)):
                path = f"{base}_{plane}{ext}"
                fig.savefig(path, dpi=150, bbox_inches="tight")
                saved.append(os.path.basename(path))
            self._log(f"그래프 저장 완료: {', '.join(saved)}")
        except (OSError, ValueError) as e:
            self._log(f"그래프 저장 실패: {e}")

    def _on_open_precision_analyzer(self):
        if not self.mw.precision_test_manager.measurements:
            QMessageBox.warning(self.mw, "데이터 없음",
                              "분석할 측정 데이터가 없습니다.\n먼저 정밀도 테스트를 수행하세요.")
            return

        try:
            import sys
            analyzer_dir = str(paths.SCRIPTS_DIR)
            if analyzer_dir not in sys.path:
                sys.path.insert(0, analyzer_dir)

            from precision_analyzer import MainWindow as AnalyzerWindow

            self.mw.analyzer_window = AnalyzerWindow()
            self.mw.analyzer_window.load_from_manager(self.mw.precision_test_manager)
            self.mw.analyzer_window.show()
            self._log("정밀도 분석 도구를 실행했습니다.")

        except Exception as e:
            QMessageBox.warning(self.mw, "실행 오류", f"정밀도 분석 도구 실행 실패:\n{e}")


    def _update_precision_test_ui(self):
        ui = self.precision_ui
        manager = self.mw.precision_test_manager

        progress = manager.get_progress_percentage()
        ui.progressBar_test.setValue(int(progress))
        ui.label_progress.setText(
            f"진행: {manager.current_iteration}/{manager.total_iterations} ({progress:.1f}%)"
        )

        stats = manager.get_statistics()
        ui.label_xStatsValue.setText(f"μ={stats.mean_x:.4f}  σ={stats.std_x:.4f}")
        ui.label_yStatsValue.setText(f"μ={stats.mean_y:.4f}  σ={stats.std_y:.4f}")
        ui.label_zStatsValue.setText(f"μ={stats.mean_z:.4f}  σ={stats.std_z:.4f}")
        ui.label_rxStatsValue.setText(f"μ={stats.mean_rx:.4f}  σ={stats.std_rx:.4f}")
        ui.label_ryStatsValue.setText(f"μ={stats.mean_ry:.4f}  σ={stats.std_ry:.4f}")
        ui.label_rzStatsValue.setText(f"μ={stats.mean_rz:.4f}  σ={stats.std_rz:.4f}")

        ui.label_3sigmaPosition.setText(
            f"X=±{stats.sigma3_x:.4f}  Y=±{stats.sigma3_y:.4f}  Z=±{stats.sigma3_z:.4f}"
        )
        ui.label_3sigmaRotation.setText(
            f"Rx=±{stats.sigma3_rx:.4f}  Ry=±{stats.sigma3_ry:.4f}  Rz=±{stats.sigma3_rz:.4f}"
        )

        ui.tableWidget_measurements.setRowCount(len(manager.measurements))
        for i, m in enumerate(manager.measurements):
            ui.tableWidget_measurements.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            ui.tableWidget_measurements.setItem(i, 1, QTableWidgetItem(f"{m.x:.4f}"))
            ui.tableWidget_measurements.setItem(i, 2, QTableWidgetItem(f"{m.y:.4f}"))
            ui.tableWidget_measurements.setItem(i, 3, QTableWidgetItem(f"{m.z:.4f}"))
            ui.tableWidget_measurements.setItem(i, 4, QTableWidgetItem(f"{m.rx:.4f}"))
            ui.tableWidget_measurements.setItem(i, 5, QTableWidgetItem(f"{m.ry:.4f}"))
            ui.tableWidget_measurements.setItem(i, 6, QTableWidgetItem(f"{m.rz:.4f}"))
            ui.tableWidget_measurements.setItem(i, 7, QTableWidgetItem(f"{m.tcp_x:.2f}"))
            ui.tableWidget_measurements.setItem(i, 8, QTableWidgetItem(f"{m.tcp_y:.2f}"))
            ui.tableWidget_measurements.setItem(i, 9, QTableWidgetItem(f"{m.tcp_z:.2f}"))
            ui.tableWidget_measurements.setItem(i, 10, QTableWidgetItem(f"{m.tcp_rx:.2f}"))
            ui.tableWidget_measurements.setItem(i, 11, QTableWidgetItem(f"{m.tcp_ry:.2f}"))
            ui.tableWidget_measurements.setItem(i, 12, QTableWidgetItem(f"{m.tcp_rz:.2f}"))
            ui.tableWidget_measurements.setItem(i, 13, QTableWidgetItem(m.timestamp))

        self._update_precision_test_graphs()

    def _update_precision_test_graphs(self):
        data = self.mw.precision_test_manager.get_measurements_as_arrays()

        self.ax_xy.clear()
        self.ax_xy.set_xlabel('X (mm)')
        self.ax_xy.set_ylabel('Y (mm)')
        self.ax_xy.set_title('X-Y Plane')
        self.ax_xy.grid(True)
        if len(data['x']) > 0:
            self.ax_xy.scatter(data['x'], data['y'], alpha=0.6)
        self.ax_xy.set_aspect('equal', adjustable='datalim')
        self.canvas_xy.draw()

        self.ax_yz.clear()
        self.ax_yz.set_xlabel('Y (mm)')
        self.ax_yz.set_ylabel('Z (mm)')
        self.ax_yz.set_title('Y-Z Plane')
        self.ax_yz.grid(True)
        if len(data['y']) > 0:
            self.ax_yz.scatter(data['y'], data['z'], alpha=0.6)
        self.ax_yz.set_aspect('equal', adjustable='datalim')
        self.canvas_yz.draw()

        self.ax_zx.clear()
        self.ax_zx.set_xlabel('X (mm)')
        self.ax_zx.set_ylabel('Z (mm)')
        self.ax_zx.set_title('X-Z Plane')
        self.ax_zx.grid(True)
        if len(data['x']) > 0:
            self.ax_zx.scatter(data['x'], data['z'], alpha=0.6)
        self.ax_zx.set_aspect('equal', adjustable='datalim')
        self.canvas_zx.draw()

        self.ax_rotation.clear()
        self.ax_rotation.set_xlabel('Rx (deg)')
        self.ax_rotation.set_ylabel('Rz (deg)')
        self.ax_rotation.set_title('Rotation Distribution')
        self.ax_rotation.grid(True)
        if len(data['rx']) > 0:
            self.ax_rotation.scatter(data['rx'], data['rz'], alpha=0.6)
        self.canvas_rotation.draw()


    JIG_COLORS = ('#d62728', '#1f77b4', '#2ca02c', '#ff7f0e')
    DATASET_PLANES = (
        ('xy', 'x', 'y', 'X (mm)', 'Y (mm)', 'X-Y Plane'),
        ('yz', 'y', 'z', 'Y (mm)', 'Z (mm)', 'Y-Z Plane'),
        ('zx', 'x', 'z', 'X (mm)', 'Z (mm)', 'X-Z Plane'),
        ('rot', 'rx', 'rz', 'Rx (deg)', 'Rz (deg)', 'Rotation Distribution'),
    )
    PALLET_OVERLAY_COLORS = ('#1f77b4', '#ff7f0e', '#2ca02c',
                             '#d62728', '#9467bd', '#8c564b')

    def _init_plate_dataset_block(self):
        from ..services.plate_pose_dataset import PlatePoseDataset

        self.plate_dataset = PlatePoseDataset()
        self.mw.plate_dataset = self.plate_dataset

        self._init_plate_dataset_graphs()
        self._connect_plate_dataset_signals()

        self.plate_dataset.set_root(self.plate_dataset.default_root())
        self._refresh_pallet_combo()

    def _connect_plate_dataset_signals(self):
        ui = self.precision_ui

        ui.pushButton_loadDataset.clicked.connect(self._on_load_plate_dataset)
        ui.pushButton_browseDataset.clicked.connect(self._on_browse_dataset_root)
        ui.pushButton_exportDatasetCSV.clicked.connect(self._on_export_dataset_csv)
        ui.pushButton_saveDatasetGraph.clicked.connect(self._on_save_dataset_graph)

        ui.checkBox_datasetAbsolute.toggled.connect(self._on_dataset_view_toggled)
        ui.checkBox_overlayAllPallets.toggled.connect(self._on_overlay_toggled)
        ui.pushButton_saveJigShape.clicked.connect(self._on_save_jig_shape)

    def _init_plate_dataset_graphs(self):
        ui = self.precision_ui

        self.figure_dataset = Figure(figsize=(8, 6))
        self.canvas_dataset = FigureCanvas(self.figure_dataset)
        self.axes_dataset = {}
        for index, (key, _, _, xlabel, ylabel, title) in enumerate(self.DATASET_PLANES, start=1):
            ax = self.figure_dataset.add_subplot(2, 2, index)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
            self.axes_dataset[key] = ax
        self.figure_dataset.tight_layout()

        layout_dataset = QVBoxLayout(ui.widget_datasetScatter)
        layout_dataset.setContentsMargins(0, 0, 0, 0)
        layout_dataset.addWidget(self.canvas_dataset)

        self.figure_jig3d = Figure(figsize=(6, 5))
        self.canvas_jig3d = FigureCanvas(self.figure_jig3d)
        self.ax_jig3d = self.figure_jig3d.add_subplot(111, projection='3d')
        self.ax_jig3d.set_xlabel('X (mm)')
        self.ax_jig3d.set_ylabel('Y (mm)')
        self.ax_jig3d.set_zlabel('Z (mm)')

        layout_jig3d = QVBoxLayout(ui.widget_jig3D)
        layout_jig3d.setContentsMargins(0, 0, 0, 0)
        layout_jig3d.addWidget(self.canvas_jig3d)

    def _refresh_pallet_combo(self):
        ui = self.precision_ui
        pallets = self.plate_dataset.list_pallets()

        ui.comboBox_plateFolder.clear()
        ui.comboBox_plateFolder.addItems(pallets)

        if not pallets:
            root = self.plate_dataset.default_root()
            ui.label_datasetStatus.setText(f"데이터 폴더 없음: {root}")
        else:
            ui.label_datasetStatus.setText(f"팔레트 {len(pallets)}개 발견")

    def _current_dataset_variant(self) -> str:
        from ..services.plate_pose_dataset import VARIANT_CORRECTED, VARIANT_RAW

        if self.precision_ui.radioButton_datasetRaw.isChecked():
            return VARIANT_RAW
        return VARIANT_CORRECTED

    def _on_browse_dataset_root(self):
        directory = QFileDialog.getExistingDirectory(
            self.mw,
            "plate_pose_calc 폴더 선택",
            str(self.plate_dataset.default_root().parent)
        )
        if not directory:
            return

        if self.plate_dataset.set_root(directory):
            self._log(f"데이터셋 루트 변경: {directory}")
        else:
            QMessageBox.warning(self.mw, "폴더 오류",
                                "팔레트 하위 폴더를 찾지 못했습니다:\n" + directory)
        self._refresh_pallet_combo()

    def _on_load_plate_dataset(self):
        ui = self.precision_ui
        pallet = ui.comboBox_plateFolder.currentText()

        if not pallet:
            QMessageBox.warning(self.mw, "선택 없음", "팔레트를 먼저 선택하세요.")
            return

        success, message = self.plate_dataset.load(pallet, self._current_dataset_variant())
        ui.label_datasetStatus.setText(message)
        self._log(f"[데이터셋] {message}")

        if not success:
            QMessageBox.warning(self.mw, "로드 실패", message)
            return

        self._update_dataset_stats_table()
        self._update_dataset_scatter()
        self._update_jig_shape()

    def _update_dataset_stats_table(self):
        ui = self.precision_ui
        rows = self.plate_dataset.all_statistics()

        ui.tableWidget_datasetStats.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = [
                row.target,
                row.axis,
                str(row.count),
                f"{row.mean:.4f}",
                f"{row.std:.4f}",
                f"±{row.sigma3:.4f}",
                f"{row.minimum:.4f}",
                f"{row.maximum:.4f}",
                f"{row.value_range:.4f}",
            ]
            for column, text in enumerate(values):
                ui.tableWidget_datasetStats.setItem(i, column, QTableWidgetItem(text))

    def _update_dataset_scatter(self):
        from ..services.plate_pose_dataset import JIG_KEYS

        absolute = self.precision_ui.checkBox_datasetAbsolute.isChecked()
        if absolute:
            series = [self.plate_dataset.jig_series(i) for i in range(len(JIG_KEYS))]
        else:
            series = [self.plate_dataset.jig_deviation_series(i) for i in range(len(JIG_KEYS))]

        for key, x_axis, y_axis, xlabel, ylabel, title in self.DATASET_PLANES:
            ax = self.axes_dataset[key]
            ax.clear()
            ax.set_xlabel(xlabel if absolute else f"Δ{xlabel}")
            ax.set_ylabel(ylabel if absolute else f"Δ{ylabel}")
            ax.set_title(title if absolute else f"{title} (평균 대비 편차)")
            ax.grid(True, alpha=0.3)

            for index, data in enumerate(series):
                if not data[x_axis]:
                    continue
                ax.scatter(data[x_axis], data[y_axis], alpha=0.7, s=25,
                           color=self.JIG_COLORS[index], label=JIG_KEYS[index])

            if not absolute:
                ax.axhline(0, color='#999', linewidth=0.8, zorder=0)
                ax.axvline(0, color='#999', linewidth=0.8, zorder=0)

            if key != 'rot':
                ax.set_aspect('equal', adjustable='datalim')
            ax.legend(loc='best', fontsize=8)

        self.figure_dataset.tight_layout()
        self.canvas_dataset.draw()

    def _on_dataset_view_toggled(self):
        if self.plate_dataset.records:
            self._update_dataset_scatter()

    def _side_pair_colors(self, sides: dict, validator) -> dict:
        pairs = (
            (('jig1-jig3', 'jig2-jig4'), validator.TOLERANCE_SIDE_DIFF),
            (('jig1-jig2', 'jig3-jig4'), validator.TOLERANCE_SIDE_DIFF),
            (('jig1-jig4', 'jig2-jig3'), validator.TOLERANCE_DIAGONAL_DIFF),
        )

        colors = {}
        for (first, second), tolerance in pairs:
            over = abs(sides[first] - sides[second]) > tolerance
            colors[first] = colors[second] = '#d62728' if over else '#1f77b4'
        return colors

    def _draw_jig_rectangle(self, ax, marks, sides, colors, label=None, annotate=True):
        edges = (
            ('jig1-jig3', 0, 2, '-', 0.5),
            ('jig2-jig4', 1, 3, '-', 0.5),
            ('jig1-jig2', 0, 1, '-', 0.5),
            ('jig3-jig4', 2, 3, '-', 0.5),
            ('jig1-jig4', 0, 3, '--', 0.30),
            ('jig2-jig3', 1, 2, '--', 0.70),
        )

        for index, (key, start, end, style, label_at) in enumerate(edges):
            a, b = marks[start], marks[end]
            ax.plot([a['x'], b['x']], [a['y'], b['y']], [a['z'], b['z']],
                    linestyle=style, linewidth=2 if style == '-' else 1.2,
                    color=colors.get(key, '#1f77b4'),
                    alpha=1.0 if style == '-' else 0.6,
                    label=label if (label and index == 0) else None)

            if annotate:
                ax.text(a['x'] + (b['x'] - a['x']) * label_at,
                        a['y'] + (b['y'] - a['y']) * label_at,
                        a['z'] + (b['z'] - a['z']) * label_at,
                        f"{sides[key]:.2f}", fontsize=8,
                        color=colors.get(key, '#1f77b4'), ha='center')

        for index, mark in enumerate(marks):
            ax.scatter([mark['x']], [mark['y']], [mark['z']],
                       color=self.JIG_COLORS[index] if annotate else colors.get('jig1-jig3'),
                       s=45, depthshade=False)
            if annotate:
                ax.text(mark['x'], mark['y'], mark['z'], f"  jig{index + 1}", fontsize=9)

        center_x = sum(m['x'] for m in marks) / 4
        center_y = sum(m['y'] for m in marks) / 4
        center_z = sum(m['z'] for m in marks) / 4
        ax.scatter([center_x], [center_y], [center_z], marker='*', s=140,
                   color='#7f7f7f' if annotate else colors.get('jig1-jig3', '#7f7f7f'),
                   depthshade=False)

    def _update_jig_shape(self):
        ui = self.precision_ui

        if self.precision_ui.checkBox_overlayAllPallets.isChecked():
            self._update_jig3d_overlay()
            return

        marks = self.plate_dataset.mean_marks()
        sides, results = self.plate_dataset.geometry_report(marks)

        if not results:
            ui.label_jigShapeVerdict.setText("(검사할 데이터 없음)")
            ui.tableWidget_jigCheck.setRowCount(0)
            return

        validator = self.plate_dataset.build_validator(marks)
        colors = self._side_pair_colors(sides, validator)

        self._fill_jig_check_table(sides, results)

        failed = [r for r in results if not r.passed]
        if failed:
            ui.label_jigShapeVerdict.setText(f"❌ FAIL — {len(failed)}개 항목 초과")
            ui.label_jigShapeVerdict.setStyleSheet("color: #c00; font-weight: bold;")
        else:
            ui.label_jigShapeVerdict.setText("✅ PASS — 전 항목 허용 이내")
            ui.label_jigShapeVerdict.setStyleSheet("color: #080; font-weight: bold;")

        ax = self.ax_jig3d
        ax.clear()
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Z (mm)')
        ax.set_title(f"{self.plate_dataset.pallet} / {self.plate_dataset.variant} "
                     f"(n={len(self.plate_dataset.records)} 평균)")

        self._draw_jig_rectangle(ax, marks, sides, colors)
        self._apply_equal_3d_range(ax, marks)

        self.figure_jig3d.tight_layout()
        self.canvas_jig3d.draw()

    def _fill_jig_check_table(self, sides: dict, results):
        ui = self.precision_ui
        side_labels = (
            ('장변 jig1-jig3', 'jig1-jig3'),
            ('장변 jig2-jig4', 'jig2-jig4'),
            ('단변 jig1-jig2', 'jig1-jig2'),
            ('단변 jig3-jig4', 'jig3-jig4'),
            ('대각선 jig1-jig4', 'jig1-jig4'),
            ('대각선 jig2-jig3', 'jig2-jig3'),
        )

        ui.tableWidget_jigCheck.setRowCount(len(side_labels) + len(results))

        row = 0
        for label, key in side_labels:
            ui.tableWidget_jigCheck.setItem(row, 0, QTableWidgetItem(label))
            ui.tableWidget_jigCheck.setItem(row, 1, QTableWidgetItem(f"{sides[key]:.3f} mm"))
            ui.tableWidget_jigCheck.setItem(row, 2, QTableWidgetItem("-"))
            ui.tableWidget_jigCheck.setItem(row, 3, QTableWidgetItem("측정"))
            row += 1

        for result in results:
            verdict = QTableWidgetItem("PASS" if result.passed else "FAIL")
            verdict.setForeground(QBrush(QColor('#008800' if result.passed else '#cc0000')))

            ui.tableWidget_jigCheck.setItem(row, 0, QTableWidgetItem(result.name))
            ui.tableWidget_jigCheck.setItem(
                row, 1, QTableWidgetItem(f"{result.value:.3f} {result.unit}"))
            ui.tableWidget_jigCheck.setItem(
                row, 2, QTableWidgetItem(f"±{result.threshold} {result.unit}"))
            ui.tableWidget_jigCheck.setItem(row, 3, verdict)
            row += 1

    @staticmethod
    def _centred(marks):
        center = {axis: sum(m[axis] for m in marks) / len(marks) for axis in ('x', 'y', 'z')}
        return [dict(m, x=m['x'] - center['x'], y=m['y'] - center['y'], z=m['z'] - center['z'])
                for m in marks]

    def _update_jig3d_overlay(self):
        from ..services.plate_pose_dataset import PlatePoseDataset

        ui = self.precision_ui
        variant = self._current_dataset_variant()
        pallets = self.plate_dataset.list_pallets()

        ax = self.ax_jig3d
        ax.clear()
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Z (mm)')
        ax.set_title(f"팔레트 전체 겹쳐보기 (중심 정렬) / {variant}")

        overlay = PlatePoseDataset()
        overlay.root = self.plate_dataset.root

        all_marks = []
        summary_rows = []

        for index, pallet in enumerate(pallets):
            loaded, _ = overlay.load(pallet, variant)
            if not loaded:
                continue

            marks = overlay.mean_marks()
            sides, results = overlay.geometry_report(marks)
            if not results:
                continue

            centred = self._centred(marks)
            color = self.PALLET_OVERLAY_COLORS[index % len(self.PALLET_OVERLAY_COLORS)]
            flat_colors = {key: color for key in sides}
            self._draw_jig_rectangle(ax, centred, sides, flat_colors,
                                     label=pallet, annotate=False)
            all_marks.extend(centred)
            summary_rows.append((pallet, results))

        if not all_marks:
            ui.label_jigShapeVerdict.setText("(겹쳐볼 데이터 없음)")
            ui.tableWidget_jigCheck.setRowCount(0)
            self.canvas_jig3d.draw()
            return

        self._apply_equal_3d_range(ax, all_marks)
        ax.legend(loc='upper left', fontsize=8)
        self.figure_jig3d.tight_layout()
        self.canvas_jig3d.draw()

        self._fill_overlay_summary_table(summary_rows)

    def _fill_overlay_summary_table(self, summary_rows):
        ui = self.precision_ui
        ui.tableWidget_jigCheck.setRowCount(len(summary_rows))

        failed_pallets = 0
        for row, (pallet, results) in enumerate(summary_rows):
            failed = [r for r in results if not r.passed]
            if failed:
                failed_pallets += 1
                worst = max(failed, key=lambda r: r.value - r.threshold)
                value_text = f"{worst.value:.3f} {worst.unit}"
                threshold_text = f"±{worst.threshold} {worst.unit}"
                name = worst.name
                verdict_text, color = "FAIL", '#cc0000'
            else:
                name = "전 항목 이내"
                value_text = threshold_text = "-"
                verdict_text, color = "PASS", '#008800'

            verdict = QTableWidgetItem(verdict_text)
            verdict.setForeground(QBrush(QColor(color)))

            ui.tableWidget_jigCheck.setItem(row, 0, QTableWidgetItem(f"{pallet} · {name}"))
            ui.tableWidget_jigCheck.setItem(row, 1, QTableWidgetItem(value_text))
            ui.tableWidget_jigCheck.setItem(row, 2, QTableWidgetItem(threshold_text))
            ui.tableWidget_jigCheck.setItem(row, 3, verdict)

        if failed_pallets:
            ui.label_jigShapeVerdict.setText(f"❌ {failed_pallets}/{len(summary_rows)} 팔레트 FAIL")
            ui.label_jigShapeVerdict.setStyleSheet("color: #c00; font-weight: bold;")
        else:
            ui.label_jigShapeVerdict.setText(f"✅ {len(summary_rows)} 팔레트 전부 PASS")
            ui.label_jigShapeVerdict.setStyleSheet("color: #080; font-weight: bold;")

    def _apply_equal_3d_range(self, ax, marks):
        xs = [m['x'] for m in marks]
        ys = [m['y'] for m in marks]
        zs = [m['z'] for m in marks]

        spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        half = max(max(spans) / 2.0, 1.0) * 1.15

        centers = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2)
        ax.set_xlim(centers[0] - half, centers[0] + half)
        ax.set_ylim(centers[1] - half, centers[1] + half)
        ax.set_zlim(centers[2] - half, centers[2] + half)
        ax.set_box_aspect([1, 1, 1])

    def _on_overlay_toggled(self):
        if not self.plate_dataset.records:
            return
        self._update_jig_shape()

    def _dataset_default_path(self, suffix: str) -> str:
        now = datetime.now()
        data_dir = os.path.join(str(paths.DATA_DIR), now.strftime('%Y%m%d'))
        os.makedirs(data_dir, exist_ok=True)

        pallet = self.plate_dataset.pallet or 'pallet'
        variant = self.plate_dataset.variant
        return os.path.join(
            data_dir,
            f"plate_dataset_{pallet}_{variant}_{now.strftime('%Y%m%d_%H%M%S')}{suffix}"
        )

    def _on_export_dataset_csv(self):
        import csv

        if not self.plate_dataset.records:
            QMessageBox.warning(self.mw, "데이터 없음",
                                "먼저 plate_pose_calc 데이터를 불러오세요.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self.mw, "분석 결과 저장", self._dataset_default_path('.csv'), "CSV Files (*.csv)")
        if not filename:
            return

        marks = self.plate_dataset.mean_marks()
        sides, results = self.plate_dataset.geometry_report(marks)

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['팔레트', self.plate_dataset.pallet,
                                 '변형', self.plate_dataset.variant,
                                 '파일 수', len(self.plate_dataset.records)])
                writer.writerow([])

                writer.writerow(['통계 (jig 반복 재현성)'])
                writer.writerow(['대상', '축', 'n', '평균', '표준편차', '3σ', '최소', '최대', 'Range'])
                for row in self.plate_dataset.all_statistics():
                    writer.writerow([row.target, row.axis, row.count,
                                     f'{row.mean:.4f}', f'{row.std:.4f}', f'{row.sigma3:.4f}',
                                     f'{row.minimum:.4f}', f'{row.maximum:.4f}',
                                     f'{row.value_range:.4f}'])
                writer.writerow([])

                writer.writerow(['변 길이 (평균 좌표 기준, mm)'])
                for key, value in sides.items():
                    writer.writerow([key, f'{value:.4f}'])
                writer.writerow([])

                writer.writerow(['형상 검사'])
                writer.writerow(['항목', '측정값', '허용', '단위', '판정'])
                for result in results:
                    writer.writerow([result.name, f'{result.value:.4f}',
                                     result.threshold, result.unit,
                                     'PASS' if result.passed else 'FAIL'])

            self._log(f"[데이터셋] CSV 저장 완료: {filename}")
        except OSError as e:
            self._log(f"[데이터셋] CSV 저장 실패: {e}")
            QMessageBox.warning(self.mw, "저장 실패", str(e))

    def _save_figure(self, figure, suffix: str, title: str):
        if not self.plate_dataset.records:
            QMessageBox.warning(self.mw, "데이터 없음",
                                "먼저 plate_pose_calc 데이터를 불러오세요.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self.mw, title, self._dataset_default_path(suffix), "PNG Files (*.png)")
        if not filename:
            return

        try:
            figure.savefig(filename, dpi=150, bbox_inches='tight')
            self._log(f"[데이터셋] 그래프 저장 완료: {filename}")
        except (OSError, ValueError) as e:
            self._log(f"[데이터셋] 그래프 저장 실패: {e}")
            QMessageBox.warning(self.mw, "저장 실패", str(e))

    def _on_save_dataset_graph(self):
        self._save_figure(self.figure_dataset, '_scatter.png', "산점도 저장")

    def _on_save_jig_shape(self):
        self._save_figure(self.figure_jig3d, '_jig3d.png', "3D 그래프 저장")
