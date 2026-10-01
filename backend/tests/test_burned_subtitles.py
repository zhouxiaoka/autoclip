import subprocess

import pytest

from backend.services.studio import burned_subtitles as bs
from backend.services.studio import jobs


def _video(tmp_path, name, lines):
    """12 s clip; `lines` is one caption per second, or a single string shown throughout."""
    path = tmp_path / f'{name}.mp4'
    style = "font='Sans':fontsize=44:fontcolor=white:borderw=4:bordercolor=black:x=(w-text_w)/2:y=h-90"
    if isinstance(lines, str):
        draw = f"drawtext={style}:text='{lines}'"
    else:
        draw = ','.join(f"drawtext={style}:text='{text}':enable='between(t,{i},{i + 1})'" for i, text in enumerate(lines))
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=0x6E7F8F:s=640x360:d=12:r=10',
        '-vf', draw, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(path),
    ], check=True)
    return path


CAPTIONS = [
    'Where does creativity come from', 'I read in libraries myself', 'Super Mario changed my life',
    'Testing is a crucial stage', 'Players should feel the love', 'Hard sci-fi or a Western',
    'New genres over old ones', 'Sound on headphones and speakers', 'Pacing needs rhythm fixes',
    'Death Stranding came first', 'Contact me to help', 'The future of games',
]


def test_changing_outlined_captions_count_as_burned_subtitles(tmp_path):
    video = _video(tmp_path, 'captions', CAPTIONS)
    assert bs.has_burned_subtitles(video, 12.0) is True


def test_static_logo_text_is_not_mistaken_for_subtitles(tmp_path):
    video = _video(tmp_path, 'logo', 'CHANNEL LOGO WATERMARK')
    assert bs.has_burned_subtitles(video, 12.0) is False


def test_plain_frames_have_no_subtitles():
    assert bs.decide([set() for _ in range(12)]) is False


@pytest.mark.parametrize('strategy_id, layout', [('tiktok', 'blur'), ('douyin', 'blur'), ('youtube_long', 'fit')])
def test_burned_subtitles_disable_our_track_and_keep_full_vertical_frame(strategy_id, layout):
    base = jobs.Draft(id='d', title='T', scenes=[jobs.Scene(id='s', label='S', start=0, end=5)], subtitles=True).model_dump()
    draft = jobs._apply_strategy(base, strategy_id, burned_subtitles=True)
    assert draft.subtitles is False and draft.layout == layout
    assert jobs._apply_strategy(base, 'tiktok').subtitles is True
    assert jobs._apply_strategy(base, 'tiktok').layout == 'crop'
