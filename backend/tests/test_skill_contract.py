"""The autoclip skill tells an agent when to produce a publish kit."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / 'skills/autoclip/SKILL.md'
LEGACY = ROOT / 'skills/autoclip/references/legacy.md'


def _frontmatter(text: str) -> str:
    assert text.startswith('---\n')
    return text.split('---', 2)[1]


@pytest.mark.stdlib_only
def test_skill_triggers_on_publish_kits_and_keeps_three_flows():
    text = SKILL.read_text(encoding='utf-8')
    description = _frontmatter(text)
    assert 'name: autoclip' in description
    for word in ('发布包', '封面', '文案', '链接', '本地'):
        assert word in description
    assert 'references/legacy.md' in description
    for title in ('## 示例 1：链接出发布包', '## 示例 2：选剪辑风格', '## 示例 3：批量'):
        assert title in text
    for style in ('editorial', 'street', 'classic'):
        assert style in text
    assert '--template' in text and 'list_styles' in text
    assert '没有 list_styles 就不要传 template' in text
    assert '以返回结果里的风格为准' in text
    assert 'poll_after_sec' in text and 'unknown' in text
    assert 'sources' in text and '不要自造' in text
    assert 'clip_video' not in text and 'start_clip_job' not in text
    assert '1.5.0' not in text
    assert 'get_version' in text and 'autoclip --version' in text


@pytest.mark.stdlib_only
def test_legacy_reference_holds_the_old_slice_tools():
    text = LEGACY.read_text(encoding='utf-8')
    for name in ('clip_video', 'start_clip_job', 'get_job_status', 'export_clip', 'publish_clip'):
        assert name in text
    assert 'api_key' in text and 'AUTOCLIP_API_KEY' in text
    assert '不要传 `api_key`' in text
    assert '1.5.0' not in text
