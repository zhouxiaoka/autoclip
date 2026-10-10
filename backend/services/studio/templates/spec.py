"""Pydantic contract for one packaging template.

Each template lives in ``backend/assets/templates/<id>/`` and is rejected at
load time when this model, or the page contract, does not hold. A template
that fails validation never becomes a candidate.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HTML_TEMPLATE_IDS = ('editorial', 'street')
SAFE_AREAS = ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts')
PACKAGING_FIELDS = ('title_lines', 'cues', 'kicker', 'emphasis', 'numbers', 'gloss', 'speakers', 'stickers')


class NameSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    zh: str = Field(min_length=1, max_length=40)
    en: str = Field(min_length=1, max_length=40)


class FitSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    formats: dict[str, float]
    needs_face: bool

    @field_validator('formats')
    @classmethod
    def weights(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError('fit.formats 不能为空')
        cleaned: dict[str, float] = {}
        for key, weight in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError('fit.formats 的名称无效')
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= float(weight) <= 1:
                raise ValueError('fit.formats 的权重必须在 0 到 1 之间')
            cleaned[key] = float(weight)
        return cleaned


class CanvasSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    aspects: list[Literal['portrait']] = Field(min_length=1, max_length=1)
    overlay_px: tuple[int, int]
    fps: Literal[30]

    @field_validator('overlay_px')
    @classmethod
    def even_pixels(cls, value: tuple[int, int]) -> tuple[int, int]:
        width, height = (int(value[0]), int(value[1]))
        if width < 2 or height < 2 or width % 2 or height % 2:
            raise ValueError('overlay_px 必须是偶数像素')
        if (width, height) != (720, 1280):
            raise ValueError('v1 叠加层固定为 720×1280')
        return width, height


class IntroZoom(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    from_scale: float = Field(alias='from', ge=1, le=1.4)
    dur: float = Field(gt=0, le=3)


class ZoomSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['creep', 'step']
    creep: float | None = Field(default=None, ge=0, le=0.3)
    key_punch: float | None = Field(default=None, ge=0, le=0.2)
    intro: IntroZoom | None = None
    end_push: float | None = Field(default=None, ge=0, le=0.2)
    step: list[float] | None = None

    @model_validator(mode='after')
    def mode_fields(self):
        if self.mode == 'creep' and self.creep is None:
            raise ValueError('creep 模式需要 creep 比例')
        if self.mode == 'step':
            if not self.step or len(self.step) < 2:
                raise ValueError('step 模式至少需要两个缩放档')
            if any(not 1 <= float(item) <= 1.4 for item in self.step):
                raise ValueError('step 缩放必须在 1 到 1.4 之间')
        return self


class TransitionSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    broll: Literal['zoomblur', 'cut', 'none'] = 'none'
    max: int = Field(ge=0, le=4)


class BaseSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    framing: Literal['full_face', 'window', 'square']
    face_y: float = Field(ge=0, le=1)
    head_zone: tuple[int, int]
    zoom: ZoomSpec
    transitions: TransitionSpec
    grade: str = Field(min_length=1, max_length=400)

    @model_validator(mode='after')
    def head_band(self):
        top, bottom = self.head_zone
        if top < 0 or bottom <= top:
            raise ValueError('head_zone 必须是自上而下的区间')
        return self


class SlotSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    top: int = Field(ge=0)
    alt_top: int | None = Field(default=None, ge=0)
    left: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    max_rows: int | None = Field(default=None, ge=1, le=2)


class OverlaySpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entry: Literal['index.html'] = 'index.html'
    slots: dict[str, SlotSpec | list[SlotSpec]]
    safe_area: Literal['xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts']
    limits: dict[str, float | int]

    @model_validator(mode='after')
    def named_slots(self):
        if 'subtitle' not in self.slots or 'hook' not in self.slots:
            raise ValueError('overlay.slots 必须包含 hook 和 subtitle')
        subtitle = self.slots['subtitle']
        if isinstance(subtitle, list) or subtitle.max_rows != 2:
            raise ValueError('字幕槽最多 2 行')
        for key, value in self.limits.items():
            if not key.isidentifier() or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError('overlay.limits 只接受数字')
        return self


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    required: list[str] = Field(min_length=1)
    optional: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def known_fields(self):
        names = [*self.required, *self.optional]
        if any(name not in PACKAGING_FIELDS for name in names):
            raise ValueError('未知包装字段')
        if len(names) != len(set(names)):
            raise ValueError('包装字段不能重复')
        if 'title_lines' not in self.required or 'cues' not in self.required:
            raise ValueError('title_lines 和 cues 是必填字段')
        return self


class AudioSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    bgm: Literal['none', 'bed'] = 'none'
    optional_bed: bool = False


class CoverSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    layout: str = Field(min_length=1, max_length=40)
    from_overlay: bool = True


class TemplateSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Literal['editorial', 'street']
    version: Literal[1]
    name: NameSpec
    fit: FitSpec
    canvas: CanvasSpec
    base: BaseSpec
    overlay: OverlaySpec
    fields: FieldSpec
    audio: AudioSpec
    cover: CoverSpec
    qa: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def empty_qa(self):
        if self.qa:
            raise ValueError('v1 不覆盖质检阈值')
        return self
