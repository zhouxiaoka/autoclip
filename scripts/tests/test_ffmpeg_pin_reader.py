"""/: the bash and pwsh pinned-ffmpeg readers apply one rule.
The same samples go through scripts/lib/ffmpeg_pin.sh (read_ffmpeg_pin) and
scripts/lib/ffmpeg_pin.ps1. Bad samples must be rejected by BOTH; good samples
must be accepted by both with identical values. pwsh is preinstalled on GitHub's
ubuntu runners; without it the pwsh half fails under CI and is skipped locally."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SH_READER = ROOT / 'scripts' / 'lib' / 'ffmpeg_pin.sh'
PS_READER = ROOT / 'scripts' / 'lib' / 'ffmpeg_pin.ps1'
KEYS = ('FFMPEG_VERSION', 'FFMPEG_URL', 'FFMPEG_SHA256')
# The key set each checked-in pin file is read with (same as its build script).
MAC_KEYS = KEYS + ('FFPROBE_URL', 'FFPROBE_SHA256')
PIN_KEYS = {
    'ffmpeg-win64.env': KEYS,
    'ffmpeg-macos-arm64.env': MAC_KEYS,
    'ffmpeg-macos-x64.env': MAC_KEYS,
}
SHA = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
URL = 'https://example.invalid/ffmpeg-9.0.2.zip'
GOOD = f'# comment\nFFMPEG_VERSION=9.0.2\nFFMPEG_URL={URL}\nFFMPEG_SHA256={SHA}\n'
EXPECTED = {'FFMPEG_VERSION': '9.0.2', 'FFMPEG_URL': URL, 'FFMPEG_SHA256': SHA}

BAD = {
    'duplicate_line': GOOD + 'FFMPEG_VERSION=9.0.3\n',
    'trailing_space': GOOD.replace('FFMPEG_VERSION=9.0.2\n', '') + 'FFMPEG_VERSION=9.0.2 \n',
    'trailing_space_duplicate': GOOD + 'FFMPEG_VERSION=9.0.3 \n',
    'lowercase_key': GOOD.replace('FFMPEG_URL=', 'ffmpeg_url='),
    'lowercase_extra_key': GOOD + f'ffmpeg_url={URL}\n',
    'bom': '\ufeff' + GOOD,
    'bom_on_key_line': '\ufeff' + GOOD.replace('# comment\n', ''),
    'missing_key': GOOD.replace(f'FFMPEG_SHA256={SHA}\n', ''),
    'extra_unknown_key': GOOD + 'FFMPEG_MIRROR=https://example.invalid/x.zip\n',
    'empty_value': GOOD.replace('FFMPEG_VERSION=9.0.2', 'FFMPEG_VERSION='),
    'space_around_equals': GOOD.replace('FFMPEG_VERSION=9.0.2', 'FFMPEG_VERSION = 9.0.2'),
    'leading_space': GOOD.replace('FFMPEG_VERSION=', ' FFMPEG_VERSION='),
    'tab_in_value': GOOD.replace('FFMPEG_VERSION=9.0.2', 'FFMPEG_VERSION=9.0.2\t'),
    'non_ascii_value': GOOD.replace('FFMPEG_VERSION=9.0.2', 'FFMPEG_VERSION=9.0.2\u00a0'),
    'non_ascii_letter': GOOD.replace('FFMPEG_VERSION=9.0.2', 'FFMPEG_VERSION=9.0.2\u00e9'),
    'whitespace_only_line': GOOD + '   \n',
}
GOOD_SAMPLES = {
    'lf': GOOD,
    'crlf': GOOD.replace('\n', '\r\n'),
    'no_final_newline': GOOD.rstrip('\n'),
    'blank_lines_and_comments': '\n# a\n\n' + GOOD + '\n#b\n',
}


def run_bash(path, keys=KEYS):
    script = (
        'source "$1"; shift; f="$1"; shift; read_ffmpeg_pin "$f" "$@" || exit 1; '
        'for k in "$@"; do printf "%s=%s\\n" "$k" "${!k}"; done'
    )
    return subprocess.run(['bash', '-c', script, 'reader', str(SH_READER), str(path), *keys],
                          capture_output=True)


def run_pwsh(path, keys=KEYS):
    keys = ','.join(f"'{k}'" for k in keys)
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"$pin = & '{PS_READER}' -Path '{path}' -Keys {keys}; "
        "foreach ($e in $pin.GetEnumerator()) { [Console]::Out.Write(\"$($e.Key)=$($e.Value)`n\") }"
    )
    return subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', command],
                          capture_output=True)


def parse(stdout):
    return dict(line.split('=', 1) for line in stdout.decode().splitlines() if '=' in line)


class FfmpegPinReaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pwsh = shutil.which('pwsh')
        if not cls.pwsh and os.environ.get('CI'):
            raise AssertionError('pwsh is required in CI to check the pwsh reader')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def write(self, name, text):
        path = Path(self.tmp.name) / f'{name}.env'
        path.write_bytes(text.encode('utf-8'))
        return path

    def readers(self):
        yield 'bash', run_bash
        if self.pwsh:
            yield 'pwsh', run_pwsh

    def test_bad_samples_rejected_by_both_readers(self):
        for name, text in BAD.items():
            path = self.write(name, text)
            for shell, run in self.readers():
                with self.subTest(sample=name, shell=shell):
                    result = run(path)
                    if result.returncode == 0:
                        self.fail(f'{shell} accepted bad sample {name}: {parse(result.stdout)}')
                    if name.startswith('bom'):
                        # both readers reject a BOM explicitly instead of stripping it.
                        self.assertIn('BOM', result.stderr.decode(errors='replace'))

    def test_good_samples_accepted_with_identical_values(self):
        for name, text in GOOD_SAMPLES.items():
            path = self.write(name, text)
            for shell, run in self.readers():
                with self.subTest(sample=name, shell=shell):
                    result = run(path)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(parse(result.stdout), EXPECTED)

    def test_checked_in_pin_files_pass_both_readers(self):
        pins = sorted((ROOT / 'scripts').glob('ffmpeg-*.env'))
        self.assertEqual([p.name for p in pins], sorted(PIN_KEYS))
        for path in pins:
            for shell, run in self.readers():
                with self.subTest(pin=path.name, shell=shell):
                    result = run(path, PIN_KEYS[path.name])
                    self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_pin_files_only_accept_their_own_key_set(self):
        win = ROOT / 'scripts' / 'ffmpeg-win64.env'
        mac = ROOT / 'scripts' / 'ffmpeg-macos-arm64.env'
        for shell, run in self.readers():
            with self.subTest(case='mac file, windows keys', shell=shell):
                self.assertNotEqual(run(mac).returncode, 0)
            with self.subTest(case='windows file, mac keys', shell=shell):
                self.assertNotEqual(run(win, MAC_KEYS).returncode, 0)


if __name__ == '__main__':
    unittest.main()
