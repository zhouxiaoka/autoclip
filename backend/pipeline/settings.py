"""Read saved processing settings at the start of each pipeline step."""
from ..core.llm_manager import get_llm_manager

# Local models (Ollama / LM Studio / localhost OpenAI-compat) often have a small
# context. A 5000-character chunk makes step1/step2 prompts fail as
# analyze / invalid_response or timeline_empty after several minutes.
LOCAL_CHUNK_SIZE_CAP = 2000


def processing_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = get_llm_manager().get_processing_setting(name, default)
    try:
        if isinstance(value, bool) or int(value) != float(value):
            return default
        number = int(value)
        return number if minimum <= number <= maximum else default
    except (ValueError, TypeError, OverflowError):
        return default


def effective_chunk_size() -> int:
    """Configured chunk_size, capped for a local or localhost-compatible model.

    A saved value already at or below LOCAL_CHUNK_SIZE_CAP is kept. Cloud providers
    keep the configured value (default 5000, accepted range 1000–10000). If the
    active model cannot be classified, the configured value is kept. Step2 reads
    the SRT chunks step1 writes with this size and does not chunk again.
    """
    configured = processing_int("chunk_size", 5000, 1000, 10000)
    if configured <= LOCAL_CHUNK_SIZE_CAP:
        return configured
    try:
        from backend.core.local_presets import is_local_model
        local = is_local_model(get_llm_manager().settings)
    except Exception:  # noqa: BLE001 - unreadable model: do not shrink a cloud prompt
        return configured
    return LOCAL_CHUNK_SIZE_CAP if local else configured
