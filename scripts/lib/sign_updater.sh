# Shared by build_macos_arm.sh / build_windows_x64.sh.
# Signs a file with the Tauri updater minisign key and writes <file>.sig.
# Missing key is not fatal: the installer/DMG still ships; in-app update just
# won't have a signed artifact for this platform.

sign_updater_artifact() {
    local file="$1"
    if [ ! -f "$file" ]; then
        echo "ERROR: cannot sign missing file: $file"
        return 1
    fi
    if [ -z "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
        echo "NOTE: TAURI_SIGNING_PRIVATE_KEY unset — skip updater signature for $(basename "$file")"
        return 0
    fi
    echo "==> Signing updater artifact $(basename "$file")"
    cargo tauri signer sign "$file"
    if [ ! -f "${file}.sig" ]; then
        echo "ERROR: signer did not write ${file}.sig"
        return 1
    fi
    echo "OK (${file}.sig)"
}
