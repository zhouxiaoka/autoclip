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


# windows-asyncio.yml runs this file on a Windows runner. Pull in the pip isolation checks so they
# also run on Windows (event loop stays responsive while pip streams; no shared stdin/console/group).
from backend.tests.test_pip_install_isolation import (  # noqa: E402,F401
    test_event_loop_stays_responsive_while_pip_streams,
    test_framing_install_runs_off_the_event_loop,
    test_pip_child_reads_eof_from_stdin,
    test_pip_does_not_share_stdin_console_or_process_group,
)
from backend.tests.test_pip_child_guard import (  # noqa: E402,F401
    test_cancel_kills_pip_and_reports_cancel,
    test_cancel_only_hits_its_owner_and_does_not_leak_into_next_run,
    test_pip_dies_when_backend_is_killed_hard,
    test_shutdown_kills_every_live_pip,
)
from backend.tests.test_pip_failure_classes import (  # noqa: E402,F401
    test_genuine_no_wheel,
    test_network_errors_are_network_not_no_wheel,
    test_stream_classifies_real_pip_output,
)
