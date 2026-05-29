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
    backend/ "$BACKEND_DEST/"
echo "OK"

# ---- ffmpeg ----
echo "==> Bundling ffmpeg"
mkdir -p "$RESOURCES_DIR/ffmpeg"
if command -v ffmpeg &> /dev/null; then
    # Use ditto to avoid copying extended attributes that break Tauri's resource scan
    ditto --noacl --noextattr "$(which ffmpeg)" "$RESOURCES_DIR/ffmpeg/ffmpeg"
    chmod 755 "$RESOURCES_DIR/ffmpeg/ffmpeg"
    echo "OK ($(ls -lh "$RESOURCES_DIR/ffmpeg/ffmpeg" | awk '{print $5}'))"
else
    echo "WARN: ffmpeg not on PATH — bundling empty placeholder"
    : > "$RESOURCES_DIR/ffmpeg/ffmpeg"
    chmod 755 "$RESOURCES_DIR/ffmpeg/ffmpeg"
fi

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
DMG_PATH="src-tauri/target/release/bundle/macos/AutoClip Desktop_1.0.0_aarch64.dmg"
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
