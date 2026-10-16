"""Scrub the real QA key (read from env, never printed), the app's masked key form and personal
home directories (C:\\Users\\x, /Users/x, /home/x, in any escaped spelling) from evidence text files.

Usage: python3 redact.py EVIDENCE_DIR   (key from WINQA_MODEL_API_KEY, or legacy AUTOCLIP_QA_DASHSCOPE_KEY)
       python3 redact.py --stdin        (diagnostics: home directories and URLs; used by pull_run_installer.sh,
                                         which also pipes everything pull_run_installer.ps1 prints through it)

R22 rewrite: one implementation, no regex for home directories.
1. Files are decoded strictly (BOM -> utf-8-sig / utf-16 / utf-32; else utf-8; else gb18030, which also keeps
   Shift-JIS and Big5 double-byte characters whole). Bytes gb18030 cannot read are kept as surrogateescape and
   written back 1:1; if a decode/encode round trip is not exact the file is left alone and reported.
   Line endings and the original encoding (and BOM) are written back unchanged.
2. scrub_homes() decodes every escape layer into logical characters (\\\\ -> \\, \\/ -> /, \\uXXXX -> char,
   repeated: \\u005cu5f20 -> 张) and scans them once, left to right (linear time).
3. After a home root (X:<sep>Users, /Users, /home; "Users" case-insensitive) everything up to the next logical
   separator (/ or \\) is the user name and is replaced whole by <user>. No partial put-back.
   A name also ends at '"' or a line break; Windows names also at : < > | * ? (not allowed in Windows names);
   POSIX names only at ':' besides that (passwd/macOS short names cannot contain ':').
"""
import json, os, re, sys
from pathlib import Path

USER = '<user>'
_HEX = set('0123456789abcdefABCDEF')
_WIN_STOP = set('"\r\n:<>|*?')
_POSIX_STOP = set('"\r\n:')
_SUFFIXES = ('.json', '.log', '.err', '.txt', '.md', '.cmd')


def _tokens(text):
    """Logical characters of text: (char, raw start, raw end). Escapes are undone layer by layer."""
    ch, st, en = list(text), list(range(len(text))), list(range(1, len(text) + 1))
    changed = True
    while changed:
        changed = False
        oc, os_, oe = [], [], []
        i, m = 0, len(ch)
        while i < m:
            c = ch[i]
            if c == '\\' and i + 1 < m:
                d = ch[i + 1]
                if d in '\\/':
                    oc.append(d); os_.append(st[i]); oe.append(en[i + 1]); i += 2; changed = True
                    continue
                if d == 'u' and i + 5 < m and all(x in _HEX for x in ch[i + 2:i + 6]):
                    oc.append(chr(int(''.join(ch[i + 2:i + 6]), 16))); os_.append(st[i]); oe.append(en[i + 5])
                    i += 6; changed = True
                    continue
            oc.append(c); os_.append(st[i]); oe.append(en[i]); i += 1
        ch, st, en = oc, os_, oe
    return ch, st, en


def _word(c):
    return c.isalnum() or c == '_'


def scrub_homes(text: str) -> str:
    ch, st, en = _tokens(text)
    n = len(ch)
    sep = lambda k: k < n and ch[k] in '/\\'

    def word_at(k, w, ci):
        if k + len(w) > n:
            return False
        got = ''.join(ch[k:k + len(w)])
        return (got.lower() == w) if ci else (got == w)

    def root_end(k):
        """k starts a home root -> (index of first name token, stop set, implicit separator) or None."""
        prev = ch[k - 1] if k else ''
        if ch[k].isascii() and ch[k].isalpha() and k + 1 < n and ch[k + 1] == ':' and not _word(prev):
            j = k + 2
            if not sep(j):
                return None
            while sep(j):
                j += 1
            if not word_at(j, 'users', True):
                return None
            return _after_root(j + 5, _WIN_STOP)
        if ch[k] == '/' and not (prev and (_word(prev) or prev in '.-\\')):
            for w, ci in (('users', True), ('home', False)):
                if word_at(k + 1, w, ci):
                    return _after_root(k + 1 + len(w), _POSIX_STOP)
        return None

    def _after_root(j, stop):
        if sep(j):
            while sep(j):
                j += 1
            return j, stop, False
        # "C:\Users\u1234": a backslash escape straight after the root is a plain separator + name.
        if j < n and en[j] - st[j] > 1 and text[st[j]] == '\\':
            return j, stop, True
        return None

    out, last, k = [], 0, 0
    while k < n:
        r = root_end(k)
        if r is None:
            k += 1
            continue
        j, stop, implicit = r
        if text.startswith(USER, st[j]) if j < n else True:
            k = j if j > k else k + 1
            continue
        e = j
        while e < n and ch[e] not in '/\\' and ch[e] not in stop:
            e += 1
        if e == j:
            k = j if j > k else k + 1
            continue
        start = st[j]
        if implicit:
            raw = text[st[j]:en[j]]
            start += len(raw) - len(raw.lstrip('\\'))
        out.append(text[last:start]); out.append(USER)
        last, k = en[e - 1], e
    out.append(text[last:])
    return ''.join(out)


