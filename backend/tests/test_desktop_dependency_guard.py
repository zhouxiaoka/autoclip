"""Exercise the actual portable-runtime guard without development packages."""

from pathlib import Path
import subprocess
import sys


def run_guard(tmp_path, source):
    common = Path(__file__).resolve().parents[2] / "scripts/lib/desktop_build_common.sh"
    function = common.read_text().split("verify_backend_deps() {", 1)[1]
    program = function.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "feature.py").write_text(source)
    return subprocess.run(
        [sys.executable, "-S", "-c", program, str(backend)],
        capture_output=True, text=True, timeout=10,
    )


def test_whisper_lazy_dependencies_do_not_block_clean_bundle(tmp_path):
    result = run_guard(tmp_path, "def transcribe():\n    import faster_whisper\n    import numpy\n")
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_mandatory_dependency_still_blocks_bundle(tmp_path):
    result = run_guard(tmp_path, "import openai\n")
    assert result.returncode == 1
    assert "- openai" in result.stdout


def test_isolated_sensevoice_worker_dependencies_are_not_bundled(tmp_path):
    result = run_guard(tmp_path, "def worker():\n    import torch\n    import funasr\n    import huggingface_hub\n")
    assert result.returncode == 0, result.stdout + result.stderr


def test_bundle_local_modules_resolve(tmp_path):
    result = run_guard(tmp_path, "import backend\nimport json\n")
    assert result.returncode == 0, result.stdout + result.stderr
