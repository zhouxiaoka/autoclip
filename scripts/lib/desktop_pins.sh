#!/bin/bash
# shellcheck shell=bash
# Read the Desktop Build pin files. bash 3.2 safe. Does not download anything.

load_desktop_pins() {
    local root="$1"
    # shellcheck source=ffmpeg_pin.sh
    source "$root/scripts/lib/ffmpeg_pin.sh"
    read_ffmpeg_pin "$root/scripts/lib/desktop_toolchain.env" \
        RUST_TOOLCHAIN NODE_VERSION TAURI_CLI_VERSION RUSTUP_ACTION_SHA \
        MACOS_RUNNER WINDOWS_RUNNER MACOS_TARGET WINDOWS_TARGET || return 1
    read_ffmpeg_pin "$root/scripts/lib/desktop_download_pins.env" \
        PBS_VERSION PBS_PYTHON_VERSION \
        PBS_SHA256_x86_64_pc_windows_msvc \
        PBS_SHA256_aarch64_apple_darwin \
        PBS_SHA256_x86_64_apple_darwin || return 1
    read_ffmpeg_pin "$root/scripts/lib/tauri_cli_checksums.env" \
        TAURI_CLI_SHA256_aarch64_apple_darwin \
        TAURI_CLI_SHA256_x86_64_pc_windows_msvc || return 1
    is_exact_semver "$RUST_TOOLCHAIN" || { echo "ERROR: RUST_TOOLCHAIN must be exact x.y.z" >&2; return 1; }
    is_exact_semver "$NODE_VERSION" || { echo "ERROR: NODE_VERSION must be exact x.y.z" >&2; return 1; }
    is_exact_semver "$TAURI_CLI_VERSION" || { echo "ERROR: TAURI_CLI_VERSION must be exact x.y.z" >&2; return 1; }
    [[ "$RUSTUP_ACTION_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: RUSTUP_ACTION_SHA must be 40 hex chars" >&2; return 1; }
    [[ "$MACOS_RUNNER" == "macos-15" && "$WINDOWS_RUNNER" == "windows-latest" ]] || {
        echo "ERROR: desktop runners must stay macos-15 and windows-latest" >&2; return 1; }
    [[ "$MACOS_TARGET" == "aarch64-apple-darwin" && "$WINDOWS_TARGET" == "x86_64-pc-windows-msvc" ]] || {
        echo "ERROR: desktop targets must stay arm64 macOS and x64 Windows" >&2; return 1; }
    local sha_name sha_value
    for sha_name in PBS_SHA256_x86_64_pc_windows_msvc PBS_SHA256_aarch64_apple_darwin \
        PBS_SHA256_x86_64_apple_darwin TAURI_CLI_SHA256_aarch64_apple_darwin \
        TAURI_CLI_SHA256_x86_64_pc_windows_msvc; do
        sha_value="${!sha_name}"
        is_sha256 "$sha_value" || { echo "ERROR: $sha_name is not a lowercase sha256" >&2; return 1; }
    done
}

is_exact_semver() {
    [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

is_sha256() {
    [[ "$1" =~ ^[0-9a-f]{64}$ ]]
}

tauri_cli_target_for() {
    local os="$1" mach="$2"
    case "$os:$mach" in
        Darwin:arm64) printf '%s\n' "$MACOS_TARGET" ;;
        MINGW*:x86_64|MSYS*:x86_64|CYGWIN*:x86_64) printf '%s\n' "$WINDOWS_TARGET" ;;
        *) echo "ERROR: no pinned tauri-cli asset for $os $mach" >&2; return 1 ;;
    esac
}

tauri_cli_asset_url() {
    local version="$1" target="$2"
    is_exact_semver "$version" || { echo "ERROR: tauri-cli version must be exact x.y.z" >&2; return 1; }
    case "$target" in
        aarch64-apple-darwin|x86_64-pc-windows-msvc) ;;
        *) echo "ERROR: tauri-cli target is not a Desktop Build target: $target" >&2; return 1 ;;
    esac
    printf 'https://github.com/tauri-apps/tauri/releases/download/tauri-cli-v%s/cargo-tauri-%s.zip\n' \
        "$version" "$target"
}

tauri_cli_sha256_for() {
    local target="$1" name value
    name="TAURI_CLI_SHA256_${target//-/_}"
    value="${!name-}"
    is_sha256 "$value" || { echo "ERROR: missing tauri-cli sha256 for $target" >&2; return 1; }
    printf '%s\n' "$value"
}

pbs_sha256_for_triple() {
    local triple="$1" name value
    name="PBS_SHA256_${triple//-/_}"
    value="${!name-}"
    is_sha256 "$value" || { echo "ERROR: missing portable Python sha256 for $triple" >&2; return 1; }
    printf '%s\n' "$value"
}

sha256_file() {
    local file="$1" hash
    if [ ! -f "$file" ]; then
        echo "ERROR: cannot hash missing file: $file" >&2
        return 1
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        hash=$(sha256sum "$file" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
        hash=$(shasum -a 256 "$file" | awk '{print $1}')
    elif command -v python3 >/dev/null 2>&1; then
        hash=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$file")
    elif command -v python >/dev/null 2>&1; then
        hash=$(python -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$file")
    else
        echo "ERROR: need sha256sum, shasum, or python to verify pinned downloads" >&2
        return 1
    fi
    printf '%s\n' "$hash"
}

# Returns 0 when the file matches. A mismatch deletes the file and returns 1.
verify_sha256_file() {
    local file="$1" expected="$2" actual
    is_sha256 "$expected" || { echo "ERROR: checksum is not lowercase sha256" >&2; return 1; }
    [ -f "$file" ] || return 1
    actual=$(sha256_file "$file") || return 1
    if [ "$actual" != "$expected" ]; then
        echo "ERROR: sha256 mismatch for $file" >&2
        rm -f "$file"
        return 1
    fi
}

assert_tauri_cli_output() {
    local expected="$1" text="$2" found count
    found=$(printf '%s\n' "$text" | grep -E '^tauri-cli [0-9]+\.[0-9]+\.[0-9]+$' || true)
    count=$(printf '%s\n' "$found" | grep -c . || true)
    if [ "$count" -ne 1 ] || [ "$found" != "tauri-cli $expected" ]; then
        echo "ERROR: expected tauri-cli $expected" >&2
        printf '%s\n' "$text" >&2
        return 1
    fi
}
