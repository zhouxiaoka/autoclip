#!/usr/bin/env python3
"""Lightweight CI guards for the 1.5.7 closeout.

Blocking: review-round test filenames, review ids in comments and docstrings,
product error-code literals outside event_catalog.json (including quoted keys),
a second literal copy of a catalog error-code table, a Python string
that copies a failure_messages.json sentence, tracked paths that collide
when case is ignored, directory prefixes that differ only by case, and tests
that record every global urlopen body as a PostHog event. The line-count
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


# Vite tries these in order. On a case-insensitive disk, import './FailureHint'
# binds failureHint.ts before FailureHint.tsx, and the component default is missing.
RESOLVE_EXTS = ('.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json', '.cjs', '.cts')


def casefold_collisions(paths) -> list[str]:
    """Paths that cannot stay distinct on macOS or Windows, including extensionless imports."""
    exact: dict[str, list[str]] = {}
    stems: dict[str, list[str]] = {}
    for raw in paths:
        rel = str(raw).replace('\\', '/').strip()
        if not rel or any(part in SKIP_PARTS for part in rel.split('/')):
            continue
        exact.setdefault(rel.casefold(), []).append(rel)
        root, ext = os.path.splitext(rel)
        if ext.lower() in RESOLVE_EXTS:
            stems.setdefault(root.casefold(), []).append(rel)
    found = []
    reported = set()
    for group in exact.values():
        unique = tuple(sorted(set(group)))
        if len(unique) > 1:
            found.append('大小写相同的路径: ' + ', '.join(unique))
            reported.add(unique)
    for group in stems.values():
        unique = tuple(sorted(set(group)))
        if len(unique) > 1 and unique not in reported:
            found.append('大小写折叠后的模块名相同: ' + ', '.join(unique))
    return found


def tracked_paths(root: Path = ROOT) -> list[str]:
    out = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z'])
    return [part.decode() for part in out.split(b'\0') if part]


def resolve_casefolded(spec: str, paths, extensions=RESOLVE_EXTS) -> str | None:
    """The file an extensionless import hits when lookup ignores case."""
    folded: dict[str, str] = {}
    for raw in paths:
        rel = str(raw).replace('\\', '/')
        folded.setdefault(rel.casefold(), rel)
    for ext in extensions:
        hit = folded.get((spec + ext).casefold())
        if hit:
            return hit
    return None


def directory_casefold_collisions(paths) -> list[str]:
    """Directory prefixes that differ only by case.

    Foo/a.ts and foo/b.ts are different full paths, so a whole-path casefold
    check does not see them. macOS and Windows still collapse the directory.
    Sibling files such as Readme.md and readme.md are a separate check.
    """
    directories: dict[str, set[str]] = {}
    files: list[str] = []
    for raw in paths:
        rel = str(raw).replace('\\', '/').strip().strip('/')
        if not rel or any(part in SKIP_PARTS for part in rel.split('/')):
            continue
        files.append(rel)
        parts = rel.split('/')
        for index in range(1, len(parts)):
            prefix = '/'.join(parts[:index])
            directories.setdefault(prefix.casefold(), set()).add(prefix)
    found = []
    for spellings in directories.values():
        if len(spellings) > 1:
            found.append('目录名大小写不同: ' + ', '.join(sorted(spellings)))
    for rel in files:
        spellings = directories.get(rel.casefold())
        if not spellings:
            continue
        mixed = set(spellings)
        mixed.add(rel)
        if len(mixed) > 1:
            found.append('文件和目录大小写折叠后相同: ' + ', '.join(sorted(mixed)))
    return sorted(found)


def _is_global_urlopen_patch(node) -> bool:
    """The process-wide urllib.request.urlopen. A module's own urllib.request is not this."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'setattr':
        return False
    if len(node.args) < 2:
        return False
    target, name = node.args[0], node.args[1]
    if isinstance(target, ast.Constant) and target.value == 'urllib.request.urlopen':
        return True
    return (
        isinstance(name, ast.Constant) and name.value == 'urlopen'
        and isinstance(target, ast.Attribute) and target.attr == 'request'
        and isinstance(target.value, ast.Name) and target.value.id == 'urllib'
    )


