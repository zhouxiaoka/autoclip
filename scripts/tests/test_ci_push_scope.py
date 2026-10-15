"""CI push scope must not grow with individual draft review branches."""
from pathlib import Path
import unittest


class CIPushScopeTest(unittest.TestCase):
    def test_push_scope_matches_pre_u3_workflow(self):
        source = (Path(__file__).resolve().parents[2] / '.github/workflows/ci.yml').read_text()
        push = source.split('  push:\n', 1)[1].split('\npermissions:', 1)[0]
        branches = [line.strip()[2:] for line in push.splitlines() if line.strip().startswith('- ')]
        self.assertEqual(branches, ['main', 'master', 'cursor/normalize-provider-url-aa38',
            'cursor/provider-presets-json-42d9'])
