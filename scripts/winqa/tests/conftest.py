"""Boundary for the Windows QA harness tests: they test scripts/winqa only and never import the backend, so they run
with just pytest (the macOS Bash 3.2 job). Kept out of backend/tests on purpose: backend/tests/conftest.py loads
backend.services (sqlalchemy, ...) for every test in its tree.

R29 #332: the "a backend module was imported -> the session fails" guard applies only to a session whose tests
are ALL in this directory (the quality gate's winqa_tests step and the macOS job). A combined run that also
collects backend tests imports the backend legitimately and is left alone."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))   # _winqa_helpers
_scope = {'winqa_only': False}


def _in_scope(item) -> bool:
    try:
        Path(str(item.fspath)).resolve().relative_to(HERE)
        return True
    except ValueError:
        return False


def pytest_collection_modifyitems(session, config, items):
    _scope['winqa_only'] = bool(items) and all(_in_scope(i) for i in items)


def pytest_sessionfinish(session, exitstatus):
    if not _scope['winqa_only']:
        return
    loaded = sorted(m for m in sys.modules if m == 'backend' or m.startswith('backend.'))
    if loaded:   # the boundary is the point of this directory: fail loudly if a test starts importing the backend
        print(f'\nscripts/winqa/tests imported backend modules: {loaded[:5]}', file=sys.stderr)
        session.exitstatus = 1
