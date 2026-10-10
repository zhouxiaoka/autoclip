"""Capture Studio render ffmpeg commands with pinned inputs.

The argv in ``fixtures/render_ffmpeg_c5a72281`` was recorded from c5a72281
(main after #314, before #315/#316/#317). ``concat_script`` is the one field
updated later: both render paths use ``concat_quote``, which does not wrap a
plain path in single quotes. Do not regenerate the argv from a later tree.
"""
from __future__ import annotations

import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path('/tmp/autoclip-render-golden')
FFMPEG = '/usr/bin/ffmpeg'
FFPROBE = '/usr/bin/ffprobe'
NICE = '/usr/bin/nice'
ENCODER = 'libx264'
BASELINE = 'c5a72281'

CASES = (
    ('portrait', False),
    ('portrait', True),
    ('landscape', False),
    ('landscape', True),
)

PROBE = {
    'streams': [
        {
            'index': 0,
            'codec_type': 'video',
            'codec_name': 'h264',
            'width': 1920,
            'height': 1080,
            'avg_frame_rate': '30/1',
            'r_frame_rate': '30/1',
            'time_base': '1/15360',
        },
        {
            'codec_type': 'audio',
            'index': 1,
            'sample_rate': '48000',
            'channels': 2,
        },
    ],
    'format': {'duration': '30.00'},
}


def case_name(aspect: str, outro: bool) -> str:
    return f'{aspect}-{"outro" if outro else "no-outro"}'


def canonical(document: dict) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


class _FixedTemp:
    """Yield one stable directory per render prefix. Other prefixes are refused."""

    def __init__(self, *args, **kwargs):
        prefix = kwargs.get('prefix')
        if prefix == 'ac-studio-render-':
            self.path = ROOT / 'studio'
        elif prefix == 'ac-outro-':
            self.path = ROOT / 'outro'
        else:
            raise AssertionError(f'unexpected temporary directory prefix: {prefix!r}')

    def __enter__(self):
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(parents=True)
        return str(self.path)

    def __exit__(self, *_exc):
        shutil.rmtree(self.path, ignore_errors=True)
        return False


def _fixed_temp(*args, **kwargs):
    # Match tempfile.TemporaryDirectory(suffix, prefix, dir, ...) positional form.
    if args and 'prefix' not in kwargs:
        # signature: (suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False)
        names = ('suffix', 'prefix', 'dir', 'ignore_cleanup_errors')
        for name, value in zip(names, args):
            kwargs.setdefault(name, value)
        args = ()
    return _FixedTemp(*args, **kwargs)


def _is_ffprobe(argv: list[str]) -> bool:
    return Path(argv[0]).name.startswith('ffprobe')


def _is_audio(argv: list[str]) -> bool:
    tokens = set(argv)
    if tokens & {'-c:a', '-an', '-af', '0:a:0', '0:a:0?'}:
        return True
    return any('anullsrc' in token or '[0:a' in token for token in argv)


def _role(argv: list[str]) -> str:
    output = argv[-1]
    if output.endswith('.mkv'):
        return 'shot'
    if output.endswith('.branding.part.mp4'):
        return 'outro'
    joined = ' '.join(argv)
    if output.endswith('.part.mp4') and 'scale=' in joined and '-c:v' in argv:
        return 'outro'
    if '-f' in argv and argv[argv.index('-f') + 1] == 'concat':
        return 'concat'
    return 'other'


