"""QA capture prints closed fields and does not echo downloader text."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts' / 'qa' / 'acceptance_capture.py'
CHECK = ROOT / 'scripts' / 'check_telemetry_environment.py'


class CaptureTests(unittest.TestCase):
    def test_heartbeat_snapshot_keeps_ts_stage_and_pid_only(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            instance = 'a' * 32
            (directory / f'{instance}.hb').write_text(json.dumps({
                'ts': 12.5, 'stage': 'screening', 'uptime_s': 3, 'rss_mb': 10,
                'note': 'do-not-print',
            }), encoding='ascii')
            (directory / 'not-an-instance.hb').write_text('{}', encoding='ascii')
            result = subprocess.run(
                [sys.executable, str(SCRIPT), 'heartbeat', '--marker-dir', temp, '--pid', '10276'],
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['rows'], [{
                'instance': instance,
                'readable': True,
                'ts': 12.5,
                'stage': 'screening',
                'observed_pid': 10276,
            }])
            self.assertNotIn('do-not-print', result.stdout)

    def test_download_error_capture_does_not_echo_the_text(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'err.txt'
            source.write_text('ERROR: timed out https://secret.example/watch?v=abc', encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(SCRIPT), 'download-error',
                 '--exception-type', 'DownloadError', '--seconds', '131.5',
                 '--text-file', str(source)],
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('secret.example', result.stdout)
            self.assertNotIn('watch', result.stdout)
            self.assertEqual(json.loads(result.stdout), {
                'exception_type': 'DownloadError',
                'seconds': 131.5,
                'token': 'timeout',
                'code': 'connection',
            })

    def test_release_observation_cannot_pass_as_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            observed = Path(temp) / 'env.json'
            observed.write_text(json.dumps({
                'AUTOCLIP_BUILD_ENVIRONMENT': 'production',
                'AUTOCLIP_APP_VERSION': '1.5.9',
                'AUTOCLIP_MODE': 'desktop',
            }), encoding='utf-8')
            ok = subprocess.run(
                [sys.executable, str(CHECK), '--observed', str(observed), '--expect', 'production'],
                capture_output=True, text=True, check=False)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            blocked = subprocess.run(
                [sys.executable, str(CHECK), '--observed', str(observed), '--expect', 'validation'],
                capture_output=True, text=True, check=False)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn('production', blocked.stderr + blocked.stdout)
            printed = subprocess.run(
                [sys.executable, str(CHECK), '--print-validation-build'],
                capture_output=True, text=True, check=False)
            self.assertEqual(printed.returncode, 0, printed.stderr)
            flags = json.loads(printed.stdout)
            self.assertEqual(flags['frontend'], 'VITE_TELEMETRY_VALIDATION=true')
            self.assertIn('production', flags['not_the_release_launcher'])


if __name__ == '__main__':
    unittest.main()
