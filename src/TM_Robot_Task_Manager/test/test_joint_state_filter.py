"""robot_motion_service 의 TM 조인트 메시지 판별(is_tm_joint_state)을 검증한다."""
from tm_task_manager.services.robot_motion_service import (
    TM_JOINT_NAMES,
    is_tm_joint_state,
)

TIAGO_NAMES = [
    'wheel_right_joint', 'head_2_joint', 'arm_1_joint', 'head_1_joint',
    'gripper_right_finger_joint', 'arm_2_joint', 'arm_3_joint',
    'gripper_left_finger_joint', 'arm_6_joint', 'wheel_left_joint',
    'arm_7_joint', 'arm_5_joint', 'arm_4_joint', 'torso_lift_joint',
]


class TestIsTmJointState:

    def test_accepts_tm_message(self):
        assert is_tm_joint_state(list(TM_JOINT_NAMES), [0.1] * 6) is True

    def test_rejects_foreign_14_joint_message(self):
        assert is_tm_joint_state(TIAGO_NAMES, [0.0] * 14) is False

    def test_rejects_foreign_six_joint_message(self):
        names = ['a_joint', 'b_joint', 'c_joint', 'd_joint', 'e_joint', 'f_joint']
        assert is_tm_joint_state(names, [0.0] * 6) is False

    def test_accepts_nameless_six_joint_message(self):
        assert is_tm_joint_state([], [0.0] * 6) is True

    def test_rejects_nameless_other_count(self):
        assert is_tm_joint_state([], [0.0] * 14) is False

    def test_rejects_short_message(self):
        assert is_tm_joint_state(list(TM_JOINT_NAMES), [0.0] * 3) is False

    def test_rejects_none_positions(self):
        assert is_tm_joint_state(list(TM_JOINT_NAMES), None) is False

    def test_accepts_tm_message_with_extra_joints(self):
        assert is_tm_joint_state(list(TM_JOINT_NAMES) + ['ext_1'], [0.0] * 7) is True
