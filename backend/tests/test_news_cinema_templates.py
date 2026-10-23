"""news and cinema are importable HTML templates and a render can start."""
import subprocess
import typing
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.services.studio.models import ImportOptions
from backend.services.studio.templates.spec import HTML_TEMPLATE_IDS


ROOT = Path(__file__).resolve().parents[2]


def _literal_values(annotation):
    values = set()
    for item in typing.get_args(annotation):
        nested = typing.get_args(item)
        if nested:
            values.update(value for value in nested if isinstance(value, str))
        elif isinstance(item, str):
            values.add(item)
    return values


def test_import_accepts_news_and_cinema_and_rejects_unknown_styles():
    from backend.api.v1.studio import import_visual
    from backend.services.studio.models import OutputVariant
    from backend.services.studio.template_choice import selected_template, style_for_request

    form = _literal_values(typing.get_type_hints(import_visual)['html_template'])
    assert {'editorial', 'street', 'news', 'cinema', 'classic'} <= form
    assert 'magazine' not in form
    for name in ('news', 'cinema'):
        assert ImportOptions(html_template=name).html_template == name
        assert style_for_request(name, {'pkg_templates_v1': True}) == {'template': name, 'requested_template': name}
        assert selected_template({'html_template': name, 'features': {'pkg_templates_v1': True}}) == name
    with pytest.raises(ValidationError):
        ImportOptions(html_template='magazine')
    with pytest.raises(ValueError):
        style_for_request('magazine')
    variant = _literal_values(OutputVariant.model_fields['html_template'].annotation)
    assert {'editorial', 'street', 'news', 'cinema'} <= variant


def test_desktop_bundle_ships_the_four_template_folders():
    script = (ROOT / 'scripts/lib/desktop_build_common.sh').read_text(encoding='utf-8')
    ignore = script[script.index('IGNORED_DIRS'):script.index('shutil.copytree')]
    assert 'templates' not in ignore and '"assets"' not in ignore
    for name in HTML_TEMPLATE_IDS:
        folder = ROOT / 'backend/assets/templates' / name
        for item in ('index.html', 'template.js', 'style.css', 'template.yaml'):
            assert (folder / item).is_file(), item
        page = (folder / 'template.js').read_text(encoding='utf-8')
        assert 'title_lines' not in page or name in {'editorial', 'street'}
    import tomllib
    package_data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['tool']['setuptools']['package-data']['backend']
    assert 'assets/templates/*/*' in package_data


def test_news_and_cinema_do_not_burn_cover_titles():
    from backend.services.studio.models import Packaging
    from backend.services.studio.overlay_fill import build_fill, paint_fill
    from backend.tests.test_template_preview_look import _render

    for template, title in (('news', '新闻标题不进成片'), ('cinema', '电影标题不进成片')):
        packaging = Packaging(
            version=2, template=template, audience_language='zh', title_lines=[title],
            cues=[{'start': 0.2, 'end': 3.0, 'text': '这一句是字幕', 'original': 'this line is a caption'}],
        )
        filled = build_fill(packaging, 4, template=template)
        assert filled['title_lines'] == [title]
        painted = paint_fill(filled, packaging, template)
        assert painted['title_lines'] == [] and painted['hook']['text'] == ''
        frame = _render(template, painted, times=['1.0'])['1.0']
        blob = __import__('json').dumps(frame, ensure_ascii=False)
        assert title not in blob
        assert '这一句是字幕' in frame['zh']['text'] or '这一句是字幕' in frame['zh']['html']
        assert 'caption' in (frame['en']['html'] or frame['en']['text'])
        assert frame['hook']['html'] == ''


def test_news_and_cinema_overlay_can_start(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    from backend.services.studio import packaging_html as html
    from backend.services.studio import store
    from backend.services.studio.models import Draft, Scene
    from backend.services.studio.render import render_draft

    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    png = tmp_path / 'frame.png'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', 'color=c=red@0.4:s=16x16:d=0.04,format=rgba',
        '-frames:v', '1', '-update', '1', str(png),
    ], check=True, capture_output=True)
    blob = png.read_bytes()

    def capture(count, _fps):
        return [{'index': 0, 'count': count, 'png': blob}]

    for name in ('news', 'cinema'):
        job = html.prepare_overlay(f'p-{name}', name, None, 0.2, features={'pkg_templates_v1': True}, capture=capture)
        assert job.path and job.path.is_file() and job.downgraded is False and job.template == name

    root = store.directory('p-render')
    root.mkdir(parents=True)
    (root / 'raw').mkdir()
    source = root / 'raw' / 'input.mp4'
    overlay = tmp_path / 'overlay.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=30:d=1', '-f', 'lavfi', '-i', 'sine=f=440:d=1', '-shortest', '-y', str(source)], check=True, capture_output=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=white@0.3:s=64x64:d=1,format=rgba', '-y', str(overlay)], check=True, capture_output=True)

    def fake_overlay(*args, **_kwargs):
        template = args[1]
        return html.OverlayJob(overlay, template, False, 'none', 'none', 'completed', requested_template=template, duration_ms=4)

    monkeypatch.setattr(html, 'prepare_overlay', fake_overlay)
    draft = Draft(id='d1', title='Short', scenes=[Scene(id='s1', start=0.0, end=0.4)], subtitles=False, original_audio=False, aspect='original', layout='fit')
    for name in ('news', 'cinema'):
        result = render_draft('p-render', source, draft, f'job-{name}', lambda _p: None, html_template=name, features={'pkg_templates_v1': True})
        assert (root / 'output' / 'studio' / f'job-{name}.mp4').is_file()
        assert result['template'] == name and result['template_render']['downgraded'] is False
