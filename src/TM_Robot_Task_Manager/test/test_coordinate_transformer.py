import pytest
import math
import numpy as np
from tm_task_manager.services.coordinate_transformer import CoordinateTransformer


class TestCoordinateTransformer:
    def test_deg_to_rad(self):
        assert CoordinateTransformer.deg_to_rad(0) == pytest.approx(0)
        assert CoordinateTransformer.deg_to_rad(90) == pytest.approx(math.pi / 2)
        assert CoordinateTransformer.deg_to_rad(180) == pytest.approx(math.pi)
        assert CoordinateTransformer.deg_to_rad(360) == pytest.approx(2 * math.pi)

    def test_rad_to_deg(self):
        assert CoordinateTransformer.rad_to_deg(0) == pytest.approx(0)
        assert CoordinateTransformer.rad_to_deg(math.pi / 2) == pytest.approx(90)
        assert CoordinateTransformer.rad_to_deg(math.pi) == pytest.approx(180)
        assert CoordinateTransformer.rad_to_deg(2 * math.pi) == pytest.approx(360)

    def test_mm_to_m(self):
        assert CoordinateTransformer.mm_to_m(0) == pytest.approx(0)
        assert CoordinateTransformer.mm_to_m(1000) == pytest.approx(1.0)
        assert CoordinateTransformer.mm_to_m(500) == pytest.approx(0.5)
        assert CoordinateTransformer.mm_to_m(2500) == pytest.approx(2.5)

    def test_m_to_mm(self):
        assert CoordinateTransformer.m_to_mm(0) == pytest.approx(0)
        assert CoordinateTransformer.m_to_mm(1.0) == pytest.approx(1000)
        assert CoordinateTransformer.m_to_mm(0.5) == pytest.approx(500)
        assert CoordinateTransformer.m_to_mm(2.5) == pytest.approx(2500)

    def test_euler_to_rotation_matrix_identity(self):
        R = CoordinateTransformer.euler_to_rotation_matrix(0, 0, 0)

        expected = [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ]

        for i in range(3):
            for j in range(3):
                assert R[i][j] == pytest.approx(expected[i][j])

    def test_euler_to_rotation_matrix_90deg_z(self):
        rz = math.pi / 2
        R = CoordinateTransformer.euler_to_rotation_matrix(0, 0, rz)

        expected = [
            [0, -1, 0],
            [1, 0, 0],
            [0, 0, 1]
        ]

        for i in range(3):
            for j in range(3):
                assert R[i][j] == pytest.approx(expected[i][j], abs=1e-10)

    def test_quaternion_to_euler_identity(self):
        qx, qy, qz, qw = 0, 0, 0, 1
        rx, ry, rz = CoordinateTransformer.quaternion_to_euler(qx, qy, qz, qw)

        assert rx == pytest.approx(0, abs=1e-6)
        assert ry == pytest.approx(0, abs=1e-6)
        assert rz == pytest.approx(0, abs=1e-6)

    def test_quaternion_to_euler_90deg_yaw(self):
        angle = math.pi / 4
        qx, qy, qz, qw = 0, 0, math.sin(angle), math.cos(angle)

        rx, ry, rz = CoordinateTransformer.quaternion_to_euler(qx, qy, qz, qw)

        assert rx == pytest.approx(0, abs=1e-6)
        assert ry == pytest.approx(0, abs=1e-6)
        assert rz == pytest.approx(90, abs=1e-6)

    def test_transform_tool_to_base_no_rotation(self):
        tool_delta = [100, 0, 0]
        tcp_orientation = [0, 0, 0]

        base_delta = CoordinateTransformer.transform_tool_to_base(
            tool_delta, tcp_orientation
        )

        assert base_delta[0] == pytest.approx(100)
        assert base_delta[1] == pytest.approx(0)
        assert base_delta[2] == pytest.approx(0)

    def test_transform_tool_to_base_with_rotation(self):
        tool_delta = [100, 0, 0]
        tcp_orientation = [0, 0, 90]

        base_delta = CoordinateTransformer.transform_tool_to_base(
            tool_delta, tcp_orientation
        )

        assert base_delta[0] == pytest.approx(0, abs=1e-10)
        assert base_delta[1] == pytest.approx(100, abs=1e-10)
        assert base_delta[2] == pytest.approx(0, abs=1e-10)

    def test_convert_tcp_to_service_format(self):
        tcp_pose = [100, 200, 300, 90, 0, 180]

        result = CoordinateTransformer.convert_tcp_to_service_format(tcp_pose)

        assert result[0] == pytest.approx(0.1)
        assert result[1] == pytest.approx(0.2)
        assert result[2] == pytest.approx(0.3)

        assert result[3] == pytest.approx(math.pi / 2)
        assert result[4] == pytest.approx(0)
        assert result[5] == pytest.approx(math.pi)

    def test_convert_joint_to_service_format(self):
        joint_pose = [0, 90, 180, 270, 45, 135]

        result = CoordinateTransformer.convert_joint_to_service_format(joint_pose)

        assert result[0] == pytest.approx(0)
        assert result[1] == pytest.approx(math.pi / 2)
        assert result[2] == pytest.approx(math.pi)
        assert result[3] == pytest.approx(3 * math.pi / 2)
        assert result[4] == pytest.approx(math.pi / 4)
        assert result[5] == pytest.approx(3 * math.pi / 4)
