#!/usr/bin/env python3
"""Verify packaged updater files against the public key shipped in this release.

Tauri stores base64-encoded Minisign public keys/signatures. Only modern ED
(prehashed Ed25519) signatures are accepted, matching minisign-verify in Tauri.
Requires cryptography (already pinned in requirements.txt).
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def verify(artifact: Path, encoded_key: str) -> None:
    key = base64.b64decode(base64.b64decode(encoded_key).decode().splitlines()[1])
    lines = base64.b64decode(Path(str(artifact) + '.sig').read_text().strip()).decode().splitlines()
    signature = base64.b64decode(lines[1])
    if len(key) != 42 or len(signature) != 74 or signature[:2] != b'ED':
        raise ValueError('Invalid or unsupported updater signature')
    if key[2:10] != signature[2:10]:
        raise ValueError('Updater signing key does not match the shipped public key')
    if not lines[2].startswith('trusted comment: '):
        raise ValueError('Invalid signature comment')
    public_key = Ed25519PublicKey.from_public_bytes(key[10:])
    with artifact.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'blake2b').digest()
    public_key.verify(signature[10:], digest)
    public_key.verify(base64.b64decode(lines[3]), signature[10:] + lines[2][17:].encode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('src-tauri/tauri.conf.json'))
    parser.add_argument('artifacts', type=Path, nargs='+')
    args = parser.parse_args()
    pubkey = json.loads(args.config.read_text())['plugins']['updater']['pubkey']
    for artifact in args.artifacts:
        verify(artifact, pubkey)
        print(f'Verified updater signature: {artifact.name}')
