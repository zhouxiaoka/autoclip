#!/bin/bash
# AutoClip Desktop Windows x64 build
#
# Same python-build-standalone route as build_macos_arm.sh: portable Python +
# backend source + static ffmpeg/ffprobe, packaged by Tauri into an NSIS
# installer. Run from Git Bash (or the `bash` shell on a GitHub windows-*
# runner); the shared steps in scripts/lib/desktop_build_common.sh are written
# to work without rsync / unzip / ditto.
#
# Unlike macOS, the runtime resources are declared in
# src-tauri/tauri.windows.conf.json (bundle.resources) so the installer carries
# them; an .exe installer can't have files injected after the fact. Tauri only
# merges that file when building on Windows, so macOS builds are unaffected.
#
# Prerequisites on the build machine:
#   - Node.js 18+, Rust (stable-x86_64-pc-windows-msvc), cargo-tauri
#   - Visual Studio Build Tools (C++ workload) — required by Tauri on Windows
#   - Git Bash (provides bash, curl, tar)

set -e

echo "==> AutoClip Desktop build (Windows x64)"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) ;;
    *) echo "ERROR: this script must run on Windows (Git Bash / MSYS). Detected: $(uname -s)"; exit 1 ;;
esac

PBS_TRIPLE="x86_64-pc-windows-msvc"
PORTABLE_PY_REL="python.exe"
# shellcheck source=lib/desktop_build_common.sh
source "$PROJECT_ROOT/scripts/lib/desktop_build_common.sh"
# shellcheck source=lib/sign_updater.sh
source "$PROJECT_ROOT/scripts/lib/sign_updater.sh"

check_build_tools
prepare_portable_python
install_backend_deps
copy_backend_source
verify_backend_deps

# ---- ffmpeg ----
# Pin a versioned upstream release and its official GitHub asset digest. Alternate
# mirrors may be added only if they serve the exact same verified archive.
echo "==> Bundling static ffmpeg + ffprobe (win64)"
mkdir -p "$RESOURCES_DIR/ffmpeg"
FFMPEG_CACHE="build/ffmpeg-cache"
FFMPEG_ZIP="$FFMPEG_CACHE/ffmpeg-win64.zip"
download_with_mirrors "$FFMPEG_ZIP" 50000000 \
    "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba" \
    "https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip"
for name in ffmpeg ffprobe; do
    extract_from_zip "$FFMPEG_ZIP" "$name.exe" "$RESOURCES_DIR/ffmpeg/$name.exe"
done
"$RESOURCES_DIR/ffmpeg/ffmpeg.exe" -version | head -1
echo "OK (ffmpeg $(ls -lh "$RESOURCES_DIR/ffmpeg/ffmpeg.exe" | awk '{print $5}'), ffprobe $(ls -lh "$RESOURCES_DIR/ffmpeg/ffprobe.exe" | awk '{print $5}'))"

# ---- smoke test the portable runtime before spending minutes in cargo ----
echo "==> Smoke-testing portable runtime imports"
(cd "$RESOURCES_DIR" && "$PORTABLE_PY" -c "import backend.app_factory, backend.desktop_main; print('OK (backend imports under portable python)')")

build_frontend

# ---- Tauri build ----
# Tauri merges tauri.windows.conf.json on top of tauri.conf.json here, which
# declares resources/{python,backend,ffmpeg} and restricts targets to nsis.
echo "==> Building Tauri application (this takes a few minutes)"
(cd src-tauri && cargo tauri build --bundles nsis)

APP_VERSION="$(app_version)"
NSIS_DIR="src-tauri/target/release/bundle/nsis"
INSTALLER="$(ls "$NSIS_DIR"/*.exe 2>/dev/null | head -1)"
if [ -z "$INSTALLER" ]; then
    echo "ERROR: NSIS installer not found under $NSIS_DIR"; exit 1
fi

sign_updater_artifact "$INSTALLER"

# ---- summary ----
echo ""
echo "==> Build complete"
echo "    Version:   $APP_VERSION"
echo "    Installer: $INSTALLER ($(du -sh "$INSTALLER" | awk '{print $1}'))"
