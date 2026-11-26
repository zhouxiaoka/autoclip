#!/usr/bin/env python3
"""Synchronize shared hero elements (Download CTA, Trendshift badge, Sponsors bar) across all READMEs.

Keeps every translated README in `docs/i18n/README-*.md` aligned with root `README.md`
while respecting relative paths (`../../` inside `docs/i18n/`).

Usage:
    python3 scripts/sync_readme_blocks.py          # apply sync to all translated READMEs
    python3 scripts/sync_readme_blocks.py --check  # exit 1 if any translated README is out of sync
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N_READMES = sorted((ROOT / "docs" / "i18n").glob("README-*.md"))

HERO_CTA_RE = re.compile(
    r"<!-- hero-cta:start -->.*?<!-- hero-cta:end -->",
    re.DOTALL,
)
SPONSORS_TOP_RE = re.compile(
    r"<!-- top-sponsors:start -->.*?<!-- top-sponsors:end -->",
    re.DOTALL,
)


def _rewrite_relative_paths(block: str, prefix: str) -> str:
    """Prefix relative local asset/doc paths (`docs/...`, `CODE_SIGNING.md`, etc.) for docs/i18n/."""
    def repl(match: re.Match[str]) -> str:
        attr, quote, target = match.group(1), match.group(2), match.group(3)
        if target.startswith(("http://", "https://", "mailto:", "#", "../")):
            return match.group(0)
        return f"{attr}={quote}{prefix}{target}{quote}"

    return re.sub(r'(src|href)=(["\'])([^"\']+)\2', repl, block)


def sync(*, check_only: bool = False) -> int:
    root_text = (ROOT / "README.md").read_text(encoding="utf-8")
    hero_match = HERO_CTA_RE.search(root_text)
    sponsors_match = SPONSORS_TOP_RE.search(root_text)
    if not hero_match or not sponsors_match:
        print("ERROR: README.md must contain hero-cta and top-sponsors marker blocks.", file=sys.stderr)
        return 1

    hero_i18n = _rewrite_relative_paths(hero_match.group(0), "../../")
    sponsors_i18n = _rewrite_relative_paths(sponsors_match.group(0), "../../")
    out_of_sync: list[str] = []

    for path in I18N_READMES:
        original = path.read_text(encoding="utf-8")
        updated = original

        if HERO_CTA_RE.search(updated):
            updated = HERO_CTA_RE.sub(hero_i18n, updated, count=1)
        else:
            # Replace the existing standalone Trendshift badge (with or without <p> wrapper)
            trendshift_p = re.compile(
                r'(?:<p>\s*)?<a href="https://trendshift\.io/repositories/25801">.*?</a>(?:\s*</p>)?',
                re.DOTALL,
            )
            if trendshift_p.search(updated):
                updated = trendshift_p.sub(hero_i18n, updated, count=1)
            else:
                out_of_sync.append(f"{path.name}: missing hero-cta marker or Trendshift badge block")
                continue

        if SPONSORS_TOP_RE.search(updated):
            updated = SPONSORS_TOP_RE.sub(sponsors_i18n, updated, count=1)
        else:
            # Insert right before closing </div> of the centered hero block
            updated = updated.replace("\n</div>\n", f"\n{sponsors_i18n}\n\n</div>\n", 1)

        if updated != original:
            if check_only:
                out_of_sync.append(path.relative_to(ROOT).as_posix())
            else:
                path.write_text(updated, encoding="utf-8")

    if check_only and out_of_sync:
        print("Out-of-sync README blocks:\n" + "\n".join(out_of_sync), file=sys.stderr)
        return 1

    action = "verified" if check_only else "synced"
    print(f"OK: {len(I18N_READMES)} translated READMEs {action} with README.md hero CTA & sponsors bar.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync shared README hero blocks across translations.")
    parser.add_argument("--check", action="store_true", help="Check only; exit 1 if changes would be made.")
    args = parser.parse_args()
    return sync(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
