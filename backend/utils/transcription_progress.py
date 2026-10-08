"""Transcription progress by processed audio duration (RC156 Win QA #14).

A 35-minute source spent ~6 minutes in local Whisper while the UI only showed the
fixed SUBTITLE checkpoints (10% / 13% / 16%). Transcribers report how far into
the audio they are; whoever started the transcription decides where it shows.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

_reporter: ContextVar[Optional[Callable[[float], None]]] = ContextVar('transcription_progress', default=None)


@contextmanager
def reporting(callback: Callable[[float], None]):
    token = _reporter.set(callback)
    try:
        yield
    finally:
        _reporter.reset(token)


def report(processed_sec, total_sec) -> None:
    """Report `processed_sec` of `total_sec` audio transcribed. Display failures never stop transcription."""
    callback = _reporter.get()
    if callback is None:
        return
    try:
        processed, total = float(processed_sec or 0), float(total_sec or 0)
    except (TypeError, ValueError):
        return
    if total <= 0:
        return
    fraction = min(1.0, max(0.0, processed / total))
    try:
        callback(fraction)
    except FileNotFoundError:
        raise  # ProjectDeleted (RC156 #12): the project is gone, stop transcribing
    except Exception as error:  # noqa: BLE001
        logger.debug('Transcription progress display failed: %s', type(error).__name__)
