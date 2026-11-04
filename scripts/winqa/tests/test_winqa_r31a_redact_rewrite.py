"""#414 R31 commit A: the single redaction path (I430, I431, I432, I470, I472; Dong R31 points 1 and 2).
Every case drives redact.py --stdin / --lines or redact.Stream, which exist before and after the rewrite, so a
failure before the fix is an assertion (a leak, a wrong exit code, a held line), never a missing name."""
import os
import select
import subprocess
import sys
import time

import pytest

from _winqa_helpers import KEY, ROOT

REDACT = [sys.executable, str(ROOT / 'redact.py')]
MARK = '[REDACTED:encoding]'
SECRET = 'hunter2xyz'


def _cli(data, mode='--stdin', key=None, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ('WINQA_MODEL_API_KEY', 'AUTOCLIP_QA_DASHSCOPE_KEY')}
    if key is not None:
        env['WINQA_MODEL_API_KEY'] = key
    env.update(env_extra or {})
    return subprocess.run(REDACT + [mode], input=data, capture_output=True, env=env, timeout=120)


def _stream(data, size, keys=(KEY,)):
    sys.path.insert(0, str(ROOT))
    import redact
    out = []
    s = redact.Stream(list(keys), out.append)
    for i in range(0, len(data), size):
        s.feed(data[i:i + size])
    s.close()
    return b''.join(out)


def _plain(out, *words):
    """Any of the words readable in the output: as UTF-8 / UTF-16LE / UTF-16BE bytes, or in the raw bytes with the
    NULs removed (a UTF-16 run shifted by one byte)."""
    view = out.replace(b'\x00', b'')
    return [w for w in words for f in (w.encode(), w.encode('utf-16-le'), w.encode('utf-16-be'))
            if f in out] + [w for w in words if w.encode() in view]


# ---------------------------------------------------------------- I430 (Dong point 1): long lines masked whole
def test_i430_key_exactly_across_the_64k_boundary_never_appears_and_the_marker_counts_bytes():
    line = b'k' * (65536 - 8) + KEY.encode() + b' tail'
    data = line + b'\nafter ok\n'
    assert line.index(KEY.encode()) < 65536 < line.index(KEY.encode()) + len(KEY)
    want = f'[REDACTED:long-line {len(line)}B]\nafter ok\n'.encode()
    for mode in ('--stdin', '--lines'):
        done = _cli(data, mode, key=KEY)
        assert done.returncode == 0, done.stderr[-200:]
        assert not _plain(done.stdout, KEY, 'nonstd42'), done.stdout[-200:]
        assert done.stdout == want, done.stdout[-200:]
    assert _stream(data, 65536) == _stream(data, 1) == want


def test_i430_field_value_across_the_boundary_chunked_and_byte_by_byte_give_the_same_bytes_no_leak():
    line = b'a' * (65536 - 12) + b' password=PRIVB0SECRET1 next'
    data = b'head\n' + line + b'\nvisible=1\n'
    by_chunk, by_byte = _stream(data, 65536, ()), _stream(data, 1, ())
    assert by_chunk == by_byte
    assert not _plain(by_chunk, 'SECRET1', 'PRIVB0'), by_chunk[-200:]
    assert by_chunk == b'head\n' + f'[REDACTED:long-line {len(line)}B]\n'.encode() + b'visible=1\n'


def test_i430_value_left_open_by_a_long_line_still_masks_the_next_line():
    data = b'x' * 70000 + b' password="abc\nPRIVB still inside\nend" ok=1\n'
    out = _cli(data).stdout
    assert out.startswith(b'[REDACTED:long-line 70014B]\n') and not _plain(out, 'PRIVB'), out[:200]
    assert out.endswith(b'" ok=1\n')


def test_i430_mixed_encoding_long_line_whose_prefix_carries_a_secret_outputs_no_prefix():
    line = b'note PRIVB plain ' + b'y' * 70000 + 'tail'.encode('utf-16-le')
    done = _cli(line + b'\nnext\n')
    assert done.returncode == 0
    assert done.stdout == f'[REDACTED:long-line {len(line)}B]\nnext\n'.encode(), done.stdout[:120]


# ---------------------------------------------------------------- I431: UTF-16 stream, then UTF-8 (both directions)
TAILS = [b'password=' + SECRET.encode() + b'\n',                     # odd length
         b'password=' + SECRET.encode() + b'z\n',                    # even length
         b'password=' + SECRET.encode() + b'z\nmore text\n',
         '中文 password='.encode() + SECRET.encode() + b'\n',
         '中 password='.encode() + SECRET.encode() + b'\nnext\n']


