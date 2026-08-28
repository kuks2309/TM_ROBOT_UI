from typing import List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

try:
    from magazine_detect.msg import MagazineState as _MagazineState
except ImportError:
    _MagazineState = None


class MagazineStateService(QObject):

    magazine_updated = pyqtSignal(list, list, bool)

    SLOT_COUNT = 6

    SLOT_NAMES = ['앞 왼', '뒤 왼', '앞 중', '뒤 중', '앞 오', '뒤 오']

    TOPIC = '/magazine_detect_node/state'

    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node

        self._present: List[bool] = [False] * self.SLOT_COUNT
        self._raw: List[bool] = [False] * self.SLOT_COUNT
        self._valid = False
        self._received = False

        self.available = _MagazineState is not None and ros_node is not None
        if not self.available:
            if ros_node is not None:
                ros_node.get_logger().warn(
                    'magazine_detect 미소싱 — 매거진 재고 기능 비활성')
            return

        self._sub = ros_node.create_subscription(
            _MagazineState, self.TOPIC, self._on_state, self._make_qos())
        ros_node.get_logger().info(f'[매거진] {self.TOPIC} 구독 시작')

    @staticmethod
    def _make_qos():
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
        return QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

    def _on_state(self, msg):
        self._present = [bool(v) for v in msg.present]
        self._raw = [bool(v) for v in msg.raw]
        self._valid = bool(msg.valid)
        self._received = True
        self.magazine_updated.emit(list(self._present), list(self._raw), self._valid)

    def is_valid(self) -> bool:
        return self._received and self._valid

    def slot_present(self, slot: int) -> Optional[bool]:
        if not self.is_valid():
            return None
        if not 0 <= slot < self.SLOT_COUNT:
            return None
        return self._present[slot]

    def present_list(self) -> List[bool]:
        return list(self._present)

    def slot_name(self, slot: int) -> str:
        return self.SLOT_NAMES[slot] if 0 <= slot < self.SLOT_COUNT else '?'
