#!/usr/bin/env python3
"""Lightweight CI guards for the 1.5.7 closeout.

Blocking: review-round test filenames, review ids in comments and docstrings,
and product error-code literals outside event_catalog.json. The line-count
table is written to the PR job summary and never fails the run.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import subprocess
import sys
import tokenize
import io

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
_ERROR_LITERAL = re.compile(r'''(?:error_code|errorCode)\s*[:=]\s*['"]([A-Za-z0-9_]+)['"]''')
# A review label is R or I plus the round digits (optional single letter) or the reviewer name.
# Bare status codes, version numbers and ordinary words do not match.
_REVIEW_ID = re.compile(r"\b(?:R\d{1,2}[a-z]?|I\d{3,4}|Dong(?:'s)?)\b")
_REVIEW_FILE = re.compile(r'^(?:test_[ri]\d|r\d+[-_.]|i\d+[-_.])', re.IGNORECASE)


# A leading "#12/#34 for #56." is the merged-module index, not the reason.
_LEADING_INDEX = re.compile(
    r'^(?:[ \t]*#\d+(?:[ \t]*[/#+\-–—][ \t]*#\d+)*[ \t.]*'
    r'(?:for[ \t]+#\d+[ \t.]*)?)+'
)
_BEHAVIOR_TAG = re.compile(r'^\((?:behavior|behaviour)\)\s*:?\s*', re.IGNORECASE)
_DECOR_LEAD = re.compile(r'^[ \t\-–—=|#/]{2,}[ \t]*:?[ \t]*|^[ \t:;,\-–—]+')
_DECOR_TAIL = re.compile(r'[ \t]*[\-–—=|#/]{2,}[ \t]*$')


def clean_review_text(text: str) -> str:
    """Drop review ids from a comment or docstring. Keep the sentence that says why."""
    if _REVIEW_ID.search(text) is None:
        return text
    cleaned = _REVIEW_ID.sub('', text)
    cleaned = re.sub(r'\(\s*:\s*', '(', cleaned)
    cleaned = re.sub(r'\bafter\s+\.', 'on the fixed side.', cleaned)
    cleaned = re.sub(r'\bafter\s+at\b', 'on the fixed side at', cleaned)
    cleaned = re.sub(r'\s+-\s+', ' ', cleaned)
    cleaned = re.sub(r'\s*-\s*,', ',', cleaned)
    cleaned = re.sub(r'\(\s*,\s*', '(', cleaned)
    cleaned = re.sub(r'\s+,', ',', cleaned)
    cleaned = re.sub(r'\(\s+\)', '', cleaned)
    cleaned = re.sub(r'\(\s+', '(', cleaned)
    cleaned = re.sub(r'\s+\)', ')', cleaned)
    lines = []
    for line in cleaned.splitlines():
        line = re.sub(r'^\s*\*\s?', '', line)
        line = _LEADING_INDEX.sub('', line)
        line = _DECOR_TAIL.sub('', line)
        line = _DECOR_LEAD.sub('', line)
        line = re.sub(r'^\(\s*\+\s*', '', line)
        line = re.sub(r'[ \t]{2,}', ' ', line).strip()
        line = _BEHAVIOR_TAG.sub('', line)
        line = re.sub(r'\(\s*\)', '', line).strip()
        if re.match(r'Moved here from\b', line):
            continue
        words = re.findall(r'[A-Za-z\u4e00-\u9fff]{2,}', line)
        if words and not all(word.lower() == 'review' for word in words):
            lines.append(line)
    return '\n'.join(lines).strip()


def _split_string_token(token: str) -> tuple[str, str, str]:
    """Return (prefix, quote, body) for a Python string token, including r/b/f/u prefixes."""
    prefix = ''
    match = re.match(r'^[rRuUbBfF]{1,2}', token)
    if match and token[match.end():match.end() + 1] in '"\'':
        prefix = token[:match.end()]
        token = token[match.end():]
    quote = token[:3] if token.startswith(("'''", '"""')) else token[:1]
    if quote in {'"', "'", '"""', "'''"} and token.endswith(quote) and len(token) >= 2 * len(quote):
        body = token[len(quote):-len(quote)]
    else:
        body = token[len(quote):]
    return prefix, quote, body


