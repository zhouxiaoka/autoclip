"""#122: Intel Mac packaging script exists and targets x86_64 without notarization."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_intel_macos_build_script_targets_x86_64():
    arm = (ROOT / 'scripts/build_macos_arm.sh').read_text()
    intel = (ROOT / 'scripts/build_macos_intel.sh').read_text()
    assert 'PBS_TRIPLE="aarch64-apple-darwin"' in arm
    assert 'PBS_TRIPLE="x86_64-apple-darwin"' in intel
    assert '_x64.dmg' in intel and '_aarch64.dmg' not in intel
    # each script reads its own pinned ffmpeg file, and the Intel pin is an x86_64 build.
    assert 'scripts/ffmpeg-macos-x64.env' in intel and 'ffmpeg-macos-arm64.env' not in intel
    assert 'scripts/ffmpeg-macos-arm64.env' in arm and 'ffmpeg-macos-x64.env' not in arm
    intel_pin = (ROOT / 'scripts/ffmpeg-macos-x64.env').read_text()
    assert '/download/macos/amd64/' in intel_pin and '/arm64/' not in intel_pin
    assert 'notariz' not in intel.lower()
    common = (ROOT / 'scripts/lib/desktop_build_common.sh').read_text()
    assert "macosx_11_0_x86_64" in common
    assert "PBS_TRIPLE" in common


def test_updater_manifest_already_accepts_darwin_x86_64():
    text = (ROOT / 'scripts/write_updater_manifest.py').read_text()
    assert '--darwin-x86_64' in text
