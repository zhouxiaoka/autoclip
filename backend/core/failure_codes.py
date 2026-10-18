"""Error codes from event_catalog.json; user sentences from failure_messages.json."""
from __future__ import annotations
import json, logging, re
from pathlib import Path
from backend.core.event_catalog import load_catalog
logger = logging.getLogger(__name__)
_HTTP, _DUMP, _CJK = re.compile(r"^http_[45][0-9]{2}$"), re.compile(r"FAILED|Traceback|Exception|HTTP Error|Error code|sk-", re.I), re.compile(r"[\u4e00-\u9fff]")
def _enum(name):
    return frozenset(load_catalog()["enums"][name])
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
def user_visible_error(error):
    from backend.pipeline.failures import PipelineFailure
    text = error.user_message() if isinstance(error, PipelineFailure) else str(error)
    if isinstance(error, PipelineFailure) or (text and _DUMP.search(text) is None and _CJK.search(text)): return text[:700]
    logger.warning("provider text omitted from UI (%s): %s", type(error).__name__, text[:700])
    from backend.core.sentry_setup import studio_error_code
    return sentence(studio_error_code(error))[:700]
