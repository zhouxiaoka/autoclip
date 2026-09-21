#!/usr/bin/env python3
"""Check README language navigation, local assets, and shared command examples."""

from html import unescape
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "README.md", "README-EN.md", "README-JA.md", "README-KO.md",
    "README-ES.md", "README-PT.md", "README-RU.md", "README-FR.md",
)
GUIDES = (
    "DOCKER.md", "docs/DOCKER.en.md", "docs/README.md", "docs/i18n.md",
    "docs/USER_INSTALLATION_GUIDE.md", "docs/USER_INSTALLATION_GUIDE.en.md",
    "docs/FAQ.md", "docs/FAQ.en.md", "docs/images/README.md",
    "CONTRIBUTING.md", "docs/MULTI_LLM_PROVIDER_GUIDE.md",
)
FENCES = re.compile(r"^```[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
LINKS = re.compile(r'\]\(([^\s)]+)\)|(?:href|src)="([^"]+)"')


def main() -> int:
    errors = []
    files = {name: ROOT / name for name in FILES}
    baseline = None
    badge_baseline = None
    for name, path in files.items():
        if not path.is_file():
            errors.append(f"Missing translation: {name}")
            continue
        content = path.read_text(encoding="utf-8")
        blocks = FENCES.findall(content)
        if baseline is None:
            baseline = blocks
        elif blocks != baseline:
            errors.append(f"{name}: command examples differ from README.md")
        if len(re.findall(r"^```", content, re.MULTILINE)) != 2 * len(blocks):
            errors.append(f"{name}: unbalanced code fences")
        prose = FENCES.sub("", content)
        links = [unescape(a or b) for a, b in LINKS.findall(prose)]
        for other in FILES:
            if other != name and other not in links:
                errors.append(f"{name}: missing language link to {other}")
        for link in links:
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = path.parent / unquote(url.path)
            if not target.exists():
                errors.append(f"{name}: broken local link: {link}")
        badges = sorted(link for link in links if "trendshift.io/api/badge/" in link)
        if badge_baseline is None:
            badge_baseline = badges
        elif badges != badge_baseline:
            errors.append(f"{name}: achievement badges differ from README.md")
        if any("/25801" not in badge for badge in badges):
            errors.append(f"{name}: achievement badge belongs to another repository")
        if any("qq_qr" in link or "feishu_qr" in link for link in links):
            errors.append(f"{name}: removed personal contact QR code is linked again")
        if content.count("<details>") != content.count("</details>"):
            errors.append(f"{name}: unbalanced FAQ disclosure blocks")

    for name in GUIDES:
        path = ROOT / name
        if not path.is_file():
            errors.append(f"Missing guide: {name}")
            continue
        prose = FENCES.sub("", path.read_text(encoding="utf-8"))
        for a, b in LINKS.findall(prose):
            link = unescape(a or b)
            url = urlsplit(link)
            if not url.scheme and not url.netloc and url.path:
                if not (path.parent / unquote(url.path)).exists():
                    errors.append(f"{name}: broken local link: {link}")

    if (ROOT / ".github/README.md").exists():
        errors.append(".github/README.md would override the canonical root README")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {len(FILES)} READMEs and {len(GUIDES)} guides; local links and README consistency checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
