"""#414 R31 (Dong): the output-side key_leak guard is kept. Bypass the main path and hand bytes carrying a
(fake) key straight to Stream._emit; the guard alone must keep every key form out of the output."""
import sys

import pytest

from _winqa_helpers import ROOT

FAKE_KEY = 'sk-FAKE0000kl0guard0test0000'


@pytest.mark.parametrize('enc', ['utf-8', 'utf-16-le', 'utf-16-be'])
@pytest.mark.parametrize('eol', ['', '\n'])
def test_kl_guard_blocks_a_key_handed_straight_to_the_output_side(enc, eol):
    sys.path.insert(0, str(ROOT))
    import redact
    out = []
    s = redact.Stream([FAKE_KEY], out.append)
    s._emit(('before ' + FAKE_KEY + ' after' + eol).encode(enc), enc)
    data = b''.join(out)
    assert not redact.key_leak(data, [FAKE_KEY])
    for c in ('utf-8', 'utf-16-le', 'utf-16-be'):
        assert FAKE_KEY.encode(c) not in data
    assert data.startswith(redact.SECRET.encode(enc)), data
    if enc == 'utf-8':                       # UTF-16 newline handling of the guard: see PR R31 note
        assert data == redact.SECRET.encode(enc) + eol.encode(enc)
