"""Scrub the real QA key (read from env, never printed), the app's masked key form and personal
home directories (C:\\Users\\x, /Users/x, /home/x, in any escaped spelling) from evidence text files.

Usage: python3 redact.py EVIDENCE_DIR   (key from WINQA_MODEL_API_KEY, or legacy AUTOCLIP_QA_DASHSCOPE_KEY)
       python3 redact.py --stdin        (diagnostics: home directories and URLs; pull_run_installer.sh pipes
                                         everything it prints, stdout and stderr, through it)

Design (R23): one boundary rule, no per-sample branches.
1. Views. A text is read as its raw characters AND as its decoded characters (every escape layer undone in
   repeated left-to-right passes, each later pass touching only what the previous one produced: \\\\ -> \\, \\/ -> /, \\uXXXX -> char, so \\u005cu005c -> \\).
   Bytes are additionally read under every candidate encoding (BOM codec; else utf-8; else gb18030 plus
   shift_jis / big5 when they decode; UTF-16 without BOM when NUL bytes dominate).
2. Rule, applied identically to every view. After a home root (X:<sep>Users<sep>, /Users/, /home/; roots
   case-insensitive) the user name runs from the separator to the next real separator (POSIX: '/',
   Windows: '\\' or '/') or the end of the line. Nothing else ends a name: no quote, colon or prefix rule.
   '.' and '..' segments are skipped and the following segment is masked.
3. Union. Every view yields raw ranges; overlapping ranges of all views are merged and each merged range is
   replaced by <user> (or <url> for URLs in --stdin mode: http(s):// case-insensitive, up to whitespace, in
   any view). When views disagree, the union is masked: when in doubt, mask more.
4. Files are written back in their original encoding, BOM and line endings; a decode/encode round trip
   that is not exact leaves the file alone and reports it.
"""
import json, os, re, sys
from pathlib import Path

USER, URLMARK = '<user>', '<url>'
_HEX = set('0123456789abcdefABCDEF')
_EOL = '\r\n'
_WIN_SEPS, _POSIX_SEPS = '\\/', '/'
_SUFFIXES = ('.json', '.log', '.err', '.txt', '.md', '.cmd')


def _decoded_view(text):
    """Logical characters with raw spans after undoing every escape layer, exactly as repeated left-to-right
    passes would (\\\\ -> \\, \\/ -> /, \\uXXXX -> char, then again on the result), in O(n log n):
    a later pass can only match next to a character the previous pass produced, so each pass after the
    first only looks at the <= 5 tokens before each produced character (#154, #184)."""
    n = len(text)
    ch, st, en = list(text), list(range(n)), list(range(1, n + 1))
    nxt, prv, alive = list(range(1, n + 1)), list(range(-1, n - 1)), [True] * n

    def match(i):
        if ch[i] != '\\':
            return None
        j = nxt[i]
        if j >= n:
            return None
        if ch[j] in '\\/':
            return [j], ch[j]
        if ch[j] != 'u':
            return None
        ids, k = [j], j
        for _ in range(4):
            k = nxt[k]
            if k >= n or ch[k] not in _HEX:
                return None
            ids.append(k)
        return ids, chr(int(''.join(ch[x] for x in ids[1:]), 16))

    def reduce(i, ids, val):
        last = ids[-1]
        for x in ids:
            alive[x] = False
        ch[i], en[i] = val, en[last]
        nxt[i] = nxt[last]
        if nxt[i] < n:
            prv[nxt[i]] = i

    produced, i = [], 0
    while i < n:                      # pass 1: every position
        m = match(i)
        if m:
            reduce(i, *m)
            produced.append(i)
        i = nxt[i]
    while produced:                   # later passes: only around what the previous pass produced
        cand = set()
        for t in produced:
            k = t
            for _ in range(6):
                if k < 0:
                    break
                cand.add(k)
                k = prv[k]
        produced = []
        for c in sorted(cand):
            if alive[c]:
                m = match(c)
                if m:
                    reduce(c, *m)
                    produced.append(c)
    out_c, out_s, out_e, i = [], [], [], 0
    while i < n:
        out_c.append(ch[i]); out_s.append(st[i]); out_e.append(en[i])
        i = nxt[i]
    return out_c, out_s, out_e


def _raw_view(text):
    return list(text), range(len(text)), range(1, len(text) + 1)


def _word(c):
    return c.isalnum() or c == '_'