def _has_global_urlopen_patch(fn) -> bool:
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if _is_global_urlopen_patch(node):
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def _mentions_event(node) -> bool:
    return any(isinstance(child, ast.Constant) and child.value == 'event' for child in ast.walk(node))


def _is_request_json(node) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'loads':
        return False
    owner = node.func.value
    if not isinstance(owner, ast.Name) or owner.id != 'json':
        return False
    return any(
        isinstance(child, ast.Attribute) and child.attr == 'data'
        for arg in node.args for child in ast.walk(arg)
    )


def _unguarded_appends(fn) -> list[tuple[int, str]]:
    """append(json body) that is not inside an if which looks at the event field."""
    parsed: set[str] = set()
    found = []

    def walk(node, parents):
        if isinstance(node, ast.Assign) and _is_request_json(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    parsed.add(target.id)
        elif isinstance(node, ast.AnnAssign) and node.value is not None and _is_request_json(node.value):
            if isinstance(node.target, ast.Name):
                parsed.add(node.target.id)
        if (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'append'
            and isinstance(node.func.value, ast.Name) and node.args
        ):
            arg = node.args[0]
            records_body = _is_request_json(arg) or (isinstance(arg, ast.Name) and arg.id in parsed)
            guarded = any(isinstance(parent, ast.If) and _mentions_event(parent.test) for parent in parents)
            if records_body and not guarded:
                found.append((node.lineno, node.func.value.id))
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            walk(child, parents + (node,))

    walk(fn, ())
    return found


def _enables_posthog(fn) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != 'setenv':
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            if 'POSTHOG' in node.args[0].value:
                return True
    return False


def _reads_telemetry(fn, list_name: str) -> bool:
    aliases = {list_name}
    nodes = list(ast.walk(fn))
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.For):
                targets, value = [node.target], node.iter
            else:
                continue
            root = value
            while isinstance(root, ast.Subscript):
                root = root.value
            if not isinstance(root, ast.Name) or root.id not in aliases:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    for node in nodes:
        if not isinstance(node, ast.Subscript) or not isinstance(node.slice, ast.Constant):
            continue
        if node.slice.value not in {'event', 'properties'}:
            continue
        root = node.value
        while isinstance(root, ast.Subscript):
            root = root.value
        if isinstance(root, ast.Name) and root.id in aliases:
            return True
    return False


def _nested_functions(fn):
    return [
        node for node in ast.walk(fn)
        if node is not fn and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def global_urlopen_telemetry_mixes(root: Path = ROOT) -> list[str]:
    """A global urlopen fake recorded a diagnostics body as if it were a PostHog event.

    Diagnostics uploads and PostHog captures both call urllib.request.urlopen.
    A diagnostics body has no event name. Patch the module that sends the event
    when the test only cares about that module.
    """
    found = []
    for name in TEST_ROOTS:
        base = root / name
        if not base.exists():
            continue
        for path in base.rglob('*.py'):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeError):
                continue
            functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
            patching = [fn for fn in functions if _has_global_urlopen_patch(fn)]
            nested = {id(child) for fn in patching for child in _nested_functions(fn)}
            for fn in patching:
                if id(fn) in nested:
                    continue
                posthog = _enables_posthog(fn)
                for scope in (fn, *_nested_functions(fn)):
                    for line, list_name in _unguarded_appends(scope):
                        if posthog or _reads_telemetry(fn, list_name):
                            found.append(f'{path.relative_to(root)}:{line}: 未过滤的 JSON body 被当成 PostHog 事件')
    return sorted(found)


_LEGACY_ORPHAN_COMPONENTS = frozenset({
    'frontend/src/features/studio/FailureActions.tsx',
    'frontend/src/features/settings/EndpointProviderSetup.tsx',
})


