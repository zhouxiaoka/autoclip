"""A template output changes crop on the cut frame itself, not one frame later.

dad_suit showed the old crop (the back of a head) on the first frame of six shots: the track
starts were cut times rounded up to 0.01 s, past the cut frame's own time.
"""
import shutil
import subprocess

import numpy as np
import pytest

from backend.services.studio.framing import detect_cuts, layout_filter, on_cut_frames
from backend.services.studio.models import CropPoint, Draft, Scene
from backend.services.studio.packaging_render import picture_only

FFMPEG = shutil.which('ffmpeg')
CUT_FRAME = 116  # 3.8667 s at 30 fps; detection rounds it to 3.87


def _two_shots(path):
    # Shot A: red | blue. Shot B: green | yellow. A crop at x=0 sees the left half, x=1 the right.
    a = f'color=red:s=320x360:r=30:d={CUT_FRAME / 30}[al];color=blue:s=320x360:r=30:d={CUT_FRAME / 30}[ar];[al][ar]hstack[a]'
    b = 'color=green:s=320x360:r=30:d=2[bl];color=yellow:s=320x360:r=30:d=2[br];[bl][br]hstack[b]'
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-filter_complex', f'{a};{b};[a][b]concat=n=2:v=1[v]', '-map', '[v]',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-g', '15', '-crf', '10', str(path)], check=True)


def _frames(path, graph, label, w, h):
    out = subprocess.run([FFMPEG, '-v', 'error', '-i', str(path), '-filter_complex', graph, '-map', f'[{label}]',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], check=True, capture_output=True).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(-1, h, w, 3)


def _colour(frame):
    r, g, b = frame[frame.shape[0] // 2, frame.shape[1] // 2].astype(int)
    if r > 180 and g > 180 and b < 100:
        return 'yellow'
    return {0: 'red', 1: 'green', 2: 'blue'}[int(np.argmax([r, g, b]))]


@pytest.mark.skipif(FFMPEG is None, reason='ffmpeg missing')
def test_the_cut_frame_takes_the_new_shots_crop(tmp_path):
    src = tmp_path / 'two_shots.mp4'
    _two_shots(src)
    cuts = detect_cuts(src, 0.0, 5.0)
    assert cuts == [3.87]  # the stored start lies 3 ms after the cut frame at 3.8667 s
    scene = Scene(id='s', start=0, end=5, crop_track=[CropPoint(start=0, crop_x=0.0), CropPoint(start=cuts[0], crop_x=1.0)])
    draft = Draft(id='d', title='t', scenes=[scene], layout='crop', crop_x=0.5)
    graph, label = picture_only(draft, scene, 180, 320)
    frames = _frames(src, graph, label, 180, 320)
    seen = [_colour(frames[i]) for i in (0, CUT_FRAME - 1, CUT_FRAME, CUT_FRAME + 1)]
    assert seen == ['red', 'red', 'yellow', 'yellow']
    # The stored track and the classic graph keep their exact values.
    assert scene.crop_track[1].start == 3.87
    assert 'lt(t,3.87)' in layout_filter(scene, 0.5, 180, 320)


def test_fit_spans_and_eases_move_with_their_cut():
    scene = Scene(id='s', start=0, end=9, crop_track=[
        CropPoint(start=0, crop_x=0.3), CropPoint(start=2.07, crop_x=0.5, mode='fit'),
        CropPoint(start=7.33, crop_x=0.4), CropPoint(start=8.0, crop_x=0.6, ease=0.45)])
    moved = on_cut_frames(scene)
    assert [p.start for p in moved.crop_track] == [0, 2.064, 7.324, 7.994]
    assert [(p.crop_x, p.mode, p.ease) for p in moved.crop_track] == [(p.crop_x, p.mode, p.ease) for p in scene.crop_track]
    graph = layout_filter(moved, 0.5, 180, 320)
    assert 'between(t,2.064,7.324)' in graph and 'lt(t,2.07)' not in graph
    assert on_cut_frames(Scene(id='x', start=0, end=2)) .crop_track is None
