"""매크로 계층의 계약 — 컨텍스트·결과·명세·레지스트리.

매크로는 재사용 가능한 함수다: 파라미터를 받아 MacroResult 를 돌려준다.
Job 은 매크로를 순서대로 포함해 호출하는 단위다.

`requires`/`produces` 가 이 계층의 실질이다 — 그것이 있어야 어떤 매크로를
먼저 불러야 하는지 코드를 읽지 않고 알 수 있다.
설계 근거: docs/adr/2026-08-11-macro-layer.md
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# requires 에 이 접두를 붙이면 칠판 키가 아니라 외부 선행조건(설정·학습 데이터)을
# 뜻한다. 정적 검사 대상에서 제외하고 매크로가 런타임에 스스로 확인한다.
EXTERNAL_PREFIX = 'config:'


@dataclass
class MacroResult:
    """매크로 실행 결과. bool 만 돌려주던 기존 핸들러와 달리 사유·산출물을 담는다."""
    ok: bool
    message: str = ''
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str = '', **data) -> 'MacroResult':
        return cls(True, message, data)

    @classmethod
    def failure(cls, message: str, **data) -> 'MacroResult':
        return cls(False, message, data)


class MacroContext:
    """매크로가 쓰는 장비·공유상태·helper 의 단일 진입점.

    JobExecutor 를 감싸므로 매크로는 executor 내부 구조를 모르고, executor 는
    매크로 구현을 모른다. executor 의 비공개 멤버 의존을 여기 한 곳에 모아
    executor 리팩터링 시 고칠 지점을 1곳으로 좁힌다.
    """

    def __init__(self, executor, blackboard: Optional[Dict[str, Any]] = None):
        self._executor = executor
        self.blackboard: Dict[str, Any] = blackboard if blackboard is not None else {}

    def log(self, message: str) -> None:
        self._executor._log(message)

    @property
    def ros_node(self):
        return self._executor.ros_node

    @property
    def vision_manager(self):
        return self._executor.vision_manager

    @property
    def vision_origin_check_service(self):
        return self._executor.vision_origin_check_service

    @property
    def coordinate_system_manager(self):
        return self._executor.coordinate_system_manager

    @property
    def is_stop_requested(self) -> bool:
        return self._executor._stop_requested

    def clear_stop_request(self) -> None:
        """새 실행 시작 — 남아 있던 정지 요청을 지운다.

        `JobExecutor._stop_requested` 는 `stop()` 이 켜고 `run_from()` 계열만 끈다.
        매크로를 레시피 밖에서 직접 부르는 호출자(팔레트 티칭 탭)는 그 경로를 지나지
        않으므로, [정지]를 한 번 누르면 플래그가 영구히 남아 이후 모든 매크로가
        진입 즉시 중단된다(2026-08-24 실기). 호출자는 새 동작을 시작할 때 이걸 부른다.

        ⚠️ **시작 시점에만** 부를 것 — 실행 중에 부르면 사용자의 정지가 무시된다.
        """
        self._executor._stop_requested = False

    def move_to_position(self, *args, **kwargs):
        return self._executor._move_to_position(*args, **kwargs)

    def move_pose_keep(self, label: str, target: Dict[str, float], velocity: float,
                       decel_zone_mm: float = 0.0, decel_velocity: float = 3.0,
                       straight: bool = False) -> bool:
        """자세를 먼저 맞춘 뒤 **직선(LINE_T)** 으로 접근한다.

        `move_to_position` 은 PTP_T 한 방이라 이 로봇에서 컨트롤러 기능 라이브러리
        에러가 난다(2026-08-24 실기). `_move_pose_keep` 은 검증된 레시피
        (`move_to_plane_pose`)가 쓰는 바로 그 경로이고, 실패 시 **PTP 로 대체하지
        않고 중단**한다 — 이 프로젝트가 PTP 를 의도적으로 배제해 온 규약이다.
        """
        return self._executor._move_pose_keep(
            label, target, velocity, decel_zone_mm, decel_velocity, straight)

    def scan_landmark_averaged(self, *args, **kwargs):
        return self._executor.scan_landmark_averaged(*args, **kwargs)

    def emit(self, callback_name: str, payload: Any) -> None:
        """executor 의 on_* 콜백을 발화한다. 미설정이면 조용히 지나간다."""
        callback = getattr(self._executor, callback_name, None)
        if callback:
            callback(payload)

    def put(self, key: str, value: Any) -> None:
        self.blackboard[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.blackboard.get(key, default)

    def has(self, key: str) -> bool:
        return key in self.blackboard


@dataclass
class MacroSpec:
    """매크로 1개의 계약. 카탈로그는 전적으로 이 명세에서 생성된다."""
    name: str
    summary: str
    category: str
    params: Dict[str, Dict[str, Any]]
    fn: Callable
    requires: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)

    def defaults(self) -> Dict[str, Any]:
        return {key: spec.get('default') for key, spec in self.params.items()}

    def blackboard_requires(self) -> List[str]:
        return [r for r in self.requires if not r.startswith(EXTERNAL_PREFIX)]

    def external_requires(self) -> List[str]:
        return [r[len(EXTERNAL_PREFIX):] for r in self.requires if r.startswith(EXTERNAL_PREFIX)]


MACROS: Dict[str, MacroSpec] = {}


def register(name: str, summary: str, category: str,
             params: Optional[Dict[str, Dict[str, Any]]] = None,
             requires: Optional[List[str]] = None,
             produces: Optional[List[str]] = None):
    """매크로를 레지스트리에 등록하는 데코레이터."""
    def decorator(fn: Callable) -> Callable:
        if name in MACROS:
            raise ValueError(f"매크로 이름 중복: {name}")
        MACROS[name] = MacroSpec(
            name=name, summary=summary, category=category,
            params=params or {}, fn=fn,
            requires=requires or [], produces=produces or [],
        )
        return fn
    return decorator


def get_macro(name: str) -> Optional[MacroSpec]:
    return MACROS.get(name)


def run_macro(name: str, ctx: MacroContext,
              params: Optional[Dict[str, Any]] = None) -> MacroResult:
    """매크로를 이름으로 실행한다. 선언된 파라미터만 기본값과 합쳐 전달한다.

    Job 파라미터에 매크로가 모르는 키가 섞여 있어도 TypeError 로 죽지 않는다.
    """
    spec = MACROS.get(name)
    if spec is None:
        return MacroResult.failure(f"등록되지 않은 매크로: {name}")

    resolved = spec.defaults()
    for key, value in (params or {}).items():
        if key in resolved:
            resolved[key] = value

    missing = [k for k in spec.blackboard_requires() if not ctx.has(k)]
    if missing:
        return MacroResult.failure(
            f"선행 조건 미충족: {', '.join(missing)} — 앞선 매크로가 먼저 실행되어야 합니다"
        )

    result = spec.fn(ctx, **resolved)
    if isinstance(result, MacroResult):
        return result
    if isinstance(result, bool):
        return MacroResult(result, '' if result else f"{name} 실패")
    return MacroResult.failure(f"{name} 이 MacroResult 를 반환하지 않았습니다: {type(result).__name__}")


def validate_sequence(uses: List[str]) -> Tuple[bool, List[str]]:
    """매크로 시퀀스의 칠판 선행조건이 충족되는지 정적으로 검사한다.

    Job 정의 시점의 순서 오류(뒤에 올 매크로를 앞에 둔 경우)를 잡는다.
    외부 선행조건(config:)은 런타임 사안이라 여기서 보지 않는다.
    """
    available: set = set()
    problems: List[str] = []

    for index, name in enumerate(uses, start=1):
        spec = MACROS.get(name)
        if spec is None:
            problems.append(f"{index}번: 등록되지 않은 매크로 '{name}'")
            continue
        for need in spec.blackboard_requires():
            if need not in available:
                problems.append(f"{index}번 '{name}': 선행 산출물 '{need}' 없음")
        available.update(spec.produces)

    return (not problems), problems
