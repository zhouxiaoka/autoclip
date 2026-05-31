#!/bin/bash
# AutoClip Desktop macOS Apple Silicon build
# Bundles a portable python-build-standalone Python runtime + backend source
# so end users can double-click to run without installing Python.

set -e

echo "==> AutoClip Desktop build (macOS arm64)"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# ---- prerequisite checks ----
echo "==> Checking build environment"
for cmd in node python3 cargo; do
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

RESOURCES_DIR="src-tauri/resources"

# ---- portable Python runtime ----
PBS_VERSION="20260510"
PBS_PYTHON_VERSION="3.13.13"
PBS_TARBALL="cpython-${PBS_PYTHON_VERSION}+${PBS_VERSION}-aarch64-apple-darwin-install_only.tar.gz"
# Mirrors (first that works wins). ghproxy.com is a github release proxy commonly
# used in CN; falls back to direct github + jsdelivr cdn.
PBS_URLS=(
    "https://ghproxy.com/https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_VERSION}/${PBS_TARBALL}"
    "https://mirror.ghproxy.com/https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_VERSION}/${PBS_TARBALL}"
    "https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_VERSION}/${PBS_TARBALL}"
)
PBS_CACHE="build/pbs-cache/${PBS_TARBALL}"

echo "==> Preparing portable Python runtime"
mkdir -p "build/pbs-cache"
# Sanity check: PBS install_only tarballs are ~25MB. Anything smaller is a partial download.
PBS_MIN_BYTES=20000000
if [ -f "$PBS_CACHE" ]; then
    cached_size=$(stat -f %z "$PBS_CACHE" 2>/dev/null || stat -c %s "$PBS_CACHE" 2>/dev/null || echo 0)
    if [ "$cached_size" -lt "$PBS_MIN_BYTES" ]; then
        echo "  Cached file too small ($cached_size bytes), redownloading"
        rm -f "$PBS_CACHE"
    fi
fi
if [ ! -f "$PBS_CACHE" ]; then
    for url in "${PBS_URLS[@]}"; do
        echo "  Trying: $url"
        if curl -L --fail --connect-timeout 15 --max-time 600 -o "$PBS_CACHE.tmp" "$url"; then
            tmp_size=$(stat -f %z "$PBS_CACHE.tmp" 2>/dev/null || stat -c %s "$PBS_CACHE.tmp" 2>/dev/null || echo 0)
            if [ "$tmp_size" -ge "$PBS_MIN_BYTES" ]; then
                mv "$PBS_CACHE.tmp" "$PBS_CACHE"
                break
            else
                echo "  Download too small ($tmp_size bytes), trying next mirror..."
                rm -f "$PBS_CACHE.tmp"
            fi
        else
            rm -f "$PBS_CACHE.tmp"
            echo "  Failed, trying next mirror..."
        fi
    done
    if [ ! -f "$PBS_CACHE" ]; then
        echo "ERROR: failed to download Python runtime from all mirrors"
        echo "       You can download it manually:"
        echo "         ${PBS_URLS[0]}"
        echo "       and place it at: $PBS_CACHE"
        exit 1
    fi
fi
echo "  Cached: $PBS_CACHE ($(du -h "$PBS_CACHE" | awk '{print $1}'))"

PYTHON_DIR="$RESOURCES_DIR/python"
rm -rf "$PYTHON_DIR"
mkdir -p "$RESOURCES_DIR"
tar -xzf "$PBS_CACHE" -C "$RESOURCES_DIR"
# PBS extracts into ./python — move into resources/python (already correct)
echo "OK"

PORTABLE_PY="$PYTHON_DIR/bin/python3"
"$PORTABLE_PY" -V

# ---- install backend Python deps into the portable runtime ----
echo "==> Installing backend Python dependencies into portable runtime"
PIP_INDEX="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
"$PORTABLE_PY" -m pip install --upgrade pip --quiet --index-url "$PIP_INDEX"
"$PORTABLE_PY" -m pip install -r requirements.txt --quiet --index-url "$PIP_INDEX"
echo "OK"

# ---- copy backend source ----
echo "==> Copying backend source"
BACKEND_DEST="$RESOURCES_DIR/backend"
rm -rf "$BACKEND_DEST"
mkdir -p "$BACKEND_DEST"
# Use rsync to exclude noise
rsync -a \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache/' \
    --exclude='.mypy_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='tests/' \
    --exclude='data/' \
    --exclude='logs/' \
    --exclude='temp/' \
    --exclude='*.log' \
    --exclude='*.pid' \
    --exclude='*.rdb' \
    backend/ "$BACKEND_DEST/"
echo "OK"

# ---- dependency completeness check ----
# Guard against the classic "works in dev, broken in the bundle" trap: the dev
# venv accumulates packages that requirements.txt never listed, so the portable
# runtime ships without them and the backend 500s at runtime (e.g. pytz, the
# LLM SDKs). Statically scan the copied backend for third-party imports and
# assert every one resolves in the portable runtime. Fail the build if not.
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

