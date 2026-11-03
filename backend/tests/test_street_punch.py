"""Street footage takes the template's hard 1.00 <-> 1.22 punch-ins, as the preview does."""
import subprocess

import pytest

from backend.services.studio.models import Draft, Packaging, Scene
from backend.services.studio.packaging_render import street_picture, street_punches


def _draft(scenes, starts):
    cues = [{'start': start, 'end': start + 0.9, 'text': f'第{index}句话', 'original': f'line {index}'} for index, start in enumerate(starts)]
    packaging = Packaging(version=2, template='street', audience_language='zh', title_lines=['标题'], cues=cues)
    return Draft(id='d', title='t', scenes=scenes, layout='crop', crop_x=0.5, packaging=packaging)


def test_every_other_sentence_punches_in_and_the_first_second_starts_tight():
    draft = _draft([Scene(id='a', start=10, end=14)], [10.2, 11.5, 12.5, 13.2])
    scale, spans = street_punches(draft, 0)
    assert scale == pytest.approx(1.22)
    # Intro holds the tight framing to 1.0 s; sentence 1 is punched until sentence 2 at 1.5 s.
    assert spans == [(0.0, 1.5), (2.5, 3.2)]


def test_punches_follow_the_output_clock_across_a_cut():
    # The second scene starts 3 s into the output. Its sentence starts are counted on that clock.
    draft = _draft([Scene(id='a', start=10, end=13), Scene(id='b', start=40, end=44)], [10.5, 11.5, 40.5, 42.0])
    assert street_punches(draft, 0)[1] == [(0.0, 1.5)]
    # Starts on the output clock: 0.5 (on), 1.5 (off), 3.5 (on), 5.0 (off).
    assert street_punches(draft, 1)[1] == [(0.5, 2.0)]


def test_without_an_index_the_window_is_unchanged():
    scene = Scene(id='a', start=0, end=4)
    draft = _draft([scene], [0.2, 1.5])
    graph, _label = street_picture(draft, scene, 1920, 1080)
    assert 'enable=' not in graph.split('[win]')[-1]
    graph, label = street_picture(draft, scene, 1920, 1080, index=0)
    assert "overlay=0:0:enable='between(t,0.000,1.499)'" in graph
    assert graph.endswith('[punched]pad=1080:1920:0:0:black,setsar=1[base]') and label == 'base'


def _square_width(frame: bytes, width: int, height: int) -> int:
    best = 0
    for y in range(0, height, 4):
        row = frame[y * width:(y + 1) * width]
        best = max(best, sum(1 for value in row if value > 128))
    return best


def test_rendered_window_is_122_percent_larger_on_punched_frames():
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    scene = Scene(id='a', start=0, end=4)
    draft = _draft([scene], [0.2, 1.5, 2.5])
    graph, label = street_picture(draft, scene, 1920, 1080, index=0)
    source = 'color=black:s=1920x1080:r=30:d=4,drawbox=x=860:y=440:w=200:h=200:color=white:t=fill'
    picks = [15, 60, 90]  # 0.5 s intro (tight), 2.0 s (wide), 3.0 s (third sentence, tight)
    select = '+'.join(f'eq(n,{n})' for n in picks)
    done = subprocess.run([
        get_ffmpeg_path(), '-v', 'error', '-f', 'lavfi', '-i', source,
        '-filter_complex', f"{graph};[{label}]select='{select}',format=gray[out]",
        '-map', '[out]', '-fps_mode', 'passthrough', '-f', 'rawvideo', '-',
    ], capture_output=True, check=True)
    size = 1080 * 1920
    frames = [done.stdout[i * size:(i + 1) * size] for i in range(len(picks))]
    tight, wide, again = (_square_width(frame, 1080, 1920) for frame in frames)
    assert wide == pytest.approx(200 * 1290 / 1080, abs=4)
    assert tight / wide == pytest.approx(1.22, abs=0.02)
    assert again / wide == pytest.approx(1.22, abs=0.02)
