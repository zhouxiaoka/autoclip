"""Scrub the real QA key (read from env, never printed), the app's masked key form and personal
home directories (C:\\Users\\x, /Users/x, /home/x, also JSON-escaped) from evidence text files.

Usage: python3 redact.py EVIDENCE_DIR  (key from WINQA_MODEL_API_KEY, or legacy AUTOCLIP_QA_DASHSCOPE_KEY)
"""
import json, os, re, sys
from pathlib import Path

# R16 #53: the user name segment after a home root becomes <user>; the rest of the path stays.
# R17 #56: a user name may contain spaces ("Jane Doe"); the whole segment up to the next path
# separator (or end of value) is masked. A spaced run only counts when another path separator,
# a quote, a colon (R18 #88: "/Users/Jane Doe: Permission denied") or the end of the line follows,
# so prose after a bare "/home/a" is not swallowed.
# R18 #85: JSON text may carry the name as \\uXXXX escapes ("/Users/\\u5f20\\u4e09"); an escape is one
# name character, and a backslash that starts an escape is never a path separator. .json files are
# additionally parsed and scrubbed string by string (see _scrub_json).
# R18 #86: ps/pull_run_installer.ps1 embeds these exact pattern strings (test_ps1_uses_redact_py_patterns).
CH = r'(?:\\u[0-9a-fA-F]{4}|[^\\/\s"\'<>|:*?])'
SEP = r'(?:\\\\|\\(?!u[0-9a-fA-F]{4})|/)+'
SEG = r'(?!<user>)(?:' + CH + r'+(?: +' + CH + r'+)*(?=\\|/|["\':]|$)|' + CH + r'+)'
WIN_PATTERN = r'(?im)\b([a-z]:)(' + SEP + r')users(' + SEP + r')' + SEG
POSIX_PATTERN = r'(?m)(?<![\w.-])/(Users|home)/' + SEG
HOME_PATTERNS = [
    (re.compile(WIN_PATTERN), r'\1\2Users\3<user>'),
    (re.compile(POSIX_PATTERN), r'/\1/<user>'),
]
URL = re.compile(r'https?://\S+')


def scrub_homes(text: str) -> str:
    for pattern, replacement in HOME_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _scrub_text(n: str, key: str) -> str:
    if key:
        n = n.replace(key, '***')
    n = scrub_homes(n)
    n = re.sub(r'("api_key_masked"\s*:\s*")[^"]*(")', r'\1***\2', n)
    if key and len(key) > 8:
        n = n.replace(key[:3] + '…' + key[-3:], '***')
    return n


def _scrub_json(text: str, key: str):
    """R18 #85: decode first so \\u-escaped names are seen as text; returns None if not JSON."""
    try:
        data = json.loads(text)
    except ValueError:
        return None

    def walk(o, field=None):
        if isinstance(o, dict):
            return {walk(k): walk(v, k) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(x) for x in o]
        if isinstance(o, str):
            return '***' if field == 'api_key_masked' else _scrub_text(o, key)
        return o

    clean = walk(data)
    if clean == data:
        return text
    return json.dumps(clean, ensure_ascii=False, indent=2 if '\n' in text.strip() else None) + ('\n' if text.endswith('\n') else '')


def main(folder):
    return _run(Path(folder))


def _run(folder):
    key = os.environ.get('WINQA_MODEL_API_KEY') or os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY', '')
    hits = 0
    for p in folder.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in ('.json', '.log', '.err', '.txt', '.md', '.cmd'):
            continue
        t = p.read_text(encoding='utf-8', errors='replace')
        n = _scrub_json(t, key) if p.suffix.lower() == '.json' else None
        if n is None:
            n = _scrub_text(t, key)
        if n != t:
            hits += 1
            p.write_text(n, encoding='utf-8')
    print(f'redact: rewrote {hits} file(s)')
    return hits


def scrub_stream(text: str) -> str:
    """Diagnostics piped from the shell puller: home directories and URLs (signed links)."""
    return URL.sub('<url>', scrub_homes(text))


if __name__ == '__main__':
    if sys.argv[1:] == ['--stdin']:
        sys.stdout.write(scrub_stream(sys.stdin.read()))
    else:
        main(sys.argv[1])
