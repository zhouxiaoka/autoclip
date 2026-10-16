"""The one scrubber for Windows-QA evidence and diagnostics. The other winqa scripts call it instead of keeping
their own rules (scanned by test_r25_247).

Removes, with one rule table in every mode: the real QA key and its app-masked form (exact, from
WINQA_MODEL_API_KEY / callers), generic key shapes (sk-..., Bearer/Authorization/api_key values), values of
credential-named JSON fields (api_key*, authorization, *token, secret, password, cookie), URLs, and personal home
directories (C:\\Users\\x, X$\\Users\\x on UNC shares, /Users/x, /home/x) in the spellings listed below.

Usage: python3 redact.py --stdin [--keys-fd N]  whole stream
       python3 redact.py --lines [--keys-fd N]  line by line (for a live `tee` log)
       Exact keys come from file descriptor N, one per line (R27 #308: never from argv). Without --keys-fd the
       environment variables WINQA_MODEL_API_KEY / AUTOCLIP_QA_DASHSCOPE_KEY are read (pull_run_installer.sh).
       Evidence files are no longer rewritten in place: they leave the test machine only through
       py/export_evidence.py (R27 #312: the old directory / --drop-failed / zip / image mode is gone).

Design (R24/R25): one boundary rule, applied to each reading below, union of the results.
1. Readings. Text: raw; URL-decoded once; after one escape pass; fully decoded (escape layers \\\\ \\/ \\uXXXX %XX
   undone, as repeated left-to-right passes would). Bytes: BOM codec, or utf-8 / gb18030 plus shift_jis and big5;
   plus utf-8 and UTF-16 LE/BE at both byte alignments when a NUL byte is present or a BOM names UTF-16 (R25 #242).
2. Root: a drive letter followed by ':' or '$', separators, 'Users', separators; or '/Users/', '/home/'.
   Case-insensitive. A root right after an ASCII letter or digit continues a word or path and is not one; a POSIX
   root right after '\\' or as a relative './' '../' path is not one either. Anything else before it ('.', '-',
   '_', CJK, quotes) does not protect it (R25 #250).
3. Name: from the raw offset where the name starts, in each participating reading, up to that reading's next
   separator or the end of the line. '.'/'..' segments are skipped.
4. Union: all ranges are merged and replaced (<url> > <user> > ***). When in doubt, mask more.
5. Streams keep their encoding, BOM and line endings.

Known limitation: a home path hidden under three or more mixed escape layers whose intermediate layer is itself
only a partial root (for example a JSON string of a URL-encoded JSON string of a path) may not be recognised; the
readings cover raw, one URL decode, one escape pass and the fully decoded text.
"""
import os, re, sys
from bisect import bisect_right

USER, URLMARK, SECRET = '<user>', '<url>', '***'
_RANK = {URLMARK: 2, USER: 1, SECRET: 0}
_HEX = set('0123456789abcdefABCDEF')
_EOL = '\r\n'
_WIN_SEPS, _POSIX_SEPS = '\\/', '/'
# value group 2 is masked; the prefix stays readable
_SECRET_PATTERNS = [re.compile(r'()(sk-[A-Za-z0-9_\-]{6,})'),
                    re.compile(r'(?i)(authorization["\'=:\s]+)((?:(?:bearer|basic|token)\s+)?(?!\*\*\*(?:[\s"\',]|$))[^\s"\',]+)'),
                    re.compile(r'(?i)(bearer\s+)((?!\*\*\*(?:[\s"\',]|$))[^\s"\',]+)'),
                    re.compile(r'(?i)(api[_-]?key["\'=:\s]+)((?!\*\*\*(?:[\s"\',]|$))[^\s"\',]+)'),
                    re.compile(r'("api_key_masked"\s*:\s*")((?!\*\*\*")[^"]+)')]


