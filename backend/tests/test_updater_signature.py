"""Updater release verification rejects tampering and mismatched signing keys."""
import base64
import hashlib
import importlib.util
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

spec = importlib.util.spec_from_file_location('verify_updater_signatures', Path(__file__).resolve().parents[2] / 'scripts/verify_updater_signatures.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def signed(tmp_path):
    artifact = tmp_path / 'app.tar.gz'
    artifact.write_bytes(b'packaged app')
    private = Ed25519PrivateKey.generate()
    key_id = b'12345678'
    pub = b'Ed' + key_id + private.public_key().public_bytes_raw()
    encode = lambda b: base64.b64encode(b).decode()
    key = encode(('untrusted comment: public key\n' + encode(pub) + '\n').encode())
    sig = private.sign(hashlib.blake2b(artifact.read_bytes()).digest())
    comment = 'timestamp:1234'
    text = '\n'.join(['untrusted comment: signature', encode(b'ED' + key_id + sig), 'trusted comment: ' + comment, encode(private.sign(sig + comment.encode()))])
    Path(str(artifact) + '.sig').write_text(encode(text.encode()))
    return artifact, key


def test_valid_signature(tmp_path):
    artifact, key = signed(tmp_path)
    mod.verify(artifact, key)


def test_tampered_artifact(tmp_path):
    artifact, key = signed(tmp_path)
    artifact.write_bytes(b'tampered')
    with pytest.raises(InvalidSignature):
        mod.verify(artifact, key)


def test_different_public_key(tmp_path):
    artifact, key = signed(tmp_path)
    decoded = base64.b64decode(key).decode().splitlines()
    raw = bytearray(base64.b64decode(decoded[1])); raw[2] ^= 1
    decoded[1] = base64.b64encode(raw).decode()
    key = base64.b64encode('\n'.join(decoded).encode()).decode()
    with pytest.raises(ValueError, match='does not match'):
        mod.verify(artifact, key)
