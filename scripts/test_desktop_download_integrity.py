"""Offline download-boundary checks; never download or execute a runtime."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'scripts/lib/desktop_build_common.sh'


class DownloadIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.good = self.root / 'good'
        self.good.write_bytes(b'verified test archive')
        self.bad = self.root / 'bad'
        self.bad.write_bytes(b'corrupt test archive!')
        self.digest = hashlib.sha256(self.good.read_bytes()).hexdigest()
        self.dest = self.root / 'cache.tar.gz'
        self.env = {**os.environ, 'COMMON': str(COMMON), 'DEST': str(self.dest),
                    'GOOD': str(self.good), 'BAD': str(self.bad),
                    'DIGEST': self.digest, 'LOG': str(self.root / 'calls')}
        self.env.pop('PBS_SHA256', None)
        self.env.pop('TAURI_SIGNING_PRIVATE_KEY', None)
        self.env.pop('TAURI_SIGNING_PRIVATE_KEY_PASSWORD', None)

    def shell(self, command):
        # Fake only transport; real shell hashing/cache code remains under test.
        fake = '''
source "$COMMON"
curl() {
    local dest url
    while [ "$#" -gt 0 ]; do
        if [ "$1" = -o ]; then dest="$2"; shift; fi
        url="$1"; shift
    done
    echo called >> "$LOG"
    case "$url" in
        https://good) cp "$GOOD" "$dest" ;;
        https://bad) cp "$BAD" "$dest" ;;
        *) return 22 ;;
    esac
}
'''
        return subprocess.run(['bash', '-c', fake + command], env=self.env,
                              cwd=self.root, capture_output=True, text=True)

    def test_valid_archive(self):
        r = self.shell('download_with_mirrors "$DEST" 1 "$DIGEST" https://good')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.dest.read_bytes(), self.good.read_bytes())

    def test_wrong_digest_never_promoted(self):
        r = self.shell('download_with_mirrors "$DEST" 1 "$DIGEST" https://bad')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.dest.exists())
        self.assertEqual(list(self.root.glob('*.tmp.*')), [])

    def test_missing_or_malformed_digest_fails_before_transport(self):
        for digest in ('', 'not-a-hash'):
            self.env['DIGEST'] = digest
            r = self.shell('download_with_mirrors "$DEST" 1 "$DIGEST" https://good')
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(Path(self.env['LOG']).exists())

    def test_valid_cache_is_verified_without_network(self):
        self.dest.write_bytes(self.good.read_bytes())
        r = self.shell('download_with_mirrors "$DEST" 1 "$DIGEST" https://unavailable')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(Path(self.env['LOG']).exists())

    def test_corrupt_cache_cannot_bypass_check(self):
        self.dest.write_bytes(self.bad.read_bytes())
        r = self.shell('download_with_mirrors "$DEST" 1 "$DIGEST" https://unavailable')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.dest.exists())

    def test_bad_mirror_then_good_source(self):
        r = self.shell('download_with_mirrors "$DEST" 1 "$DIGEST" https://bad https://good')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.dest.read_bytes(), self.good.read_bytes())

    def test_custom_pbs_requires_trusted_pin(self):
        r = self.shell('PBS_VERSION=custom; PBS_TRIPLE=custom; pbs_expected_sha256')
        self.assertNotEqual(r.returncode, 0)
        self.env['PBS_SHA256'] = self.digest
        r = self.shell('PBS_VERSION=custom; PBS_TRIPLE=custom; pbs_expected_sha256')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), self.digest)

    def test_both_platform_pins_available(self):
        for platform in ('aarch64-apple-darwin', 'x86_64-pc-windows-msvc'):
            r = self.shell(f'PBS_VERSION=20260510; PBS_PYTHON_VERSION=3.13.13; PBS_TRIPLE={platform}; pbs_expected_sha256')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertRegex(r.stdout.strip(), r'^[0-9a-f]{64}$')

    def test_signing_secrets_rejected_before_runtime_preparation(self):
        self.env['TAURI_SIGNING_PRIVATE_KEY'] = 'test-only-not-a-real-key'
        r = self.shell('PBS_TRIPLE=aarch64-apple-darwin; PORTABLE_PY_REL=bin/python3; prepare_portable_python')
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(Path(self.env['LOG']).exists())
        self.assertFalse((self.root / 'src-tauri').exists())

    def test_unsigned_build_environment_allowed(self):
        self.assertEqual(self.shell('require_unsigned_build_environment').returncode, 0)


if __name__ == '__main__':
    unittest.main()