def _home_ranges(text, ch, st, en):
    n, out = len(ch), []

    def word_at(k, w):
        return k + len(w) <= n and ''.join(ch[k:k + len(w)]).lower() == w

    def skip(j, seps):
        if j >= n or ch[j] not in seps:
            return None
        while j < n and ch[j] in seps:
            j += 1
        return j

    def root(k):
        prev = ch[k - 1] if k else ''
        if ch[k].isascii() and ch[k].isalpha() and k + 1 < n and ch[k + 1] == ':' and not _word(prev):
            j = skip(k + 2, _WIN_SEPS)
            if j is not None and word_at(j, 'users'):
                j += 5
                if j < n and ch[j] not in _WIN_SEPS and text[st[j]] == '\\':
                    return j, _WIN_SEPS   # the root's '\\' also opens an escape ("Users\\u5f20"): both readings
                j = skip(j, _WIN_SEPS)
                return None if j is None else (j, _WIN_SEPS)
            return None
        if ch[k] == '/' and not (prev and (_word(prev) or prev in '.-\\')):
            for w in ('users', 'home'):
                if word_at(k + 1, w):
                    j = skip(k + 1 + len(w), _POSIX_SEPS)
                    return None if j is None else (j, _POSIX_SEPS)
        return None

    k = 0
    while k < n:
        r = root(k)
        if r is None:
            k += 1
            continue
        j, seps = r
        while True:
            e = j
            while e < n and ch[e] not in seps and ch[e] not in _EOL:
                e += 1
            nxt = skip(e, seps)
            if ''.join(ch[j:e]) in ('.', '..') and nxt is not None:
                j = nxt
                continue
            break
        if e > j:
            out.append((st[j], en[e - 1], USER))
        k = max(e, k + 1)
    return out


def _url_ranges(ch, st, en):
    n, out, k = len(ch), [], 0
    while k < n:
        if ch[k] in 'hH':
            for p in ('https://', 'http://'):
                if k + len(p) <= n and ''.join(ch[k:k + len(p)]).lower() == p:
                    e = k + len(p)
                    while e < n and not ch[e].isspace():
                        e += 1
                    out.append((st[k], en[e - 1], URLMARK))
                    k = e
                    break
        k += 1
    return out


def text_ranges(text, urls=False):
    """Raw ranges to mask in text: union over the raw and the decoded view."""
    views = [_raw_view(text)]
    dec = _decoded_view(text)
    if len(dec[0]) != len(text):
        views.append(dec)
    out = []
    for v in views:
        for s, e, lab in _home_ranges(text, *v) + (_url_ranges(*v) if urls else []):
            if lab == USER and s and text[s - 1] not in '\\/':
                while e - s > 1 and text[s] == '\\':
                    s += 1   # an escape glued to the root ("Users\\u5f20"): its backslashes stay as the separator
            out.append((s, e, lab))
    return out


def _merge(ranges):
    merged = []
    for s, e, lab in sorted(ranges):
        if merged and s <= merged[-1][1]:
            ps, pe, pl = merged[-1]
            merged[-1] = (ps, max(pe, e), URLMARK if URLMARK in (pl, lab) else USER)
        else:
            merged.append((s, e, lab))
    return merged


def _apply(seq, ranges, mark):
    """seq is str or bytes; mark(label) gives the replacement of the same type."""
    out, last = [], 0
    for s, e, lab in _merge(ranges):
        out.append(seq[last:s]); out.append(mark(lab)); last = e
    out.append(seq[last:])
    return seq[:0].join(out)


def scrub_homes(text: str) -> str:
    return _apply(text, text_ranges(text), str)


def scrub_stream(text: str) -> str:
    """Diagnostics: home directories and URLs (signed links)."""
    return _apply(text, text_ranges(text, urls=True), str)


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


_BOMS = [(b'\xef\xbb\xbf', 'utf-8', 'surrogateescape'), (b'\xff\xfe\x00\x00', 'utf-32-le', 'surrogatepass'),
         (b'\x00\x00\xfe\xff', 'utf-32-be', 'surrogatepass'), (b'\xff\xfe', 'utf-16-le', 'surrogatepass'),
         (b'\xfe\xff', 'utf-16-be', 'surrogatepass')]
_FALLBACK = ('gb18030', 'surrogateescape')      # reads every byte string; written back 1:1
_ALTERNATES = ('shift_jis', 'big5')             # extra readings of non-UTF-8 bytes, masked as a union (#181)


def _exact(body, codec, errors):
    """Decode, refusing (ValueError) anything that does not encode back to the same bytes."""
    try:
        text = body.decode(codec, errors)
    except UnicodeDecodeError as exc:
        raise ValueError(f'cannot decode as {codec}') from exc
    if text.encode(codec, errors) != body:
        raise ValueError(f'{codec} round trip is not exact')
    return text


