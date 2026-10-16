"""R10-R1: Digest / quoted-with-space Authorization and spaced api_key values must not leak."""
import pytest

from backend.core.log_redaction import redact_text

FAKE = "FAKEsecretTOKEN123"  # not a real key

CASES = [
    f'Authorization: Digest username="u", realm="r", response="{FAKE}"',
    f'Proxy-Authorization: Digest username="u", nonce="n", response="{FAKE}"',
    f'{{"Authorization": "Digest username=\\"u\\", response=\\"{FAKE}\\""}}',
    f"{{'Authorization': 'Bearer abc {FAKE}'}}",
    f'Authorization: "Token prefix {FAKE}"',
    f'api_key="prefix {FAKE}"',
    f"api_key='prefix {FAKE}'",
    f'{{"api_key": "prefix {FAKE}", "model": "m"}}',
    f'{{"x-api-key": "a b {FAKE}"}}',
    f'password="two words {FAKE}"',
    f"https://h/v1?api_key=prefix%20{FAKE}&model=m",
    f"api_key=prefix+{FAKE}&model=m",
]


@pytest.mark.parametrize("text", CASES)
def test_spaced_and_digest_credentials_redacted(text):
    out = redact_text(text)
    assert FAKE not in out, out
    assert "[REDACTED]" in out


def test_neighbouring_fields_kept():
    out = redact_text(f'{{"api_key": "prefix {FAKE}", "model": "gemini-x"}}')
    assert '"model": "gemini-x"' in out
    out = redact_text(f"{{'Authorization': 'Digest a=\"b\" {FAKE}', 'Accept': 'json'}}")
    assert FAKE not in out and "'Accept': 'json'" in out


def test_idempotent():
    once = redact_text(f'Authorization: Digest response="{FAKE}"')
    assert redact_text(once) == once
