import pytest

from tm_task_manager.services.config_manager import ConfigManager
from tm_task_manager.services.vision_origin_check_service import (
    DEFAULT_TOLERANCE_RPY,
    DEFAULT_TOLERANCE_XYZ,
    VisionOriginCheckService,
    normalize_angle_deg,
)


def make_pose(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
    return {'x': x, 'y': y, 'z': z, 'rx': rx, 'ry': ry, 'rz': rz}


@pytest.fixture
def service(tmp_path):
    config_manager = ConfigManager(config_path=str(tmp_path / 'positions.yaml'))
    return VisionOriginCheckService(config_manager=config_manager)


@pytest.fixture
def learned_service(service):
    service.save_reference(
        tcp_pose=make_pose(10.0, 700.0, -30.0, 180.0, 0.0, 180.0),
        landmark=make_pose(12.11, 708.6, -35.31, 179.24, 0.44, 178.86),
        measure={'repeat_count': 5, 'outlier_method': 'iqr'},
        std=make_pose(0.01, 0.02, 0.03, 0.04, 0.05, 0.06),
    )
    return service


class TestNormalizeAngleDeg:
    def test_wraps_positive_boundary(self):
        assert normalize_angle_deg(359.8) == pytest.approx(-0.2)

    def test_wraps_negative_boundary(self):
        assert normalize_angle_deg(-359.8) == pytest.approx(0.2)

    def test_keeps_small_angle(self):
        assert normalize_angle_deg(0.3) == pytest.approx(0.3)


class TestReferenceLifecycle:
    def test_has_no_reference_when_empty(self, service):
        assert service.has_reference() is False
        assert service.load_reference() is None

    def test_save_then_load_roundtrip(self, learned_service):
        assert learned_service.has_reference() is True

        reference = learned_service.load_reference()
        assert reference['landmark']['x'] == pytest.approx(12.11)
        assert reference['tcp_pose']['y'] == pytest.approx(700.0)
        assert reference['measure'] == {'repeat_count': 5, 'outlier_method': 'iqr'}
        assert reference['learned_std']['z'] == pytest.approx(0.03)
        assert 'learned_at' in reference

    def test_reference_survives_new_service_instance(self, learned_service):
        reloaded = VisionOriginCheckService(
            config_manager=ConfigManager(config_path=learned_service.config_manager.config_path)
        )
        assert reloaded.has_reference() is True
        assert reloaded.load_reference()['landmark']['z'] == pytest.approx(-35.31)

    def test_get_reference_tcp_pose_order(self, learned_service):
        assert learned_service.get_reference_tcp_pose() == pytest.approx(
            [10.0, 700.0, -30.0, 180.0, 0.0, 180.0]
        )

    def test_get_reference_tcp_pose_is_none_when_unlearned(self, service):
        assert service.get_reference_tcp_pose() is None

    def test_save_rejects_incomplete_landmark(self, service):
        incomplete = {'x': 1.0, 'y': 2.0, 'z': 3.0}
        assert service.save_reference(make_pose(), incomplete) is False
        assert service.has_reference() is False

    def test_save_rejects_incomplete_tcp_pose(self, service):
        assert service.save_reference({'x': 1.0}, make_pose()) is False
        assert service.has_reference() is False

    def test_save_preserves_existing_tolerance(self, service):
        service.set_tolerance(0.25, 0.1)
        service.save_reference(make_pose(), make_pose())
        assert service.get_tolerance() == {'xyz': pytest.approx(0.25), 'rpy': pytest.approx(0.1)}


class TestTolerance:
    def test_defaults_when_unset(self, service):
        assert service.get_tolerance() == {
            'xyz': pytest.approx(DEFAULT_TOLERANCE_XYZ),
            'rpy': pytest.approx(DEFAULT_TOLERANCE_RPY),
        }

    def test_set_then_get(self, service):
        assert service.set_tolerance(2.5, 1.5) is True
        assert service.get_tolerance() == {'xyz': pytest.approx(2.5), 'rpy': pytest.approx(1.5)}

    @pytest.mark.parametrize('xyz,rpy', [(0.0, 0.5), (1.0, 0.0), (-1.0, 0.5), (1.0, -0.5)])
    def test_rejects_non_positive(self, service, xyz, rpy):
        assert service.set_tolerance(xyz, rpy) is False
        assert service.get_tolerance()['xyz'] == pytest.approx(DEFAULT_TOLERANCE_XYZ)

    def test_rejects_non_numeric(self, service):
        assert service.set_tolerance('abc', 0.5) is False

    def test_falls_back_when_stored_value_is_corrupt(self, service):
        service.config_manager.set('vision_origin_check.tolerance', {'xyz': 'oops', 'rpy': -3})
        assert service.get_tolerance() == {
            'xyz': pytest.approx(DEFAULT_TOLERANCE_XYZ),
            'rpy': pytest.approx(DEFAULT_TOLERANCE_RPY),
        }


class TestEvaluate:
    def test_returns_none_when_unlearned(self, service):
        assert service.evaluate(make_pose()) is None

    def test_returns_none_for_malformed_measurement(self, learned_service):
        assert learned_service.evaluate({'x': 1.0, 'y': 2.0}) is None

    def test_passes_on_exact_match(self, learned_service):
        result = learned_service.evaluate(make_pose(12.11, 708.6, -35.31, 179.24, 0.44, 178.86))
        assert result.passed is True
        assert result.failed_axes == []
        assert result.deltas['x'] == pytest.approx(0.0)

    def test_boundary_equal_to_tolerance_passes(self, learned_service):
        learned_service.set_tolerance(1.0, 0.5)
        result = learned_service.evaluate(
            make_pose(13.11, 708.6, -35.31, 179.74, 0.44, 178.86)
        )
        assert result.passed is True, result.message
        assert result.deltas['x'] == pytest.approx(1.0)
        assert result.deltas['rx'] == pytest.approx(0.5)

    def test_just_over_tolerance_fails(self, learned_service):
        learned_service.set_tolerance(1.0, 0.5)
        result = learned_service.evaluate(
            make_pose(13.12, 708.6, -35.31, 179.24, 0.44, 178.86)
        )
        assert result.passed is False
        assert result.failed_axes == ['x']

    def test_identifies_every_failed_axis(self, learned_service):
        learned_service.set_tolerance(1.0, 0.5)
        result = learned_service.evaluate(
            make_pose(20.0, 708.6, -50.0, 179.24, 10.0, 178.86)
        )
        assert result.passed is False
        assert result.failed_axes == ['x', 'z', 'ry']

    def test_rotation_wraparound_is_not_false_alarm(self, service):
        service.save_reference(tcp_pose=make_pose(), landmark=make_pose(rz=179.9))
        service.set_tolerance(1.0, 0.5)

        result = service.evaluate(make_pose(rz=-179.9))

        assert result.deltas['rz'] == pytest.approx(0.2)
        assert result.passed is True, result.message

    def test_explicit_tolerance_argument_overrides_stored(self, learned_service):
        learned_service.set_tolerance(10.0, 10.0)
        measured = make_pose(13.0, 708.6, -35.31, 179.24, 0.44, 178.86)

        assert learned_service.evaluate(measured).passed is True
        assert learned_service.evaluate(measured, {'xyz': 0.1, 'rpy': 0.1}).passed is False

    def test_result_carries_reference_and_tolerance(self, learned_service):
        learned_service.set_tolerance(1.0, 0.5)
        result = learned_service.evaluate(make_pose(12.11, 708.6, -35.31, 179.24, 0.44, 178.86))

        assert result.reference['x'] == pytest.approx(12.11)
        assert result.measured['y'] == pytest.approx(708.6)
        assert result.tolerance == {'xyz': pytest.approx(1.0), 'rpy': pytest.approx(0.5)}

    def test_failure_message_names_failed_axes(self, learned_service):
        learned_service.set_tolerance(1.0, 0.5)
        result = learned_service.evaluate(make_pose(100.0, 708.6, -35.31, 179.24, 0.44, 178.86))

        assert '실패' in result.message
        assert 'x' in result.message


class TestFormatDeltas:
    def test_includes_units_and_signs(self):
        text = VisionOriginCheckService.format_deltas(
            {'x': 0.1, 'y': -0.2, 'z': 0.0, 'rx': 0.01, 'ry': -0.02, 'rz': 0.0}
        )
        assert 'dX=+0.100' in text
        assert 'dY=-0.200' in text
        assert 'mm' in text and 'deg' in text
