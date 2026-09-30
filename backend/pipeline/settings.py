"""Read saved processing settings at the start of each pipeline step."""
from ..core.llm_manager import get_llm_manager


def processing_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = get_llm_manager().get_processing_setting(name, default)
    try:
        if isinstance(value, bool) or int(value) != float(value):
            return default
        number = int(value)
        return number if minimum <= number <= maximum else default
    except (ValueError, TypeError, OverflowError):
        return default
