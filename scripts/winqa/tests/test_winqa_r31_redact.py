"""#414 design v5 part A (scripts/winqa): one streaming redaction path (decoder -> line splitter -> line-by-line
scanner -> encoder) shared by redact.py --stdin / --lines and logpipe.py; the log channel's real exit status (M3,
#395); test_a2 hardening (#389). Every case drives the CLI or the real run_winqa.sh, so the same test runs unchanged
against the code before v5 (and fails there on an assertion, not on an import)."""
import json
import os
import random
import subprocess
import sys
import time

import pytest

from _winqa_helpers import KEY, ROOT, BASHES, _env, _assert_no_raw_on_control, _wpwc, classify_a2

REDACT = [sys.executable, str(ROOT / 'redact.py')]
CODECS = ('utf-8', 'utf-16-le', 'utf-16-be')


def _cli(data, mode='--lines', key=None, timeout=60):
    env = {k: v for k, v in os.environ.items() if k not in ('WINQA_MODEL_API_KEY', 'AUTOCLIP_QA_DASHSCOPE_KEY')}
    if key is not None:
        env['WINQA_MODEL_API_KEY'] = key
    return subprocess.run(REDACT + [mode], input=data, capture_output=True, env=env, timeout=timeout)


def _forms(s):
    return [s.encode(c) for c in CODECS]


def _clean(out, *probes):
    return not any(f in out for p in probes for f in _forms(p))


# ---------------------------------------------------------------- T-A1 / T-A2: #382 (UTF-16 across lines)
SPAN = 'start\npassword: "abc\nPRIVB second line\nend" ok=1\n'


@pytest.mark.parametrize('mode', ['--lines', '--stdin'])
@pytest.mark.parametrize('codec,bom', [('utf-16-le', b''), ('utf-16-le', b'\xff\xfe'), ('utf-16-be', b''),
                                       ('utf-16-be', b'\xfe\xff'), ('utf-8', b''), ('utf-8', b'\xef\xbb\xbf')])
def test_a1_a2_value_spanning_lines_never_leaks_in_any_encoding(codec, bom, mode):
    done = _cli(bom + SPAN.encode(codec), mode)
    assert done.returncode == 0, done.stderr
    assert _clean(done.stdout, 'PRIVB'), done.stdout
    assert done.stdout.startswith(bom)
    assert done.stdout.startswith(bom + 'start\npassword: '.encode(codec))   # decoded, not just marked away


# ---------------------------------------------------------------- T-A12: M1 empty first line, value on the next
@pytest.mark.parametrize('text', ['Authorization:\r\n  PRIVB\r\nnext: 1\n', '"password":\n "PRIVB"\nnext: 1\n',
                                  'password:\n  PRIVB\nnext: 1\n', 'Cookie:\n\tPRIVB=1\n'])
@pytest.mark.parametrize('codec', CODECS)
def test_a12_credential_with_value_on_the_next_line(text, codec):
    done = _cli(text.encode(codec))
    assert done.returncode == 0 and _clean(done.stdout, 'PRIVB'), done.stdout
    if 'next' in text:
        assert 'next: 1'.encode(codec) in done.stdout          # the following ordinary line is readable again


# ---------------------------------------------------------------- T-A3 / T-A9: #383 linear, counted not timed
def test_a3_unclosed_quote_then_8000_lines_is_linear():
    data = b'password: "abc\n' + b'plain log line 0123456789\n' * 8000
    env = dict(os.environ, WINQA_REDACT_STATS='1')
    try:
        done = subprocess.run(REDACT + ['--lines'], input=data, capture_output=True, timeout=30, env=env)
    except subprocess.TimeoutExpired:
        pytest.fail('8000 lines after an unclosed quote took more than 30 s (quadratic rescanning)')
    assert done.returncode == 0 and b'abc' not in done.stdout
    assert done.stdout.count(b'\n') == 8001                         # every line written (masked), none held back
    stats = [l for l in done.stderr.split(b'\n') if l.startswith(b'WINQA_STATS scanned=')]
    assert stats, done.stderr[-200:]
    assert int(stats[0].split(b'=')[1]) <= 2 * len(data)           # each character handed to the scanner ~once


