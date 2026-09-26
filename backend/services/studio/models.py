from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Goal = Literal['content', 'highlight', 'promo']
Language = Literal['source', 'zh', 'en', 'ja']

class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goal: Goal = 'content'
    language: Language = 'source'
    aspect: Literal['original', 'portrait', 'landscape'] = 'original'
    duration: int = Field(30, ge=10, le=120)

class Scene(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', min_length=1, max_length=100)
    label: str = Field(default='片段', max_length=120)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    evidence: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def interval(self):
        if self.end - self.start < .1:
            raise ValueError('片段至少需要 0.1 秒')
        return self

class CTA(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    template: Literal['off', 'auto', 'continue', 'challenge', 'brand'] = 'off'
    version: Literal[1] = 1
    style: Literal['glossy', 'soft', 'tactical', 'type'] = 'glossy'
    accent: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    brand: str = Field(default='', max_length=40)
    text: str = Field(default='', max_length=80)
    language: Literal['zh', 'en', 'ja'] = 'zh'
    position: float = Field(default=.65, ge=.2, le=.7)
    confirmed_scene: str = Field(default='', max_length=200)


class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', max_length=100)
    title: str = Field(min_length=1, max_length=200)
    hook: str = Field(default='', max_length=120)
    cta: CTA = Field(default_factory=CTA)
    scenes: list[Scene] = Field(min_length=1, max_length=30)
    language: Language = 'source'
    aspect: Literal['original', 'portrait', 'landscape'] = 'original'
    layout: Literal['fit', 'crop', 'blur'] = 'fit'
    crop_x: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    title_style: Literal['plain', 'impact', 'card', 'comic', 'neon', 'arena', 'editorial', 'pixel', 'frosted'] = 'plain'
    title_template_version: Literal[1, 2, 3, 4, 5, 6] = 1
    title_motion: bool = True
    title_scale: float = Field(default=1, ge=.75, le=1.2, allow_inf_nan=False)
    title_y: float = Field(default=.12, ge=.06, le=.70, allow_inf_nan=False)
    title_accent: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    subtitles: bool = True
    original_audio: bool = True
    revision: int = Field(default=1, ge=1)
    updated_at: str = ''
    origin: str = 'manual'
    parent_draft_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]+$', max_length=100)
    parent_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def title_version(self):
        if self.title_template_version == 6 and self.title_style in ('plain', 'impact', 'card'):
            raise ValueError('文字模板版本 6 仅支持六款设计预设')
        if self.title_template_version in (4, 5) and self.title_style != 'comic':
            raise ValueError('文字模板版本 4/5 仅支持漫画冲击')
        if self.title_style == 'editorial' and self.title_template_version < 2:
            raise ValueError('极简大字需要文字模板版本 2 或更新')
        if self.title_style in ('pixel', 'frosted') and self.title_template_version not in (3, 6):
            raise ValueError('像素与磨砂模板需要文字模板版本 3 或 6')
        return self

class CreateDraft(BaseModel):
    reuse_existing: bool = False
    clip_ids: list[str] = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=200)

class RewriteRequest(BaseModel):
    draft: Draft
    instruction: str = Field(min_length=1, max_length=2000)

class DuplicateDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    draft: Draft
    title: str = Field(min_length=1, max_length=200)
    language: Language

    @model_validator(mode='after')
    def valid_title(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('请填写新版本名称')
        return self


class ExportDraftRequest(BaseModel):
    revision: int = Field(ge=1)


class ImportOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goal: Literal['auto', 'content', 'highlight', 'promo'] = 'auto'
    language: Language = 'source'
    aspect: Literal['original', 'portrait', 'landscape'] | None = None
    duration: int | None = Field(default=None, ge=10, le=120)
    instruction: str = Field(default='', max_length=1000)


class ConfirmPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis_mode: Literal['subtitle', 'visual'] | None = None
    plan_id: str = Field(min_length=1, max_length=100)
    goals: list[Goal] = Field(min_length=1, max_length=3)
    language: Language | None = None
    aspect: Literal['original', 'portrait', 'landscape'] | None = None
    duration: int | None = Field(default=None, ge=10, le=120)

    @model_validator(mode='after')
    def unique_goals(self):
        if len(set(self.goals)) != len(self.goals):
            raise ValueError('制作类型不能重复')
        return self
