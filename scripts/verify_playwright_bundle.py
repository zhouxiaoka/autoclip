"""W157-F7 bundle check: the portable Python must import playwright and ship its driver,
but must not carry browser binaries (rendering uses the system Chrome / Edge).

Run with the bundled interpreter:  <portable python> -B scripts/verify_playwright_bundle.py --python-dir <dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BROWSER_DIR_PREFIXES = ("chromium", "chromium_headless_shell", "firefox", "webkit", "ffmpeg")


def check(python_dir: Path | None) -> list[str]:
    problems: list[str] = []
    try:
        import playwright
        from playwright.async_api import async_playwright  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return [f"playwright is not importable from the bundled Python: {type(exc).__name__}: {exc}"]
    package = Path(playwright.__file__).resolve().parent
    if python_dir is not None and python_dir.resolve() not in package.parents:
        problems.append(f"playwright resolves outside the bundle: {package}")
    driver = package / "driver"
    if not driver.is_dir() or not any(driver.iterdir()):
        problems.append("playwright driver directory is missing or empty")
    for root in [package / "driver" / "package" / ".local-browsers", package / ".local-browsers"]:
        if root.is_dir() and any(c.name.startswith(BROWSER_DIR_PREFIXES) for c in root.iterdir()):
            problems.append(f"browser binaries were bundled under {root.name}; the desktop build must not ship browsers")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    problems = check(args.python_dir)
    if problems:
        for line in problems:
            print("ERROR:", line)
        return 1
    import playwright
    print(f"OK (playwright bundled at {Path(playwright.__file__).parent.name}, no browsers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
