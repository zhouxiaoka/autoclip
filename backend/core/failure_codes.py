"""Error codes from event_catalog.json; user sentences from failure_messages.json."""
from __future__ import annotations
import json, logging, re
from pathlib import Path
from backend.core.event_catalog import load_catalog
logger = logging.getLogger(__name__)
_HTTP, _DUMP = re.compile(r"^http_[45][0-9]{2}$"), re.compile(r"FAILED|Traceback|Exception|HTTP Error|Error code|sk-", re.I)
def _enum(name):
    values = (load_catalog().get("enums") or {}).get(name) or json.loads(Path(__file__).with_name("event_catalog.json").read_text(encoding="utf-8"))["enums"][name]
    return frozenset(values)
def studio_codes(): return _enum("studio_error_code")
def download_codes(): return _enum("download_error_code")
def sentry_codes(): return (studio_codes() - {"unknown", "multiple"}) | download_codes()
def stored_codes(): return sentry_codes() | {"multiple"}
def error_code_pattern(): return re.compile(rf"^(?:http_[45][0-9]{{2}}|{'|'.join(sorted(studio_codes()))})$")
def require_code(code):
    if code in studio_codes() or code in download_codes() or _HTTP.fullmatch(code): return code
    raise ValueError(code)
def messages(): return json.loads(Path(__file__).with_name("failure_messages.json").read_text(encoding="utf-8"))
def sentence(code):
    table = messages(); return table.get(code) or table["unknown"]
def _omit(error):
    logger.warning("provider text omitted from UI (%s): %s", type(error).__name__, str(error)[:700])
class UserFacingError(ValueError):
    """A sentence we wrote for the screen. Other ValueErrors use the catalog sentence."""
def _keep_authored(error, text):
    # Only copy we wrote, or a catalog sentence. pydantic ValidationError and JSONDecodeError
    # are ValueErrors; their text is a dump, not a sentence for the user.
    if not text or _DUMP.search(text) or "sk-" in text: return False
    if type(error).__name__ in {"UserFacingError", "CoverError", "ImageError"}: return True
    return text in messages().values()
def _local_sentence_code(error):
    """ffmpeg, a full disk and a missing file get a local sentence, never the model-settings one."""
    import errno, subprocess
    if isinstance(error, FileNotFoundError): return "missing_resource"
    if isinstance(error, OSError) and (getattr(error, "errno", None) in {errno.ENOSPC, errno.EDQUOT, errno.EROFS} or getattr(error, "winerror", None) in {112, 39}):
        return "disk"
    if isinstance(error, subprocess.CalledProcessError): return "frame_extract_failed"
    if type(error) is RuntimeError and str(error).startswith("渲染镜头失败"): return "frame_extract_failed"
    return None
_BARE = frozenset({"错误", "失败", "Error", "error", "处理失败", "处理失败：错误"})


def _shown(text, code):
    """A failure card never shows only 「错误」. Empty or bare text uses the catalog sentence."""
    cleaned = (text or "").strip()
    if not cleaned or cleaned in _BARE:
        return sentence(code or "unknown")[:700]
    return cleaned[:700]


def user_visible_error(error):
    from backend.pipeline.failures import PipelineFailure
    if type(error).__name__ == "JobDurationExceeded":
        return _shown(str(error), "timeout")
    if isinstance(error, PipelineFailure):
        return _shown(error.user_message(), error.code or "unknown")
    local = _local_sentence_code(error)
    if local:
        _omit(error)
        return sentence(local)[:700]
    text = str(error) if error is not None else ""
    if _keep_authored(error, text):
        from backend.core.sentry_setup import studio_error_code
        return _shown(text, studio_error_code(error))
    _omit(error)
    from backend.core.sentry_setup import studio_error_code
    code = studio_error_code(error)
    fine = _fine_upstream_sentence(error, code)
    return _shown(fine or sentence(code), code)


def _fine_upstream_sentence(error, coarse: str):
    """503 is stored as coarse ``provider_error`` but already classified.

    Use the fine sentence only when the coarse code is ``provider_error`` and a
    known upstream type is already on a typed provider error. Do not parse an
    arbitrary RuntimeError: a 401 dump and a raw balance sentence must stay
    ``unexpected`` so the key and the provider text never reach the screen.
    """
    if coarse != "provider_error" or error is None:
        return None
    from backend.core.upstream_errors import UPSTREAM_ERROR_TYPES, UpstreamErrorType, classify_exception, hint_key_for
    attr = getattr(error, "attribution", None)
    candidate = getattr(attr, "upstream_error_type", None) if attr is not None else None
    if isinstance(candidate, str) and candidate in UPSTREAM_ERROR_TYPES:
        # An explicit unknown stays the coarse sentence. Do not re-read the HTTP
        # status: the boundary already decided this one was not a known type.
        if candidate == UpstreamErrorType.UNKNOWN.value:
            return None
        return hint_key_for(candidate)
    if isinstance(candidate, str) or not _typed_provider_error(error):
        return None
    kind = classify_exception(error).error_type
    if kind is UpstreamErrorType.UNKNOWN:
        return None
    return hint_key_for(kind.value)


def _typed_provider_error(error) -> bool:
    from backend.core.failure_attribution import AttributedError, ProviderTransportError
    if isinstance(error, (AttributedError, ProviderTransportError)):
        return True
    try:
        from openai import APIError
    except ImportError:
        return False
    return isinstance(error, APIError)