# ---- ffmpeg ----
# We bundle STATIC, self-contained ffmpeg + ffprobe (arm64). Do NOT copy the
# homebrew binary from PATH: it is dynamically linked against ~57 dylibs under
# /opt/homebrew and is unusable on any machine without homebrew installed.
echo "==> Bundling static ffmpeg + ffprobe (arm64)"
mkdir -p "$RESOURCES_DIR/ffmpeg"
FFMPEG_CACHE="build/ffmpeg-cache"
mkdir -p "$FFMPEG_CACHE"
# Static arm64 builds from osxexperts.net (zero non-system dylib deps).
FFMPEG_MIN_BYTES=15000000  # static binaries are ~48MB; zips ~20MB
declare -a FF_NAMES=("ffmpeg" "ffprobe")
declare -a FF_URLS=(
    "https://www.osxexperts.net/ffmpeg711arm.zip"
    "https://www.osxexperts.net/ffprobe711arm.zip"
)
for i in 0 1; do
    name="${FF_NAMES[$i]}"
    url="${FF_URLS[$i]}"
    zip_cache="$FFMPEG_CACHE/${name}.zip"
    if [ -f "$zip_cache" ]; then
        sz=$(stat -f %z "$zip_cache" 2>/dev/null || stat -c %s "$zip_cache" 2>/dev/null || echo 0)
        [ "$sz" -lt "$FFMPEG_MIN_BYTES" ] && { echo "  cached $name zip too small, redownloading"; rm -f "$zip_cache"; }
    fi
    if [ ! -f "$zip_cache" ]; then
        echo "  Downloading static $name: $url"
        if ! curl -L --fail --connect-timeout 15 --max-time 300 -o "$zip_cache.tmp" "$url"; then
            echo "ERROR: failed to download static $name from $url"; rm -f "$zip_cache.tmp"; exit 1
        fi
        mv "$zip_cache.tmp" "$zip_cache"
    fi
    # Extract just the binary into the bundle (ditto strips xattrs that trip Tauri's scanner)
    tmp_extract="$FFMPEG_CACHE/extract-$name"
    rm -rf "$tmp_extract"; mkdir -p "$tmp_extract"
    unzip -o -q "$zip_cache" -d "$tmp_extract"
    src_bin="$(find "$tmp_extract" -type f -name "$name" | head -1)"
    if [ -z "$src_bin" ]; then echo "ERROR: $name binary not found inside $zip_cache"; exit 1; fi
    ditto --noacl --noextattr "$src_bin" "$RESOURCES_DIR/ffmpeg/$name"
    chmod 755 "$RESOURCES_DIR/ffmpeg/$name"
    rm -rf "$tmp_extract"
done
# Sanity: bundled binaries must have no homebrew dylib deps
for name in ffmpeg ffprobe; do
    hb=$(otool -L "$RESOURCES_DIR/ffmpeg/$name" 2>/dev/null | grep -c homebrew || true)
    if [ "$hb" -ne 0 ]; then
        echo "ERROR: bundled $name still has $hb homebrew dylib deps — not self-contained"; exit 1
    fi
done
echo "OK (ffmpeg $(ls -lh "$RESOURCES_DIR/ffmpeg/ffmpeg" | awk '{print $5}'), ffprobe $(ls -lh "$RESOURCES_DIR/ffmpeg/ffprobe" | awk '{print $5}'))"

# ---- frontend ----
echo "==> Building frontend"
cd frontend
npm ci --silent
npm run build
cd ..
echo "OK"

# ---- Tauri build ----
echo "==> Building Tauri application (this takes a few minutes)"
cd src-tauri
# Skip the bundler-driven dmg step (it's flaky on macOS 26); we'll create the dmg ourselves
cargo tauri build --bundles app
cd ..

APP_PATH="src-tauri/target/release/bundle/macos/AutoClip Desktop.app"
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: app bundle not built at $APP_PATH"; exit 1
fi
echo "OK"

# ---- inject resources into .app ----
# We don't declare resources in tauri.conf.json because Tauri's resource
# scanner trips on extended attributes / large binaries on macOS 26.
# Copying them in post-build is reliable.
echo "==> Injecting runtime resources into app bundle"
APP_RESOURCES="$APP_PATH/Contents/Resources/resources"
rm -rf "$APP_RESOURCES"
mkdir -p "$APP_RESOURCES"
cp -R "$RESOURCES_DIR/python" "$APP_RESOURCES/"
cp -R "$RESOURCES_DIR/backend" "$APP_RESOURCES/"
cp -R "$RESOURCES_DIR/ffmpeg" "$APP_RESOURCES/"
echo "OK"

# ---- ad-hoc re-sign so macOS will let users open it ----
echo "==> Re-signing app (ad-hoc)"
codesign --force --deep --sign - "$APP_PATH"
echo "OK"

# ---- create DMG manually ----
echo "==> Creating DMG"
# Read the version from tauri.conf.json so the DMG name never drifts from the app version.
APP_VERSION=$(grep '"version"' src-tauri/tauri.conf.json | head -1 | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')
APP_VERSION="${APP_VERSION:-1.1.0}"
DMG_PATH="src-tauri/target/release/bundle/macos/AutoClip Desktop_${APP_VERSION}_aarch64.dmg"
rm -f "$DMG_PATH"
hdiutil create -volname "AutoClip Desktop" \
    -srcfolder "$APP_PATH" \
    -ov -format UDZO \
    "$DMG_PATH"
echo "OK"

# ---- summary ----
APP_SIZE=$(du -sh "$APP_PATH" | awk '{print $1}')
DMG_SIZE=$(du -sh "$DMG_PATH" | awk '{print $1}')
echo ""
echo "==> Build complete"
echo "    App:  $APP_PATH ($APP_SIZE)"
echo "    DMG:  $DMG_PATH ($DMG_SIZE)"
