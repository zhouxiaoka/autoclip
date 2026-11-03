"""Local failure-log correlation, restricted to generated IDs and fixed step names."""
from __future__ import annotations

import contextvars
import logging
import re
from functools import wraps

from backend.core.project_cancellation import current

_context = contextvars.ContextVar("failure_log_ids", default="")
# Pipeline clips/chunks use decimal IDs; projects use UUIDs. Reject free-form text,
# even if it could otherwise pass a generic ASCII identifier check.
_ID = re.compile(r"(?:[0-9]{1,10}|[a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})\Z")


def _id(value):
    if type(value) not in (int, str):
        return ""
    value = str(value)
    return value if _ID.fullmatch(value) else ""


def _clip_ids(clips):
    return ",".join(dict.fromkeys(value for clip in clips if isinstance(clip, dict)
                                if (value := _id(clip.get("id")))))


def chunk_failure_context(step):
    """Bind IDs inside each worker; reset on success, fallback and exceptions."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(item):
            index, items = item
            fields = f"step={step}"
            if value := _id(index):
                fields += f" chunk_index={value}"
            # Step 1's second item is a file path: never inspect or log it.
            if isinstance(items, list) and (ids := _clip_ids(items)):
                fields += f" clip_ids={ids}"
            token = _context.set(fields)
            try:
                return fn(item)
            finally:
                _context.reset(token)
        return wrapped
    return decorate


def clips_failure_context(step):
    """Step 5 operates on all clips rather than one chunk."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(self, clips_with_titles):
            fields = f"step={step}"
            if ids := _clip_ids(clips_with_titles):
                fields += f" clip_ids={ids}"
            token = _context.set(fields)
            try:
                return fn(self, clips_with_titles)
            finally:
                _context.reset(token)
        return wrapped
    return decorate


class _FailureLogger(logging.LoggerAdapter):
    def log(self, level, msg, *args, **kwargs):
        if not self.isEnabledFor(level):
            return
        if level >= logging.WARNING:
            fields = _context.get() or self.extra["step"]
            if project_id := _id(current()):
                fields += f" project_id={project_id}"
            if fields:
                msg = fields.strip() + " " + msg
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        self.logger.log(level, msg, *args, **kwargs)


def failure_logger(name):
    step = "step=" + name.rsplit(".", 1)[-1] if name.startswith("backend.pipeline.step") else ""
    return _FailureLogger(logging.getLogger(name), {"step": step})
