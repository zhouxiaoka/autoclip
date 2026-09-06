#!/bin/bash
# Shared steps for the AutoClip Desktop bundle (python-build-standalone route).
#
# Sourced by scripts/build_macos_arm.sh and scripts/build_windows_x64.sh. Every
# function here must work on macOS (BSD userland) AND on Git Bash / MSYS on
# Windows, so: no rsync, no unzip, no ditto, no `stat -f`-only calls. Anything
# non-trivial is delegated to the portable Python we just downloaded.
#
# Callers must `cd` to the project root and define these before sourcing:
#   PBS_TRIPLE          e.g. aarch64-apple-darwin / x86_64-pc-windows-msvc
#   PORTABLE_PY_REL     python executable relative to resources/python
#                       e.g. bin/python3 (unix) / python.exe (windows)

set -e

PBS_VERSION="${PBS_VERSION:-20260510}"
PBS_PYTHON_VERSION="${PBS_PYTHON_VERSION:-3.13.13}"
RESOURCES_DIR="src-tauri/resources"
PYTHON_DIR="$RESOURCES_DIR/python"
BACKEND_DEST="$RESOURCES_DIR/backend"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
file_size() {
    # `wc -c` is the only size probe that behaves the same under BSD (macOS)
    # and GNU (Linux / Git Bash) userlands. GNU `stat -f %z` "succeeds" but
    # prints filesystem info, which is what the old stat-based fallback did.
    if [ -f "$1" ]; then
        wc -c < "$1" | tr -d '[:space:]'
    else
        echo 0
    fi
}

human_size() {
    du -h "$1" | awk '{print $1}'
}

# download_with_mirrors <dest> <min_bytes> <url>...
# Tries each URL in order; keeps the first download that is at least
# <min_bytes> (guards against truncated files / HTML error pages).
download_with_mirrors() {
    local dest="$1" min_bytes="$2"
    shift 2
    if [ -f "$dest" ]; then
        local cached_size
        cached_size=$(file_size "$dest")
        if [ "$cached_size" -lt "$min_bytes" ]; then
            echo "  Cached file too small ($cached_size bytes), redownloading"
            rm -f "$dest"
        fi
    fi
    if [ -f "$dest" ]; then
        echo "  Cached: $dest ($(human_size "$dest"))"
        return 0
    fi
    mkdir -p "$(dirname "$dest")"
    local url tmp_size
    for url in "$@"; do
        echo "  Trying: $url"
        if curl -L --fail --connect-timeout 15 --max-time 600 -o "$dest.tmp" "$url"; then
            tmp_size=$(file_size "$dest.tmp")
            if [ "$tmp_size" -ge "$min_bytes" ]; then
                mv "$dest.tmp" "$dest"
                echo "  Downloaded: $dest ($(human_size "$dest"))"
                return 0
            fi
            echo "  Download too small ($tmp_size bytes), trying next mirror..."
        else
            echo "  Failed, trying next mirror..."
        fi
        rm -f "$dest.tmp"
    done
    echo "ERROR: failed to download from all mirrors:"
    for url in "$@"; do echo "         $url"; done
    echo "       You can download it manually and place it at: $dest"
    return 1
}

# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------
check_build_tools() {
    echo "==> Checking build environment"
    local cmd
    for cmd in node cargo curl tar; do
        if ! command -v "$cmd" &> /dev/null; then
            echo "ERROR: $cmd not installed"; exit 1
        fi
    done
    if ! command -v tauri &> /dev/null && ! command -v cargo-tauri &> /dev/null; then
        if ! cargo tauri --version &> /dev/null; then
            echo "ERROR: tauri CLI not installed (run: cargo install tauri-cli)"; exit 1
        fi
    fi
    echo "OK"
}

# Downloads the PBS "install_only" tarball for $PBS_TRIPLE (with CN-friendly
# mirrors first) and extracts it to src-tauri/resources/python. Sets PORTABLE_PY.
prepare_portable_python() {
    : "${PBS_TRIPLE:?PBS_TRIPLE must be set}"
    : "${PORTABLE_PY_REL:?PORTABLE_PY_REL must be set}"
    local tarball="cpython-${PBS_PYTHON_VERSION}+${PBS_VERSION}-${PBS_TRIPLE}-install_only.tar.gz"
    local cache="build/pbs-cache/${tarball}"
    local release="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_VERSION}/${tarball}"

    echo "==> Preparing portable Python runtime (${PBS_TRIPLE})"
    # install_only tarballs are 25-50MB; anything smaller is a partial download.
    download_with_mirrors "$cache" 20000000 \
        "https://ghproxy.com/${release}" \
        "https://mirror.ghproxy.com/${release}" \
        "${release}"

    rm -rf "$PYTHON_DIR"
    mkdir -p "$RESOURCES_DIR"
    tar -xzf "$cache" -C "$RESOURCES_DIR"   # extracts into ./python
    # Absolute so callers can `cd` (subshells into src-tauri/resources etc.) and still use it.
    PORTABLE_PY="$(pwd)/$PYTHON_DIR/$PORTABLE_PY_REL"
    if [ ! -f "$PORTABLE_PY" ]; then
        echo "ERROR: portable python not found at $PORTABLE_PY after extraction"; exit 1
    fi
    "$PORTABLE_PY" -V
    echo "OK"
}