def _offsets(source: str) -> list[int]:
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _pos(offsets: list[int], line: int, col: int) -> int:
    return offsets[line - 1] + col


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


def _python_spans(source: str) -> list[tuple[int, int, str]]:
    """Comment and docstring spans as (start, end, replacement) for review ids."""
    offsets = _offsets(source)
    doc_starts = _expr_string_starts(source)
    spans = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    except tokenize.TokenError:
        return spans
    for tok in tokens:
        if tok.type == tokenize.COMMENT and _REVIEW_ID.search(tok.string):
            inner = clean_review_text(tok.string[1:])
            new = f'# {inner}' if inner else ''
            spans.append((_pos(offsets, *tok.start), _pos(offsets, *tok.end), new))
        elif tok.type == tokenize.STRING and tok.start in doc_starts and _REVIEW_ID.search(tok.string):
            prefix, quote, body = _split_string_token(tok.string)
            inner = clean_review_text(body)
            new = f'{prefix}{quote}{inner}{quote}' if inner else ''
            spans.append((_pos(offsets, *tok.start), _pos(offsets, *tok.end), new))
    return spans


def _js_spans(source: str) -> list[tuple[int, int, str]]:
    spans = []
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
        if source.startswith('//', i):
            end = source.find('\n', i)
            end = n if end < 0 else end
            text = source[i + 2:end]
            if _REVIEW_ID.search(text):
                inner = clean_review_text(text)
                spans.append((i, end, f'// {inner}' if inner else ''))
            i = end
            continue
        if source.startswith('/*', i):
            end = source.find('*/', i + 2)
            end = n if end < 0 else end + 2
            text = source[i + 2:end - 2]
            if _REVIEW_ID.search(text):
                inner = clean_review_text(text)
                spans.append((i, end, f'/* {inner} */' if inner else ''))
            i = end
            continue
        i += 1
    return spans


def _drop_blank_note(source: str, start: int, end: int) -> tuple[int, int]:
    """When a note is the whole line, remove that line instead of leaving a blank."""
    line_start = source.rfind('\n', 0, start) + 1
    if source[line_start:start].strip():
        return start, end
    if end < len(source) and source[end] == '\n':
        end += 1
    return line_start, end


def _apply(source: str, spans: list[tuple[int, int, str]]) -> str:
    pieces = []
    prev = 0
    for start, end, new in spans:
        if new == '' and start >= prev:
            start, end = _drop_blank_note(source, start, end)
            if start < prev:
                start = prev
        if start < prev:
            continue
        pieces.append(source[prev:start])
        pieces.append(new)
        prev = max(prev, end)
    pieces.append(source[prev:])
    return ''.join(pieces)


def rewrite_review_notes(root: Path = ROOT) -> list[str]:
    """One-shot cleaner. CI only checks; it does not rewrite the tree."""
    changed = []
    for path in _note_files(root):
        source = path.read_text(encoding='utf-8')
        spans = _python_spans(source) if path.suffix == '.py' else _js_spans(source)
        if not spans:
            continue
        path.write_text(_apply(source, spans), encoding='utf-8')
        changed.append(str(path.relative_to(root)))
    return changed


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
            offsets = _offsets(source)
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
            for start, _end, _new in _js_spans(source):
                line = source[:start].count('\n') + 1
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
    from backend.core.event_catalog import load_catalog
    enums = load_catalog().get('enums') or {}
    allowed = set()
    for name, values in enums.items():
        if isinstance(name, str) and name.endswith('_error_code') and isinstance(values, list):
            allowed.update(value for value in values if isinstance(value, str))
    return allowed


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
    if problems:
        print('\n\n'.join(problems), file=sys.stderr)
        return 1
    print('ci guards passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
