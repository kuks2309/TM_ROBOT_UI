"""매거진 재고 상태 구독자 — magazine_detect 노드의 6슬롯 상태를 캐시한다."""
from typing import List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

# magazine_detect 는 exec_depend 선택 의존 — 미소싱이면 기능 전체 비활성(available=False)
try:
    from magazine_detect.msg import MagazineState as _MagazineState
except ImportError:
    _MagazineState = None


class MagazineStateService(QObject):
    """/magazine_detect_node/state 구독 캐시 + Qt 시그널 발행.

    캐시(_present 등)는 executor 콜백 스레드가 쓰고 GUI 가 읽는다 — 각 대입은
    리스트 재대입이라 원자적이지만 (received, valid, present) 조합 판정은
    비원자라 1틱 낡은 조합이 보일 수 있다 (재고 표시 용도라 허용).
    """

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
        """발행측(magazine_detect_node)과 맞춘 RELIABLE·VOLATILE·KEEP_LAST(10)."""
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
        """수신 이력이 있고 감지 노드가 유효 판정을 낸 상태인지."""
        return self._received and self._valid

    def slot_present(self, slot: int) -> Optional[bool]:
        """슬롯 재고 여부 — 무효 상태·범위 밖이면 None (False 와 구분)."""
        if not self.is_valid():
            return None
        if not 0 <= slot < self.SLOT_COUNT:
            return None
        return self._present[slot]

    def present_list(self) -> List[bool]:
        return list(self._present)

    def slot_name(self, slot: int) -> str:
        """슬롯 인덱스의 한국어 표시명 (범위 밖은 '?')."""
        return self.SLOT_NAMES[slot] if 0 <= slot < self.SLOT_COUNT else '?'