def _strict(body, codec):
    try:
        return body.decode(codec)
    except UnicodeDecodeError:
        return None


def readings(raw: bytes):
    """-> (bom, (codec, errors) used for writing back, [(codec, errors), ...] every reading to mask)."""
    for bom, codec, errors in _BOMS:
        if raw.startswith(bom):
            return bom, (codec, errors), [(codec, errors)]
    if raw and raw.count(0) * 4 >= len(raw) and len(raw) % 2 == 0:   # #190: UTF-16 without BOM
        odd = raw[1::2].count(0) >= raw[0::2].count(0)
        for codec in (('utf-16-le', 'utf-16-be') if odd else ('utf-16-be', 'utf-16-le')):
            if _strict(raw, codec) is not None:
                return b'', (codec, 'strict'), [(codec, 'strict')]
    if _strict(raw, 'utf-8') is not None:
        return b'', ('utf-8', 'strict'), [('utf-8', 'strict')]
    return b'', _FALLBACK, [_FALLBACK] + [(c, 'strict') for c in _ALTERNATES if _strict(raw, c) is not None]


def decode(raw: bytes):
    """-> (bom, codec, errors, text). Raises ValueError when the bytes cannot be mapped back exactly."""
    bom, (codec, errors), _ = readings(raw)
    return bom, codec, errors, _exact(raw[len(bom):], codec, errors)


def _byte_ranges(body, codec, errors, urls):
    text = body.decode(codec, errors)
    offs, o = [0], 0
    for c in text:
        o += len(c.encode(codec, errors))
        offs.append(o)
    return [(offs[s], offs[e], lab) for s, e, lab in text_ranges(text, urls)]


def scrub_bytes(raw: bytes, key: str = '', json_file: bool = False, stream: bool = False) -> bytes:
    bom, codec, errors, text = decode(raw)
    body = raw[len(bom):]
    scrubbed = _scrub_json(text, key) if json_file else None
    if scrubbed is not None:
        return raw if scrubbed == text else bom + scrubbed.encode(codec, errors)
    ranges = []
    for c, e in readings(raw)[2]:
        ranges += _byte_ranges(body, c, e, stream)
    body = _apply(body, ranges, lambda lab: lab.encode(codec))
    werr = errors if errors != 'strict' else 'surrogateescape'
    out = body.decode(codec, werr)
    if key:
        forms = [key] + ([key[:3] + '…' + key[-3:]] if len(key) > 8 else [])
        for form in forms:
            out = out.replace(form, '***')
            if codec != 'utf-8':
                # the key and its "abc…xyz" form are UTF-8 bytes even inside a GBK file
                try:
                    out = out.replace(form.encode('utf-8').decode(codec, werr), '***')
                except UnicodeDecodeError:
                    pass
    out = re.sub(r'("api_key_masked"\s*:\s*")[^"]*(")', r'\1***\2', out)
    new = bom + out.encode(codec, werr)
    return raw if new == raw else new


def main(folder):
    return _run(Path(folder))


def _run(folder):
    key = os.environ.get('WINQA_MODEL_API_KEY') or os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY', '')
    hits, failed = 0, []
    for p in sorted(folder.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in _SUFFIXES:
            continue
        try:   # R23 #188: read, scrub and write per file; one bad file must not stop the rest
            raw = p.read_bytes()
            out = scrub_bytes(raw, key, json_file=p.suffix.lower() == '.json')
            if out != raw:
                p.write_bytes(out)
                hits += 1
        except Exception as exc:
            rel = scrub_homes(str(p.relative_to(folder)))
            failed.append(rel)
            print(f'redact: ERROR {rel}: {type(exc).__name__}; file left unchanged', file=sys.stderr)
    print(f'redact: rewrote {hits} file(s)' + (f', {len(failed)} failed' if failed else ''))
    if failed:
        raise SystemExit(2)
    return hits


def scrub_stream_bytes(raw: bytes) -> bytes:
    return scrub_bytes(raw, stream=True)


def _stdin():
    """R23 #187: on any error print nothing of the input and exit non-zero (no traceback)."""
    try:
        out = scrub_stream_bytes(sys.stdin.buffer.read())
    except Exception as exc:
        print(f'redact: ERROR {type(exc).__name__}; diagnostics withheld', file=sys.stderr)
        return 3
    sys.stdout.buffer.write(out)
    return 0


if __name__ == '__main__':
    if sys.argv[1:] == ['--stdin']:
        sys.exit(_stdin())
    main(sys.argv[1])
