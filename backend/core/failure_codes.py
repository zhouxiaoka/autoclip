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
def _keep_authored(error, text):
    # ValueError / cover / image wrappers carry copy we wrote. Provider bodies stay out, including Chinese.
    if not text or _DUMP.search(text) or "sk-" in text: return False
    if isinstance(error, ValueError): return True
    return type(error).__name__ in {"CoverError", "ImageError"}
def _local_sentence_code(error):
    """ffmpeg, a full disk and a missing file get a local sentence, never the model-settings one."""
    import errno, subprocess
    if isinstance(error, FileNotFoundError): return "missing_resource"
    if isinstance(error, OSError) and (getattr(error, "errno", None) in {errno.ENOSPC, errno.EDQUOT, errno.EROFS} or getattr(error, "winerror", None) in {112, 39}):
        return "disk"
    if isinstance(error, subprocess.CalledProcessError): return "frame_extract_failed"
    if type(error) is RuntimeError and str(error).startswith("渲染镜头失败"): return "frame_extract_failed"
    return None
def user_visible_error(error):
    from backend.pipeline.failures import PipelineFailure
    if isinstance(error, PipelineFailure): return (error.user_message() or "")[:700]
    local = _local_sentence_code(error)
    if local:
        _omit(error)
        return sentence(local)[:700]
    text = str(error) if error is not None else ""
    if _keep_authored(error, text): return text[:700]
    _omit(error)
    from backend.core.sentry_setup import studio_error_code
    return sentence(studio_error_code(error))[:700]
