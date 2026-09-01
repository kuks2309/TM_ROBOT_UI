#!/usr/bin/env python3
"""tabs/precision_test_tab 데이터셋 블록 UI 로직을 검증한다(Qt offscreen)."""
import os
import sys
from pathlib import Path

import pytest
import yaml

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip('PyQt5')
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QWidget

from tm_task_manager import paths
from tm_task_manager.services.plate_pose_dataset import (
    JIG_KEYS, PlatePoseDataset, normalize_jig_order,
)
from tm_task_manager.tabs.precision_test_tab import PrecisionTestTab

RAW_PALLET0 = [
    {'x': 491.311, 'y': 152.674, 'z': -295.904, 'rx': 179.548, 'ry': -0.300, 'rz': 90.039},
    {'x': 295.205, 'y': 153.258, 'z': -294.544, 'rx': -179.884, 'ry': -0.361, 'rz': 90.052},
    {'x': 490.627, 'y': 290.182, 'z': -299.674, 'rx': -177.279, 'ry': -0.159, 'rz': 89.810},
    {'x': 294.083, 'y': 290.424, 'z': -298.264, 'rx': -179.494, 'ry': -0.311, 'rz': 90.117},
]
SQUARE = [
    {'x': 500.0, 'y': 290.0, 'z': -297.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
    {'x': 500.0, 'y': 152.0, 'z': -297.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
    {'x': 300.0, 'y': 290.0, 'z': -297.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
    {'x': 300.0, 'y': 152.0, 'z': -297.0, 'rx': 180.0, 'ry': 0.0, 'rz': 90.0},
]


@pytest.fixture(scope='session')
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _StubMainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.logs = []
        self.current_tcp_pose = None

    def _log(self, message):
        self.logs.append(message)


def _write_yaml(directory: Path, name: str, marks):
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        'saved_at': '2026-08-19 11:11:17',
        'plate_pose': {'x': 392.8, 'y': 221.6, 'z': -297.1,
                       'rx': 0.4, 'ry': 1.6, 'rz': 90.4},
        'landmarks': {k: dict(m, measured_at='2026-08-19 11:11:17')
                      for k, m in zip(JIG_KEYS, marks)},
    }
    with open(directory / name, 'w', encoding='utf-8') as f:
        yaml.safe_dump(payload, f)


@pytest.fixture
def dataset_root(tmp_path):
    root = tmp_path / 'plate_pose_calc'
    for index in range(3):
        bumped0 = [dict(m, x=m['x'] + index * 0.002) for m in RAW_PALLET0]
        bumped1 = [dict(m, x=m['x'] + index * 0.002) for m in SQUARE]

        _write_yaml(root / 'pallet0', f'p0_{index}.yaml', bumped0)
        _write_yaml(root / 'pallet0' / 'corrected', f'p0_{index}.corrected.yaml',
                    normalize_jig_order(bumped0))

        _write_yaml(root / 'pallet1', f'p1_{index}.yaml', bumped1)
        _write_yaml(root / 'pallet1' / 'corrected', f'p1_{index}.corrected.yaml',
                    normalize_jig_order(bumped1))

        _write_yaml(root / 'pallet2', f'p2_{index}.yaml', bumped0)
    return root


@pytest.fixture
def tab(qapp, dataset_root):
    stub = _StubMainWindow()
    instance = PrecisionTestTab(stub)
    instance.mw = stub
    instance.precision_ui = uic.loadUi(paths.ui('precision_test_tab.ui'))

    instance._init_plate_dataset_block()
    instance.plate_dataset.set_root(dataset_root)
    instance._refresh_pallet_combo()
    return instance


class TestUiWiring:
    def test_ui_exposes_every_new_widget(self, qapp):
        ui = uic.loadUi(paths.ui('precision_test_tab.ui'))
        expected = [
            'groupBox_plateDataset', 'comboBox_plateFolder',
            'radioButton_datasetRaw', 'radioButton_datasetCorrected',
            'pushButton_loadDataset', 'pushButton_browseDataset',
            'label_datasetStatus', 'widget_datasetScatter', 'checkBox_datasetAbsolute',
            'tableWidget_datasetStats', 'pushButton_exportDatasetCSV',
            'pushButton_saveDatasetGraph',
            'groupBox_jigShape', 'checkBox_overlayAllPallets',
            'pushButton_saveJigShape', 'label_jigShapeVerdict',
            'widget_jig3D', 'tableWidget_jigCheck',
        ]
        missing = [name for name in expected if not hasattr(ui, name)]
        assert missing == []

    def test_existing_widgets_survive(self, qapp):
        ui = uic.loadUi(paths.ui('precision_test_tab.ui'))
        existing = [
            'radioButton_staticTest', 'radioButton_dynamicTest',
            'spinBox_iterations', 'checkBox_autoSave', 'widget_dynamicSettings',
            'label_currentRecipe', 'pushButton_startTest', 'pushButton_stopTest',
            'pushButton_resetTest', 'label_progress', 'progressBar_test',
            'widget_graphXY', 'widget_graphYZ', 'widget_graphZX', 'widget_graphRotation',
            'label_xStatsValue', 'label_yStatsValue', 'label_zStatsValue',
            'label_rxStatsValue', 'label_ryStatsValue', 'label_rzStatsValue',
            'label_3sigmaPosition', 'label_3sigmaRotation',
            'tableWidget_measurements', 'pushButton_exportCSV',
            'pushButton_saveGraph', 'pushButton_precisionAnalyzer',
        ]
        missing = [name for name in existing if not hasattr(ui, name)]
        assert missing == []

    def test_measurement_table_keeps_14_columns(self, qapp):
        ui = uic.loadUi(paths.ui('precision_test_tab.ui'))
        assert ui.tableWidget_measurements.columnCount() == 14

    def test_pallet_combo_is_populated(self, tab):
        items = [tab.precision_ui.comboBox_plateFolder.itemText(i)
                 for i in range(tab.precision_ui.comboBox_plateFolder.count())]
        assert items == ['pallet0', 'pallet1', 'pallet2']


class TestLoadFlow:
    def test_load_fills_stats_scatter_and_shape(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        assert len(tab.plate_dataset.records) == 3
        assert tab.precision_ui.tableWidget_datasetStats.rowCount() == 24
        assert tab.precision_ui.tableWidget_jigCheck.rowCount() > 0

    def test_scatter_plots_four_jigs_per_plane(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        for key in ('xy', 'yz', 'zx', 'rot'):
            assert len(tab.axes_dataset[key].collections) == len(JIG_KEYS)

    def test_failing_pallet_reports_fail(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        assert 'FAIL' in tab.precision_ui.label_jigShapeVerdict.text()

    def test_square_pallet_reports_pass(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet1')
        tab._on_load_plate_dataset()
        assert 'PASS' in tab.precision_ui.label_jigShapeVerdict.text()

    def test_jig3d_draws_edges_and_center(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        assert len(tab.ax_jig3d.lines) == 6

    def test_overlay_covers_every_pallet(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        tab.precision_ui.checkBox_overlayAllPallets.setChecked(True)

        assert tab.precision_ui.tableWidget_jigCheck.rowCount() == 2
        assert len(tab.ax_jig3d.lines) == 12

    def test_overlay_in_raw_variant_covers_all_three(self, tab):
        tab.precision_ui.radioButton_datasetRaw.setChecked(True)
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        tab.precision_ui.checkBox_overlayAllPallets.setChecked(True)

        assert tab.precision_ui.tableWidget_jigCheck.rowCount() == 3
        assert len(tab.ax_jig3d.lines) == 18

    def test_overlay_toggle_back_restores_single_view(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        tab.precision_ui.checkBox_overlayAllPallets.setChecked(True)
        tab.precision_ui.checkBox_overlayAllPallets.setChecked(False)
        assert len(tab.ax_jig3d.lines) == 6


class TestScatterView:
    def test_defaults_to_deviation_view(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        assert tab.axes_dataset['xy'].get_xlabel().startswith('Δ')

    def test_deviation_view_is_centred_on_origin(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        offsets = tab.axes_dataset['xy'].collections[0].get_offsets()
        assert abs(offsets[:, 0]).max() < 1.0

    def test_absolute_checkbox_switches_to_real_coordinates(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        tab.precision_ui.checkBox_datasetAbsolute.setChecked(True)

        assert tab.axes_dataset['xy'].get_xlabel() == 'X (mm)'
        offsets = tab.axes_dataset['xy'].collections[0].get_offsets()
        assert offsets[:, 0].min() > 100.0

    def test_toggling_back_returns_to_deviation(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        tab.precision_ui.checkBox_datasetAbsolute.setChecked(True)
        tab.precision_ui.checkBox_datasetAbsolute.setChecked(False)
        assert tab.axes_dataset['xy'].get_xlabel().startswith('Δ')


class TestOverlayRendering:
    def test_overlay_centres_each_pallet_on_origin(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        tab.precision_ui.checkBox_overlayAllPallets.setChecked(True)

        xs = [x for line in tab.ax_jig3d.lines for x in line.get_xdata()]
        assert max(abs(x) for x in xs) < 150.0

    def test_overlay_legend_names_every_pallet_once(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        tab.precision_ui.checkBox_overlayAllPallets.setChecked(True)

        labels = [t.get_text() for t in tab.ax_jig3d.get_legend().get_texts()]
        assert labels == ['pallet0', 'pallet1']

    def test_overlay_uses_distinct_colour_per_pallet(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        tab.precision_ui.checkBox_overlayAllPallets.setChecked(True)

        first = tab.ax_jig3d.lines[0].get_color()
        second = tab.ax_jig3d.lines[6].get_color()
        assert first != second

    def test_single_view_has_no_legend_entries(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        assert tab.ax_jig3d.get_legend() is None


class TestIsolation:
    def test_new_block_uses_a_separate_manager(self, tab):
        assert not hasattr(tab.mw, 'precision_test_manager')

        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        assert not hasattr(tab.mw, 'precision_test_manager')
        assert isinstance(tab.mw.plate_dataset, PlatePoseDataset)

    def test_existing_measurement_table_untouched(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        assert tab.precision_ui.tableWidget_measurements.rowCount() == 0

    def test_existing_stat_labels_untouched(self, tab):
        before = tab.precision_ui.label_xStatsValue.text()
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        assert tab.precision_ui.label_xStatsValue.text() == before

    def test_existing_graph_axes_not_created_by_new_block(self, tab):
        assert tab.ax_xy is None and tab.ax_rotation is None


class TestVariantSelection:
    def test_defaults_to_corrected(self, tab):
        from tm_task_manager.services.plate_pose_dataset import VARIANT_CORRECTED
        assert tab._current_dataset_variant() == VARIANT_CORRECTED

    def test_raw_radio_switches_variant(self, tab):
        from tm_task_manager.services.plate_pose_dataset import VARIANT_RAW
        tab.precision_ui.radioButton_datasetRaw.setChecked(True)
        assert tab._current_dataset_variant() == VARIANT_RAW

    def test_missing_corrected_reports_failure(self, tab):
        success, message = tab.plate_dataset.load('pallet2', 'corrected')
        assert success is False
        assert 'YAML 파일이 없습니다' in message

    def test_raw_and_corrected_give_same_geometry(self, tab):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()
        corrected_sides, _ = tab.plate_dataset.geometry_report()

        tab.precision_ui.radioButton_datasetRaw.setChecked(True)
        tab._on_load_plate_dataset()
        raw_sides, _ = tab.plate_dataset.geometry_report()

        for key in corrected_sides:
            assert raw_sides[key] == pytest.approx(corrected_sides[key], abs=1e-6)


class TestExport:
    def test_csv_export_writes_stats_and_verdicts(self, tab, tmp_path, monkeypatch):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        target = tmp_path / 'out.csv'
        monkeypatch.setattr(
            'tm_task_manager.tabs.precision_test_tab.QFileDialog.getSaveFileName',
            lambda *a, **k: (str(target), 'CSV Files (*.csv)'))

        tab._on_export_dataset_csv()

        text = target.read_text(encoding='utf-8')
        assert '통계 (jig 반복 재현성)' in text
        assert '변 길이 (평균 좌표 기준, mm)' in text
        assert '대각선 차이' in text
        assert 'FAIL' in text

    def test_png_export_writes_file(self, tab, tmp_path, monkeypatch):
        tab.precision_ui.comboBox_plateFolder.setCurrentText('pallet0')
        tab._on_load_plate_dataset()

        target = tmp_path / 'shape.png'
        monkeypatch.setattr(
            'tm_task_manager.tabs.precision_test_tab.QFileDialog.getSaveFileName',
            lambda *a, **k: (str(target), 'PNG Files (*.png)'))

        tab._on_save_jig_shape()
        assert target.exists() and target.stat().st_size > 0
