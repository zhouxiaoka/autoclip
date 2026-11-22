#!/usr/bin/env python3
"""Sign a sponsor promotion document. The private key must stay outside this repo.

Examples, run by a maintainer on their own machine:

  python scripts/sponsor_promo_sign.py generate --private-key ~/secrets/autoclip-sponsor.pem
  python scripts/sponsor_promo_sign.py sign --private-key ~/secrets/autoclip-sponsor.pem \\
      --payload promo.json --out envelope.json

This does not upload the file, mint a production key into the tree, or enable the client.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.core.sponsor_promo import canonical_bytes, validate_payload, builtin_sponsor_hosts
from datetime import datetime, timezone


def _outside_repo(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(REPO)
    except ValueError:
        return resolved
    raise SystemExit("private key path is inside the repository; refuse to read or write it")


def _generate(path: Path) -> None:
    target = _outside_repo(path)
    parent = target.parent
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise SystemExit("private key directory is not a real directory")
    if target.is_symlink() or target.exists():
        raise SystemExit("private key file already exists")
    parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise SystemExit("private key file mode is not private")
        os.write(fd, pem)
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        try:
            target.unlink()
        except OSError:
            pass
        raise
    os.close(fd)
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    print(base64.b64encode(public).decode("ascii"))


def _sign(key_path: Path, payload_path: Path, out_path: Path) -> None:
    private_path = _outside_repo(key_path)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    decision = validate_payload(
        payload,
        app_version=str(payload.get("min_app") or ""),
        now=datetime.now(timezone.utc),
        hosts=builtin_sponsor_hosts(),
        min_sequence=0,
        cache_sequence=None,
        retired=set(),
    )
    if not decision.ok:
        raise SystemExit(f"payload rejected before signing: {decision.reason}")
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("private key is not Ed25519")
    signature = base64.b64encode(key.sign(canonical_bytes(payload))).decode("ascii")
    out_path.write_text(json.dumps({"payload": payload, "signature": signature}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sign an AutoClip sponsor promotion document")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--private-key", required=True, type=Path)
    sign = commands.add_parser("sign")
    sign.add_argument("--private-key", required=True, type=Path)
    sign.add_argument("--payload", required=True, type=Path)
    sign.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "generate":
        _generate(args.private_key)
        return
    _sign(args.private_key, args.payload, args.out)


if __name__ == "__main__":
    main()
