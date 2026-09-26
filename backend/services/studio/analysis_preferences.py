"""Explicit analysis preferences, independent from configured model capabilities.

Foundation for dual routing. Callers must wire this contract into planning and
production before exposing a mode selector; this module does not switch routes.
"""
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from backend.core.path_utils import get_data_directory

AnalysisMode = Literal['subtitle', 'auto', 'visual']
_lock = threading.RLock()


class AnalysisPreferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis_mode: AnalysisMode = 'subtitle'
    allow_visual_screening: StrictBool = False

    @model_validator(mode='after')
    def subtitle_is_text_only(self):
        if self.analysis_mode == 'subtitle' and self.allow_visual_screening:
            raise ValueError('字幕分析不能启用视觉初筛')
        return self


def settings_path() -> Path:
    return get_data_directory() / 'analysis-preferences.json'


def load() -> AnalysisPreferences:
    """Old installations default to subtitle, regardless of model or env keys.

    An invalid saved preference is an error, never permission to spend money.
    The caller should preserve source material and ask for corrected settings.
    """
    with _lock:
        path = settings_path()
        if not path.exists():
            return AnalysisPreferences()
        try:
            return AnalysisPreferences.model_validate_json(path.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as error:
            raise ValueError('分析偏好无法读取，请重新设置；尚未授权视觉调用') from error


def save(preferences: AnalysisPreferences) -> AnalysisPreferences:
    # Revalidate even model_construct/model_copy inputs before persisting them.
    validated = AnalysisPreferences.model_validate(preferences.model_dump())
    with _lock:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(validated.model_dump(), stream, ensure_ascii=False, indent=2)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    return validated


def visual_screening_allowed(preferences: AnalysisPreferences, *, vision_configured: bool) -> bool:
    """Capability alone is not consent. This never initiates a model request."""
    return (preferences.analysis_mode != 'subtitle'
            and preferences.allow_visual_screening is True
            and vision_configured is True)
