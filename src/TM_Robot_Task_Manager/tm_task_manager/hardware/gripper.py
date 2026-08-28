"""그리퍼 백엔드(SMC 전동/SCHUNK 서보) 선언과 자동 감지.

클라이언트 존재·메시지 모듈 import·서버 생존의 3단계로 상태를 판정하고,
명시 지정 또는 자동 감지로 사용할 백엔드를 확정한다.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# probe 3상: 클라이언트/msg 모듈 없음(absent) — 코드만 준비됨(built) — 서버 응답(live)
ABSENT = 'absent'
BUILT = 'built'
LIVE = 'live'


@dataclass(frozen=True)
class GripperBackend:
    """그리퍼 한 기종의 잡 타입·ROS 클라이언트 속성·메시지 모듈을 기술하는 불변 데이터."""
    id: str
    label: str
    grip: str
    release: str
    home: str
    node_attr: str
    msg_module: str
    kind: str

    def job_type(self, closing: bool) -> str:
        """파지(closing=True)/놓기 잡 타입 문자열을 고른다."""
        return self.grip if closing else self.release

    def job_name(self, closing: bool) -> str:
        """레시피 표시용 한국어 잡 이름을 만든다."""
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

ORDER: Tuple[GripperBackend, ...] = (SMC, SCHUNK)
BACKENDS: Dict[str, GripperBackend] = {b.id: b for b in ORDER}


class NoGripperDetected(RuntimeError):
    """사용 가능한 그리퍼 백엔드를 확정하지 못했을 때."""
    pass


def probe(backend: GripperBackend, ros_node, timeout_sec: float = 3.0) -> str:
    """백엔드 하나의 가용 상태를 판정한다.

    ros_node 의 클라이언트 속성(node_attr)을 차용해 검사할 뿐, 클라이언트
    생성은 루트 노드 소관이다. wait_for_server/service 는 호출 스레드를
    최대 timeout_sec(s) 블로킹한다.

    Returns:
        ABSENT/BUILT/LIVE 상태 문자열.
    """
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
    """전 백엔드를 ORDER 순으로 probe 한 (백엔드, 상태) 목록을 돌려준다."""
    return [(b, probe(b, ros_node, timeout_sec)) for b in ORDER]


def detect(ros_node, timeout_sec: float = 3.0) -> Optional[GripperBackend]:
    """ORDER 순으로 탐색해 첫 LIVE 백엔드를 돌려준다 (없으면 None)."""
    for backend, state in survey(ros_node, timeout_sec):
        if state == LIVE:
            return backend
    return None


def resolve(explicit: Optional[str], ros_node, timeout_sec: float = 3.0) -> GripperBackend:
    """사용할 그리퍼 백엔드를 확정한다.

    Args:
        explicit: 백엔드 id('smc'/'schunk'). 지정 시 감지 없이 그대로 채택.
            빈 값이면 detect 로 자동 감지.

    Raises:
        NoGripperDetected: id 가 미등록이거나 LIVE 백엔드가 하나도 없을 때.
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
