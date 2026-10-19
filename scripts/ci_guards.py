#!/usr/bin/env python3
"""Lightweight CI guards for the 1.5.7 closeout.

Blocking: review-round test filenames, review ids in comments and docstrings,
product error-code literals outside event_catalog.json (including quoted keys),
a second literal copy of a catalog error-code table, and a Python string
that copies a failure_messages.json sentence. The line-count
table is written to the PR job summary and never fails the run.
"""
from __future__ import annotations

import ast
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tokenize

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TEST_ROOTS = ('backend/tests', 'frontend/tests', 'scripts/tests', 'scripts/windows_tests')
NOTE_ROOTS = ('backend', 'frontend/src', 'frontend/tests', 'scripts')
NOTE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.cjs', '.mjs'}
SKIP_PARTS = {'node_modules', '__pycache__', 'dist', '.venv', 'venv'}
PRODUCT_ROOTS = ('backend', 'frontend/src', 'scripts')
# HTTP response constants (VALIDATION_ERROR) are not catalog error codes.
_CATALOG_CODE = re.compile(r'^[a-z][a-z0-9_]*$')
# A quoted key is the same assignment as a bare name.
_ERROR_LITERAL = re.compile(r'''['"]?(?:error_code|errorCode)['"]?\s*[:=]\s*['"]([A-Za-z0-9_]+)['"]''')
# A review label is R or I plus the round digits (optional single letter) or the reviewer name.
# Bare status codes, version numbers and ordinary words do not match.
_REVIEW_ID = re.compile(r"\b(?:R\d{1,2}[a-z]?|I\d{3,4}|Dong(?:'s)?)\b")
_REVIEW_FILE = re.compile(r'^(?:test_[ri]\d|r\d+[-_.]|i\d+[-_.])', re.IGNORECASE)


def _expr_string_starts(source: str) -> set[tuple[int, int]]:
    starts = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return starts
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(getattr(node, 'value', None), ast.Constant):
            if isinstance(node.value.value, str):
                starts.add((node.lineno, node.col_offset))
    return starts


def _js_review_lines(source: str) -> list[int]:
    """Line numbers of review ids in JS comments. Strings are skipped."""
    lines = []
    i, n = 0, len(source)
    while i < n:
        char = source[i]
        if char in '"\'`':
            quote = char
            i += 1
            while i < n:
                if source[i] == '\\':
                    i += 2
                    continue
                if quote == '`' and source.startswith('${', i):
                    i += 2
                    depth = 1
                    while i < n and depth:
                        if source[i] in '"\'`':
                            break
                        if source[i] == '{':
                            depth += 1
                        elif source[i] == '}':
                            depth -= 1
                        i += 1
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if source.startswith('//', i) or source.startswith('/*', i):
            block = source.startswith('/*', i)
            end = source.find('*/', i + 2) if block else source.find('\n', i)
            end = n if end < 0 else (end + 2 if block else end)
            text = source[i + 2:end - (2 if block else 0)]
            if _REVIEW_ID.search(text):
                lines.append(source[:i].count('\n') + 1)
            i = end
            continue
        i += 1
    return lines


def _note_files(root: Path):
    for name in NOTE_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix not in NOTE_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            yield path


def review_filenames(root: Path = ROOT) -> list[str]:
    found = []
    for name in TEST_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix not in NOTE_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if _REVIEW_FILE.match(path.name):
                found.append(str(path.relative_to(root)))
    return sorted(found)


def review_notes(root: Path = ROOT) -> list[str]:
    found = []
    for path in _note_files(root):
        source = path.read_text(encoding='utf-8')
        if path.suffix == '.py':
            doc_starts = _expr_string_starts(source)
            try:
                tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
            except tokenize.TokenError:
                continue
            for tok in tokens:
                if tok.type == tokenize.COMMENT or (tok.type == tokenize.STRING and tok.start in doc_starts):
                    if _REVIEW_ID.search(tok.string):
                        found.append(f'{path.relative_to(root)}:{tok.start[0]}')
        else:
            for line in _js_review_lines(source):
                found.append(f'{path.relative_to(root)}:{line}')
    return found


def _mcp_error_codes() -> set[str]:
    """The closed MCP set already in product code. Read it, do not copy it."""
    path = ROOT / 'backend/services/mcp_telemetry.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == 'ERROR_CODES' for target in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call) or not call.args or not isinstance(call.args[0], ast.Set):
            break
        return {elt.value for elt in call.args[0].elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)}
    raise RuntimeError('mcp_telemetry.ERROR_CODES is not a frozenset of strings')


