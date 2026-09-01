"""macros 공개 API 재수출 — builtin/pallet_teach import 는 매크로 등록 부수효과를 겸한다."""
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
from . import builtin
from . import pallet_teach

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
