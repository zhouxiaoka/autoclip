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

class CropPoint(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    # Seconds from the start of the scene; the framing holds until the next point.
    start: float = Field(ge=0)
    crop_x: float = Field(ge=0, le=1)
    # 'crop' follows crop_x; 'fit' shows the whole frame on a blurred backdrop (text cards, slides, no faces).
    mode: Literal['crop', 'fit'] = 'crop'


class Scene(BaseModel):
    framing_source: Literal["auto", "manual"] | None = None
    framing_adjusted: bool = False
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', min_length=1, max_length=100)
    label: str = Field(default='片段', max_length=120)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    evidence: str = Field(default='', max_length=1000)
    # Per-scene horizontal framing for the crop layout (0 = left, 1 = right); None follows the draft.
    crop_x: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    # Speaker-following framing: piecewise-constant crop_x over the scene. Empty/None = static crop_x.
    crop_track: list[CropPoint] | None = Field(default=None, max_length=400)

    @model_validator(mode='after')
    def interval(self):
        if self.end - self.start < .1:
            raise ValueError('片段至少需要 0.1 秒')
        return self

class PackagingCue(BaseModel):
    """One caption line in source seconds: text in the audience language, plus the original."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=600)
    original: str = Field(default='', max_length=900)


class PackagingSpeaker(BaseModel):
    """Lower-third nameplate shown when this person first appears (source seconds)."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    at: float = Field(ge=0)
    name: str = Field(min_length=1, max_length=40)
    role: str = Field(default='', max_length=60)


class PackagingMark(BaseModel):
    """A commentary tag or a highlighted word anchored at a source time."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    at: float = Field(ge=0)
    text: str = Field(min_length=1, max_length=30)


class Packaging(BaseModel):
    """Automatic template packaging, generated once per content and audience language."""
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    template: Literal['interview_zh', 'podcast_en']
    audience_language: Literal['zh', 'en']
    source_language: Literal['zh', 'en', 'other'] = 'other'
    title_lines: list[str] = Field(default_factory=list, max_length=2)
    title_accent_line: int = Field(default=1, ge=0, le=1)
    cues: list[PackagingCue] = Field(default_factory=list, max_length=600)
    speakers: list[PackagingSpeaker] = Field(default_factory=list, max_length=8)
    tags: list[PackagingMark] = Field(default_factory=list, max_length=8)
    tags_enabled: bool = True
    highlights: list[PackagingMark] = Field(default_factory=list, max_length=40)
    burned_captions: bool = False
    fallback: bool = False
    # Visual style inside the template; None = the golden default (classic / pop).
    style: Literal['classic', 'boxed', 'spotlight', 'pop', 'cinematic'] | None = None
    # Content mood chosen by the model; it picks the palette and style (packaging.choose_look).
    mood: Literal['calm', 'serious', 'bold', 'warm', 'playful'] | None = None
    palette: Literal['azure', 'amber', 'coral', 'mint', 'lemon', 'rose', 'lilac'] | None = None

    @model_validator(mode='after')
    def short_title_lines(self):
        self.title_lines = [line.strip() for line in self.title_lines if line.strip()]
        if any(len(line) > 40 for line in self.title_lines):
            raise ValueError('标题每行最多 40 个字符')
        allowed = {'interview_zh': ('classic', 'boxed', 'spotlight'), 'podcast_en': ('pop', 'boxed', 'cinematic')}[self.template]
        if self.style is not None and self.style not in allowed:
            raise ValueError('这个模板不支持所选样式')
        return self


class Draft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', max_length=100)
    title: str = Field(min_length=1, max_length=200)
    hook: str = Field(default='', max_length=120)
    scenes: list[Scene] = Field(min_length=1, max_length=30)
    language: Language = 'source'
    aspect: Literal['original', 'portrait', 'landscape'] = 'original'
    layout: Literal['fit', 'crop', 'blur', 'window'] = 'fit'
    crop_x: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    title_style: Literal['plain', 'impact', 'card', 'comic', 'neon', 'arena', 'editorial', 'pixel', 'frosted'] = 'plain'
    title_template_version: Literal[1, 2, 3, 4, 5, 6] = 1
    title_motion: bool = True
    title_scale: float = Field(default=1, ge=.75, le=1.2, allow_inf_nan=False)
    title_y: float = Field(default=.12, ge=.06, le=.70, allow_inf_nan=False)
    title_accent: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    subtitles: bool = True
    subtitle_style: Literal['clean', 'bold', 'box', 'accent'] = 'clean'
    original_audio: bool = True
    revision: int = Field(default=1, ge=1)
    updated_at: str = ''
    origin: str = 'manual'
    parent_draft_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]+$', max_length=100)
    parent_revision: int | None = Field(default=None, ge=1)
    packaging: Packaging | None = None
    # (top, bottom) of burned captions as fractions of the frame height, blurred out before layout:
    # an English version of a source with Chinese captions in the picture.
    caption_mask: tuple[float, float] | None = None

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


class BrandingOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    outro_enabled: bool = True
    outro_version: str = 'v1'


class PostCopy(BaseModel):
    """Ready-to-publish copy for one platform (post_copy enforces the platform's limits)."""
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='', max_length=100)
    description: str = Field(default='', max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=12)


class CoverJob(BaseModel):
    job_id: str
    status: Literal['queued', 'running', 'completed', 'failed']
    error: str | None = None
    instance: str | None = None


class OutputVariant(BaseModel):
    """One immutable rendered delivery version derived from a draft revision."""
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', min_length=1, max_length=100)
    draft_id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', min_length=1, max_length=100)
    draft_revision: int = Field(ge=1)
    strategy_id: str = Field(min_length=1, max_length=64)
    strategy_version: int = Field(default=1, ge=1)
    branding: BrandingOptions = Field(default_factory=BrandingOptions)
    # on_demand: ranked below the automatic limit; framed, packaged and rendered when the user asks.
    # preparing: being framed and packaged for that request; it is queued for rendering only once ready.
    status: Literal['queued', 'running', 'completed', 'failed', 'on_demand', 'preparing'] = 'queued'
    render_job_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]+$', max_length=100)
    created_at: str = ''
    error: str | None = Field(default=None, max_length=700)
    # Set only when a hard platform limit (e.g. YouTube Shorts 180 s) shortened the moment.
    trimmed_to_sec: int | None = Field(default=None, ge=1)
    # How a vertical version was framed: speaker-following crop, or the full frame on a backdrop.
    framing: Literal['speaker', 'full_frame', 'full_frame_pending', 'full_frame_captions'] | None = None
    # Publish kit: copy written during production, cover designed after the render.
    post: PostCopy | None = None
    cover: Literal['design', 'ai'] | None = None
    cover_job: CoverJob | None = None
    # A backup whose preparation failed or was interrupted: retrying prepares it again instead of
    # rendering the unpackaged draft. `instance` marks which server run is preparing it.
    needs_prepare: bool = False
    instance: str | None = None


class ImportOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goal: Literal['auto', 'content', 'highlight', 'promo'] = 'auto'
    language: Language = 'source'
    aspect: Literal['original', 'portrait', 'landscape'] | None = None
    duration: int | None = Field(default=None, ge=10, le=120)
    instruction: str = Field(default='', max_length=1000)
    platforms: list[str] = Field(default_factory=lambda: ['douyin'], min_length=1, max_length=8)
    auto_start: bool = False
    portrait_style: Literal['auto', 'interview', 'podcast'] = 'auto'
    branding: BrandingOptions = Field(default_factory=BrandingOptions)

    @model_validator(mode='after')
    def unique_platforms(self):
        from backend.services.platform_strategy import normalize_platform_ids
        self.platforms = normalize_platform_ids(self.platforms)
        return self


class AppendPlatformsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    platforms: list[str] = Field(min_length=1, max_length=8)
    branding: BrandingOptions = Field(default_factory=BrandingOptions)

    @model_validator(mode='after')
    def unique_platforms(self):
        from backend.services.platform_strategy import normalize_platform_ids
        self.platforms = normalize_platform_ids(self.platforms)
        return self


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
