"""R20 #165: conftest simulates an installed Whisper by replacing whisper_runtime.get_status.

A test that exercises get_status itself would silently read that stand-in and pass for the wrong
reason, so every test that calls whisper_runtime.get_status must carry @pytest.mark.own_whisper_status
(it then simulates its own state). This scans the test sources so a new unmarked test fails here."""
import ast
from pathlib import Path

TESTS = Path(__file__).parent
# Asserts the conftest stand-in itself, so it must read it.
READS_STAND_IN = {'test_whisper_gate_runs_everywhere.py::test_conftest_simulates_installed_whisper_not_a_disabled_gate'}


def _calls_runtime_get_status(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == 'get_status'
                and isinstance(sub.func.value, ast.Name) and sub.func.value.id == 'whisper_runtime'):
            return True
    return False


def _marked(fn: ast.FunctionDef, module_marked: bool) -> bool:
    if module_marked:
        return True
    return any('own_whisper_status' in ast.unparse(d) or 'stdlib_only' in ast.unparse(d) for d in fn.decorator_list)


def unmarked_get_status_tests(root: Path = TESTS) -> list[str]:
    found = []
    for path in sorted(root.glob('test_*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        module_marked = any(isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == 'pytestmark' for t in n.targets)
                            and 'own_whisper_status' in ast.unparse(n.value) for n in tree.body)
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name.startswith('test_') \
                    and _calls_runtime_get_status(fn) and not _marked(fn, module_marked):
                found.append(f'{path.name}::{fn.name}')
    return found


def test_every_get_status_test_simulates_its_own_state():
    assert [name for name in unmarked_get_status_tests() if name not in READS_STAND_IN] == []


def test_guard_flags_an_unmarked_test(tmp_path):
    (tmp_path / 'test_x.py').write_text(
        'from backend.services import whisper_runtime\n'
        'def test_a():\n    assert whisper_runtime.get_status()["status"] == "installed"\n', encoding='utf-8')
    assert unmarked_get_status_tests(tmp_path) == ['test_x.py::test_a']
