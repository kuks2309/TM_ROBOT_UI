"""매크로 계층 — 재사용 가능한 함수 단위.

builtin 을 여기서 import 해야 @register 가 실행되어 레지스트리가 채워진다.
새 매크로 모듈을 추가하면 이 파일에 import 를 한 줄 더한다.
"""
from .base import (
    EXTERNAL_PREFIX,
    MACROS,
    MacroContext,
    MacroResult,
    MacroSpec,
    get_macro,
    register,
    run_macro,
    validate_sequence,
)
from . import builtin  # noqa: F401  — import 부작용으로 레지스트리 등록
from . import pallet_teach  # noqa: F401  — 팔레트 티칭 매크로 등록

__all__ = [
    'EXTERNAL_PREFIX',
    'MACROS',
    'MacroContext',
    'MacroResult',
    'MacroSpec',
    'get_macro',
    'register',
    'run_macro',
    'validate_sequence',
]
