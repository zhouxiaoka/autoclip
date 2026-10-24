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

Design (R24/R25): one boundary rule, applied to each reading of a decoded text, union of the results.
1. Readings of a text: raw; URL-decoded once; after one escape pass; fully decoded (escape layers \\\\ \\/ \\uXXXX %XX
   undone, as repeated left-to-right passes would).
2. Root: a drive letter followed by ':' or '$', separators, 'Users', separators; or '/Users/', '/home/'.
   Case-insensitive. A root right after an ASCII letter or digit continues a word or path and is not one; a POSIX
   root right after '\\' or as a relative './' '../' path is not one either. Anything else before it ('.', '-',
   '_', CJK, quotes) does not protect it (R25 #250).
3. Name: from the raw offset where the name starts, in each participating reading, up to that reading's next
   separator or the end of the line. '.'/'..' segments are skipped.
4. Union: all ranges are merged and replaced (<url> > <user> > ***). When in doubt, mask more.
5. Bytes (#414 R31): one streaming path, Stream below. UTF-8, UTF-16LE and UTF-16BE (BOM or NUL pattern) are
   decoded strictly line by line; a line in any other encoding (GBK, Shift_JIS, Big5, broken bytes) or misaligned
   is written only as [REDACTED:encoding], a line longer than 64 KiB only as [REDACTED:long-line <n>B]. Streams keep
   their encoding, BOM and line endings.

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


_FD_KEYS = None


def _env_keys():
    if _FD_KEYS is not None:
        return _FD_KEYS
    return [k for k in (os.environ.get('WINQA_MODEL_API_KEY'), os.environ.get('AUTOCLIP_QA_DASHSCOPE_KEY')) if k]


def _read_fd_keys(fd: int):
    with os.fdopen(fd, 'r', encoding='utf-8', errors='strict') as fh:
        return [k for k in (line.rstrip('\r\n') for line in fh) if k]


# ---------------------------------------------------------------------------------------------------------------
# #414 R31: ONE streaming path for every live and whole-stream caller (--stdin, --lines, logpipe.py).
#   bytes -> framer (byte level, current encoding E) -> line classifier -> strict decode -> Machine -> encode in E
# The framer splits on the newline of E. In a UTF-16 stream a 0x0A / 0x0D byte in the high half of a code unit is a
# stray newline (I431): the bytes before it are one line written only as [REDACTED:encoding], and the encoding of
# the bytes after it is decided again. A line that is not E (NULs in UTF-8, odd length or invalid UTF-16, invalid
# UTF-8) is written only as [REDACTED:encoding]. Every UTF-16 line is scanned a second time as its raw bytes with the
# NULs removed (fail closed). A line longer than MAX_LINE bytes is never output in pieces: it is written once, as
# [REDACTED:long-line <n>B], when its newline arrives (I430); the Machine still reads it, so the state is exact.
# ---------------------------------------------------------------------------------------------------------------
HOLD_LIMIT = 1 << 20      # an unclosed value longer than this: every later line is masked whole until EOF
MAX_LINE = 1 << 16        # a longer line is masked whole (bounded memory, nothing output before its end)
ENC_MARK = '[REDACTED:encoding]'
STATS = {'scanned': 0}    # characters the Machine actually examined (linearity is asserted on this counter, I470)
E_USAGE, E_INTERNAL = 2, 3
_U8, _LE, _BE = 'utf-8', 'utf-16-le', 'utf-16-be'
_BOM_OF = [(b'\xef\xbb\xbf', _U8), (b'\xff\xfe', _LE), (b'\xfe\xff', _BE)]
# first aligned code unit that ends a line: an aligned "\n" or a stray 0x0A / 0x0D in the high byte (I431)
_UNIT_END = {_LE: re.compile(rb'(?s)(?:..)*?(?:\n\x00|.[\n\r])'), _BE: re.compile(rb'(?s)(?:..)*?(?:\x00\n|[\n\r].)')}
_CARRY = 160              # a field name + separator straddling two pieces of a long line is still seen


def key_byte_forms(keys):
    """I-A7: every key form (exact + app-masked) as UTF-8, UTF-16LE and UTF-16BE bytes."""
    return [f.encode(c) for f in _key_forms(keys) for c in ('utf-8', 'utf-16-le', 'utf-16-be')]


def key_leak(data: bytes, keys) -> bool:
    """I-A7 check, shared by the stream writer and export_evidence (one function, design review M-2c)."""
    return any(f and f in data for f in key_byte_forms(keys))


def _is_header(name):
    return any(_norm_field(name).endswith(w) for w in _TO_EOL)


def _blank_to(s, a):
    """Index of the first character at or after a that is not ' \\t\\r'. Skips by index (I470: no suffix copies)."""
    j = a
    while j < len(s) and s[j] in ' \t\r':
        j += 1
    STATS['scanned'] += j - a
    return j


def _close(st, s, b):
    """Advance an open value (Q or S) over s from b. -> (None, index where it closed) or (state, len(s))."""
    n, start = len(s), b
    if st[0] == 'Q':
        q, esc = st[1], st[2]
        while b < n:
            c = s[b]
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == q:
                STATS['scanned'] += b - start
                return None, b
            b += 1
        STATS['scanned'] += n - start
        return ('Q', q, esc), n
    opener, depth, quote, esc = st[1], st[2], st[3], st[4]
    closer = _CLOSE[opener]
    while b < n:
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
                STATS['scanned'] += b + 1 - start
                return None, b + 1
        b += 1
    STATS['scanned'] += n - start
    return ('S', opener, depth, quote, esc), n


def _value_state(s, a, name):
    """A credential value starts at a. -> (state, index after it): state None when it closed on this line."""
    c = s[a]
    if c in '"\'':
        return _close(('Q', c, False), s, a + 1)
    if c in _CLOSE:
        return _close(('S', c, 0, None, False), s, a)
    if _is_header(name):
        return ('H',), len(s)
    v = _field_value(s, a, name)
    b = v[1] if v else a
    STATS['scanned'] += b - a
    return None, b


def _advance(s, i=0, floor=0):
    """The state machine in NORMAL from s[i:]: the first credential value left open at the end of s, else None.
    States: None (N), ('Q', quote, esc), ('S', opener, depth, quote, esc), ('H',) header folding, ('P', name) value
    not started yet. Quotes in ordinary text open nothing (M5). Field matches ending at or before floor were already
    seen by the previous piece of a long line."""
    n = len(s)
    while i < n:
        m = _FIELD_TEXT.search(s, i)
        if not m:
            STATS['scanned'] += n - i
            return None
        STATS['scanned'] += m.end() - i
        i = m.end()
        if i <= floor or not is_secret_field(m.group(2)):
            continue
        if _blank_to(s, i) >= n:
            return ('P', m.group(2))
        st, i = _value_state(s, i, m.group(2))
        if st:
            return st
    return None


def _end_state(s):
    for view in _views(s):
        st = _advance(''.join(view[0]))
        if st:
            return st
    return None


class Machine:
    """Line-by-line credential state machine. Each line is output as soon as it arrives: the part inside an open
    value becomes ***; nothing is held back or rescanned. text_ranges masks inside one line."""

    def __init__(self, keys):
        self.keys, self.st, self.masked, self.to_eof, self.carry = list(keys), None, 0, False, None

    def _hold(self, n, st):
        self.st = st
        self.masked += n
        if self.masked > HOLD_LIMIT:
            self.to_eof = True

    def _start(self, s):
        """Line start in the current state. -> ('hold', None) the whole line is inside a value; ('blank', None) a
        pending value whose line is blank (output as is); ('normal', (prefix, b)) mask s[:b] as prefix, then NORMAL."""
        st = self.st
        if st is None:
            return 'normal', ('', 0)
        kind = st[0]
        if kind in 'QS':
            new, b = _close(st, s, 0)
            if new:
                self._hold(len(s), new)
                return 'hold', None
            return 'normal', (SECRET, b)
        if kind == 'H':
            if s[:1] in (' ', '\t'):          # HTTP folded continuation
                self._hold(len(s), st)
                return 'hold', None
            return 'normal', ('', 0)
        name = st[1]                           # PENDING: the value is the first token of this line (M1)
        if _blank_to(s, 0) >= len(s):
            if _is_header(name):
                self.st = None
            return 'blank', None
        if _is_header(name):
            if s[:1] in (' ', '\t'):
                self._hold(len(s), ('H',))
                return 'hold', None
            return 'normal', ('', 0)
        a = 0
        while s[a] in ' \t':
            a += 1
        new, b = _value_state(s, a, name)
        if new:
            self._hold(len(s) - a, new)
            return 'hold', a
        return 'normal', (s[:a] + SECRET, b)

    def line(self, s):
        if self.to_eof:
            STATS['scanned'] += len(s)
            return SECRET if s else ''
        kind, arg = self._start(s)
        if kind == 'hold':
            return (s[:arg] if arg else '') + (SECRET if s[arg or 0:] else '')
        if kind == 'blank':
            return s
        prefix, b = arg
        rest = s[b:] if b else s
        out = prefix + scrub(rest, self.keys)
        self.st = _end_state(rest)
        self.masked = len(rest) if self.st and self.st[0] != 'P' else 0   # the open part counts toward the limit
        if self.masked > HOLD_LIMIT:
            self.to_eof = True
        return out

    def piece(self, t, first):
        """Part of a long line that is never output (I430): only the state advances. A field name straddling two
        pieces is seen through a small carried tail."""
        if self.to_eof:
            return
        if first:
            self.carry = None
            kind, arg = self._start(t)
            if kind != 'normal':
                return
            self.st, b = _advance(t, arg[1]), 0
        elif self.st is None:
            s = (self.carry or '') + t
            self.st = _advance(s, len(self.carry or ''), len(self.carry or ''))
            t = s
        elif self.st[0] in 'QS':
            new, b = _close(self.st, t, 0)
            self.st = new if new else _advance(t, b)
        elif self.st[0] == 'P':
            j = _blank_to(t, 0)
            if j < len(t):
                st, b = _value_state(t, j, self.st[1])
                self.st = st if st else _advance(t, b)
        if self.st and self.st[0] not in ('P',):
            self._hold(len(t), self.st)
        self.carry = t[-_CARRY:]

    def mark(self, view):
        """A line written only as a marker: it can still open a value (read conservatively, NULs removed)."""
        STATS['scanned'] += len(view)
        if self.to_eof:
            return
        if self.st is None:
            self.st, self.masked = _end_state(view), 0
        elif self.st[0] != 'P':
            self._hold(len(view), self.st)


def _byte_view(data: bytes) -> str:
    return data.replace(b'\x00', b'').decode('latin-1')


class Stream:
    """Framer + classifier + Machine + encoder for one byte stream. feed() any chunk sizes; close() at EOF.
    Output bytes do not depend on how the input was chunked (I-A1)."""

    def __init__(self, keys, write):
        self.keys, self.write, self.sc = list(keys), write, Machine(keys)
        self.enc, self.first, self.buf, self.pos = None, True, b'', 0
        self.long, self.ldec, self.truncated, self.enc_lines, self._final = None, None, False, 0, False
        self.half = False                      # the line right after a stray newline is misaligned: marker only

    # ---- encoding decision: at the start (BOM first) and again after a stray newline
    def _pick(self, final):
        data = self.buf
        if self.first:
            for bom, enc in _BOM_OF:
                if data.startswith(bom):
                    self.write(bom)
                    self.buf, self.enc, self.first = data[len(bom):], enc, False
                    return True
            if not final and any(b.startswith(data) for b, _ in _BOM_OF):
                return False                   # only a BOM prefix so far
        nl = data.find(b'\n', 2, 4)          # I472: a newline after >= 2 bytes decides at once ("ok\n")
        if not final and nl < 0 and len(data) < 4:
            return False                       # otherwise 4 bytes do (a UTF-16 unit may hold 0x0A)
        sample = data[:nl + 1 if 0 <= nl < 4 else 4]
        if len(sample) >= 2 and sample.count(0):
            self.enc = _LE if sample[1::2].count(0) >= sample[0::2].count(0) else _BE
        else:
            self.enc = _U8
        self.first = False
        return True

    def _find(self):
        """-> (line end, next start, eol, stray) for the first line in buf, or None."""
        buf = self.buf
        if self.enc == _U8:
            i = buf.find(b'\n', self.pos)
            if i < 0:
                self.pos = max(len(buf) - 1, 0)
                return None
            e = i - 1 if i and buf[i - 1] == 0x0D else i
            return e, i + 1, '\r\n' if e < i else '\n', False
        m = _UNIT_END[self.enc].match(buf, self.pos)
        if not m:
            self.pos = len(buf) & ~1
            return None
        u = m.end() - 2                        # the unit that ends the line
        hi = u + 1 if self.enc == _LE else u
        if (self.enc == _LE and buf[u:u + 2] == b'\n\x00') or (self.enc == _BE and buf[u:u + 2] == b'\x00\n'):
            cr = b'\r\x00' if self.enc == _LE else b'\x00\r'
            e = u - 2 if u >= 2 and buf[u - 2:u] == cr else u
            return e, u + 2, '\r\n' if e < u else '\n', False
        # stray newline byte in the high half of a unit (I431)
        if buf[hi] == 0x0D:
            if hi + 1 >= len(buf):
                if not self._final:
                    self.pos = u
                    return None
                return hi, hi + 1, '\n', True
            if buf[hi + 1] == 0x0A:
                return hi, hi + 2, '\r\n', True
        return hi, hi + 1, '\n', True

    def _pump(self, final):
        self._final = final
        while True:
            if self.enc is None and not (self.buf or final):
                return
            if self.enc is None:
                if not self.buf or not self._pick(final):
                    return
                self.pos = 0
            hit = self._find()
            if hit is None:
                if len(self.buf) > MAX_LINE or self.long is not None:
                    keep = 1 if self.enc == _U8 else 2
                    cut = len(self.buf) - keep
                    if self.enc != _U8:
                        cut &= ~1
                    if cut > 0:
                        self._long_piece(self.buf[:cut])
                        self.buf, self.pos = self.buf[cut:], 0
                return
            e, nxt, eol, stray = hit
            line, self.buf, self.pos = self.buf[:e], self.buf[nxt:], 0
            enc = self.enc
            half, self.half = self.half, stray
            if stray:
                self.enc = None                # the bytes after a stray newline are decided again
            self._line(line, eol, stray or half, enc)

    def _long_piece(self, data):
        import codecs
        first = self.long is None
        if first:
            self.long, self.ldec = 0, codecs.getincrementaldecoder(self.enc)('replace')
        self.long += len(data)
        self.sc.piece(self.ldec.decode(data), first)

    def feed(self, data: bytes):
        self.buf += data
        self._pump(False)

    def close(self):
        self._pump(True)
        if self.buf or self.long is not None:
            enc = self.enc or _U8
            if enc != _U8 and len(self.buf) % 2:
                self.truncated = True          # I432: a dangling byte of UTF-16 at EOF
                if self.long is not None:
                    self._long_piece(self.buf)
                    self.buf = b''
                    self._end_long('', enc)
                else:
                    self.sc.mark(_byte_view(self.buf))
                    self._emit(ENC_MARK.encode(enc), enc)
                self.buf = b''
            else:
                line, self.buf = self.buf, b''
                self._line(line, '', self.half, enc)

    def _end_long(self, eol, enc):
        n, self.long, self.ldec = self.long, None, None
        self._emit(f'[REDACTED:long-line {n}B]{eol}'.encode(enc), enc)

    def _line(self, line, eol, stray, enc):
        if self.long is not None or len(line) > MAX_LINE:     # I430: a long line is written once, as the marker
            self._long_piece(line)
            self.sc.piece(self.ldec.decode(b'', True), False)
            self._end_long(eol, enc)
            return
        text = None
        if not stray:
            if enc == _U8:
                if b'\x00' not in line:
                    try:
                        text = line.decode(_U8)
                    except UnicodeDecodeError:
                        text = None
            elif len(line) % 2 == 0:
                try:
                    text = line.decode(enc)
                except UnicodeDecodeError:
                    text = None
        if text is None:                       # not E (M2, I431): only the marker, read conservatively
            self.enc_lines += 1
            self.sc.mark(_byte_view(line))
            self._emit((ENC_MARK + eol).encode(enc), enc)
            return
        body = self.sc.line(text).encode(enc)
        if enc != _U8:                         # double scan (fail closed): the written bytes without NULs
            view = _byte_view(body)
            if scrub(view, self.keys) != view:
                self.enc_lines += 1
                if self.sc.st is None:
                    self.sc.mark(view)
                body = ENC_MARK.encode(enc)
        self._emit(body + eol.encode(enc), enc)

    def _emit(self, data, enc):
        if key_leak(data, self.keys):          # I-A7: no output in any mode carries a key in any encoding
            data = SECRET.encode(enc) + (b'\n' if data.endswith(b'\n') else b'')
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
    if s.truncated:
        sys.stderr.write('WINQA_W_REDACT_TRUNCATED\n')
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