def _decoded_view(text, first_pass=None):
    """Logical characters with raw spans after undoing every escape layer (\\\\, \\/, \\uXXXX, %XX), exactly as
    repeated left-to-right passes would, in O(n log n): a later pass can only match next to a character the
    previous pass produced, so each later pass only looks at the <= 5 tokens before each produced one."""
    n = len(text)
    ch, st, en = list(text), list(range(n)), list(range(1, n + 1))
    nxt, prv, alive = list(range(1, n + 1)), list(range(-1, n - 1)), [True] * n

    def hexes(k, count):
        ids = []
        for _ in range(count):
            k = nxt[k]
            if k >= n or ch[k] not in _HEX:
                return None
            ids.append(k)
        return ids

    def match(i):
        if ch[i] == '%':
            ids = hexes(i, 2)
            return (ids, chr(int(ch[ids[0]] + ch[ids[1]], 16))) if ids else None
        if ch[i] != '\\':
            return None
        j = nxt[i]
        if j >= n:
            return None
        if ch[j] in '\\/':
            return [j], ch[j]
        if ch[j] != 'u':
            return None
        ids = hexes(j, 4)
        return ([j] + ids, chr(int(''.join(ch[x] for x in ids), 16))) if ids else None

    def reduce(i, ids, val):
        last = ids[-1]
        for x in ids:
            alive[x] = False
        ch[i], en[i] = val, en[last]
        nxt[i] = nxt[last]
        if nxt[i] < n:
            prv[nxt[i]] = i

    produced, i = [], 0
    while i < n:
        m = match(i)
        if m:
            reduce(i, *m)
            produced.append(i)
        i = nxt[i]
    if first_pass is not None:
        first_pass.append(_walk(ch, st, en, nxt, n))
    while produced:
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
    return _walk(ch, st, en, nxt, n)


def _walk(ch, st, en, nxt, n):
    out_c, out_s, out_e, i = [], [], [], 0
    while i < n:
        out_c.append(ch[i]); out_s.append(st[i]); out_e.append(en[i])
        i = nxt[i]
    return out_c, out_s, out_e


def _percent_view(text):
    """One URL-decoding pass only (%XX), so text escaped inside a query string is read as text."""
    ch, st, en, i, n = [], [], [], 0, len(text)
    while i < n:
        if text[i] == '%' and i + 2 < n and text[i + 1] in _HEX and text[i + 2] in _HEX:
            ch.append(chr(int(text[i + 1:i + 3], 16))); st.append(i); en.append(i + 3); i += 3
        else:
            ch.append(text[i]); st.append(i); en.append(i + 1); i += 1
    return ch, st, en


def _views(text):
    """Readings of one text: raw; URL-decoded once; every escape layer undone."""
    raw = (list(text), list(range(len(text))), list(range(1, len(text) + 1)))
    out = [raw]
    if '%' in text:
        pct = _percent_view(text)
        if len(pct[0]) != len(text):
            out.append(pct)
    first = []
    dec = _decoded_view(text, first)
    if len(dec[0]) == len(text):
        return out
    if len(first[0][0]) != len(dec[0]):
        out.append(first[0])      # one decoding pass: "C:\\u005cUsers\\u005cu0022x" has its root only here
    return out + [dec]


def _relative_dot(ch, k):
    """'./home/x' or '../home/x': a POSIX relative path, not a home root (R25 #250: 'x.C:', 'a-/home' are roots)."""
    if k < 1 or ch[k - 1] != '.':
        return False
    j = k - 1
    while j > 0 and ch[j - 1] == '.':
        j -= 1
    return k - j <= 2 and (j == 0 or not (ch[j - 1].isascii() and ch[j - 1].isalnum()) and ch[j - 1] not in '-_')


def _roots(view):
    """-> [(raw offset where the user name starts, separators)] for every home root in this reading."""
    ch, st, en = view
    n, out = len(ch), []

    def word_at(k, w):
        return k + len(w) <= n and ''.join(ch[k:k + len(w)]).lower() == w

    def skip(j, seps):
        if j >= n or ch[j] not in seps:
            return None
        while j < n and ch[j] in seps:
            j += 1
        return j

    for k in range(n):
        prev = ch[k - 1] if k else ''
        if prev and prev.isascii() and prev.isalnum():
            continue                  # continues an ASCII word or path ("api/home", "xC:")
        if ch[k].isascii() and ch[k].isalpha() and k + 1 < n and ch[k + 1] in ':$':
            j, seps, words = skip(k + 2, _WIN_SEPS), _WIN_SEPS, ('users',)
        elif ch[k] == '/' and prev != '\\' and not _relative_dot(ch, k):
            j, seps, words = k + 1, _POSIX_SEPS, ('users', 'home')
        else:
            continue
        for w in words:
            if j is not None and word_at(j, w):
                s = skip(j + len(w), seps)
                if s is not None and s < n:
                    out.append((st[s], seps))
    return out


def _segment(view, s, seps, own):
    """Raw range of the user name that starts at raw offset s, as this reading sees it: it ends at this
    reading's next separator. A reading takes part when it found this root itself (own) or when its own
    token straddles s (it cannot split there, e.g. "Users\\u5f20"). The range always starts at s."""
    ch, st, en = view
    n = len(ch)
    t = bisect_right(en, s)          # token containing raw offset s
    if t >= n or not (own or st[t] < s):
        return None
    while True:
        e = t
        while e < n and ch[e] not in seps and ch[e] not in _EOL:
            e += 1
        if ''.join(ch[t:e]) in ('.', '..') and e < n and ch[e] in seps:
            t = e
            while t < n and ch[t] in seps:
                t += 1
            continue
        return (max(st[t], s), en[e - 1]) if e > t else None