@pytest.mark.parametrize('mode', ['--stdin', '--lines'])
@pytest.mark.parametrize('tail', TAILS, ids=['odd', 'even', 'even-more', 'cjk', 'cjk-odd-more'])
@pytest.mark.parametrize('codec,bom', [('utf-16-le', b''), ('utf-16-le', b'\xff\xfe'), ('utf-16-be', b''),
                                       ('utf-16-be', b'\xfe\xff')])
def test_i431_utf16_stream_followed_by_utf8_never_leaks(codec, bom, tail, mode):
    data = bom + 'hello\n'.encode(codec) + tail
    done = _cli(data, mode)
    assert done.returncode == 0, done.stderr
    assert not _plain(done.stdout, SECRET), done.stdout
    assert done.stdout.startswith(bom + 'hello\n'.encode(codec))
    assert MARK.encode(codec) in done.stdout or MARK.encode() in done.stdout


@pytest.mark.parametrize('mode', ['--stdin', '--lines'])
def test_d1_hello_le_then_password_line(mode):
    """The sample of the review (D1 survived): 'hello' as UTF-16LE, then a UTF-8 line."""
    done = _cli('hello\n'.encode('utf-16-le') + b'password=hunter2xyz\n', mode)
    assert done.returncode == 0 and not _plain(done.stdout, SECRET), done.stdout
    assert done.stdout == ('hello\n' + MARK + '\n').encode('utf-16-le')


# ---------------------------------------------------------------- Dong point 2: odd-position newline, half line
@pytest.mark.parametrize('codec', ['utf-16-le', 'utf-16-be'])
def test_odd_position_newline_breaks_the_line_and_the_misaligned_half_line_is_only_the_marker(codec):
    # LE: 'k' + '\n' is one code unit whose high byte is 0x0A; BE: '\n' + 'p' is one whose high byte is 0x0A
    mid = b'k\n' if codec == 'utf-16-le' else b'\n'
    data = 'hello\n'.encode(codec) + mid + b'password=' + SECRET.encode() + b'\nnext ok\n'
    for mode in ('--stdin', '--lines'):
        done = _cli(data, mode)
        assert done.returncode == 0, done.stderr
        assert not _plain(done.stdout, SECRET), done.stdout
        # the line cut by the stray newline is the marker (in UTF-16); the misaligned half line after it is the
        # marker too, never decoded text; the line after that is read again
        assert done.stdout == ('hello\n' + MARK + '\n').encode(codec) + (MARK + '\nnext ok\n').encode(), done.stdout


@pytest.mark.parametrize('codec,bom', [('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff'), ('utf-16-le', b'')])
def test_chinese_utf16_lines_with_shang_zhong_are_decoded_not_masked(codec, bom):
    text = 'a 上中 文 /Users/kris/x\n中上 ok\n上\n'
    done = _cli(bom + text.encode(codec))
    assert done.returncode == 0
    assert done.stdout == bom + 'a 上中 文 /Users/<user>/x\n中上 ok\n上\n'.encode(codec), done.stdout


# ---------------------------------------------------------------- I432: odd byte count of UTF-16 at EOF
@pytest.mark.parametrize('mode', ['--stdin', '--lines'])
def test_i432_odd_length_utf16_exits_0_with_the_marker_and_a_warning(mode):
    done = _cli(b'\xff\xfe' + 'ok\n/Users/bob'.encode('utf-16-le') + b'\x00', mode)
    assert done.returncode == 0, done.stderr
    assert done.stdout == b'\xff\xfe' + ('ok\n' + MARK).encode('utf-16-le')
    assert b'WINQA_W_REDACT_TRUNCATED' in done.stderr and not _plain(done.stdout, 'bob')


# ---------------------------------------------------------------- I472: a first line under 4 bytes is not held
def test_i472_ok_newline_comes_out_before_eof():
    p = subprocess.Popen(REDACT + ['--lines'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        p.stdin.write(b'ok\n'); p.stdin.flush()
        ready, _, _ = select.select([p.stdout], [], [], 3)
        assert ready, 'the first line "ok\\n" was held back until more data or EOF'
        assert os.read(p.stdout.fileno(), 100) == b'ok\n'
    finally:
        p.stdin.close(); p.wait(10)


# ---------------------------------------------------------------- I470: linear, counted not timed
@pytest.mark.parametrize('n', [32000, 64000, 128000])
def test_i470_many_fields_on_one_line_scan_each_character_a_bounded_number_of_times(n):
    line = b'password=x ' * n + b'\n'
    small = b'password=x ' * 5000 + b'\n'
    data = (small * (n // 5000)) + line
    done = _cli(data, env_extra={'WINQA_REDACT_STATS': '1'})
    assert done.returncode == 0 and b'x ' not in done.stdout.replace(b'***', b'')
    got = [l for l in done.stderr.split(b'\n') if l.startswith(b'WINQA_STATS scanned=')]
    assert got and int(got[0].split(b'=')[1]) <= 4 * len(data), got