URL = re.compile(r'https?://\S+')


def _scrub_text(n: str, key: str) -> str:
    if key:
        n = n.replace(key, '***')
    n = scrub_homes(n)
    n = re.sub(r'("api_key_masked"\s*:\s*")[^"]*(")', r'\1***\2', n)
    if key and len(key) > 8:
        n = n.replace(key[:3] + '…' + key[-3:], '***')
    return n


_LONE = re.compile('[\ud800-\udfff]')


def _scrub_json(text: str, key: str):
    """R18 #85: parse first so escaped names are seen as text; returns None if not JSON."""
    nl = '\r\n' if '\r\n' in text else '\n'
    try:
        data = json.loads(text)
    except ValueError:
        return None

    def walk(o, field=None):
        if isinstance(o, dict):
            out = {}   # R20 #119: two home paths used as keys may scrub to one key; keep both.
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
    s = json.dumps(clean, ensure_ascii=False, indent=2 if '\n' in text.strip() else None)
    s = _LONE.sub(lambda m: '\\u%04x' % ord(m.group()), s)   # R22 #156: lone surrogates stay escaped
    if nl == '\r\n':
        s = s.replace('\n', '\r\n')                           # R22 #129: keep CRLF
    return s + (nl if text.endswith('\n') else '')


_BOMS = [(b'\xef\xbb\xbf', 'utf-8'), (b'\xff\xfe\x00\x00', 'utf-32-le'), (b'\x00\x00\xfe\xff', 'utf-32-be'),
         (b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be')]


def decode(raw: bytes):
    """-> (bom, codec, errors, text). Raises ValueError when the bytes cannot be mapped back exactly."""
    for bom, codec in _BOMS:
        if raw.startswith(bom):
            body, errors = raw[len(bom):], 'surrogatepass' if codec != 'utf-8' else 'surrogateescape'
            break
    else:
        bom, body = b'', raw
        try:
            return b'', 'utf-8', 'strict', body.decode('utf-8')
        except UnicodeDecodeError:
            codec, errors = 'gb18030', 'surrogateescape'
    try:
        text = body.decode(codec, errors)
    except UnicodeDecodeError as exc:
        raise ValueError(f'cannot decode as {codec}') from exc
    if text.encode(codec, errors) != body:
        raise ValueError(f'{codec} round trip is not exact')
    return bom, codec, errors, text


def scrub_bytes(raw: bytes, key: str = '', json_file: bool = False, stream: bool = False) -> bytes:
    bom, codec, errors, text = decode(raw)
    out = text
    if key and codec != 'utf-8':
        # the key and its "abc…xyz" form are UTF-8 bytes even inside a GBK file
        for form in (key, key[:3] + '…' + key[-3:] if len(key) > 8 else ''):
            if form:
                try:
                    out = out.replace(form.encode('utf-8').decode(codec, errors), '***')
                except UnicodeDecodeError:
                    pass
    scrubbed = _scrub_json(out, key) if json_file else None
    out = _scrub_text(out, key) if scrubbed is None else scrubbed
    if stream:
        out = URL.sub('<url>', out)
    return raw if out == text else bom + out.encode(codec, errors)


def main(folder):
    return _run(Path(folder))


def _run(folder):
    key = os.environ.get('WINQA_MODEL_API_KEY') or os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY', '')
    hits, failed = 0, []
    for p in sorted(folder.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in _SUFFIXES:
            continue
        raw = p.read_bytes()
        try:
            out = scrub_bytes(raw, key, json_file=p.suffix.lower() == '.json')
        except Exception as exc:   # one bad file must not stop the rest (R22 #156)
            rel = scrub_homes(str(p.relative_to(folder)))
            failed.append(rel)
            print(f'redact: ERROR {rel}: {type(exc).__name__}: {exc}; file left unchanged', file=sys.stderr)
            continue
        if out != raw:
            hits += 1
            p.write_bytes(out)
    print(f'redact: rewrote {hits} file(s)' + (f', {len(failed)} failed' if failed else ''))
    if failed:
        raise SystemExit(2)
    return hits


def scrub_stream(text: str) -> str:
    """Diagnostics: home directories and URLs (signed links)."""
    return URL.sub('<url>', scrub_homes(text))


def scrub_stream_bytes(raw: bytes) -> bytes:
    return scrub_bytes(raw, stream=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--stdin']:
        sys.stdout.buffer.write(scrub_stream_bytes(sys.stdin.buffer.read()))
    else:
        main(sys.argv[1])