def _catalog_error_codes() -> set[str]:
    """Enums named *_error_code, plus the attribution list user_caused_error_codes."""
    from backend.core.event_catalog import load_catalog
    catalog = load_catalog()
    enums = catalog.get('enums') or {}
    allowed = set()
    for name, values in enums.items():
        if isinstance(name, str) and name.endswith('_error_code') and isinstance(values, list):
            allowed.update(value for value in values if isinstance(value, str))
    caused = (catalog.get('attribution') or {}).get('user_caused_error_codes') or []
    if isinstance(caused, list):
        allowed.update(value for value in caused if isinstance(value, str))
    return allowed


def _catalog_error_sets() -> list[tuple[str, set[str]]]:
    """Named error-code tables. A second literal copy of one of these is a handwritten set."""
    from backend.core.event_catalog import load_catalog
    catalog = load_catalog()
    tables = []
    for name, values in (catalog.get('enums') or {}).items():
        if isinstance(name, str) and name.endswith('_error_code') and isinstance(values, list):
            codes = {value for value in values if isinstance(value, str)}
            if len(codes) >= 3:
                tables.append((f'enums.{name}', codes))
    caused = (catalog.get('attribution') or {}).get('user_caused_error_codes') or []
    if isinstance(caused, list):
        codes = {value for value in caused if isinstance(value, str)}
        if len(codes) >= 3:
            tables.append(('attribution.user_caused_error_codes', codes))
    return tables


def _literal_strings(node):
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        values = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                values.append(elt.value)
            else:
                return None
        return values
    if isinstance(node, ast.Call) and node.args:
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, 'attr', None)
        if name in {'frozenset', 'set', 'tuple', 'list'}:
            return _literal_strings(node.args[0])
    return None


def _python_code_sets(path: Path) -> list[tuple[int, set[str]]]:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        value = None
        lineno = getattr(node, 'lineno', 1)
        if isinstance(node, ast.Assign):
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            value = node.value
        if value is None:
            continue
        values = _literal_strings(value)
        if values and len(values) >= 3:
            found.append((lineno, set(values)))
    return found


_TS_COLLECTION = re.compile(
    r'(?m)^[ \t]*(?:export[ \t]+)?(?:const|let)[ \t]+[A-Za-z0-9_]+[ \t]*(?::[^\n=]+)?=[ \t]*\[([^\]]*)\]'
)
_QUOTED = re.compile(r'''['"]([A-Za-z0-9_]+)['"]''')


def _ts_code_sets(path: Path) -> list[tuple[int, set[str]]]:
    text = path.read_text(encoding='utf-8')
    found = []
    for match in _TS_COLLECTION.finditer(text):
        values = _QUOTED.findall(match.group(1))
        if len(values) >= 3:
            found.append((text[:match.start()].count('\n') + 1, set(values)))
    return found


def handwritten_error_code_sets(root: Path = ROOT) -> list[str]:
    """A literal collection that equals a catalog error-code table is a second copy."""
    tables = _catalog_error_sets()
    found = []
    for name in PRODUCT_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or path.name in {'event_catalog.json', 'failure_messages.json'}:
                continue
            if any(part in SKIP_PARTS or part == 'tests' for part in path.parts) or path.name.startswith('test_'):
                continue
            if path.suffix == '.py':
                collections = _python_code_sets(path)
            elif path.suffix in {'.ts', '.tsx', '.js', '.cjs'}:
                collections = _ts_code_sets(path)
            else:
                continue
            for line, codes in collections:
                for label, table in tables:
                    if codes == table:
                        found.append(f'{path.relative_to(root)}:{line}: duplicates {label}')
                        break
    return found


def error_code_literal_allowed(code: str, catalog: set[str], mcp: set[str]) -> bool:
    if _CATALOG_CODE.fullmatch(code) is None:
        return True
    if code in catalog or code in mcp:
        return True
    from backend.core.failure_codes import require_code
    try:
        require_code(code)
    except ValueError:
        return False
    return True