def _url_ranges(view):
    ch, st, en = view
    n, out, k = len(ch), [], 0
    while k < n:
        if ch[k] in 'hH':
            for p in ('https://', 'http://'):
                if k + len(p) <= n and ''.join(ch[k:k + len(p)]).lower() == p:
                    e = k + len(p)
                    while e < n and not ch[e].isspace():
                        e += 1
                    out.append((st[k], en[e - 1], URLMARK))
                    k = e - 1
                    break
        k += 1
    return out


# R26 #255: one credential-field rule for JSON fields and text ("token=...", "Cookie: ...", '"api_token": 5').
# A field name is split into words (camelCase, '-', '_', '.', spaces) and is a credential field when its last
# words are one of these (an optional trailing "masked" is ignored): api_token, session_token, secret_access_key,
# x-api-key, apiKey, ... but not tokens_used / max_tokens / token_count.
_FIELD_TAIL = re.compile(r'(?:^|_)(?:api_?key|access_?key|secret_?key|private_?key|token|secret|password|passwd|'
                         r'passphrase|cookie|authorization|credentials?|session_?id|signature|sig)(?:_?masked)?$')
_TO_EOL = ('cookie', 'authorization')       # header-style values with spaces: masked to the end of the line
_FIELD_TEXT = re.compile(r'(?<![A-Za-z0-9_\-])(["\']?)([A-Za-z][A-Za-z0-9_.\-]{0,63})\1[ \t]*[:=][ \t]*')
_CLOSE = {'{': '}', '[': ']'}


def _norm_field(name):
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name.strip(' "\''))
    return re.sub(r'[\s.\-]+', '_', s).lower().strip('_')


def is_secret_field(name) -> bool:
    return isinstance(name, str) and bool(_FIELD_TAIL.search(_norm_field(name)))


_TERMINATORS = ',;&<>)}]'


def _field_value(s, a, name):
    """Raw [a, b) of the value that starts at a, or None."""
    v = _field_value_ex(s, a, name)
    return v[:2] if v else None


def _field_value_ex(s, a, name):
    """R29 #316: (a, b, open) of the value that starts at a, or None. Line breaks do not end quoted or bracketed
    values; a value still open at the end of the text is masked to the end (open=True) - never left as plain text.
    Header-style values (cookie, authorization) run to the end of the line plus HTTP folded lines (next line starts
    with a blank); open=True when the text ends right after such a value (a folded line may still follow)."""
    n = len(s)
    if a >= n or s[a] in _EOL:
        return None
    c = s[a]
    if c in '"\'':
        b = a + 1
        while b < n and s[b] != c:
            b += 2 if s[b] == '\\' else 1
        if b >= n:
            return (a + 1, n, True) if n > a + 1 else None
        return (a + 1, b, False) if b > a + 1 else None
    if c in _CLOSE:
        depth, b, quote = 0, a, None
        while b < n:
            ch = s[b]
            if quote:                                   # R27 #303: a } or ] inside a string does not close
                if ch == '\\':
                    b += 1
                elif ch == quote:
                    quote = None
            elif ch in '"\'':
                quote = ch
            else:
                depth += 1 if ch == c else -1 if ch == _CLOSE[c] else 0
            b += 1
            if depth == 0 and not quote:
                return a, min(b, n), False
        return a, n, True
    b = a
    if any(_norm_field(name).endswith(w) for w in _TO_EOL):
        while True:
            while b < n and s[b] not in _EOL:
                b += 1
            e = b + (2 if s[b:b + 2] == '\r\n' else 1 if b < n else 0)
            if e < n and s[e] in ' \t':                  # HTTP folded continuation line
                b = e
                continue
            break
        open_ = s[b:].strip('\r\n') == ''
        while b > a and s[b - 1] in ' \t':
            b -= 1
        return (a, b, open_) if b > a else None
    if c in _TERMINATORS:                             # R29 #327: a value starting with a terminator is still a value
        while b < n and not s[b].isspace():
            b += 1
        return (a, b, False) if b > a else None
    while b < n and not s[b].isspace() and s[b] not in ',;&"\'<>)}]':
        b += 1
    return (a, b, False) if b > a else None


