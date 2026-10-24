"""an unmarked test that reads the conftest Whisper stand-in directly fails, whatever the import
style (module alias, from-import) or directory (sub-packages); marked tests and product-code callers pass.
Runs a child pytest against the real backend/tests/conftest.py fixture."""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

CASES = {
    'test_alias.py': 'from backend.services import whisper_runtime as wr\ndef test_a():\n    assert wr.get_status()["status"] == "installed"\n',
    'test_from_import.py': 'def test_b():\n    from backend.services.whisper_runtime import get_status\n    assert get_status()["status"] == "installed"\n',
    'sub/test_nested.py': 'from backend.services import whisper_runtime\ndef test_c():\n    assert whisper_runtime.get_status()["status"] == "installed"\n',
    'test_string_marker.py': 'import pytest\nfrom backend.services import whisper_runtime\n@pytest.mark.skipif(False, reason="not own_whisper_status")\ndef test_d():\n    assert whisper_runtime.get_status()["status"] == "installed"\n',
    'test_model.py': 'from backend.services.studio import readiness\ndef test_e():\n    assert readiness._whisper_model("small")["ok"]\n',
}
OK = {
    'test_marked.py': 'import pytest\nfrom backend.services import whisper_runtime as wr\n@pytest.mark.own_whisper_status\ndef test_m(monkeypatch):\n    monkeypatch.setattr(wr, "get_status", lambda *a, **k: {"status": "missing"})\n    assert wr.get_status()["status"] == "missing"\n',
    'test_product_path.py': 'from backend.services.studio import readiness\ndef test_p():\n    readiness.transcription_check()  # product code reads the stand-in: fine\n',
}


@pytest.fixture
def suite(tmp_path):
    root = tmp_path / 'tests'
    for name, body in {**CASES, **OK}.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding='utf-8')
    (root / 'sub' / '__init__.py').write_text('', encoding='utf-8')
    (root / '__init__.py').write_text('', encoding='utf-8')
    conftest = (REPO / 'backend' / 'tests' / 'conftest.py').read_text(encoding='utf-8')
    (root / 'conftest.py').write_text(conftest, encoding='utf-8')
    return root


def test_unmarked_direct_readers_fail_and_marked_or_product_callers_pass(suite, tmp_path):
    proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-rA', str(suite)],
                          cwd=tmp_path, capture_output=True, text=True, env={**__import__('os').environ, 'PYTHONPATH': str(REPO)})
    out = proc.stdout + proc.stderr
    for name in CASES:
        stem = Path(name).name
        assert any(line.startswith('ERROR') and stem in line for line in out.splitlines()), (name, out[-3000:])
    for name in OK:
        assert any(line.startswith('PASSED') and name in line for line in out.splitlines()), (name, out[-3000:])
