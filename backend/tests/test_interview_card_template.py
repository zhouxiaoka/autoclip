"""The first cloned hot-update template (templates-catalog/interview_card) and the
declarative primitives it introduced: burn_cover_title, keep_punctuation, picture_layout.

Every visible line must come from the clip's own packaging; nothing from the reference video is hardcoded."""
from __future__ import annotations

from pathlib import Path

from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill, paint_fill
from backend.services.studio.templates import registry
from scripts import template_cloner, template_factory

ROOT = Path(__file__).resolve().parents[2]
CARD = ROOT / 'templates-catalog' / 'interview_card'
REFERENCE_ONLY = ('YC Lightcone', '土豆姐', 'Lauren', 'Grok', 'Y Combinator', '四百万', 'Coworkers')


def _packaging(template: str, **overrides) -> Packaging:
    fields = dict(
        version=2, template=template, audience_language='zh', source_language='en',
        issue='Y Combinator《The Rise Of AI Coworkers》（2026-11-14）',
        title_lines=['土豆姐：', 'agent怎么自己合PR'],
        speakers=[{'name': 'Garry Tan', 'role': '主持人', 'at': 0.0}, {'name': 'Lauren Tan', 'role': 'Grok Bot 团队', 'at': 0.0}],
        cues=[{'start': 0.0, 'end': 3.0, 'speaker': 'Garry Tan',
               'text': '我记得你讲过开发流程，那次分享好像有超过四百万播放。',
               'original': 'When you did that presentation that had over four million views on your dev process,'}],
    )
    fields.update(overrides)
    return Packaging(**fields)


def test_interview_card_is_a_hot_update_template_not_a_builtin():
    spec, _info = template_factory.verify_folder(CARD)
    assert spec.id == 'interview_card'
    assert spec.base.picture_layout == 'fit'
    layout = spec.effective_caption_layout()
    assert layout.burn_cover_title and layout.keep_punctuation
    assert not (ROOT / 'backend' / 'assets' / 'templates' / 'interview_card').exists()


def test_page_hardcodes_no_reference_content():
    page = ''.join((CARD / name).read_text(encoding='utf-8') for name in ('index.html', 'template.js', 'style.css'))
    for text in REFERENCE_ONLY:
        assert text not in page, text
    # The translation disclosure is conditional, not static HTML.
    assert '辅助翻译' not in (CARD / 'index.html').read_text(encoding='utf-8')


def test_installed_card_keeps_title_and_clause_punctuation(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    assert template_cloner.main(['install-local', str(CARD)]) == 0
    assert registry.is_html_template('interview_card')

    pkg = _packaging('interview_card')
    turns = [(0.0, 3.0, '>> When you did that presentation that had over four million views on your dev process,')]
    painted = paint_fill(build_fill(pkg, 3.0, template='interview_card', transcript=turns), pkg, 'interview_card')
    assert painted['title_lines'] == ['土豆姐：', 'agent怎么自己合PR']
    pieces = [piece['s'] for piece in painted['moments'][0]['zh']]
    assert pieces == ['我记得你讲过开发流程，', '那次分享好像有超过四百万播放。']
    assert painted['moments'][0]['speaker'] == 'Garry Tan'
    # A host identified by role is not counted as a second guest.
    assert painted['guest'] == {'name': 'Lauren Tan', 'role': 'Grok Bot 团队'}
    assert painted['hosts'] == ['Garry Tan']
    assert painted['translated'] is True


def test_fill_follows_the_input_language_and_content(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    assert template_cloner.main(['install-local', str(CARD)]) == 0
    pkg = _packaging(
        'interview_card', source_language='zh', issue='',
        title_lines=['做产品最难的，', '是学会说不'],
        speakers=[{'name': '张一鸣', 'role': '字节跳动创始人', 'at': 0.0}],
        cues=[{'start': 0.0, 'end': 3.0, 'text': '我们砍掉了一半的项目，团队反而跑得更快。', 'original': ''}],
    )
    painted = paint_fill(build_fill(pkg, 3.0, template='interview_card'), pkg, 'interview_card')
    assert painted['translated'] is False
    assert painted['title_lines'] == ['做产品最难的，', '是学会说不']
    assert painted['guest'] == {'name': '张一鸣', 'role': '字节跳动创始人'}
    assert painted['issue'] == '张一鸣 访谈'


def test_builtin_templates_still_strip_title_and_punctuation():
    pkg = _packaging('editorial')
    painted = paint_fill(build_fill(pkg, 3.0, template='editorial'), pkg, 'editorial')
    assert painted['title_lines'] == []
    joined = ''.join(piece['s'] for moment in painted['moments'] for piece in moment['zh'])
    assert '，' not in joined and '。' not in joined


def test_english_audience_issue_fallback_and_role_host_exclusion():
    pkg = _packaging(
        'editorial',
        audience_language='en',
        source_language='en',
        issue='',
        speakers=[
            {'name': 'Garry Tan', 'role': 'Host', 'at': 0.0},
            {'name': 'Sam Altman', 'role': 'CEO, OpenAI', 'at': 0.0},
        ],
    )
    filled = build_fill(pkg, 3.0, template='editorial')
    assert filled['issue'] == 'Sam Altman · Interview'
    assert '访谈' not in filled['issue']
    assert filled['guest'] == {'name': 'Sam Altman', 'role': 'CEO, OpenAI'}
    assert filled['hosts'] == ['Garry Tan']


def test_overlay_cache_invalidates_on_template_update_and_telemetry_records_dynamic_id(tmp_path, monkeypatch):
    from backend.services.studio import packaging_html, template_telemetry

    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    assert template_cloner.main(['install-local', str(CARD)]) == 0

    fill = {'moments': [], 'T': 2.0}
    first = packaging_html.overlay_cache_path('p-cache', 'interview_card', fill, frames=60)
    css = registry.resolve_dir('interview_card') / 'style.css'
    css.write_text(css.read_text(encoding='utf-8') + '\n/* v2 */\n', encoding='utf-8')
    second = packaging_html.overlay_cache_path('p-cache', 'interview_card', fill, frames=60)
    assert first != second

    ev = template_telemetry.render_event({'template': 'interview_card', 'requested_template': 'interview_card', 'outcome': 'completed'})
    assert ev['template'] == 'interview_card'
    assert ev['requested_template'] == 'interview_card'
    dropped = template_telemetry.render_event({'template': 'unknown_free_text', 'outcome': 'completed'})
    assert 'template' not in dropped
