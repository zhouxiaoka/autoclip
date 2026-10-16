"""Scrub the real QA key (read from env, never printed), the app's masked key form and personal
home directories (C:\\Users\\x, /Users/x, /home/x, also JSON-escaped) from evidence text files.

Usage: python3 redact.py EVIDENCE_DIR  (key from WINQA_MODEL_API_KEY, or legacy AUTOCLIP_QA_DASHSCOPE_KEY)
"""
import os, re, sys
from pathlib import Path

# R16 #53: the user name segment after a home root becomes <user>; the rest of the path stays.
# R17 #56: a user name may contain spaces ("Jane Doe"); the whole segment up to the next path
# separator (or end of value) is masked. A spaced run only counts when another path separator,
# a quote or the end of the line follows, so prose after a bare "/home/a" is not swallowed.
_SEG = r'(?!<user>)(?:[^\\/\s"\'<>|:*?]+(?: +[^\\/\s"\'<>|:*?]+)*(?=\\|/|["\']|$)|[^\\/\s"\'<>|:*?]+)'
HOME_PATTERNS = [
    (re.compile(r'(?im)\b([a-z]:)((?:\\\\|\\|/)+)users((?:\\\\|\\|/)+)' + _SEG), r'\1\2Users\3<user>'),
    (re.compile(r'(?m)(?<![\w.-])/(Users|home)/' + _SEG), r'/\1/<user>'),
]
URL = re.compile(r'https?://\S+')


def scrub_homes(text: str) -> str:
    for pattern, replacement in HOME_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def main(folder):
    return _run(Path(folder))


def _run(folder):
    key = os.environ.get('WINQA_MODEL_API_KEY') or os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY', '')
    hits = 0
    for p in folder.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in ('.json', '.log', '.err', '.txt', '.md', '.cmd'):
            continue
        t = p.read_text(encoding='utf-8', errors='replace')
        n = t
        if key:
            n = n.replace(key, '***')
        n = scrub_homes(n)
        n = re.sub(r'("api_key_masked"\s*:\s*")[^"]*(")', r'\1***\2', n)
        if key and len(key) > 8:
            n = n.replace(key[:3] + '…' + key[-3:], '***')
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
