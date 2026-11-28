#!/usr/bin/env python3
"""Validate frontend UI locale JSON files against en.json and README parity.

Usage:
    python3 scripts/check_locales.py --check
    python3 scripts/check_locales.py --summary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "frontend" / "src" / "i18n" / "locales"
README_I18N_DIR = ROOT / "docs" / "i18n"
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")

LOCALE_TO_README = {
    "en": ROOT / "README.md",
    "zh": README_I18N_DIR / "README-ZH.md",
    "zh-TW": README_I18N_DIR / "README-ZH-TW.md",
    "ja": README_I18N_DIR / "README-JA.md",
    "ko": README_I18N_DIR / "README-KO.md",
    "es": README_I18N_DIR / "README-ES.md",
    "pt": README_I18N_DIR / "README-PT.md",
    "ru": README_I18N_DIR / "README-RU.md",
    "fr": README_I18N_DIR / "README-FR.md",
    "id": README_I18N_DIR / "README-ID.md",
    "tr": README_I18N_DIR / "README-TR.md",
    "vi": README_I18N_DIR / "README-VI.md",
    "de": README_I18N_DIR / "README-DE.md",
    "it": README_I18N_DIR / "README-IT.md",
    "pl": README_I18N_DIR / "README-PL.md",
    "th": README_I18N_DIR / "README-TH.md",
    "nl": README_I18N_DIR / "README-NL.md",
    "uk": README_I18N_DIR / "README-UK.md",
    "hi": README_I18N_DIR / "README-HI.md",
    "ar": README_I18N_DIR / "README-AR.md",
}


def load_locale(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: top-level JSON must be an object")
    return {str(k): str(v) for k, v in raw.items()}


def check_locales(*, summary: bool = False) -> int:
    en_path = LOCALES_DIR / "en.json"
    if not en_path.is_file():
        print("ERROR: missing frontend/src/i18n/locales/en.json", file=sys.stderr)
        return 1

    en_data = load_locale(en_path)
    en_keys = set(en_data)
    en_placeholders = {k: sorted(PLACEHOLDER_RE.findall(v)) for k, v in en_data.items()}

    locale_files = sorted(LOCALES_DIR.glob("*.json"))
    errors: list[str] = []

    for path in locale_files:
        code = path.stem
        try:
            data = load_locale(path)
        except Exception as exc:
            errors.append(f"{path.name}: failed to parse JSON ({exc})")
            continue

        keys = set(data)
        missing = sorted(en_keys - keys)
        extra = sorted(keys - en_keys)
        empty = sorted(k for k, v in data.items() if not v.strip() and en_data.get(k, "").strip())
        bad_ph = [
            k for k in (en_keys & keys)
            if sorted(PLACEHOLDER_RE.findall(data[k])) != en_placeholders[k]
        ]

        if missing:
            errors.append(f"{path.name}: {len(missing)} missing keys (e.g. {', '.join(missing[:5])})")
        if extra:
            errors.append(f"{path.name}: {len(extra)} extra keys not in en.json (e.g. {', '.join(extra[:5])})")
        if empty:
            errors.append(f"{path.name}: {len(empty)} empty values (e.g. {', '.join(empty[:5])})")
        if bad_ph:
            errors.append(f"{path.name}: {len(bad_ph)} mismatched {{{{placeholders}}}} (e.g. {', '.join(bad_ph[:5])})")

        readme_path = LOCALE_TO_README.get(code) or (README_I18N_DIR / f"README-{code.upper()}.md")
        if not readme_path.is_file():
            errors.append(f"{path.name}: missing paired README at {readme_path.relative_to(ROOT)}")

        if summary:
            same = sum(1 for k in (en_keys & keys) if data[k] == en_data[k]) if code != "en" else 0
            print(f"{code:6s}  keys={len(keys):4d}  missing={len(missing):3d}  extra={len(extra):3d}  same_as_en={same:4d}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(f"OK: {len(locale_files)} UI locales ({len(en_keys)} keys each) and paired READMEs verified.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AutoClip UI locale JSON files.")
    parser.add_argument("--check", action="store_true", help="Exit 1 on any mismatch (default behavior).")
    parser.add_argument("--summary", action="store_true", help="Print per-locale statistics.")
    args = parser.parse_args()
    return check_locales(summary=args.summary)


if __name__ == "__main__":
    raise SystemExit(main())