install_backend_deps() {
    echo "==> Installing backend Python dependencies into portable runtime"
    local pip_index="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
    "$PORTABLE_PY" -m pip install --upgrade pip --quiet --index-url "$pip_index"
    "$PORTABLE_PY" -m pip install -r requirements.txt --quiet --index-url "$pip_index"
    echo "OK"
}

# Copies backend/ into the bundle, dropping caches, tests and runtime data.
# Uses Python's shutil so the exclude list behaves identically on every OS.
copy_backend_source() {
    echo "==> Copying backend source"
    rm -rf "$BACKEND_DEST"
    "$PORTABLE_PY" - backend "$BACKEND_DEST" <<'PY'
import shutil, sys
src, dest = sys.argv[1], sys.argv[2]
IGNORED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "tests", "data", "logs", "temp"}
IGNORED_SUFFIXES = (".pyc", ".log", ".pid", ".rdb")

def ignore(_dir, names):
    return {n for n in names if n in IGNORED_DIRS or n.endswith(IGNORED_SUFFIXES)}

shutil.copytree(src, dest, ignore=ignore)
PY
    echo "OK"
}

# Guard against the classic "works in dev, broken in the bundle" trap: the dev
# venv accumulates packages that requirements.txt never listed, so the portable
# runtime ships without them and the backend 500s at runtime (e.g. pytz, the
# LLM SDKs). Statically scan the copied backend for third-party imports and
# assert every one resolves in the portable runtime. Fail the build if not.
verify_backend_deps() {
    echo "==> Verifying backend dependencies are present in portable runtime"
    "$PORTABLE_PY" - "$BACKEND_DEST" <<'PY'
import ast, os, sys, importlib.util
backend_dir = sys.argv[1]
# Make the bundle's own packages resolvable (both `import backend.x` and `from core import x` styles).
sys.path.insert(0, os.path.dirname(backend_dir))  # parent → resolves `backend`
sys.path.insert(0, backend_dir)                   # backend → resolves `core`, `app`, ...
stdlib = set(sys.stdlib_module_names)
# Modules that are installed AT RUNTIME by the user (Whisper feature), not
# bundled. They are imported lazily inside functions and must NOT fail the
# build. Keep this list tight.
runtime_optional = {"faster_whisper", "ctranslate2", "huggingface_hub"}
mods = set()
for root, _, files in os.walk(backend_dir):
    if '__pycache__' in root:
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        try:
            tree = ast.parse(open(os.path.join(root, f), encoding='utf-8').read())
        except Exception:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    mods.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                mods.add(n.module.split('.')[0])
missing = sorted(
    m for m in mods
    if m and not m.startswith('_') and m not in stdlib
    and m not in runtime_optional
    and importlib.util.find_spec(m) is None
)
if missing:
    print("ERROR: backend imports modules missing from the portable runtime:")
    for m in missing:
        print("  -", m)
    print("Add them to requirements.txt so the bundle installs them.")
    sys.exit(1)
print("OK (all backend imports resolve)")
PY
}

# extract_from_zip <zip> <member-basename> <dest-file>
# Pulls a single file (matched by basename, first hit wins) out of a zip.
# Git Bash has no `unzip`, so use Python's zipfile.
extract_from_zip() {
    "$PORTABLE_PY" - "$1" "$2" "$3" <<'PY'
import os, shutil, sys, zipfile
zip_path, wanted, dest = sys.argv[1:4]
with zipfile.ZipFile(zip_path) as zf:
    for info in zf.infolist():
        if not info.is_dir() and os.path.basename(info.filename) == wanted:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
            print(f"  extracted {info.filename} -> {dest}")
            break
    else:
        print(f"ERROR: {wanted} not found inside {zip_path}")
        sys.exit(1)
PY
}

build_frontend() {
    echo "==> Building frontend"
    (cd frontend && npm ci --silent && npm run build)
    echo "OK"
}

# Reads the version from tauri.conf.json so artifact names never drift from the app version.
app_version() {
    local v
    v=$(grep '"version"' src-tauri/tauri.conf.json | head -1 | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
    echo "${v:-1.1.0}"
}
