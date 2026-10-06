"""Real YuNet inference must not mix the frames from concurrent exports."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from backend.services.studio import framing


def test_concurrent_face_and_empty_frames_keep_their_own_results(tmp_path, monkeypatch):
    monkeypatch.setattr(framing, '_data_dir', lambda: tmp_path)
    face = cv2.resize(cv2.imread(str(framing.MODEL.parents[1] / 'example' / 'cover.jpg')), (480, 270))
    empty = np.zeros_like(face)
    paths = []
    for name, frame in [('face', face), ('empty', empty)]:
        path = tmp_path / (name + '.jpg')
        assert cv2.imwrite(str(path), frame)
        paths.append((path, path))
    expected = [framing._speaker_center(pair) for pair in paths]
    assert expected[0] is not None and expected[1] is None
    pairs = paths * 200
    with ThreadPoolExecutor(max_workers=8) as pool:
        actual = list(pool.map(framing._speaker_center, pairs))
    assert actual == expected * 200, 'shared detector mixed results from different videos'
