"""그리퍼 백엔드 — 어느 그리퍼가 붙어 있는지 정하고, 레시피 잡 타입으로 옮긴다.

MK2 는 SCHUNK(`schunk_*`), MK4 는 SMC(`smc_*`) 를 쓴다. 실행기는 두 계열을 **모두**
지원하므로(`job_executor._exec_schunk_gripper` · `_exec_smc_gripper`), 기종이 갈리는
곳은 레시피를 **생성하는** 시점 하나뿐이다 — 어느 잡 타입으로 발행하느냐.

감지 순서는 기존 `GripperOverrideService` 규약을 그대로 따른다:
**SMC → SCHUNK 로 보고, 둘 다 없으면 아무것도 고르지 않는다.** 추측해서 발행하면
반대편 그리퍼 잡이 든 레시피가 로봇에 올라간다 — 실행 시점에 실패하는 것보다
생성 시점에 거부하는 편이 안전하다.

감지는 실행기가 실제로 쓰는 3단을 그대로 본다. 지어낸 신호를 쓰지 않는다:
  1) `ros_node` 의 클라이언트 속성   — job_executor.py:1200 · :1262
  2) 메시지 패키지 import 가능 여부   — job_executor.py:1206 · :1267
  3) 액션 서버 / 서비스 응답          — job_executor.py:1211 · :1271

3단까지 통과한 것만 LIVE 다. 1·2 만 되는 상태(BUILT)는 "빌드는 됐는데 노드가 안 떴다"
라서 화면에 구분해 보여준다 — 둘을 뭉뚱그리면 사용자가 원인을 못 찾는다.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 감지 상태
ABSENT = 'absent'   # 클라이언트 속성 자체가 없음 (미소싱/미빌드)
BUILT = 'built'     # 패키지는 있으나 노드/서비스가 응답하지 않음
LIVE = 'live'       # 서버·서비스까지 응답


@dataclass(frozen=True)
class GripperBackend:
    """한 그리퍼 계열의 잡 타입과 감지 신호."""
    id: str
    label: str
    grip: str
    release: str
    home: str
    node_attr: str      # ros_node 에 달리는 클라이언트 속성명
    msg_module: str     # import 가능 여부로 빌드 여부를 본다
    kind: str           # 'action' | 'service'

    def job_type(self, closing: bool) -> str:
        return self.grip if closing else self.release

    def job_name(self, closing: bool) -> str:
        head = self.label.split(' ')[0]
        return f"{head} 그리퍼 파지" if closing else f"{head} 그리퍼 놓기"


SMC = GripperBackend(
    id='smc', label='SMC 전동 그리퍼',
    grip='smc_grip', release='smc_release', home='smc_home',
    node_attr='gripper_action_client', msg_module='gripper_ros.action', kind='action',
)
SCHUNK = GripperBackend(
    id='schunk', label='SCHUNK 서보 그리퍼',
    grip='schunk_grip', release='schunk_release', home='schunk_home',
    node_attr='schunk_gripper_client', msg_module='tc_msgs.srv', kind='service',
)

# ⚠️ 순서를 바꾸지 말 것 — GripperOverrideService 가 쓰는 SMC → SCHUNK 와 같아야 한다.
ORDER: Tuple[GripperBackend, ...] = (SMC, SCHUNK)
BACKENDS: Dict[str, GripperBackend] = {b.id: b for b in ORDER}


class NoGripperDetected(RuntimeError):
    """SMC·SCHUNK 어느 쪽도 확인되지 않음 — 잡 타입을 고를 근거가 없다."""


def probe(backend: GripperBackend, ros_node, timeout_sec: float = 3.0) -> str:
    """한 백엔드의 상태를 ABSENT / BUILT / LIVE 로 돌려준다. 예외를 밖으로 내지 않는다."""
    if ros_node is None:
        return ABSENT
    client = getattr(ros_node, backend.node_attr, None)
    if client is None:
        return ABSENT
    try:
        __import__(backend.msg_module)
    except Exception:
        return ABSENT
    try:
        if backend.kind == 'action':
            alive = client.wait_for_server(timeout_sec=timeout_sec)
        else:
            alive = client.wait_for_service(timeout_sec=timeout_sec)
    except Exception:
        return BUILT
    return LIVE if alive else BUILT


def survey(ros_node, timeout_sec: float = 3.0) -> List[Tuple[GripperBackend, str]]:
    """모든 백엔드의 상태를 순서대로. 화면에 그대로 뿌릴 수 있게 쌍으로 준다."""
    return [(b, probe(b, ros_node, timeout_sec)) for b in ORDER]


def detect(ros_node, timeout_sec: float = 3.0) -> Optional[GripperBackend]:
    """SMC → SCHUNK 순으로 보고 **LIVE 인 첫 백엔드**. 없으면 None.

    BUILT 는 고르지 않는다 — 노드가 안 떠 있는 그리퍼로 레시피를 내면
    실행 시점에 실패한다. 사용자가 화면에서 직접 고르는 길은 열어 둔다.
    """
    for backend, state in survey(ros_node, timeout_sec):
        if state == LIVE:
            return backend
    return None


def resolve(explicit: Optional[str], ros_node, timeout_sec: float = 3.0) -> GripperBackend:
    """발행에 쓸 백엔드를 확정한다.

    `explicit` 가 있으면 그것을 쓴다 — 사용자가 화면에서 고른 값이 감지보다 우선한다
    (감지는 계기고 사용자는 현장이다). 없으면 감지에 맡기고, 감지도 실패하면
    `NoGripperDetected` 로 **거부**한다.
    """
    if explicit:
        key = str(explicit).strip().lower()
        if key not in BACKENDS:
            raise NoGripperDetected(
                f"알 수 없는 그리퍼 '{explicit}' — 가능한 값: {', '.join(BACKENDS)}")
        return BACKENDS[key]

    found = detect(ros_node, timeout_sec)
    if found is None:
        detail = ', '.join(f'{b.label}={s}' for b, s in survey(ros_node, 0.0))
        raise NoGripperDetected(
            "그리퍼를 확인할 수 없어 레시피를 만들지 않았습니다. "
            "그리퍼 노드를 먼저 띄우거나, 화면에서 기종을 직접 고르세요. "
            f"(감지 결과: {detail})")
    return found