def _field_ranges(s):
    out, until = [], -1
    for m in _FIELD_TEXT.finditer(s):
        # a field inside a value already being masked whole adds nothing (and would make long values quadratic)
        if m.start() < until or not is_secret_field(m.group(2)):
            continue
        v = _field_value(s, m.end(), m.group(2))
        # R27 #303: only a value that IS a mark is left alone; '***VISIBLE' is masked like any other value
        if v and s[v[0]:v[1]] not in (SECRET, URLMARK, USER):
            out.append(v)
            until = v[1]
    return out


def _secret_ranges(view, keys):
    ch, st, en = view
    s = ''.join(ch)
    out = [(st[a], en[b - 1], SECRET) for a, b in _field_ranges(s)]
    for key in keys:
        i = s.find(key)
        while key and i >= 0:
            out.append((st[i], en[i + len(key) - 1], SECRET))
            i = s.find(key, i + 1)
    for pat in _SECRET_PATTERNS:
        for m in pat.finditer(s):
            a, b = m.span(2)
            if b > a:
                out.append((st[a], en[b - 1], SECRET))
    return out


def _key_forms(keys):
    out = []
    for k in keys or ():
        if k:
            out.append(k)
            if len(k) > 8:
                out.append(k[:3] + '…' + k[-3:])
    return out


def text_ranges(text, keys=()):
    """Raw ranges to mask in text: the one boundary rule, every reading, union."""
    views = _views(text)
    roots = [set(_roots(v)) for v in views]
    starts = set().union(*roots)
    out = []
    for v, own in zip(views, roots):
        for s, seps in starts:
            seg = _segment(v, s, seps, (s, seps) in own)
            if seg:
                out.append(seg + (USER,))
        out += _url_ranges(v)
        out += _secret_ranges(v, _key_forms(keys))
    return out


def _merge(ranges):
    merged = []
    for s, e, lab in sorted(ranges, key=lambda r: (r[0], r[1])):
        if merged and s < merged[-1][1]:
            ps, pe, pl = merged[-1]
            merged[-1] = (ps, max(pe, e), pl if _RANK[pl] >= _RANK[lab] else lab)
        else:
            merged.append((s, e, lab))
    return merged


def _apply(seq, ranges, mark):
    out, last = [], 0
    for s, e, lab in _merge(ranges):
        out.append(seq[last:s]); out.append(mark(lab)); last = e
    out.append(seq[last:])
    return seq[:0].join(out)


def scrub(text: str, keys=()) -> str:
    """The single text entry point: one rule table (keys, key shapes, home directories, URLs) for every caller."""
    return _apply(text, text_ranges(text, keys), str)


def scrub_homes(text: str) -> str:
    return scrub(text)


def scrub_stream(text: str) -> str:
    return scrub(text)


def scrub_diagnostic(text: str, keys=()) -> str:
    """Everything a QA helper writes or prints (winqa_probe / winqa_real save() and log lines)."""
    return scrub(text, keys=keys)


def scrub_obj(o, keys=(), field=None):
    """Every string of a JSON-like value (dict keys included); values of credential fields (R25 #243, R26 #255:
    the same field rule as text, any value type: numbers, lists and objects too) are masked whole. Valid JSON."""
    if field is not None and is_secret_field(field) and o not in (None, '', [], {}):
        return SECRET
    if isinstance(o, dict):
        out = {}   # R20 #119: two home paths used as keys may scrub to one key; keep both.
        for k, v in o.items():
            ck = scrub_obj(k, keys) if isinstance(k, str) else k
            if ck in out:
                i = 2
                while f'{ck}#{i}' in out:
                    i += 1
                ck = f'{ck}#{i}'
            out[ck] = scrub_obj(v, keys, k if isinstance(k, str) else None)
        return out
    if isinstance(o, (list, tuple)):
        return [scrub_obj(x, keys) for x in o]
    if isinstance(o, str):
        return scrub(o, keys)
    return o


_BOMS = [(b'\xef\xbb\xbf', 'utf-8', 'surrogateescape'), (b'\xff\xfe\x00\x00', 'utf-32-le', 'surrogatepass'),
         (b'\x00\x00\xfe\xff', 'utf-32-be', 'surrogatepass'), (b'\xff\xfe', 'utf-16-le', 'surrogatepass'),
         (b'\xfe\xff', 'utf-16-be', 'surrogatepass')]
_FALLBACK = ('gb18030', 'surrogateescape')      # reads every byte string; written back 1:1
_ALTERNATES = ('shift_jis', 'big5')             # extra readings of non-UTF-8 bytes (#181)


