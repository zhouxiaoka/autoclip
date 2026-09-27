"""Text-only promotional drafts grounded in existing subtitle selections."""
import uuid
from pydantic import BaseModel, ConfigDict, Field
from backend.services.studio import intelligence
from backend.services.studio.models import Draft
from backend.services.studio.subtitle_highlights import make_highlights
from backend.services.publish_export import _load_srt_entries
from backend.pipeline.quality import to_seconds


class PromoChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate: int = Field(ge=0, le=5)
    title: str = Field(min_length=1, max_length=200)
    hook: str = Field(min_length=1, max_length=120)


class PromoResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    drafts: list[PromoChoice] = Field(min_length=1, max_length=3)


def make_promos(project_id, clips, preferences, source_duration, instruction=''):
    candidates = make_highlights(clips, preferences, source_duration)
    entries = _load_srt_entries(project_id)
    evidence = []
    for i, draft in enumerate(candidates):
        scene = draft['scenes'][0]
        # A title alone is insufficient evidence for promotional claims.
        texts = [str(e.get('text', '')) for e in entries
                 if to_seconds(e['start_time']) < scene['end']
                 and to_seconds(e['end_time']) > scene['start']]
        transcript = '\n'.join(texts).strip()[:1500]
        if transcript:
            evidence.append({'candidate': i, 'transcript': transcript})
    if not evidence:
        raise ValueError('推广草稿需要可用字幕证据，请检查字幕后重试；原素材已保留')
    response = PromoResponse.model_validate(intelligence.text_json(
        '根据字幕证据选择适合分享推广的完整片段，输出1至3条草稿。'
        '返回 {"drafts":[{"candidate":0,"title":"标题","hook":"简短开头文字"}]}。'
        'candidate只能选择输入编号；尽量选择不同主题，不为数量重复同一片段。'
        '标题和开头必须有字幕事实依据，不虚构玩法、价格、承诺、胜负或投放效果。'
        '这些是待人工复核的推广草稿，不是已验证广告。不得改变镜头起止范围。',
        {'candidates': evidence, 'language': preferences.language, 'instruction': instruction[:1000]}))
    valid = {e['candidate'] for e in evidence}
    if any(choice.candidate not in valid for choice in response.drafts):
        raise ValueError('推广方案引用了无效片段，请重试；原稿已保留')
    output = []
    seen = set()
    for choice in response.drafts:
        if choice.candidate in seen:
            continue
        seen.add(choice.candidate)
        if not choice.title.strip() or not choice.hook.strip():
            raise ValueError('推广文案为空，请重试；原稿已保留')
        output.append(Draft.model_validate({**candidates[choice.candidate],
            'id': uuid.uuid4().hex, 'title': choice.title.strip(), 'hook': choice.hook.strip(),
            'origin': 'subtitle-promo', 'title_style': 'comic', 'title_template_version': 6}).model_dump())
    return output
