"""Hand-Eye 테스트 탭 — 측정 위치 그리드 생성·편집·YAML 저장과 반복 측정 실행·통계 표시를 담당한다."""
from PyQt5.QtWidgets import (
    QVBoxLayout, QTableWidgetItem, QFileDialog, QMessageBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5 import uic

from .base_tab import BaseTab
from .. import paths


class HandEyeTestTab(BaseTab):
    """HandEyeTestManager 를 생성·소유하고 위치 목록 편집, QTimer 체인 반복 측정, 결과 표시·CSV 내보내기를 담당하는 탭."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.handeye_ui = None
        self.manager = None

    def connect_signals(self):
        """no-op — 시그널 연결은 .ui 로드가 끝나는 init_ui 내부에서 수행한다."""
        pass

    def init_ui(self):
        ui_path = paths.ui('handeye_test_tab.ui')
        self.handeye_ui = uic.loadUi(ui_path)

        layout = QVBoxLayout(self.mw.tab_handeyeTest)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.handeye_ui)

        self.mw.handeye_ui = self.handeye_ui

        self._init_manager()

        self._connect_handeye_signals()

        self._update_total_positions_label()

    def _init_manager(self):
        from ..services.handeye_test_manager import HandEyeTestManager

        self.manager = HandEyeTestManager(
            job_executor=self.mw.job_executor,
            vision_manager=self.vision_manager,
            log_callback=self._log
        )

        self.manager.on_measurement_complete = self._on_measurement_complete
        self.manager.on_test_complete = self._on_test_complete
        self.manager.on_progress_update = self._on_progress_update

    def _connect_handeye_signals(self):
        ui = self.handeye_ui

        ui.pushButton_readCurrentTcp.clicked.connect(self._on_read_current_tcp)
        ui.pushButton_generatePositions.clicked.connect(self._on_generate_positions)
        ui.pushButton_clearPositions.clicked.connect(self._on_clear_positions)

        ui.spinBox_xCount.valueChanged.connect(self._update_total_positions_label)
        ui.spinBox_yCount.valueChanged.connect(self._update_total_positions_label)
        ui.spinBox_zCount.valueChanged.connect(self._update_total_positions_label)

        ui.pushButton_addCurrentPos.clicked.connect(self._on_add_current_position)
        ui.pushButton_deleteSelectedPos.clicked.connect(self._on_delete_selected_position)
        ui.pushButton_savePositions.clicked.connect(self._on_save_positions)
        ui.pushButton_loadPositions.clicked.connect(self._on_load_positions)

        ui.pushButton_startTest.clicked.connect(self._on_start_test)
        ui.pushButton_stopTest.clicked.connect(self._on_stop_test)
        ui.pushButton_resetTest.clicked.connect(self._on_reset_test)

        ui.pushButton_exportCSV.clicked.connect(self._on_export_csv)
        ui.pushButton_openAnalyzer.clicked.connect(self._on_open_analyzer)


    def _on_read_current_tcp(self):
        tcp = self.manager.get_current_tcp()
        # (0,0,0) 정확 일치를 읽기 실패 sentinel 로 간주 — 실제 원점 근처 자세와는 구분되지 않음(함정)
        if tcp[0] == 0.0 and tcp[1] == 0.0 and tcp[2] == 0.0:
            self._log("TCP 위치를 읽을 수 없습니다")
            return

        ui = self.handeye_ui

        ui.doubleSpinBox_baseX.setValue(tcp[0])
        ui.doubleSpinBox_baseY.setValue(tcp[1])
        ui.doubleSpinBox_baseZ.setValue(tcp[2])
        ui.doubleSpinBox_baseRx.setValue(tcp[3])
        ui.doubleSpinBox_baseRy.setValue(tcp[4])
        ui.doubleSpinBox_baseRz.setValue(tcp[5])

        self._log(f"기준 위치 읽기 완료: ({tcp[0]:.2f}, {tcp[1]:.2f}, {tcp[2]:.2f})")

    def _update_total_positions_label(self):
        ui = self.handeye_ui
        x_count = ui.spinBox_xCount.value()
        y_count = ui.spinBox_yCount.value()
        z_count = ui.spinBox_zCount.value()

        x_total = 2 * x_count + 1
        y_total = 2 * y_count + 1
        total = x_total * y_total * z_count

        ui.label_totalPositions.setText(f"총 측정 위치: {total}개 ({x_total}x{y_total}x{z_count})")

    def _on_generate_positions(self):
        ui = self.handeye_ui

        base_position = {
            'x': ui.doubleSpinBox_baseX.value(),
            'y': ui.doubleSpinBox_baseY.value(),
            'z': ui.doubleSpinBox_baseZ.value(),
            'rx': ui.doubleSpinBox_baseRx.value(),
            'ry': ui.doubleSpinBox_baseRy.value(),
            'rz': ui.doubleSpinBox_baseRz.value()
        }

        self.manager.generate_positions(
            base_position,
            ui.doubleSpinBox_xStep.value(), ui.spinBox_xCount.value(),
            ui.doubleSpinBox_yStep.value(), ui.spinBox_yCount.value(),
            ui.doubleSpinBox_zStep.value(), ui.spinBox_zCount.value()
        )

        self._update_positions_table()

    def _on_clear_positions(self):
        self.manager.clear_positions()
        self._update_positions_table()
        self._log("위치 목록 초기화 완료")

    def _update_positions_table(self):
        ui = self.handeye_ui
        table = ui.tableWidget_positions
        positions = self.manager.get_positions()

        table.setRowCount(len(positions))
        for i, pos in enumerate(positions):
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            table.setItem(i, 1, QTableWidgetItem(f"{pos['x']:.2f}"))
            table.setItem(i, 2, QTableWidgetItem(f"{pos['y']:.2f}"))
            table.setItem(i, 3, QTableWidgetItem(f"{pos['z']:.2f}"))
            table.setItem(i, 4, QTableWidgetItem(f"{pos['rx']:.2f}"))
            table.setItem(i, 5, QTableWidgetItem(f"{pos['ry']:.2f}"))
            table.setItem(i, 6, QTableWidgetItem(f"{pos['rz']:.2f}"))


    def _on_add_current_position(self):
        tcp = self.manager.get_current_tcp()
        if tcp[0] == 0.0 and tcp[1] == 0.0 and tcp[2] == 0.0:
            self._log("TCP 위치를 읽을 수 없습니다")
            return

        pos = {
            'x': tcp[0], 'y': tcp[1], 'z': tcp[2],
            'rx': tcp[3], 'ry': tcp[4], 'rz': tcp[5]
        }
        self.manager.add_position(pos)
        self._update_positions_table()
        self._log(f"위치 추가: ({tcp[0]:.2f}, {tcp[1]:.2f}, {tcp[2]:.2f})")

    def _on_delete_selected_position(self):
        ui = self.handeye_ui
        table = ui.tableWidget_positions
        selected = table.selectedItems()

        if not selected:
            return

        rows = sorted(set(item.row() for item in selected), reverse=True)
        for row in rows:
            self.manager.remove_position(row)

        self._update_positions_table()
        self._log(f"위치 {len(rows)}개 삭제")

    def _on_save_positions(self):
        if not self.manager.get_positions():
            QMessageBox.warning(self.mw, "경고", "저장할 위치가 없습니다")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self.mw, "위치 목록 저장", "", "YAML Files (*.yaml)"
        )

        if filename:
            self.manager.save_positions(filename)

    def _on_load_positions(self):
        filename, _ = QFileDialog.getOpenFileName(
            self.mw, "위치 목록 불러오기", "", "YAML Files (*.yaml)"
        )

        if filename:
            if self.manager.load_positions(filename):
                self._update_positions_table()


    def _on_start_test(self):
        if not self.manager.get_positions():
            QMessageBox.warning(self.mw, "경고", "측정 위치가 없습니다. 먼저 위치 목록을 생성하세요.")
            return

        ui = self.handeye_ui
        repeat_count = ui.spinBox_repeatCount.value()
        scan_delay_sec = ui.spinBox_scanDelay.value() / 1000.0

        success, msg = self.manager.start_test(repeat_count, scan_delay_sec)

        if not success:
            QMessageBox.warning(self.mw, "경고", msg)
            return

        ui.pushButton_startTest.setEnabled(False)
        ui.pushButton_stopTest.setEnabled(True)
        ui.pushButton_resetTest.setEnabled(False)
        ui.progressBar_test.setValue(0)

        self._run_next_measurement()

    def _run_next_measurement(self):
        """측정 1회 실행 후 100ms 타이머로 자신을 재예약 — 루프 대신 체인으로 측정 사이 이벤트 루프(UI 갱신) 기회를 준다."""
        if not self.manager.is_running:
            return

        # 로봇 이동을 포함한 동기 호출 — 완료까지 GUI 스레드가 멈춘다
        success, measurement, msg = self.manager.run_single_measurement()

        if not success:
            if self.manager.is_test_complete():
                self._on_test_complete()
            else:
                self._handle_measurement_error(msg)
            return

        if self.manager.is_test_complete():
            self._on_test_complete()
        elif self.manager.is_running:
            QTimer.singleShot(100, self._run_next_measurement)

    def _handle_measurement_error(self, error_msg: str):
        reply = QMessageBox.question(
            self.mw,
            "측정 오류",
            f"{error_msg}\n계속 진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes and self.manager.is_running:
            QTimer.singleShot(100, self._run_next_measurement)
        else:
            self._on_test_complete()

    def _on_stop_test(self):
        self.manager.stop_test()

        ui = self.handeye_ui
        ui.pushButton_startTest.setEnabled(True)
        ui.pushButton_stopTest.setEnabled(False)
        ui.pushButton_resetTest.setEnabled(True)

    def _on_reset_test(self):
        self.manager.reset_test()

        ui = self.handeye_ui
        ui.tableWidget_measurements.setRowCount(0)
        ui.progressBar_test.setValue(0)
        ui.label_progress.setText("진행: 0/0 (0%)")
        ui.textEdit_statistics.clear()


    def _on_measurement_complete(self, measurement: dict):
        self._update_measurements_table()

    def _on_test_complete(self):
        ui = self.handeye_ui
        self.manager.is_running = False

        ui.pushButton_startTest.setEnabled(True)
        ui.pushButton_stopTest.setEnabled(False)
        ui.pushButton_resetTest.setEnabled(True)

        self._log(f"Hand-Eye 테스트 완료: 총 {len(self.manager.get_measurements())}회 측정")

        ui.textEdit_statistics.setText(self.manager.format_statistics_text())

    def _on_progress_update(self, current: int, total: int):
        ui = self.handeye_ui
        if total > 0:
            progress = int((current / total) * 100)
            ui.progressBar_test.setValue(progress)
            ui.label_progress.setText(f"진행: {current}/{total} ({progress}%)")

    def _update_measurements_table(self):
        ui = self.handeye_ui
        table = ui.tableWidget_measurements
        measurements = self.manager.get_measurements()

        table.setRowCount(len(measurements))
        for i, m in enumerate(measurements):
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            table.setItem(i, 1, QTableWidgetItem(str(m['position_index'])))
            success_text = "O" if m.get('success', False) else "X"
            success_item = QTableWidgetItem(success_text)
            if not m.get('success', False):
                success_item.setBackground(Qt.red)
                success_item.setForeground(Qt.white)
            table.setItem(i, 2, success_item)
            table.setItem(i, 3, QTableWidgetItem(f"{m['lm_x']:.2f}"))
            table.setItem(i, 4, QTableWidgetItem(f"{m['lm_y']:.2f}"))
            table.setItem(i, 5, QTableWidgetItem(f"{m['lm_z']:.2f}"))
            table.setItem(i, 6, QTableWidgetItem(f"{m['lm_rx']:.2f}"))
            table.setItem(i, 7, QTableWidgetItem(f"{m['lm_ry']:.2f}"))
            table.setItem(i, 8, QTableWidgetItem(f"{m['lm_rz']:.2f}"))
            table.setItem(i, 9, QTableWidgetItem(f"{m['tcp_x']:.1f}"))
            table.setItem(i, 10, QTableWidgetItem(f"{m['tcp_y']:.1f}"))
            table.setItem(i, 11, QTableWidgetItem(f"{m['tcp_z']:.1f}"))
            table.setItem(i, 12, QTableWidgetItem(f"{m['tcp_rx']:.1f}"))
            table.setItem(i, 13, QTableWidgetItem(f"{m['tcp_ry']:.1f}"))
            table.setItem(i, 14, QTableWidgetItem(f"{m['tcp_rz']:.1f}"))


    def _on_export_csv(self):
        if not self.manager.get_measurements():
            QMessageBox.warning(self.mw, "경고", "내보낼 데이터가 없습니다")
            return

        default_path = self.manager.get_default_csv_path()

        filename, _ = QFileDialog.getSaveFileName(
            self.mw, "CSV 저장", default_path, "CSV Files (*.csv)"
        )

        if filename:
            self.manager.export_to_csv(filename)

    def _on_open_analyzer(self):
        import subprocess
        import sys
        from pathlib import Path

        analyzer_path = Path(__file__).parent.parent.parent / "scripts" / "handeye_analyzer.py"

        if not analyzer_path.exists():
            QMessageBox.warning(self.mw, "경고", "분석기 스크립트를 찾을 수 없습니다")
            return

        csv_path = ""
        if self.manager.get_measurements():
            csv_path = self.manager.get_default_csv_path()
            self.manager.export_to_csv(csv_path)
            self._log(f"분석을 위해 CSV 저장: {csv_path}")

        try:
            if csv_path:
                subprocess.Popen([sys.executable, str(analyzer_path), csv_path])
            else:
                subprocess.Popen([sys.executable, str(analyzer_path)])
            self._log("Hand-Eye 분석기 실행")
        except Exception as e:
            QMessageBox.warning(self.mw, "오류", f"분석기 실행 실패: {e}")
