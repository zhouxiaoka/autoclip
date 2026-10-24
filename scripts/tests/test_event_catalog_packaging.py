"""Both backend packaging routes must copy the canonical tracking plan."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CatalogPackagingTests(unittest.TestCase):
    def verify_catalog(self, target):
        target = target.resolve()
        expected = (ROOT / 'docs/analytics/event_catalog.json').read_bytes()
        self.assertEqual((target / 'backend/core/event_catalog.json').read_bytes(), expected)
        # Isolated interpreter and cwd: no repo docs, no checkout imports.
        result = subprocess.run([sys.executable, '-I', '-c',
                        'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
                        'from backend.core.event_catalog import catalog_path, load_catalog; '
                        'assert catalog_path().is_relative_to(Path(sys.argv[1])); '
                        'assert load_catalog()["events"]', str(target)],
                       cwd=target, capture_output=True, text=True,
                       env=dict(os.environ, AUTOCLIP_EVENT_CATALOG=''))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wheel_build_py_copies_canonical_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'lib'
            result = subprocess.run([sys.executable, 'setup.py', 'build_py', '--build-lib', str(target)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.verify_catalog(target)

    @unittest.skipIf(os.name == 'nt', 'shared shell packaging exercised on POSIX')
    def test_desktop_shared_copy_includes_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            subprocess.run(['bash', '-c',
                            'source scripts/lib/desktop_build_common.sh\n'
                            'PORTABLE_PY="$1"\nBACKEND_DEST="$2/backend"\ncopy_backend_source',
                            'catalog-test', sys.executable, str(target)],
                           cwd=ROOT, check=True, capture_output=True)
            self.verify_catalog(target)
