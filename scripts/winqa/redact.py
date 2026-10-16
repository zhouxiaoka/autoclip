"""Scrub the real QA key (read from env, never printed), the app's masked key form and personal
home directories (C:\\Users\\x, /Users/x, /home/x, also JSON-escaped) from evidence text files.

Usage: python3 redact.py EVIDENCE_DIR  (key from WINQA_MODEL_API_KEY, or legacy AUTOCLIP_QA_DASHSCOPE_KEY)
"""
import json, os, re, sys
from pathlib import Path

# R21 rewrite (Dong's rule, replaces the R16-R20 patch series): after a home root (C:\Users, /Users,
# /home, in any escaped spelling) everything up to the next path separator is the user name and is
# replaced whole, whatever escapes, quotes or spaces it contains. Over-masking is accepted.
#   separator: / and \ in every spelling: \/ \\ \\\\ \u002f \u005c \\u002f ... (SEP)
#   a backslash run directly followed by u+4 hex (other than 002f/005c) is an escaped name
#   character, except a lone backslash right after a non-separator, which is a plain Windows
#   separator ("C:\Users\u1234").
#   a name also stops at '"', ':', CR/LF and < > | * ? (cannot appear in Windows names).
# Two narrow trims keep surrounding text (see _mask): a quote that opened right before the root
# closes the name ('/home/kris'), and prose ("see /home/a and more /x") stops at the first space
# when the run ends in a space right before a separator.
# ps/pull_run_installer.ps1 embeds WIN_PATTERN / POSIX_PATTERN verbatim and the same _mask steps;
# test_pwsh_and_python_redact_identically runs one corpus through both.
_HEX = r'[0-9a-fA-F]{4}'
_SEPU = r'u00(?:2[fF]|5[cC])'
SEP = r'(?:\\*/|\\+' + _SEPU + r'|(?:\\\\)+|(?<![\\/])\\|\\(?!u' + _HEX + r'))'
NAME = r'(?:\\+u(?!00(?:2[fF]|5[cC]))' + _HEX + r'|[^\\/"\r\n<>|*?:])+'
WIN_PATTERN = r'\b([a-zA-Z]:)(' + SEP + r'+)[uU][sS][eE][rR][sS](' + SEP + r'+)(?!<user>)(' + NAME + r')'
POSIX_PATTERN = r'(?<![\w.\\-])(\\*/|\\+u002[fF])(Users|home)(' + SEP + r'+)(?!<user>)(' + NAME + r')'
_WIN, _POSIX = re.compile(WIN_PATTERN), re.compile(POSIX_PATTERN)


def _mask(name: str, before: str, after: str) -> str:
    if before == "'":
        q = re.search(r"'(?=[ \t]|$)", name)   # the closing quote: one followed by a space or the end
        if q:
            return '<user>' + name[q.start():]
    if after in ('/', '\\') and name[-1] in ' \t':
        cut = min(i for i in (name.find(' '), name.find('\t')) if i >= 0)
        return '<user>' + name[cut:]
    return '<user>'


def _sub(pattern, text, head):
    def repl(m):
        before = text[m.start() - 1] if m.start() else ''
        after = text[m.end()] if m.end() < len(text) else ''
        return head(m) + _mask(m.group(4), before, after)
    return pattern.sub(repl, text)


def scrub_homes(text: str) -> str:
    text = _sub(_WIN, text, lambda m: m.group(1) + m.group(2) + 'Users' + m.group(3))
    return _sub(_POSIX, text, lambda m: m.group(1) + m.group(2) + m.group(3))


URL = re.compile(r'https?://\S+')


def _scrub_text(n: str, key: str, masked: str = None) -> str:
    """key / masked (the app's "abc…xyz" form) must be in n's own representation."""
    if key:
        n = n.replace(key, '***')
    n = scrub_homes(n)
    n = re.sub(r'("api_key_masked"\s*:\s*")[^"]*(")', r'\1***\2', n)
    if masked is None and key and len(key) > 8:
        masked = key[:3] + '…' + key[-3:]
    if masked:
        n = n.replace(masked, '***')
    return n


def _scrub_json(text: str, key: str):
    """R18 #85: decode first so \\u-escaped names are seen as text; returns None if not JSON."""
    bom = '\ufeff' if text.startswith('\ufeff') else ''   # R21 #131: strip BOM before parsing
    try:
        data = json.loads(text[len(bom):])
    except ValueError:
        return None

    def walk(o, field=None):
        if isinstance(o, dict):
            # R20 #119: two different home paths used as keys may scrub to the same key; keep both.
            out = {}
            for k, v in o.items():
                ck = walk(k)
                if ck in out:
                    i = 2
                    while f'{ck}#{i}' in out:
                        i += 1
                    ck = f'{ck}#{i}'
                out[ck] = walk(v, k)
            return out
        if isinstance(o, list):
            return [walk(x) for x in o]
        if isinstance(o, str):
            return '***' if field == 'api_key_masked' else _scrub_text(o, key)
        return o

    clean = walk(data)
    if clean == data:
        return text
    return bom + json.dumps(clean, ensure_ascii=False, indent=2 if '\n' in text.strip() else None) + ('\n' if text.endswith('\n') else '')


def main(folder):
    return _run(Path(folder))


def _run(folder):
    key = os.environ.get('WINQA_MODEL_API_KEY') or os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY', '')
    hits = 0
    for p in folder.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in ('.json', '.log', '.err', '.txt', '.md', '.cmd'):
            continue
        raw = p.read_bytes()
        out = None
        if p.suffix.lower() == '.json':
            try:
                j = _scrub_json(raw.decode('utf-8'), key)
                out = None if j is None else j.encode('utf-8')
            except UnicodeDecodeError:
                pass
        if out is None:
            # R21 #128: never decode/re-encode; latin-1 maps every byte 1:1, so GBK or broken bytes
            # outside a match come back unchanged. Masks are ASCII; the key is matched as UTF-8 bytes.
            as_bytes = lambda v: v.encode('utf-8').decode('latin-1')
            masked = as_bytes(key[:3] + '…' + key[-3:]) if key and len(key) > 8 else ''
            out = _scrub_text(raw.decode('latin-1'), as_bytes(key), masked).encode('latin-1')
        if out != raw:
            hits += 1
            p.write_bytes(out)
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
