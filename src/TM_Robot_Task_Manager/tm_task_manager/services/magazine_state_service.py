"""버퍼 매거진 재고 서비스 — magazine_detect 노드의 판정을 UI·잡에 전달한다.

판정 로직은 여기 없다. 비트 매핑·극성·디바운스는 전부 magazine_detect 노드(C++ 코어)
소유이고, 본 서비스는 그 결과를 구독해 캐시하고 시그널로 알리는 어댑터다.
같은 판정을 두 곳에서 다시 계산하면 두 곳이 서로 다른 답을 내는 날이 온다.

magazine_detect 가 소싱되지 않은 환경(다른 하드웨어·미빌드)에서는 방어적으로 비활성화한다 —
tm_task_manager 가 tc_msgs 를 다루는 방식과 같다(main_window.py:51).
"""

from typing import List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

try:
    from magazine_detect.msg import MagazineState as _MagazineState
except ImportError:  # 패키지 미소싱 — 서비스는 비활성으로 산다
    _MagazineState = None


class MagazineStateService(QObject):
    """`/magazine_detect_node/state` 를 구독해 슬롯 0~5 재고를 보관한다."""

    # (present, raw, valid) — UI 는 이 시그널만 받는다(서비스가 위젯을 직접 만지지 않는다).
    magazine_updated = pyqtSignal(list, list, bool)

    SLOT_COUNT = 6

    # 자리 이름. 표시 전용이며 판단에 쓰지 않는다 — 노드의 slotName() 과 같은 순서다.
    SLOT_NAMES = ['앞 왼', '뒤 왼', '앞 중', '뒤 중', '앞 오', '뒤 오']

    TOPIC = '/magazine_detect_node/state'

    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node

        self._present: List[bool] = [False] * self.SLOT_COUNT
        self._raw: List[bool] = [False] * self.SLOT_COUNT
        # 한 번도 못 받은 상태와 «전부 비었다» 는 다르다. 받기 전에는 판정 불가다.
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
        """구독 QoS. 발행자(magazine_detect_node)는 기본값(RELIABLE·VOLATILE·KEEP_LAST 10)이다.

        같은 값으로 맞춘다 — BEST_EFFORT 구독도 호환이지만 재고는 놓치면 안 되는 값이다.
        import 를 여기서 하는 이유: 모듈 로드 시점에 rclpy 서브모듈을 요구하면
        rclpy 를 대역으로 갈아끼우는 헤드리스 테스트(test/conftest.py)가 전부 깨진다.
        """
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
        return QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

    # ── 구독 콜백 ────────────────────────────────────────────────
    def _on_state(self, msg):
        self._present = [bool(v) for v in msg.present]
        self._raw = [bool(v) for v in msg.raw]
        self._valid = bool(msg.valid)
        self._received = True
        self.magazine_updated.emit(list(self._present), list(self._raw), self._valid)

    # ── 조회 API ─────────────────────────────────────────────────
    def is_valid(self) -> bool:
        """지금 재고를 믿어도 되는가. False 면 io_resp 가 끊겼거나 아직 못 받았다."""
        return self._received and self._valid

    def slot_present(self, slot: int) -> Optional[bool]:
        """슬롯 재고. 판정 불가(미수신·stale·범위 밖)면 None — False 와 구분해야 한다."""
        if not self.is_valid():
            return None
        if not 0 <= slot < self.SLOT_COUNT:
            return None
        return self._present[slot]

    def present_list(self) -> List[bool]:
        """마지막 확정값 사본. 신선도는 is_valid() 로 따로 물을 것."""
        return list(self._present)

    def slot_name(self, slot: int) -> str:
        return self.SLOT_NAMES[slot] if 0 <= slot < self.SLOT_COUNT else '?'
