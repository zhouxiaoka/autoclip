# Desktop dependency integrity and release signing

Desktop builds verify a reviewed SHA-256 before extracting Python or FFmpeg.
Every cached archive is rehashed; an invalid cache is discarded. Alternate
mirrors must serve the exact pinned bytes. A download failure or mismatch stops
the build before extraction. Verification uses host `sha256sum` or `shasum`,
never the downloaded Python interpreter.

The default Python 3.13.13 / 20260510 pins were read from the official
[Python release asset metadata](https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/20260510).
The Windows FFmpeg pin comes from the official
[versioned Gyan release metadata](https://api.github.com/repos/GyanD/codexffmpeg/releases/tags/9.0.2).
The macOS FFmpeg 7.1.1 archive pins were calculated from the publisher's HTTPS
[ffmpeg archive](https://www.osxexperts.net/ffmpeg711arm.zip) and
[ffprobe archive](https://www.osxexperts.net/ffprobe711arm.zip). The publisher does
not supply a separately verified signature here; pinning prevents subsequent
mirror/cache substitutions, not an already-compromised upstream release.

For a custom Python release, set `PBS_VERSION`, `PBS_PYTHON_VERSION`, and
`PBS_SHA256` to the intended release and an independently verified 64-digit
SHA-256. Unknown versions have no permissive fallback. A manually populated
`build/pbs-cache/` archive must pass the same digest verification. Never obtain
the expected digest from an untrusted download mirror.

Build without `TAURI_SIGNING_PRIVATE_KEY` or its password in the environment.
The build rejects those variables before preparing the portable runtime. For
local signing, finish the build first, then load the key in a separate shell
and source `scripts/lib/sign_updater.sh`; call `sign_updater_artifact` with the
finished `.app.tar.gz` or installer path. Do not run downloaded runtimes in
that signing shell. For stronger isolation, sign on a separate trusted machine.

CI uses a fresh release runner to sign unsigned build artifacts; the build
runners never receive updater signing secrets. Manual build-only workflow runs
produce unsigned updater artifacts. Tagged releases sign and verify both
platforms before publishing. SHA-256 checks establish download integrity, not
a complete reproducible-build or third-party dependency audit.

Offline regression checks: `python3 scripts/test_desktop_download_integrity.py`.