@pytest.mark.parametrize('bash', BASHES)
def test_a9_run_winqa_close_is_not_killed_by_a_long_log_after_an_open_value(tmp_path, bash):
    env, args = _env(tmp_path)
    ssh = tmp_path / 'bin' / 'ssh'
    ssh.write_text(ssh.read_text().replace(
        "    if req['op'] == 'hash':",
        "    if req['op'] == 'ps' and req['args']['script'] == 'collect_logs':\n"
        "        sys.stdout.write('password: \"abc\\n' + 'plain log line 0123456789\\n' * 8000); sys.stdout.flush()\n"
        "    if req['op'] == 'hash':", 1))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=170)
    assert b'WINQA_E_LOGPIPE' not in done.stderr, done.stderr[-300:]
    assert done.returncode != 70
    _assert_no_raw_on_control(tmp_path, done)


# ---------------------------------------------------------------- T-A4: chunking and mode independence (I-A1, I-A4)
def _stream(data, chunks):
    sys.path.insert(0, str(ROOT))
    import redact
    out = []
    s = redact.Stream([KEY], out.append)
    i = 0
    for c in chunks:
        s.feed(data[i:i + c]); i += c
    s.feed(data[i:]); s.close()
    return b''.join(out)


@pytest.mark.parametrize('codec', CODECS)
def test_a4_output_does_not_depend_on_chunking_or_mode(codec):
    text = ('a \U0001F600 b\npassword="x\n\U0001F600 PRIVB\ny" tail\r\nAuthorization: Basic PRIVB\r\n PRIVB\r\n'
            'url https://h.invalid/q home /Users/kris/x\n')
    data = text.encode(codec)
    whole = _stream(data, [])
    rng = random.Random(414)
    for chunks in ([1] * len(data), [3] * (len(data) // 3), [rng.randint(1, 9) for _ in range(len(data))]):
        assert _stream(data, chunks) == whole, chunks[:5]
    assert _cli(data, '--lines').stdout == whole
    assert _clean(whole, 'PRIVB', 'kris')


@pytest.mark.parametrize('codec', CODECS)
def test_a4a_lines_and_stdin_give_the_same_bytes(codec):
    text = 'a\npassword="x\nPRIVB\ny" tail\r\nAuthorization: Basic PRIVB\r\n PRIVB\r\nhome /Users/kris/x\n'
    data = text.encode(codec)
    lines, whole = _cli(data, '--lines', key=KEY), _cli(data, '--stdin', key=KEY)
    assert lines.returncode == whole.returncode == 0
    assert lines.stdout == whole.stdout and _clean(lines.stdout, 'PRIVB', 'kris'), (lines.stdout, whole.stdout)


# ---------------------------------------------------------------- T-A5: CRLF
def test_a5_crlf_across_chunks_lone_cr_and_values_spanning_crlf():
    data = b'progress 10%\rprogress 20%\r\npassword="a\r\nPRIVB\r\nz" b=1\r\nlast\n'
    out = _stream(data, [len(b'progress 10%\rprogress 20%')] + [1] * 6)
    assert out == _stream(data, [])
    assert b'progress 10%\rprogress 20%\r\n' in out and b'PRIVB' not in out and out.endswith(b'b=1\r\nlast\n')
    assert out.count(b'\r\n') == 4


# ---------------------------------------------------------------- T-A6: 1 MiB limits
def test_a6_unclosed_value_past_1_mib_masks_whole_lines_to_eof_keeping_the_line_count():
    data = b'secret="' + b'x' * (1 << 20) + b'\nPRIVB\nlater PRIVC\n'
    done = _cli(data)
    assert done.returncode == 0 and b'PRIVB' not in done.stdout and b'PRIVC' not in done.stdout
    assert done.stdout.count(b'\n') == 3 and b'WINQA_W_REDACT_MASK_EOF' in done.stderr


def test_a6_a_3_mib_line_without_newline_uses_bounded_memory():
    code = ("import sys, io, tracemalloc; sys.path.insert(0, sys.argv[1]); import redact; tracemalloc.start(); "
            "s = redact.Stream([], lambda b: None); chunk = b'y' * 65536\n"
            "for _ in range(48): s.feed(chunk)\n"
            "s.close(); print(tracemalloc.get_traced_memory()[1])")
    done = subprocess.run([sys.executable, '-c', code, str(ROOT)], capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr[-300:]
    assert int(done.stdout) < 24 << 20, int(done.stdout)


# ---------------------------------------------------------------- T-A7: exit codes
def test_a7_exit_codes():
    assert _cli(b'x', '--bogus').returncode == 2
    done = _cli(b'token=a\n', key='ab\ncd')
    assert done.returncode == 2 and done.stdout == b''
    # write failure: stdout closed
    done = subprocess.run(REDACT + ['--lines'], input=b'x\n' * 10, stdout=subprocess.DEVNULL, capture_output=False,
                          stderr=subprocess.PIPE)
    assert done.returncode == 0
    r, w = os.pipe(); os.close(r)
    p = subprocess.run(REDACT + ['--lines'], input=b'password="PRIVB\n' * 1000, stdout=w, stderr=subprocess.PIPE)
    os.close(w)
    assert p.returncode == 3 and p.stderr.strip() == b'WINQA_E_REDACT write', p.stderr


# ---------------------------------------------------------------- T-A8 / T-A8b: M2 encoding switch mid-stream
def test_a8_utf16_appended_to_utf8_is_output_only_as_the_marker():
    data = b'first line\n' + 'password: hunter2PRIVB\n'.encode('utf-16-le') + b'\n'
    done = _cli(data)
    assert done.returncode == 0 and done.stdout.startswith(b'first line\n')
    assert _clean(done.stdout, 'PRIVB', 'hunter2') and b'[REDACTED:encoding]' in done.stdout


def test_a8b_bare_key_in_a_utf16_run_inside_utf8_is_never_written_back():
    data = b'ok\n' + f'plain {KEY} words'.encode('utf-16-le') + b'\n'
    done = _cli(data)                                          # no key given: only the marker rule can catch it
    assert done.returncode == 0 and _clean(done.stdout, KEY), done.stdout
    lines = done.stdout.split(b'\n')
    assert lines[0] == b'ok' and all(l in (b'', b'[REDACTED:encoding]') for l in lines[1:]), lines


# ---------------------------------------------------------------- T-A10: M5 ordinary quotes; v4 regressions
def test_a10_quote_in_ordinary_text_does_not_open_a_value():
    done = _cli(b"don't panic\nit's fine\nnext line visible\n")
    assert done.stdout == b"don't panic\nit's fine\nnext line visible\n"


def test_a10b_escaped_quote_does_not_close_a_value_across_lines():
    done = _cli(b'password="a\\" PRIVB\nPRIVC" visible=1\n')
    assert done.returncode == 0 and b'PRIVB' not in done.stdout and b'PRIVC' not in done.stdout, done.stdout
    assert done.stdout.endswith(b'visible=1\n')


def test_ia7_key_bytes_of_another_encoding_inside_a_utf16_line_are_masked():
    # PS 5.1 mixing: a UTF-16LE line with CJK text and the key appended as UTF-8 bytes (reads as CJK in UTF-16)
    data = '\u4e2d\u6587 '.encode('utf-16-le') + KEY.encode() + '\n'.encode('utf-16-le')
    done = _cli(b'\xff\xfe' + data, key=KEY)
    assert done.returncode == 0 and not [f for f in _forms(KEY) if f in done.stdout], done.stdout


# ---------------------------------------------------------------- I-A7: no key in any encoding, any mode
def _gen(rng):
    names = ['password', 'token', 'api_key', 'Authorization', 'note', 'secret', 'cookie', 'msg']
    parts = []
    for _ in range(rng.randint(1, 6)):
        k = rng.choice(names)
        v = rng.choice([KEY, f'"{KEY}"', f'"a\n{KEY}"', f'{{"x": "{KEY}",\n"y": 1}}', f'Bearer {KEY}', 'plain',
                        f'\n  {KEY}', f'pre {KEY} post'])
        sep = rng.choice([': ', '=', '":'])
        parts.append(f'{k}{sep}{v}')
    return rng.choice(['\n', '\r\n', ' ']).join(parts) + '\n'


@pytest.mark.parametrize('codec', CODECS)
def test_ia7_property_no_output_contains_a_key_in_any_encoding(codec):
    sys.path.insert(0, str(ROOT))
    import redact
    rng = random.Random(20261017)
    for i in range(100):                                       # 3 codecs x 100 = 300 fixed-seed cases (M12)
        text = _gen(rng)
        data = text.encode(codec)
        cut = sorted(rng.sample(range(1, len(data)), min(4, len(data) - 1)))
        out = []
        s = redact.Stream([KEY], out.append)
        last = 0
        for c in cut + [len(data)]:
            s.feed(data[last:c]); last = c
        s.close()
        got = b''.join(out)
        assert not redact.key_leak(got, [KEY]), (i, text, got)


@pytest.mark.parametrize('mode', ['--lines', '--stdin'])
@pytest.mark.parametrize('codec', CODECS)
def test_ia7_cli_no_output_contains_a_key_in_any_encoding(codec, mode):
    rng = random.Random(20261017)
    data = ''.join(_gen(rng) for _ in range(100)).encode(codec)
    done = _cli(data, mode, key=KEY)
    assert done.returncode == 0, done.stderr[-200:]
    hits = [f for f in _forms(KEY) if f in done.stdout]
    assert not hits, (hits, done.stdout[:300])


# ---------------------------------------------------------------- T-A15: M14 first line is not held
def test_a15_first_short_line_is_written_immediately():
    p = subprocess.Popen(REDACT + ['--lines'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        t0 = time.monotonic()
        p.stdin.write(b'0123456789\n'); p.stdin.flush()
        import select
        ready, _, _ = select.select([p.stdout], [], [], 2)
        assert ready, 'first line held back'
        assert os.read(p.stdout.fileno(), 100) == b'0123456789\n'
        assert time.monotonic() - t0 < 1.0
    finally:
        p.stdin.close(); p.wait(10)


# ---------------------------------------------------------------- T-A13 / T-A14: M3 #395 real exit status, I-C1
def _verdict(tmp_path):
    vs = sorted((tmp_path / 'ev' / 'runs').glob('*/verdict-final.json'))
    return json.loads(vs[-1].read_text()) if vs else None


def _fake_logpipe(tmp_path, body):
    fake = (tmp_path / 'bin' / 'python3').read_text()
    (tmp_path / 'bin' / 'python3').write_text(fake.replace(
        "os.execv(", "if any(x.endswith('logpipe.py') for x in a):\n" + body + "\nos.execv(", 1))


@pytest.mark.parametrize('bash', BASHES)
def test_a13_logpipe_that_says_exit_0_then_is_killed_fails_the_run(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, (
        "    import runpy, signal\n"
        "    sys.argv = a[1:]\n"
        "    try:\n"
        "        runpy.run_path(a[1], run_name='__main__')\n"
        "    except SystemExit:\n"
        "        pass\n"
        "    os.kill(os.getpid(), signal.SIGKILL)"))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 70, (done.returncode, done.stderr[-300:])
    assert b'WINQA_E_LOGPIPE 70 killed=SIG9\n' in done.stderr, done.stderr[-300:]
    v = _verdict(tmp_path)
    assert v is None or not _wpwc()[1].is_pass(v), v


@pytest.mark.parametrize('bash', BASHES)
def test_a14_logpipe_drain_slower_than_10s_gives_70_and_no_pass_verdict(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, (
        "    import runpy, time\n"
        "    sys.argv = a[1:]\n"
        "    code = 0\n"
        "    try:\n"
        "        runpy.run_path(a[1], run_name='__main__')\n"
        "    except SystemExit as e:\n"
        "        code = e.code or 0\n"
        "    time.sleep(12)\n"
        "    sys.exit(code)"))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 70, (done.returncode, done.stderr[-300:])
    assert b'WINQA_E_LOGPIPE 70 drain_timeout' in done.stderr
    v = _verdict(tmp_path)
    assert v is None or not _wpwc()[1].is_pass(v), v


@pytest.mark.parametrize('bash', BASHES)
def test_a13b_green_run_reference_exits_0_with_a_pass_verdict(tmp_path, bash):
    """Reference for T-A13/T-A14: the same fixture with a healthy channel passes, so their verdict assertions bite."""
    env, args = _env(tmp_path)
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 0, (done.returncode, done.stdout[-500:])
    assert _wpwc()[1].is_pass(_verdict(tmp_path))


# ---------------------------------------------------------------- T-A11: #389 hardening (handshake bound)
@pytest.mark.parametrize('bash', BASHES)
def test_a11_handshake_bound_is_configurable_and_names_the_reason(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, '    import time; time.sleep(4)')
    env['WINQA_LOGPIPE_HANDSHAKE_S'] = '1'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert done.returncode == 70 and b'handshake_timeout after 1s' in done.stderr, done.stderr[-300:]
    env['WINQA_LOGPIPE_HANDSHAKE_S'] = '30'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert done.returncode == 0, (done.returncode, done.stderr[-300:])
    env['WINQA_LOGPIPE_HANDSHAKE_S'] = 'x'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert done.returncode == 70 and b'====' not in done.stdout


# ---------------------------------------------------------------- #414 a2 (Dong): killed vs exited itself vs bash crashed
@pytest.mark.parametrize('bash', BASHES)
def test_a16_logpipe_that_exits_by_itself_is_told_apart_from_a_kill(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, (
        "    import runpy\n"
        "    sys.argv = a[1:]\n"
        "    try:\n"
        "        runpy.run_path(a[1], run_name='__main__')\n"
        "    except SystemExit:\n"
        "        pass\n"
        "    st = a[a.index('--status') + 1]\n"
        "    open(st, 'a').write('EXIT 5\\n')\n"
        "    sys.exit(5)"))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 70, (done.returncode, done.stderr[-300:])
    assert b'WINQA_E_LOGPIPE 70 exited=5\n' in done.stderr, done.stderr[-300:]
    final = (tmp_path / 'ev' / 'logpipe-final.txt').read_text()
    assert 'reason exited=5' in final and 'RC 5' in final
    assert classify_a2(done.returncode, final).startswith('logpipe_exited_itself')


@pytest.mark.parametrize('bash', BASHES)
def test_a16_killed_logpipe_leaves_a_record_that_says_killed(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, (
        "    import runpy, signal\n"
        "    sys.argv = a[1:]\n"
        "    try:\n"
        "        runpy.run_path(a[1], run_name='__main__')\n"
        "    except SystemExit:\n"
        "        pass\n"
        "    os.kill(os.getpid(), signal.SIGKILL)"))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    final = (tmp_path / 'ev' / 'logpipe-final.txt').read_text()
    assert 'reason killed=SIG9' in final and 'RC 137' in final, final
    assert classify_a2(done.returncode, final).startswith('logpipe_killed')


def test_a16_classifier_covers_bash_crash_and_wrapper_loss():
    assert classify_a2(-9, None).startswith('no_close_record') and 'signal=9' in classify_a2(-9, None)
    assert classify_a2(139, None) == 'no_close_record rc=139 signal=11'
    assert classify_a2(70, 'script_rc_before_close 0\nreason wrapper_gone\nREADY 1\n').startswith('logpipe_wrapper_gone')
    assert classify_a2(70, 'reason drain_timeout\n').startswith('logpipe_hung_killed_by_script')
    assert classify_a2(0, 'reason none\nRC 0\n').startswith('logpipe_ok')
