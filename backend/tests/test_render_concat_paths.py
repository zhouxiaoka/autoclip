"""Real ffmpeg concat through classic and HTML-overlay renders.

The part paths contain a space, an apostrophe and CJK. Both listings go through
``concat_quote``. The legacy ``file '{path}'`` form fails on the apostrophe.
"""
import subprocess
import tempfile
from pathlib import Path

from backend.services.studio.packaging_html import concat_quote


def test_concat_quote_drops_plain_quotes_and_escapes_space_and_apostrophe():
    assert concat_quote('/tmp/autoclip-render-golden/studio/0.mkv') == '/tmp/autoclip-render-golden/studio/0.mkv'
    assert concat_quote('/tmp/my clip/0.mkv') == r'/tmp/my\ clip/0.mkv'
    assert concat_quote("/tmp/it's/0.mkv") == r"/tmp/it\'s/0.mkv"


def _ffmpeg(*args):
    subprocess.run(['ffmpeg', '-v', 'error', *args], check=True, capture_output=True)


def test_classic_and_overlay_concat_paths_with_space_cjk_and_apostrophe(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_VIDEO_ENCODER', 'libx264')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    nasty = tmp_path / "a clip it's 中文"
    nasty.mkdir()
    from backend.services.studio import packaging_html as html
    from backend.services.studio import store
    from backend.services.studio.models import Draft, Scene
    from backend.services.studio.render import render_draft

    store.directory('p1').mkdir(parents=True)
    source = nasty / 'input.mp4'
    overlay = nasty / 'overlay.mp4'
    _ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=64x64:r=30:d=1', '-f', 'lavfi', '-i', 'sine=f=440:d=1', '-shortest', '-y', str(source))
    _ffmpeg('-f', 'lavfi', '-i', 'color=c=white@0.3:s=64x64:d=1,format=rgba', '-y', str(overlay))
    real_temp = tempfile.TemporaryDirectory

    def rooted(*args, **kwargs):
        kwargs['dir'] = str(nasty)
        return real_temp(*args, **kwargs)

    monkeypatch.setattr(tempfile, 'TemporaryDirectory', rooted)
    listings = []
    real_write = Path.write_text

    def spy_write(self, data, *args, **kwargs):
        if self.name == 'parts.txt' and isinstance(data, str):
            listings.append(data)
        return real_write(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', spy_write)
    monkeypatch.setattr(
        html,
        'prepare_overlay',
        lambda *args, **kwargs: html.OverlayJob(overlay, 'editorial', False, 'none', 'none', 'completed', requested_template='editorial', duration_ms=1),
    )
    draft = Draft(
        id='d1',
        title='Nasty path',
        scenes=[Scene(id='s1', start=0.0, end=0.3), Scene(id='s2', start=0.3, end=0.6)],
        subtitles=False,
        original_audio=True,
        aspect='original',
        layout='fit',
    )
    classic = render_draft('p1', source, draft, 'classic', lambda _percent: None, features={'pkg_templates_v1': False})
    overlay_result = render_draft(
        'p1', source, draft, 'overlay', lambda _percent: None,
        html_template='editorial', features={'pkg_templates_v1': True},
    )
    assert len(listings) == 2
    for listing in listings:
        assert "\\'" in listing
        assert '\\ ' in listing
        assert '中文' in listing
        assert "file '" not in listing
    assert abs(classic['duration'] - 0.6) < 0.05
    assert abs(overlay_result['duration'] - 0.6) < 0.05
    assert 'template_render' not in classic
    assert overlay_result['template_render']['template'] == 'editorial'
    for job in ('classic', 'overlay'):
        output = store.directory('p1') / 'output' / 'studio' / f'{job}.mp4'
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(output)],
            check=True, capture_output=True, text=True,
        )
        assert abs(float(probe.stdout.strip()) - 0.6) < 0.05
