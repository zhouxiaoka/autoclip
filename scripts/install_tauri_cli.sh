#!/bin/bash
# Install the pinned tauri-cli release zip. Does not compile Rust.
# A restored cache is hashed again before the binary is put on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/desktop_pins.sh
source "$ROOT/scripts/lib/desktop_pins.sh"

python_bin() {
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
    elif command -v python >/dev/null 2>&1; then
        command -v python
    else
        echo "ERROR: python is required to unpack the pinned tauri-cli zip" >&2
        return 1
    fi
}

extract_tauri_binary() {
    local zip="$1" dest="$2" binary_name="$3"
    mkdir -p "$dest"
    "$(python_bin)" - "$zip" "$dest" "$binary_name" <<'PY'
import sys
import zipfile
from pathlib import Path

zip_path, dest, binary_name = sys.argv[1:]
dest_path = Path(dest)
with zipfile.ZipFile(zip_path) as archive:
    matches = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        parts = Path(name).parts
        if ".." in parts or name.startswith("/") or name.startswith("../"):
            raise SystemExit(f"ERROR: tauri-cli zip path escapes the archive: {info.filename}")
        if Path(name).name == binary_name and len(parts) == 1:
            matches.append(info)
    if len(matches) != 1:
        raise SystemExit(f"ERROR: expected one {binary_name} at the zip root, found {len(matches)}")
    target = dest_path / binary_name
    with archive.open(matches[0]) as src, target.open("wb") as out:
        out.write(src.read())
    target.chmod(0o755)
PY
}

install_pinned_tauri_cli() {
    load_desktop_pins "$ROOT"
    local os_name mach target expected_sha url dest binary_name zip output
    os_name="$(uname -s)"
    mach="$(uname -m)"
    target="$(tauri_cli_target_for "$os_name" "$mach")"
    expected_sha="$(tauri_cli_sha256_for "$target")"
    url="$(tauri_cli_asset_url "$TAURI_CLI_VERSION" "$target")"
    dest="$ROOT/build/tool-cache/tauri-cli/${TAURI_CLI_VERSION}/${target}"
    case "$target" in
        x86_64-pc-windows-msvc) binary_name="cargo-tauri.exe" ;;
        *) binary_name="cargo-tauri" ;;
    esac
    mkdir -p "$dest"
    zip="$dest/cargo-tauri-${target}.zip"
    if ! verify_sha256_file "$zip" "$expected_sha"; then
        rm -f "$zip" "$zip.partial" "$dest/$binary_name"
        echo "==> Downloading pinned tauri-cli ${TAURI_CLI_VERSION} (${target})"
        if ! curl -L --fail --retry 3 --retry-all-errors --retry-delay 2 \
            --connect-timeout 15 --max-time 180 -o "$zip.partial" "$url"; then
            rm -f "$zip.partial"
            echo "ERROR: could not download pinned tauri-cli" >&2
            return 1
        fi
        mv "$zip.partial" "$zip"
        if ! verify_sha256_file "$zip" "$expected_sha"; then
            rm -f "$zip" "$zip.partial" "$dest/$binary_name"
            echo "ERROR: downloaded tauri-cli zip failed sha256" >&2
            return 1
        fi
    else
        echo "==> Pinned tauri-cli ${TAURI_CLI_VERSION} zip matched sha256"
    fi
    extract_tauri_binary "$zip" "$dest" "$binary_name"
    output="$("$dest/$binary_name" --version 2>&1)" || {
        echo "ERROR: pinned tauri-cli did not run" >&2
        return 1
    }
    assert_tauri_cli_output "$TAURI_CLI_VERSION" "$output"
    # Drop a previously cached cargo install so `cargo tauri` cannot select it.
    if [ -n "${CARGO_HOME:-}" ]; then
        rm -f "$CARGO_HOME/bin/cargo-tauri" "$CARGO_HOME/bin/cargo-tauri.exe" \
            "$CARGO_HOME/bin/tauri" "$CARGO_HOME/bin/tauri.exe"
    elif [ -n "${HOME:-}" ]; then
        rm -f "$HOME/.cargo/bin/cargo-tauri" "$HOME/.cargo/bin/cargo-tauri.exe" \
            "$HOME/.cargo/bin/tauri" "$HOME/.cargo/bin/tauri.exe"
    fi
    if [ -n "${GITHUB_PATH:-}" ]; then
        if command -v cygpath >/dev/null 2>&1; then
            cygpath -w "$dest" >> "$GITHUB_PATH"
        else
            printf '%s\n' "$dest" >> "$GITHUB_PATH"
        fi
    fi
    echo "==> tauri-cli ${TAURI_CLI_VERSION} ready"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    install_pinned_tauri_cli
fi
