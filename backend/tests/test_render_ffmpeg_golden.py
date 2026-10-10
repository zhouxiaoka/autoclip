"""pkg_templates_v1 off: Studio render ffmpeg commands match c5a72281 byte for byte.

Fixtures were recorded from that commit (main after #314, before #315/#316/#317).
Regenerate them only by running ``render_ffmpeg_golden.py`` against that tree.
"""
from pathlib import Path

import pytest

from backend.tests.render_ffmpeg_golden import CASES, canonical, capture, case_name, command_diff

FIXTURES = Path(__file__).parent / 'fixtures' / 'render_ffmpeg_c5a72281'


@pytest.mark.parametrize('aspect,outro', CASES, ids=[case_name(aspect, outro) for aspect, outro in CASES])
def test_flag_off_render_ffmpeg_matches_c5a72281(aspect, outro):
    document, result = capture(aspect, outro)
    size = (1080, 1920) if aspect == 'portrait' else (1920, 1080)
    assert (result['width'], result['height']) == size
    assert result['outro_applied'] is outro
    assert 'template_render' not in result
    actual = canonical(document)
    expected = (FIXTURES / f'{case_name(aspect, outro)}.json').read_bytes()
    assert actual == expected, command_diff(expected, actual)
