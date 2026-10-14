#!/usr/bin/env python3
"""Check README language navigation, local assets, and shared command examples."""

from html import unescape
import os
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
    "docs/INFISTAR_SETUP.md", "docs/INFISTAR_SETUP.en.md",
    "docs/88API_SETUP.md", "docs/88API_SETUP.en.md",
    "docs/research/2026-10-what-drives-views/README.md",
    "docs/research/2026-10-what-drives-views/article-zh.md",
    "docs/research/2026-10-what-drives-views/article-en.md",
    "docs/research/2026-10-what-drives-views/sources.md",
)
FENCES = re.compile(r"^```[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
LINKS = re.compile(r'\]\(([^\s)]+)\)|(?:href|src)="([^"]+)"')
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}
CONTACT_MARKERS = ("qq", "feishu", "wechat", "weixin", "lark", "contact")
QR_NAME = re.compile(r"(?:^|[^a-z0-9])(?:qr|qrcode)(?:[^a-z0-9]|$)")
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".mypy_cache", ".pytest_cache", "coverage",
}


def is_personal_contact_qr_name(name: str) -> bool:
    """True for image names that look like a personal contact QR code."""
    filename = Path(unquote(name)).name.lower()
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    if suffix and suffix not in IMAGE_SUFFIXES:
        return False
    tokens = set(re.findall(r"[a-z0-9]+", stem))
    has_contact = any(marker in tokens or marker in stem for marker in CONTACT_MARKERS)
    has_qr = bool(tokens & {"qr", "qrcode"}) or bool(QR_NAME.search(stem))
    return has_contact and has_qr


def is_personal_contact_qr_ref(value: str) -> bool:
    path = unquote(urlsplit(value).path)
    return is_personal_contact_qr_name(Path(path).name or value)


def iter_personal_contact_qr_files(root: Path) -> list[str]:
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [item for item in dirnames if item not in SKIP_DIRS]
        for filename in filenames:
            if is_personal_contact_qr_name(filename):
                rel = Path(dirpath, filename).relative_to(root).as_posix()
                hits.append(rel)
    return sorted(hits)


def collect_links(content: str) -> list[str]:
    prose = FENCES.sub("", content)
    return [unescape(first or second) for first, second in LINKS.findall(prose)]


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
        links = collect_links(content)
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
        if any(is_personal_contact_qr_ref(link) for link in links):
            errors.append(f"{name}: personal contact QR code is linked again")
        if content.count("<details>") != content.count("</details>"):
            errors.append(f"{name}: unbalanced FAQ disclosure blocks")

    for name in GUIDES:
        path = ROOT / name
        if not path.is_file():
            errors.append(f"Missing guide: {name}")
            continue
        links = collect_links(path.read_text(encoding="utf-8"))
        for link in links:
            if is_personal_contact_qr_ref(link):
                errors.append(f"{name}: personal contact QR code is linked again")
            url = urlsplit(link)
            if not url.scheme and not url.netloc and url.path:
                if not (path.parent / unquote(url.path)).exists():
                    errors.append(f"{name}: broken local link: {link}")

    if (ROOT / ".github/README.md").exists():
        errors.append(".github/README.md would override the canonical root README")
    for found in iter_personal_contact_qr_files(ROOT):
        errors.append(f"{found}: personal contact QR image must not be committed")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {len(FILES)} READMEs and {len(GUIDES)} guides; local links and README consistency checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