def error_code_literals(root: Path = ROOT) -> list[str]:
    catalog = _catalog_error_codes()
    mcp = _mcp_error_codes()
    found = []
    for name in PRODUCT_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix not in {'.py', '.ts', '.tsx', '.js', '.cjs'}:
                continue
            if any(part in SKIP_PARTS or part == 'tests' for part in path.parts):
                continue
            if path.name.startswith('test_'):
                continue
            text = path.read_text(encoding='utf-8')
            for match in _ERROR_LITERAL.finditer(text):
                code = match.group(1)
                if not error_code_literal_allowed(code, catalog, mcp):
                    line = text[:match.start()].count('\n') + 1
                    found.append(f'{path.relative_to(root)}:{line}: {code}')
    return found


def _bucket(path: str) -> str:
    name = path.replace('\\', '/')
    if name.startswith('docs/') or name.endswith('.md'):
        return 'docs'
    if '/tests/' in f'/{name}' or name.startswith('frontend/tests/') or '.test.' in Path(name).name:
        return 'tests'
    if name.startswith(('backend/', 'frontend/src/', 'src-tauri/', 'scripts/')):
        return 'product'
    return 'other'


def diff_lines(base_ref: str) -> dict[str, list[int]] | None:
    fetch = subprocess.run(['git', 'fetch', '--depth', '1', 'origin', base_ref], cwd=ROOT, check=False,
                           capture_output=True, text=True)
    if fetch.returncode != 0:
        return None
    diff = subprocess.run(['git', 'diff', '--numstat', 'FETCH_HEAD', 'HEAD'], cwd=ROOT, check=False,
                          capture_output=True, text=True)
    if diff.returncode != 0:
        return None
    counts = {key: [0, 0] for key in ('product', 'tests', 'docs', 'other')}
    for line in diff.stdout.splitlines():
        added, deleted, path = line.split('\t', 2)
        if added == '-' or deleted == '-':
            continue
        bucket = counts[_bucket(path)]
        bucket[0] += int(added)
        bucket[1] += int(deleted)
    return counts


def write_summary(counts: dict[str, list[int]] | None) -> None:
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if not summary:
        return
    lines = ['### 行数变化（只展示，不拦截）', '', '| | 增加 | 删除 | 净变化 |', '|---|---:|---:|---:|']
    labels = (('product', '产品'), ('tests', '测试'), ('docs', '文档'), ('other', '其他'))
    if counts is None:
        lines.append('| 行数 |  |  | 未能和基线比较 |')
    else:
        for key, label in labels:
            added, deleted = counts[key]
            if key == 'other' and added == deleted == 0:
                continue
            lines.append(f'| {label} | {added} | {deleted} | {added - deleted} |')
    with open(summary, 'a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')


def catalog_sentence_copies(root: Path = ROOT) -> list[str]:
    """A Python string equal to a catalog sentence is a second copy of that sentence."""
    table = root / 'backend' / 'core' / 'failure_messages.json'
    if not table.is_file():
        return []
    sentences = {text for text in json.loads(table.read_text(encoding='utf-8')).values() if isinstance(text, str) and text}
    found = []
    base = root / 'backend'
    for path in base.rglob('*.py'):
        if any(part in SKIP_PARTS or part == 'tests' for part in path.parts) or path.name.startswith('test_'):
            continue
        try:
            tokens = tokenize.tokenize(io.BytesIO(path.read_bytes()).readline)
        except (tokenize.TokenError, SyntaxError, UnicodeError):
            continue
        for token in tokens:
            if token.type != tokenize.STRING:
                continue
            try:
                value = ast.literal_eval(token.string)
            except (SyntaxError, ValueError):
                continue
            if isinstance(value, str) and value in sentences:
                found.append(f'{path.relative_to(root)}:{token.start[0]}: {value}')
    return found


def main() -> int:
    base = os.environ.get('GITHUB_BASE_REF', '')
    if base:
        write_summary(diff_lines(base))
    problems = []
    filenames = review_filenames()
    if filenames:
        problems.append('审查轮次测试文件名:\n' + '\n'.join(filenames))
    notes = review_notes()
    if notes:
        problems.append('审查编号注释:\n' + '\n'.join(notes))
    literals = error_code_literals()
    if literals:
        problems.append('错误码字面量不在目录里:\n' + '\n'.join(literals))
    copies = handwritten_error_code_sets()
    if copies:
        problems.append('手写错误码集合:\n' + '\n'.join(copies))
    sentences = catalog_sentence_copies()
    if sentences:
        problems.append('手写失败文案:\n' + '\n'.join(sentences))
    if problems:
        print('\n\n'.join(problems), file=sys.stderr)
        return 1
    print('ci guards passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
