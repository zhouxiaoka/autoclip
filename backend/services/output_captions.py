"""Whether automatic production burns captions. Default on.

Stored like the brand-outro switch. The value is copied onto the generation
record when a project starts, so a later change does not rewrite a project
that is already underway, including its on-demand variants.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, StrictBool

logger = logging.getLogger(__name__)
_unreadable_logged = False


class CaptionSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool = True


def settings_path() -> Path:
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / 'output-captions.json'


def load_settings() -> CaptionSettings:
    path = settings_path()
    if not path.exists():
        return CaptionSettings()
    try:
        return CaptionSettings.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        _warn_unreadable()
        return CaptionSettings()


def _warn_unreadable() -> None:
    global _unreadable_logged
    if _unreadable_logged:
        return
    _unreadable_logged = True
    logger.warning('output-captions.json is unreadable; captions stay on')


def save_settings(settings: CaptionSettings) -> CaptionSettings:
    settings = CaptionSettings.model_validate(settings.model_dump())
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f'.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_text(settings.model_dump_json(), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return settings
