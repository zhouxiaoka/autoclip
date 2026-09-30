"""Keep local video encoding from saturating the user's machine.

Automatic output can queue many renders; each ffmpeg would otherwise use every core for
decoding and filter graphs. Studio renders run one at a time (see `jobs.render_executor`),
with bounded threads, at low priority.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

THREADS = str(max(2, (os.cpu_count() or 4) // 4))


def input_args() -> list[str]:
    """Global filter-thread caps plus the decoder cap; place right before the first `-i`."""
    return ['-filter_complex_threads', THREADS, '-filter_threads', THREADS, '-threads', THREADS]


def output_args() -> list[str]:
    """Encoder thread cap; place before the output path."""
    return ['-threads', THREADS]


def low_priority(cmd: list[str]) -> tuple[list[str], dict]:
    """Return (command, subprocess kwargs) that run ffmpeg at reduced CPU priority.

    POSIX wraps the command with `nice`; `preexec_fn` is avoided because it is unsafe in
    threaded processes. Windows uses the below-normal priority class.
    """
    if sys.platform == 'win32':
        return cmd, {'creationflags': getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)}
    nice = shutil.which('nice')
    return ([nice, '-n', '10', *cmd] if nice else cmd), {}
