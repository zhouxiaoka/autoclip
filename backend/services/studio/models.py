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

class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', max_length=100)
    title: str = Field(min_length=1, max_length=200)
    hook: str = Field(default='', max_length=120)
    scenes: list[Scene] = Field(min_length=1, max_length=30)
    language: Language = 'source'
    aspect: Literal['original', 'portrait', 'landscape'] = 'original'
    layout: Literal['fit', 'crop', 'blur'] = 'fit'
    crop_x: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    title_style: Literal['plain', 'impact', 'card', 'comic', 'neon', 'arena', 'editorial'] = 'plain'
    title_template_version: Literal[1, 2] = 1
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
        if self.title_style == 'editorial' and self.title_template_version != 2:
            raise ValueError('极简大字需要文字模板版本 2')
        return self

class CreateDraft(BaseModel):
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
