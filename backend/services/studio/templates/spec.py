"""Pydantic contract for one packaging template.

Each template lives in ``backend/assets/templates/<id>/`` (built-in) or
``<data_dir>/templates/<id>/`` (user-installed / hot-updated) and is rejected at
load time when this model, or the page contract, does not hold. A template
that fails validation never becomes a candidate.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.core.failure_codes import UserFacingError

# Built-in shipping HTML template IDs. Dynamic / user-installed templates are
# discovered by ``registry.py`` and are not restricted to this tuple.
BUILTIN_TEMPLATE_IDS = ('editorial', 'street', 'news', 'cinema')
HTML_TEMPLATE_IDS = BUILTIN_TEMPLATE_IDS
STYLE_IDS = (*HTML_TEMPLATE_IDS, 'classic')
SAFE_AREAS = ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts')
PACKAGING_FIELDS = ('title_lines', 'cues', 'kicker', 'emphasis', 'numbers', 'gloss', 'speakers', 'stickers')

TEMPLATE_ID_RE = re.compile(r'^[a-z][a-z0-9_-]{1,31}$')
RESERVED_TEMPLATE_IDS = frozenset({'classic', 'none', 'auto', 'default', 'custom', 'all', 'sync', 'install'})


def is_valid_template_slug(value: str) -> bool:
    return isinstance(value, str) and bool(TEMPLATE_ID_RE.match(value)) and value not in RESERVED_TEMPLATE_IDS


class NameSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    zh: str = Field(min_length=1, max_length=40)
    en: str = Field(min_length=1, max_length=40)
    locales: dict[str, str] = Field(default_factory=dict)

    def resolve(self, locale: str = 'zh') -> str:
        norm = (locale or 'zh').strip().lower()
        if norm in self.locales and self.locales[norm].strip():
            return self.locales[norm].strip()
        short = norm.split('-', 1)[0]
        if short in self.locales and self.locales[short].strip():
            return self.locales[short].strip()
        if short == 'zh':
            return self.zh
        return self.en


class LocalizedText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    zh: str = Field(min_length=1, max_length=160)
    en: str = Field(min_length=1, max_length=160)
    locales: dict[str, str] = Field(default_factory=dict)

    def resolve(self, locale: str = 'zh') -> str:
        norm = (locale or 'zh').strip().lower()
        if norm in self.locales and self.locales[norm].strip():
            return self.locales[norm].strip()
        short = norm.split('-', 1)[0]
        if short in self.locales and self.locales[short].strip():
            return self.locales[short].strip()
        if short == 'zh':
            return self.zh
        return self.en


class MetaSpec(BaseModel):
    """Self-contained catalog, i18n, and preview metadata for dynamic templates."""
    model_config = ConfigDict(extra='forbid')
    desc: LocalizedText | None = None
    tags: list[str] = Field(default_factory=list, max_length=12)
    category: str = Field(default='general', min_length=1, max_length=32)
    order: int = Field(default=100, ge=0, le=10000)
    package_version: str = Field(default='1.0.0', pattern=r'^\d+\.\d+\.\d+([-.][a-zA-Z0-9.]+)?$')
    min_app_version: str | None = Field(default=None, max_length=32)
    author: str = Field(default='AutoClip', max_length=64)
    preview_layout: Literal['crop', 'blur', 'fit'] = 'blur'


class CaptionLayoutSpec(BaseModel):
    """Declarative caption paging and bilingual alignment rules (replaces per-ID branches)."""
    model_config = ConfigDict(extra='forbid')
    font_px: int = Field(default=52, ge=20, le=120)
    inset_px: int = Field(default=60, ge=0, le=200)
    source_limit: int = Field(default=34, ge=10, le=100)
    paging_mode: Literal['phrase', 'grouped_screen', 'sentence'] = 'phrase'
    screen_chars: int | None = Field(default=None, ge=4, le=30)
    screen_sec: float | None = Field(default=None, gt=0, le=10)
    hold_slack: int = Field(default=0, ge=0, le=6)
    bilingual_align: Literal['synced', 'per_cue', 'sentence_screens'] = 'per_cue'
    strip_speaker_prefix: bool = False
    en_key_propagates: bool = True
    burn_cover_title: bool = False
    # Keep each clause's trailing punctuation (，。？) on the caption pieces instead of stripping it.
    keep_punctuation: bool = False


class ScrimSpec(BaseModel):
    """Declarative bottom gradient wash composited in ffmpeg."""
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    height: int = Field(default=1000, ge=2, le=1920)
    color: str = Field(default='0x0C0A08', pattern=r'^0x[0-9A-Fa-f]{6}$')
    mid_stop: float = Field(default=0.38, gt=0, lt=1)
    mid_alpha: float = Field(default=0.38, ge=0, le=1)
    bottom_alpha: float = Field(default=0.78, ge=0, le=1)


class ProgressBarSpec(BaseModel):
    """Declarative ffmpeg progress bar synced to the clip clock."""
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    height: int = Field(default=2, ge=2, le=32)
    inset_x: int = Field(default=0, ge=0, le=300)
    y_from_bottom: int = Field(default=0, ge=0, le=400)
    color: str = Field(default='0xF4EFE6@0.8', pattern=r'^0x[0-9A-Fa-f]{6}(@[0-9.]+)?$')

    @field_validator('height')
    @classmethod
    def even_height(cls, value: int) -> int:
        if int(value) % 2:
            raise UserFacingError('progress_bar.height 必须是偶数像素')
        return int(value)


class FitSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    formats: dict[str, float]
    needs_face: bool

    @field_validator('formats')
    @classmethod
    def weights(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise UserFacingError('fit.formats 不能为空')
        cleaned: dict[str, float] = {}
        for key, weight in value.items():
            if not isinstance(key, str) or not key.strip():
                raise UserFacingError('fit.formats 的名称无效')
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= float(weight) <= 1:
                raise UserFacingError('fit.formats 的权重必须在 0 到 1 之间')
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
            raise UserFacingError('overlay_px 必须是偶数像素')
        if (width, height) != (1080, 1920):
            raise UserFacingError('HTML 叠加层是 1080×1920')
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
            raise UserFacingError('creep 模式需要 creep 比例')
        if self.mode == 'step':
            if not self.step or len(self.step) < 2:
                raise UserFacingError('step 模式至少需要两个缩放档')
            if any(not 1 <= float(item) <= 1.4 for item in self.step):
                raise UserFacingError('step 缩放必须在 1 到 1.4 之间')
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
    step_window: bool = False
    # Lock the base picture layout under the overlay. 'auto' keeps the draft's own layout;
    # 'fit' centres a 16:9 source in the 1080x608 band (y 656..1264) for window/card templates.
    picture_layout: Literal['auto', 'crop', 'blur', 'fit'] = 'auto'
    scrim: ScrimSpec | None = None
    progress_bar: ProgressBarSpec | None = None

    @model_validator(mode='after')
    def head_band(self):
        top, bottom = self.head_zone
        if top < 0 or bottom <= top:
            raise UserFacingError('head_zone 必须是自上而下的区间')
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
            raise UserFacingError('overlay.slots 必须包含 hook 和 subtitle')
        subtitle = self.slots['subtitle']
        if isinstance(subtitle, list) or subtitle.max_rows != 2:
            raise UserFacingError('字幕槽最多 2 行')
        for key, value in self.limits.items():
            if not key.isidentifier() or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise UserFacingError('overlay.limits 只接受数字')
        return self


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    required: list[str] = Field(min_length=1)
    optional: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def known_fields(self):
        names = [*self.required, *self.optional]
        if any(name not in PACKAGING_FIELDS for name in names):
            raise UserFacingError('未知包装字段')
        if len(names) != len(set(names)):
            raise UserFacingError('包装字段不能重复')
        if 'title_lines' not in self.required or 'cues' not in self.required:
            raise UserFacingError('title_lines 和 cues 是必填字段')
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
    id: str
    version: Literal[1, 2] = 1
    name: NameSpec
    fit: FitSpec
    canvas: CanvasSpec
    base: BaseSpec
    overlay: OverlaySpec
    fields: FieldSpec
    audio: AudioSpec
    cover: CoverSpec
    caption_layout: CaptionLayoutSpec | None = None
    meta: MetaSpec | None = None
    qa: dict = Field(default_factory=dict)

    @field_validator('id')
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not is_valid_template_slug(value):
            raise UserFacingError(f'模板 id 无效或为保留字: {value}')
        return value

    @model_validator(mode='after')
    def empty_qa(self):
        if self.qa:
            raise UserFacingError('v1 不覆盖质检阈值')
        return self

    def effective_caption_layout(self) -> CaptionLayoutSpec:
        return self.caption_layout or CaptionLayoutSpec()

    def effective_meta(self) -> MetaSpec:
        return self.meta or MetaSpec()