def _exact(body, codec, errors):
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
    """-> (bom, (codec, errors) for writing back, [(codec, errors, byte offset), ...] every reading to mask)."""
    for bom, codec, errors in _BOMS:
        if raw.startswith(bom):
            body = raw[len(bom):]
            reads = [(codec, errors, 0)]
            if b'\x00' in body or not codec.startswith('utf-8'):   # R25 #242: mixed runs after a BOM too
                reads += [('utf-8', 'surrogateescape', 0)]
                reads += [(c, 'surrogatepass', off) for c in ('utf-16-le', 'utf-16-be') for off in (0, 1)]
            return bom, (codec, errors), list(dict.fromkeys(reads))
    if raw and raw.count(0) * 4 >= len(raw) and len(raw) % 2 == 0:
        odd = raw[1::2].count(0) >= raw[0::2].count(0)
        prim = next((c for c in (('utf-16-le', 'utf-16-be') if odd else ('utf-16-be', 'utf-16-le'))
                     if _strict(raw, c) is not None), None)
    else:
        prim = None
    if prim:
        primary = (prim, 'strict')
    elif _strict(raw, 'utf-8') is not None:
        primary = ('utf-8', 'strict')
    else:
        primary = _FALLBACK
    reads = [primary + (0,)]
    if primary[0] != 'utf-8' and not primary[0].startswith('utf-16'):
        reads += [(c, 'strict', 0) for c in _ALTERNATES if _strict(raw, c) is not None]
    if b'\x00' in raw:   # R24 #214: a UTF-16 run (PS 5.1 `>>`) inside another encoding, or the reverse
        reads += [('utf-8', 'surrogateescape', 0)]
        reads += [(c, 'surrogatepass', off) for c in ('utf-16-le', 'utf-16-be') for off in (0, 1)]
    return b'', primary, list(dict.fromkeys(reads))


def decode(raw: bytes):
    bom, (codec, errors), _ = readings(raw)
    return bom, codec, errors, _exact(raw[len(bom):], codec, errors)


def _width(codec):
    return 4 if 'utf-32' in codec else 2 if 'utf-16' in codec else 1


