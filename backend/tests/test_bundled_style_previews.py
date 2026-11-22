import subprocess

from backend.services.studio.templates.spec import STYLE_IDS
from scripts import build_template_previews as previews


def test_bundled_previews_cover_every_selectable_style_and_show_footage():
    assert set(previews.STYLES) == set(STYLE_IDS)
    assert previews.check() == 0


def test_caption_graphics_cannot_hide_missing_footage_partway_through_a_preview(tmp_path):
    clip = tmp_path / 'news.preview.mp4'
    subprocess.run([
        previews.ffmpeg(), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=216x384:rate=24',
        '-vf', "drawbox=w=iw:h=ih*0.8:t=fill:c=black:enable='between(t,1,2)'",
        '-t', '2.5', '-c:v', 'libx264', str(clip),
    ], check=True)
    assert not previews.shows_footage(clip)
