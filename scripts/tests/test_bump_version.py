import contextlib
import io
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bump_version as bump


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name in ('TAURI_CONF', 'CARGO_TOML', 'PYPROJECT', 'DESKTOP_CONFIG', 'PACKAGE_INIT'):
            source = getattr(bump, name)
            target = Path(self.temp.name) / source.name
            target.write_text(source.read_text())
            self.enterContext(patch.object(bump, name, target))
        self.lock = Path(self.temp.name) / 'Cargo.lock'
        self.original = (bump.ROOT / 'src-tauri' / 'Cargo.lock').read_text()
        self.lock.write_text(self.original)
        self.enterContext(patch.object(bump, 'CARGO_LOCK', self.lock, create=True))

    def test_stale_lockfile_blocks_version_contract(self):
        self.lock.write_text(re.sub(r'(name = "autoclip-desktop"\nversion = ")[^"]+', r'\g<1>0.0.1', self.original))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bump.main(['--check']), 1)

    def test_bump_preserves_locked_dependencies(self):
        bump.set_version('9.8.7')
        expected = re.sub(r'(name = "autoclip-desktop"\nversion = ")[^"]+', r'\g<1>9.8.7', self.original)
        self.assertEqual(self.lock.read_text(), expected)
        self.assertEqual(set(bump.current_versions().values()), {'9.8.7'})


if __name__ == '__main__':
    unittest.main()
