"""Exercise telemetry resources from an installed wheel, without a checkout."""
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from importlib.resources import files
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.stdlib_only
def test_packaged_catalog_matches_tracking_plan():
    assert files("backend.core").joinpath("event_catalog.json").read_bytes() == (
        ROOT / "docs" / "analytics" / "event_catalog.json"
    ).read_bytes()


@pytest.mark.stdlib_only
def test_catalog_override_does_not_change_producer_scan(monkeypatch, tmp_path):
    from backend.core import event_catalog

    expected = event_catalog.collect_producer_events(ROOT)
    assert "llm_request_finished" in expected
    with monkeypatch.context() as patch:
        override = tmp_path / "custom.json"
        override.write_text('{"common": {"os": ["custom"]}}', encoding="utf-8")
        patch.setenv("AUTOCLIP_EVENT_CATALOG", str(override))
        try:
            assert event_catalog.reload_catalog() == {"common": {"os": ["custom"]}}
            assert event_catalog.collect_producer_events() == expected
        finally:
            event_catalog.load_catalog.cache_clear()


@pytest.mark.stdlib_only
def test_installed_wheel_loads_event_catalog():
    # Build a fresh source copy: never reuse checkout build/ or egg-info caches.
    with tempfile.TemporaryDirectory(prefix="autoclip-catalog-wheel-") as directory:
        work = Path(directory).resolve()
        assert not work.is_relative_to(ROOT)
        source = work / "source"
        source.mkdir()
        for name in ("pyproject.toml", "README.md"):
            shutil.copy2(ROOT / name, source / name)
        shutil.copytree(
            ROOT / "backend", source / "backend",
            ignore=shutil.ignore_patterns("__pycache__", "tests", "data", "logs", "*.pyc"),
        )
        env = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME", "AUTOCLIP_EVENT_CATALOG",
                    "AUTOCLIP_APP_VERSION", "VITE_APP_VERSION"):
            env.pop(key, None)
        env.update(
            AUTOCLIP_DATA_DIR=str(work / "data"), AUTOCLIP_APP_DIR=str(work / "data"),
            AUTOCLIP_BUILD_ENVIRONMENT="validation", PYTHONDONTWRITEBYTECODE="1",
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-index",
             "--no-build-isolation", "--wheel-dir", str(work / "wheels"), str(source)],
            cwd=work, env=env, check=True, capture_output=True, text=True, timeout=120,
        )
        wheel, = (work / "wheels").glob("*.whl")
        target = work / "venv"
        venv.EnvBuilder(with_pip=True).create(target)
        python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [str(python), "-I", "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
            cwd=work, env=env, check=True, capture_output=True, text=True, timeout=60,
        )
        # Remove the build inputs too: neither the repository nor a source copy
        # can accidentally supply a resource missing from the installed wheel.
        shutil.rmtree(source)
        result = subprocess.run(
            [str(python), "-I", "-c", """
import sys
from pathlib import Path
import backend
from backend.core.event_catalog import detect_arch, envelope_properties, normalize_os
from backend.core.failure_codes import sentence, studio_codes
assert Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert 'llm_auth_invalid' in studio_codes() and sentence('invalid_key')
props = envelope_properties()
assert props == {
    'schema_version': 2, 'runtime': 'python', 'app_version': backend.__version__,
    'os': normalize_os(sys.platform) or 'unknown', 'arch': detect_arch(),
    'analytics_environment': 'validation',
}
"""],
            cwd=work, env=env, check=False, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
