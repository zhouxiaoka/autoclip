"""Frontend telemetry suites that need the real backend runtime."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
"""frontend telemetry suites whose v4 terminals need a backend receipt run here, where the backend runtime
exists. Their receipts come from the real backend (backend/tests/receipt_bridge.py via
frontend/tests/helpers/real-backend.cjs) instead of the deleted helpers/backend-receipts.cjs copy of its rules."""

ROOT = Path(__file__).resolve().parents[2]
SUITES = sorted(p.name for p in (ROOT / 'frontend' / 'tests').glob('*.real-backend.cjs'))


def test_the_suites_exist():
    assert set(SUITES) >= {'analytics.real-backend.cjs', 'analytics-auto-generation.real-backend.cjs', 'auto-vision-fallback.real-backend.cjs',
                           'llm-telemetry.real-backend.cjs', 'studio-retry-telemetry.real-backend.cjs'}
    assert not (ROOT / 'frontend' / 'tests' / 'helpers' / 'backend-receipts.cjs').exists()


@pytest.mark.parametrize('suite', SUITES)
def test_frontend_suite_against_the_real_backend(suite):
    node = shutil.which('node')
    if not node or not (ROOT / 'frontend' / 'node_modules' / 'typescript').is_dir():
        if os.environ.get('CI'):
            pytest.fail('node + frontend deps are installed in CI; refusing to skip')
        pytest.skip('node + frontend deps required')
    done = subprocess.run([node, '--test', f'tests/{suite}'], cwd=ROOT / 'frontend', capture_output=True, text=True, timeout=900,
                          env={**os.environ, 'AUTOCLIP_TEST_PYTHON': sys.executable})
    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-2000:]