def _input_after(argv: list[str], flag: str) -> str | None:
    if flag not in argv:
        return None
    index = argv.index(flag)
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def capture(aspect: str, outro: bool) -> tuple[dict, dict]:
    """Run one classic render and return ``(command document, render result)``."""
    if ROOT.exists():
        shutil.rmtree(ROOT)
    project = ROOT / 'project'
    project.mkdir(parents=True)
    assets = ROOT / 'outro-assets'
    assets.mkdir()
    (assets / 'outro-vertical.mp4').write_bytes(b'x' * 64)
    (assets / 'outro-horizontal.mp4').write_bytes(b'y' * 64)
    cache = ROOT / 'outro-cache'
    cache.mkdir()
    video = ROOT / 'input.mp4'

    recorded: list[list[str]] = []
    scripts: dict[str, str] = {}

    def remember(argv: list[str]) -> None:
        if '-y' in argv:
            dest = Path(argv[argv.index('-y') + 1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b'\x00')
        role = _role(argv)
        if role == 'other':
            raise AssertionError('unclassified ffmpeg command: ' + json.dumps(argv))
        recorded.append(argv)
        if '-f' in argv and argv[argv.index('-f') + 1] == 'concat':
            listing = _input_after(argv, '-i')
            if listing and Path(listing).is_file():
                scripts[role] = Path(listing).read_text(encoding='utf-8')

    def fake_run(cmd, **kwargs):
        argv = [str(part) for part in cmd]
        text = kwargs.get('text') or kwargs.get('universal_newlines')
        if _is_ffprobe(argv):
            body = json.dumps(PROBE)
            stdout = body if text else body.encode()
            return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr='' if text else b'')
        remember(argv)
        stdout = '' if text else b''
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr='' if text else b'')

    def fake_check_output(cmd, **kwargs):
        argv = [str(part) for part in cmd]
        if not _is_ffprobe(argv):
            raise AssertionError('unexpected check_output: ' + json.dumps(argv))
        body = json.dumps(PROBE)
        text = kwargs.get('text') or kwargs.get('universal_newlines')
        return body if text else body.encode()

    def which(name, *_args, **_kwargs):
        if name == 'nice':
            return NICE
        return None

    from backend.services.studio.models import Draft, Scene
    from backend.services.studio.render import render_draft

    draft = Draft(
        id='d1',
        title='Golden',
        scenes=[
            Scene(id='s1', start=0.0, end=1.0),
            Scene(id='s2', start=2.0, end=3.5),
        ],
        subtitles=False,
        original_audio=True,
        aspect=aspect,
        layout='fit',
        hook='',
    )
    kwargs = {'brand_outro': outro}
    if 'features' in inspect.signature(render_draft).parameters:
        kwargs['features'] = {'pkg_templates_v1': False}

    with patch('tempfile.TemporaryDirectory', _fixed_temp), \
            patch('subprocess.run', fake_run), \
            patch('subprocess.check_output', fake_check_output), \
            patch('backend.services.render_limits.THREADS', '2'), \
            patch('backend.services.render_limits.sys.platform', 'linux'), \
            patch('backend.services.render_limits.shutil.which', which), \
            patch('backend.services.video_encoder.encoder', lambda: ENCODER), \
            patch('backend.services.studio.render.get_ffmpeg_path', lambda: FFMPEG), \
            patch('backend.services.studio.render.directory', lambda _project: project), \
            patch('backend.services.studio.audio.get_ffprobe_path', lambda: FFPROBE), \
            patch('backend.services.publish_export.get_ffprobe_path', lambda: FFPROBE), \
            patch('backend.services.output_branding.get_ffmpeg_path', lambda: FFMPEG), \
            patch('backend.services.output_branding.get_ffprobe_path', lambda: FFPROBE), \
            patch('backend.services.output_branding.OUTRO_DIR', assets), \
            patch('backend.services.output_branding._cache_dir', lambda: cache):
        result = render_draft('golden', video, draft, 'job', lambda _percent: None, **kwargs)

    shots = [argv for argv in recorded if _role(argv) == 'shot']
    concat = [argv for argv in recorded if _role(argv) == 'concat']
    outro_cmds = [argv for argv in recorded if _role(argv) == 'outro']
    audio = [argv for argv in recorded if _is_audio(argv)]
    document = {
        'aspect': aspect,
        'audio': audio,
        'brand_outro': outro,
        'concat': concat,
        'concat_script': scripts.get('concat', ''),
        'encoder': ENCODER,
        'outro': outro_cmds,
        'outro_script': scripts.get('outro', ''),
        'shots': shots,
    }
    return document, result


def command_diff(expected: bytes, actual: bytes) -> str:
    """Explain a golden mismatch without suggesting the fixture be rewritten."""
    import difflib

    old = json.loads(expected.decode('utf-8'))
    new = json.loads(actual.decode('utf-8'))
    lines = [
        f'Render ffmpeg commands differ from {BASELINE} with pkg_templates_v1 off.',
        'The fixture was recorded from that commit and was not updated.',
    ]
    for key in ('shots', 'concat', 'audio', 'outro'):
        left = old.get(key) or []
        right = new.get(key) or []
        if left == right:
            continue
        lines.append(f'[{key}] {len(left)} command(s) recorded, {len(right)} generated')
        for index, (before, after) in enumerate(zip(left, right)):
            if before == after:
                continue
            lines.append(f'[{key} #{index}] first differing argument:')
            limit = max(len(before), len(after))
            for arg_index in range(limit):
                old_arg = before[arg_index] if arg_index < len(before) else '<missing>'
                new_arg = after[arg_index] if arg_index < len(after) else '<missing>'
                if old_arg != new_arg:
                    lines.append(f'  argv[{arg_index}]')
                    lines.append(f'    c5a72281: {old_arg}')
                    lines.append(f'    current:  {new_arg}')
                    break
            if len(before) != len(after):
                lines.append(f'  argv length {len(before)} -> {len(after)}')
        if len(left) != len(right):
            longer = right if len(right) > len(left) else left
            side = 'current' if len(right) > len(left) else BASELINE
            for extra in longer[min(len(left), len(right)):]:
                lines.append(f'  extra {side} command ends with: {extra[-1]}')
    for key in ('concat_script', 'outro_script'):
        if old.get(key, '') == new.get(key, ''):
            continue
        lines.append(f'[{key}]')
        diff = difflib.unified_diff(
            (old.get(key) or '').splitlines(),
            (new.get(key) or '').splitlines(),
            fromfile=f'{BASELINE}/{key}',
            tofile=f'current/{key}',
            lineterm='',
        )
        lines.extend(list(diff)[:80])
    return '\n'.join(lines)


def main() -> None:
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    for aspect, outro in CASES:
        name = case_name(aspect, outro)
        document, result = capture(aspect, outro)
        payload = canonical(document)
        (destination / f'{name}.json').write_bytes(payload)
        print(f'{name} bytes={len(payload)} outro_applied={result.get("outro_applied")} width={result.get("width")} height={result.get("height")}')


if __name__ == '__main__':
    main()
