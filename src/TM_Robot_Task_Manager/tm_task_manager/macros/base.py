"""매크로 프레임워크 코어 — 결과/컨텍스트/스펙 정의와 전역 레지스트리.

매크로는 register 데코레이터로 MACROS 에 등록되고, run_macro 가 기본값 병합→
선행조건 검사→실행→반환형 검증을 수행한다. 등록은 macros/__init__ 의 import
부수효과로 일어난다(단일 스레드 import 전제, 락 없음).
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# requires 항목 중 blackboard 가 아닌 외부 설정(예: config:taught_origin)을 뜻하는 접두어
EXTERNAL_PREFIX = 'config:'


@dataclass
class MacroResult:
    """매크로 실행 결과 (성공 여부 + 메시지 + 부가 데이터)."""
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
    """매크로가 보는 실행 환경 — executor 프록시 + 매크로 간 공유 blackboard.

    executor(job_executor)가 _log·ros_node·_stop_requested·_move_to_position
    등의 속성을 제공한다는 규약에 결합한다 — 속성 부재 시 AttributeError.
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
        # GUI 스레드가 세우고 매크로 실행 스레드가 폴링하는 bool 플래그 —
        # 단순 대입 읽기라 락 없이 둔다
        return self._executor._stop_requested

    def clear_stop_request(self) -> None:
        self._executor._stop_requested = False

    def move_to_position(self, *args, **kwargs):
        return self._executor._move_to_position(*args, **kwargs)

    def move_pose_keep(self, label: str, target: Dict[str, float], velocity: float,
                       decel_zone_mm: float = 0.0, decel_velocity: float = 3.0,
                       straight: bool = False) -> bool:
        return self._executor._move_pose_keep(
            label, target, velocity, decel_zone_mm, decel_velocity, straight)

    def scan_landmark_averaged(self, *args, **kwargs):
        return self._executor.scan_landmark_averaged(*args, **kwargs)

    def emit(self, callback_name: str, payload: Any) -> None:
        """executor 의 콜백 속성(예: on_origin_check_alarm)을 이름으로 발화한다."""
        callback = getattr(self._executor, callback_name, None)
        if callback:
            callback(payload)

    def put(self, key: str, value: Any) -> None:
        """blackboard 에 산출물을 기록한다 — 후속 매크로의 requires 가 참조."""
        self.blackboard[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.blackboard.get(key, default)

    def has(self, key: str) -> bool:
        return key in self.blackboard


@dataclass
class MacroSpec:
    """매크로 한 개의 선언 — 이름·파라미터 스펙·요구(requires)/산출(produces)."""
    name: str
    summary: str
    category: str
    params: Dict[str, Dict[str, Any]]
    fn: Callable
    requires: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)

    def defaults(self) -> Dict[str, Any]:
        """파라미터 기본값 dict."""
        return {key: spec.get('default') for key, spec in self.params.items()}

    def blackboard_requires(self) -> List[str]:
        """blackboard 로 충족되는 요구 (config: 접두어 제외)."""
        return [r for r in self.requires if not r.startswith(EXTERNAL_PREFIX)]

    def external_requires(self) -> List[str]:
        """외부 설정으로 충족되는 요구 (config: 접두어 벗긴 이름)."""
        return [r[len(EXTERNAL_PREFIX):] for r in self.requires if r.startswith(EXTERNAL_PREFIX)]


MACROS: Dict[str, MacroSpec] = {}


def register(name: str, summary: str, category: str,
             params: Optional[Dict[str, Dict[str, Any]]] = None,
             requires: Optional[List[str]] = None,
             produces: Optional[List[str]] = None):
    """매크로 함수를 MACROS 레지스트리에 등록하는 데코레이터 (이름 중복 시 ValueError)."""
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
    """매크로 하나를 실행한다.

    기본값에 params 를 덮어 병합(스펙에 없는 키는 무시)하고, blackboard
    선행조건을 검사한 뒤 실행한다. 반환형이 MacroResult/bool 이 아니면
    실패로 감싼다 — 매크로 구현 실수를 호출부까지 전파하지 않기 위해서다.
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
    """매크로 나열 순서의 requires/produces 정합성을 실행 없이 정적 검사한다.

    Returns:
        (문제 없음 여부, 문제 설명 목록).
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