def tauri_invoke_contracts(root: Path = ROOT) -> list[str]:
    """Every literal invoke('cmd') in frontend/src must match src-tauri/src/lib.rs generate_handler!."""
    lib_rs = root / 'src-tauri/src/lib.rs'
    if not lib_rs.is_file():
        return []
    text = lib_rs.read_text(encoding='utf-8')
    match = re.search(r'generate_handler!\[(.*?)\]', text, re.S)
    if not match:
        return ['src-tauri/src/lib.rs: missing generate_handler![]']
    handlers = {
        item.strip().split('::')[-1]
        for item in match.group(1).split(',')
        if item.strip()
    }
    hits: list[str] = []
    src_root = root / 'frontend/src'
    if not src_root.is_dir():
        return []
    for path in sorted(src_root.rglob('*.ts*')):
        if not path.is_file():
            continue
        body = path.read_text(encoding='utf-8', errors='ignore')
        for call in re.finditer(r"\binvoke(?:<[^>]+>)?\(\s*['\"]([a-z0-9_]+)['\"]", body):
            cmd = call.group(1)
            if cmd not in handlers:
                line = body[:call.start()].count('\n') + 1
                hits.append(f'{path.relative_to(root).as_posix()}:{line}: unregistered Tauri invoke({cmd!r})')
    return hits


def orphaned_ui_components(root: Path = ROOT) -> list[str]:
    """Block newly orphaned feature .tsx components in studio/ and settings/."""
    src_root = root / 'frontend/src'
    if not src_root.is_dir():
        return []
    all_ts = {
        p: p.read_text(encoding='utf-8', errors='ignore')
        for p in src_root.rglob('*.ts*')
        if p.is_file()
    }
    hits: list[str] = []
    for sub in ('frontend/src/features/studio', 'frontend/src/features/settings'):
        folder = root / sub
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob('*.tsx')):
            rel = path.relative_to(root).as_posix()
            if rel in _LEGACY_ORPHAN_COMPONENTS:
                continue
            stem = path.stem
            pattern = re.compile(
                rf"from\s+['\"][^'\"]*/{re.escape(stem)}(?:\.tsx?)?['\"]"
                rf"|import\s*\(\s*['\"][^'\"]*/{re.escape(stem)}(?:\.tsx?)?['\"]\s*\)"
            )
            if not any(other != path and pattern.search(txt) for other, txt in all_ts.items()):
                hits.append(f'{rel}: unreferenced feature component')
    return hits


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
    paths = tracked_paths()
    collisions = casefold_collisions(paths)
    if collisions:
        problems.append('跨平台文件名碰撞:\n' + '\n'.join(collisions))
    directories = directory_casefold_collisions(paths)
    if directories:
        problems.append(
            '目录名忽略大小写后相同。macOS 和 Windows 不能同时存放，Linux CI 仍会通过。'
            '改掉冲突的文件或目录名，让 casefold 后每一级只有一种写法。\n' + '\n'.join(directories)
        )
    mixes = global_urlopen_telemetry_mixes()
    if mixes:
        problems.append(
            '全局 urlopen 把诊断上传和 PostHog 记到一起。诊断请求没有 event。'
            '记录之前要确认 event 是字符串；只想断言 PostHog 时，patch 发出事件的那个模块的 urllib.request，'
            '不要 patch 进程全局的 urllib.request.urlopen。\n' + '\n'.join(mixes)
        )
    tauri_hits = tauri_invoke_contracts()
    if tauri_hits:
        problems.append('未注册的 Tauri invoke 命令:\n' + '\n'.join(tauri_hits))
    orphan_hits = orphaned_ui_components()
    if orphan_hits:
        problems.append('新增孤立 UI 组件（0 引用）:\n' + '\n'.join(orphan_hits))
    if problems:
        print('\n\n'.join(problems), file=sys.stderr)
        return 1
    print('ci guards passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