def _byte_ranges(body, codec, errors, off, keys):
    part = body[off:]
    if codec.startswith('utf-16') and errors == 'surrogatepass':
        part = part[:len(part) // 2 * 2]
        text = part.decode(codec, errors)
    else:
        text = part.decode(codec, errors)
    offs, o = [off], off
    for c in text:
        o += len(c.encode(codec, errors))
        offs.append(o)
    # the key is UTF-8 even inside a file in another encoding: also look for its UTF-8 bytes read in this codec
    forms = _key_forms(keys)
    keys = forms + [f.encode('utf-8').decode(codec, 'surrogateescape' if 'utf-16' not in codec else 'ignore')
                    for f in forms if codec != 'utf-8']
    return [(offs[s], offs[e], (lab, codec, off)) for s, e, lab in text_ranges(text, keys)]


def scrub_bytes(raw: bytes, key: str = '', stream: bool = True, keys=()) -> bytes:
    """Byte stream (live log line or whole stream) in its own encoding; every reading masked."""
    keys = [k for k in ([key] if key else []) + list(keys) if k]
    bom, codec, errors, text = decode(raw)
    body = raw[len(bom):]
    ranges = []
    for c, e, off in readings(raw)[2]:
        ranges += _byte_ranges(body, c, e, off, keys)
    # A reading of the same unit width shifted by one byte sees the same characters one byte early; where the
    # file's own reading already masks there it adds nothing but a widened edge, so it is not used there.
    own = [(s, t, lab) for s, t, (lab, c, off) in ranges if (c, off) == (codec, 0)]
    own = [(s, t) for s, t, _ in _merge(own)]
    starts = [s for s, _ in own]

    def covered(r):
        i = bisect_right(starts, r[1] - 1) - 1   # last own range starting before r ends
        return i >= 0 and own[i][1] > r[0]
    w0 = _width(codec)
    ranges = [r for r in ranges if not (w0 > 1 and _width(r[2][1]) == w0 and r[2][2] % w0 and covered(r))]
    merged = []   # [start, end, label, (codec, offset)]: written in the file's own codec when that reading saw it
    for s, t, (lab, c, off) in sorted(ranges, key=lambda r: (r[0], r[1])):
        if merged and s < merged[-1][1]:
            m = merged[-1]
            m[1] = max(m[1], t)
            m[2] = m[2] if _RANK[m[2]] >= _RANK[lab] else lab
            m[3] = (c, off) if (c, off) == (codec, 0) else m[3]
        else:
            merged.append([s, t, lab, (c, off)])
    out, last = [], 0
    for s, t, lab, (c, off) in merged:
        w = _width(c)   # whole code units of the codec written: a byte range is widened to the units it touches
        s, t = max(last, s - (s - off) % w), min(len(body), t + (-(t - off)) % w)
        out.append(body[last:s]); out.append(lab.encode(c)); last = t
    out.append(body[last:])
    new = bom + b''.join(out)
    return raw if new == raw else new


def scrub_stream_bytes(raw: bytes) -> bytes:
    return scrub_bytes(raw, stream=True)


_FD_KEYS = None


def _env_keys():
    if _FD_KEYS is not None:
        return _FD_KEYS
    return [k for k in (os.environ.get('WINQA_MODEL_API_KEY'), os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY')) if k]


def _read_fd_keys(fd: int):
    with os.fdopen(fd, 'r', encoding='utf-8', errors='strict') as fh:
        return [k for k in (line.rstrip('\r\n') for line in fh) if k]


# ---------------------------------------------------------------------------------------------------------------
# #414 design v5 part A: ONE streaming path for every live and whole-stream caller (--stdin, --lines, logpipe.py).
#   bytes -> Decoder (encoding fixed once at the start, incremental) -> line splitter (\n, \r\n, chunk-independent)
#         -> Scanner (line by line, carries only a small state across lines) -> encoder (input encoding) -> out
# An unclosed credential value only sets state; nothing is buffered or rescanned (#383), so each line costs
# O(line length). The state is judged on decoded text only, so UTF-16 input cannot slip past it (#382).
# ---------------------------------------------------------------------------------------------------------------
HOLD_LIMIT = 1 << 20      # an unclosed value longer than this: every later line is masked whole until EOF
MAX_LINE = 1 << 16        # a longer line goes to the scanner in 64 KiB pieces, state carried (bounded memory)
ENC_MARK = '[REDACTED:encoding]'
STATS = {'scanned': 0}    # characters handed to the scanner (linearity is asserted on this counter, M12)
E_USAGE, E_INTERNAL = 2, 3
_STREAM_BOMS = [(b'\xef\xbb\xbf', 'utf-8'), (b'\xff\xfe\x00\x00', 'utf-32-le'), (b'\x00\x00\xfe\xff', 'utf-32-be'),
                (b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be')]


def key_byte_forms(keys):
    """I-A7: every key form (exact + app-masked) as UTF-8, UTF-16LE and UTF-16BE bytes."""
    return [f.encode(c) for f in _key_forms(keys) for c in ('utf-8', 'utf-16-le', 'utf-16-be')]


def key_leak(data: bytes, keys) -> bool:
    """I-A7 check, shared by the stream writer and export_evidence (one function, design review M-2c)."""
    return any(f and f in data for f in key_byte_forms(keys))


def _quote_state(s, a, q):
    esc, b = False, a
    while b < len(s):
        c = s[b]
        if esc:
            esc = False
        elif c == '\\':
            esc = True
        elif c == q:
            return None, b
        b += 1
    return ('Q', q, esc), len(s)


def _struct_state(s, a, opener, depth=0, quote=None, esc=False):
    closer, b = _CLOSE[opener], a
    while b < len(s):
        c = s[b]
        if quote:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == quote:
                quote = None
        elif c in '"\'':
            quote = c
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return None, b + 1
        b += 1
    return ('S', opener, depth, quote, esc), len(s)


def _is_header(name):
    return any(_norm_field(name).endswith(w) for w in _TO_EOL)


def end_state(s):
    """State left at the end of one line scanned from NORMAL. Quotes in ordinary text are not tracked (M5): only
    the value of a credential field can open a state. A credential field with nothing after it opens PENDING (M1):
    its value is the first token of the next line."""
    for view in _views(s):
        st = _end_state_view(''.join(view[0]))
        if st:
            return st
    return None


def _end_state_view(s):
    until, state = -1, None
    for m in _FIELD_TEXT.finditer(s):
        if m.start() < until or not is_secret_field(m.group(2)):
            continue
        name, a = m.group(2), m.end()
        if s[a:].strip(' \t\r') == '':
            return ('P', name)
        c = s[a]
        if c in '"\'':
            st, until = _quote_state(s, a + 1, c)
        elif c in _CLOSE:
            st, until = _struct_state(s, a, c)
        elif _is_header(name):
            return ('H',)
        else:
            v = _field_value(s, a, name)
            st, until = None, (v[1] if v else a)
        state = st
        if st:
            return st
    return state


class Scanner:
    """Line-by-line credential scanner. State across lines: None (NORMAL), ('Q', quote, escaped),
    ('S', opener, depth, quote, escaped), ('H',) header folding, ('P', field) waiting for a value. Each line is
    output as soon as it arrives: the part inside an open value becomes ***; nothing is held back or rescanned."""

    def __init__(self, keys):
        self.keys, self.st, self.masked, self.to_eof, self.unclosed_seen = list(keys), None, 0, False, False

    def _hold(self, s, st):
        self.st = st
        self.masked += len(s)
        if self.masked > HOLD_LIMIT:
            self.to_eof = True
        return SECRET if s else ''

    def normal(self, s):
        out = scrub(s, self.keys)
        self.st = end_state(s)
        self.masked = len(s) if self.st and self.st[0] != 'P' else 0   # the open part counts toward the limit
        if self.masked > HOLD_LIMIT:
            self.to_eof = True
        return out

    def line(self, s):
        STATS['scanned'] += len(s)
        if self.to_eof:
            return SECRET if s else ''
        st = self.st
        if st is None:
            return self.normal(s)
        kind = st[0]
        if kind == 'Q':
            if st[2]:                        # the previous line ended with a backslash: this char is escaped
                if not s:
                    return self._hold(s, ('Q', st[1], False))
                new, b = _quote_state(s, 1, st[1])
            else:
                new, b = _quote_state(s, 0, st[1])
            if new:
                return self._hold(s, new)
            self.st, self.masked = None, 0
            return SECRET + self.normal(s[b:])
        if kind == 'S':
            new, b = _struct_state(s, 0, st[1], st[2], st[3], st[4])
            if new:
                return self._hold(s, new)
            self.st, self.masked = None, 0
            return SECRET + self.normal(s[b:])
        if kind == 'H':
            if s[:1] in (' ', '\t'):         # HTTP folded continuation
                return self._hold(s, st)
            return self.normal(s)
        # PENDING: the value of a credential field whose line ended right after the separator
        name = st[1]
        if s.strip(' \t\r') == '':
            if _is_header(name):
                self.st = None
            return s
        if _is_header(name):
            if s[:1] in (' ', '\t'):
                return self._hold(s, ('H',))
            return self.normal(s)
        a = len(s) - len(s.lstrip(' \t'))
        c = s[a]
        if c in '"\'':
            new, b = _quote_state(s, a + 1, c)
        elif c in _CLOSE:
            new, b = _struct_state(s, a, c)
        else:
            v = _field_value(s, a, name)
            new, b = None, (v[1] if v else len(s))
        if new:
            return s[:a] + self._hold(s[a:], new)
        self.st, self.masked = None, 0
        return s[:a] + SECRET + self.normal(s[b:] if c not in '"\'' else s[b:])


def _utf16_suspect(line):
    """In a UTF-16 stream: text that is really another encoding (shifted by a byte, or 8-bit text appended)."""
    if not line:
        return False
    if any(0xD800 <= ord(c) <= 0xDFFF for c in line):
        return True
    swapped = sum(1 for c in line if ord(c) > 0xFF and ord(c) & 0xFF == 0)
    if swapped >= 2:
        return True
    return len(line) >= 4 and all(0x20 <= ord(c) >> 8 <= 0x7e and 0x09 <= ord(c) & 0xFF <= 0x7e for c in line)


class Stream:
    """Decoder + splitter + scanner + encoder for one byte stream. feed() any chunk sizes; close() at EOF.
    Output bytes do not depend on how the input was chunked (I-A1)."""

    def __init__(self, keys, write):
        self.keys, self.write, self.sc = list(keys), write, Scanner(keys)
        self.codec, self.errors, self.head, self.dec, self.pend, self.enc_lines = None, None, b'', None, '', 0

    def _pick(self, final):
        data = self.head
        for bom, codec in _STREAM_BOMS:
            if data.startswith(bom):
                if not final and len(data) < 4 and bom == b'\xff\xfe':
                    return False             # could still be a UTF-32LE BOM
                self._set(codec, bom)
                return True
        if not final and len(data) < 4 and any(b.startswith(data) for b, _ in _STREAM_BOMS):
            return False                     # only a BOM prefix so far (never waits on ordinary text, M14)
        if not final and len(data) < 4:
            return False                     # 4 bytes decide (a 10-byte first line is never held, M14)
        data = data[:4]                      # only the first 4 bytes decide: the choice is chunk-independent
        if len(data) >= 2 and data.count(0) * 4 >= len(data):
            self._set('utf-16-le' if data[1::2].count(0) >= data[0::2].count(0) else 'utf-16-be', b'')
        else:
            self._set('utf-8', b'')
        return True

    def _set(self, codec, bom):
        import codecs
        self.codec, self.errors = codec, ('surrogateescape' if codec == 'utf-8' else 'surrogatepass')
        self.dec = codecs.getincrementaldecoder(codec)(self.errors)
        data, self.head = self.head[len(bom):], None
        if bom:
            self.write(bom)
        self._text(self.dec.decode(data))

    def feed(self, data: bytes):
        if self.codec is None:
            self.head += data
            self._pick(False)
            return
        self._text(self.dec.decode(data))

    def close(self):
        if self.codec is None:
            self._pick(True)
        self._text(self.dec.decode(b'', final=True))
        if self.pend:
            self._line(self.pend, '')
            self.pend = ''

    def _text(self, t):
        if not t:
            return
        self.pend += t
        while True:
            i = self.pend.find('\n')
            if i < 0:
                break
            line, self.pend = self.pend[:i], self.pend[i + 1:]
            if line.endswith('\r'):
                self._line(line[:-1], '\r\n')
            else:
                self._line(line, '\n')
        while len(self.pend) > MAX_LINE:
            piece, self.pend = self.pend[:MAX_LINE], self.pend[MAX_LINE:]
            self._line(piece, '')

    def _conflict(self, line):
        if self.codec == 'utf-8':
            return '\x00' in line
        if self.codec.startswith('utf-16'):
            return _utf16_suspect(line)
        return False

    def _line(self, line, eol):
        if self._conflict(line):
            # M2 (PM ruling): a line whose encoding switched is output only as the marker; it may still open state
            self.enc_lines += 1
            STATS['scanned'] += len(line)
            st = end_state(line.replace('\x00', '')) if self.sc.st is None else None
            if st:
                self.sc.st, self.sc.masked = st, 0
            out = ENC_MARK + eol
        elif self.codec == 'utf-8' and any('\udc80' <= c <= '\udcff' for c in line):
            # bytes that are not UTF-8 (gb18030, shift_jis...): the byte-level reader masks this one line
            before = self.sc.st
            text = self.sc.line(line)
            if before is None and self.sc.st is None:
                data = scrub_bytes(line.encode('utf-8', 'surrogateescape'), keys=self.keys) + eol.encode()
                self._emit(data, eol)
                return
            out = text + eol
        else:
            out = self.sc.line(line) + eol
        self._emit(out.encode(self.codec, self.errors), eol)

    def _emit(self, data, eol):
        if key_leak(data, self.keys):        # I-A7: no output in any mode carries a key in any encoding
            data = (SECRET + eol).encode(self.codec, self.errors)
        self.write(data)


def run(src_fd: int, out, keys, flush: bool) -> int:
    """The one entry point (--stdin, --lines, logpipe.py). Exit codes: 0 done (warnings only on stderr),
    3 internal error: nothing more is written, stderr gets only `WINQA_E_REDACT <stage>`."""
    stage = ['decode']

    def write(b):
        stage[0] = 'write'
        out.write(b)
        if flush:
            out.flush()
        stage[0] = 'scan'
    try:
        s = Stream(keys, write)
        while True:
            stage[0] = 'read'
            chunk = os.read(src_fd, 65536)
            stage[0] = 'scan'
            if not chunk:
                break
            s.feed(chunk)
        s.close()
        stage[0] = 'write'
        out.flush()
    except Exception:
        try:
            sys.stderr.write(f'WINQA_E_REDACT {stage[0]}\n')
        except Exception:
            pass
        return E_INTERNAL
    if s.sc.to_eof:
        sys.stderr.write('WINQA_W_REDACT_MASK_EOF\n')
    elif s.sc.st is not None and s.sc.st[0] in ('Q', 'S'):
        sys.stderr.write('WINQA_W_REDACT_UNCLOSED\n')
    return 0


def keys_ok(keys):
    return all('\n' not in k and '\r' not in k for k in keys)


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--keys-fd' in a:
        i = a.index('--keys-fd')
        try:
            _FD_KEYS = _read_fd_keys(int(a[i + 1]))
        except Exception as exc:
            print(f'redact: ERROR reading keys ({type(exc).__name__})', file=sys.stderr)
            sys.exit(E_USAGE)
        del a[i:i + 2]
    if a in (['--stdin'], ['--lines']):
        keys = _env_keys()
        if not keys_ok(keys):
            print('redact: ERROR key contains a line break', file=sys.stderr)
            sys.exit(E_USAGE)
        rc = run(0, sys.stdout.buffer, keys, flush=a == ['--lines'])
        if os.environ.get('WINQA_REDACT_STATS') == '1':
            sys.stderr.write(f"WINQA_STATS scanned={STATS['scanned']}\n")
        if rc:
            os.dup2(os.open(os.devnull, os.O_WRONLY), 1)     # nothing more reaches the old stdout at exit
        sys.exit(rc)
    print(__doc__.split('Usage: ')[1].split('\n\n')[0], file=sys.stderr)
    sys.exit(E_USAGE)
