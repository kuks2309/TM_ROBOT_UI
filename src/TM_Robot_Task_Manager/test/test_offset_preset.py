import os

import pytest
import yaml

from tm_task_manager.services.offset_preset_service import OffsetPresetService


@pytest.fixture
def service(tmp_path):
    return OffsetPresetService(config_path=str(tmp_path / 'plane_align_offsets.yaml'))


OFFSET = {'x': 1.5, 'y': -2.0, 'rx': 0.5, 'ry': -0.25, 'rz': 90.0}


def test_missing_file_lists_nothing(service):
    assert service.list_names() == []
    assert service.get('없는이름') is None


def test_save_then_get_roundtrip(service):
    ok, message = service.save('그리퍼A', OFFSET)
    assert ok is True
    assert '그리퍼A' in message

    assert service.get('그리퍼A') == pytest.approx(OFFSET)


def test_saved_file_is_readable_yaml(service):
    service.save('그리퍼A', OFFSET)

    with open(service.config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    assert data['presets']['그리퍼A']['rz'] == 90.0


def test_list_names_is_sorted(service):
    service.save('b', OFFSET)
    service.save('a', OFFSET)
    assert service.list_names() == ['a', 'b']


def test_save_overwrites_existing_name(service):
    service.save('그리퍼A', OFFSET)
    ok, message = service.save('그리퍼A', dict(OFFSET, x=9.0))

    assert ok is True
    assert '덮어썼' in message
    assert service.get('그리퍼A')['x'] == 9.0
    assert service.list_names() == ['그리퍼A']


def test_save_rejects_empty_name(service):
    ok, message = service.save('   ', OFFSET)
    assert ok is False
    assert '이름' in message
    assert service.list_names() == []


def test_missing_axes_default_to_zero(service):
    service.save('부분', {'x': 3.0})
    stored = service.get('부분')

    assert stored['x'] == 3.0
    assert stored['y'] == 0.0
    assert stored['rz'] == 0.0


def test_z_axis_is_not_stored(service):
    service.save('그리퍼A', dict(OFFSET, z=99.0))
    assert 'z' not in service.get('그리퍼A')


def test_non_numeric_value_falls_back_to_zero(service):
    service.save('이상', dict(OFFSET, x='abc'))
    assert service.get('이상')['x'] == 0.0


def test_delete_removes_preset(service):
    service.save('그리퍼A', OFFSET)
    ok, message = service.delete('그리퍼A')

    assert ok is True
    assert '삭제' in message
    assert service.list_names() == []


def test_delete_missing_preset_reports_failure(service):
    ok, message = service.delete('없는이름')
    assert ok is False
    assert '없습니다' in message


def test_broken_file_is_treated_as_empty(service):
    os.makedirs(os.path.dirname(service.config_path), exist_ok=True)
    with open(service.config_path, 'w', encoding='utf-8') as f:
        f.write("presets: [이건 dict 가 아니다\n")

    assert service.list_names() == []


def test_save_creates_missing_directory(tmp_path):
    nested = tmp_path / 'config' / 'sub' / 'offsets.yaml'
    service = OffsetPresetService(config_path=str(nested))

    ok, _ = service.save('그리퍼A', OFFSET)
    assert ok is True
    assert os.path.exists(str(nested))


def test_default_path_points_at_package_config():
    service = OffsetPresetService()
    assert service.config_path.endswith(
        os.path.join('config', 'plane_align_offsets.yaml')
    )
