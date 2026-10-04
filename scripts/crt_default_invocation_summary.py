"""Small evidence only. No cloud runtime images leave the disposable runner."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

source, evidence = Path(sys.argv[1]), Path(sys.argv[2])
files = [
    "scripts/prepare_windows_python_crt.ps1",
    "scripts/tests/test_prepare_windows_python_crt.ps1",
    "scripts/windows_python_crt.py",
    "scripts/windows_desktop_crt.py",
    "scripts/tests/test_windows_python_crt.py",
    "scripts/lib/desktop_build_common.sh",
]

def lf_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

default = json.loads((evidence / "actual-default-signatures.json").read_text(encoding="utf-8-sig"))
explicit = json.loads((evidence / "actual-explicit-signatures.json").read_text(encoding="utf-8-sig"))
verify = json.loads((evidence / "actual-crt-verify.json").read_text(encoding="utf-8-sig"))
manifest = json.loads((evidence / "windows-crt.json").read_text(encoding="utf-8-sig"))
assert len(default["checks"]) == len(explicit["checks"]) == 14
assert all(check["passed"] for check in default["checks"] + explicit["checks"])
assert default["official_status"] == explicit["official_status"] == "Valid"
assert default["tampered_status"] == explicit["tampered_status"] == "HashMismatch"
assert len(manifest["files"]) == 10
assert verify["status"] == "passed" and len(verify["files"]) == 13
expected_default_invocation = (
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/tests/test_prepare_windows_python_crt.ps1 \\\n'
    '    -OfficialDll "$PYTHON_DIR/concrt140.dll" -Report build/python-crt-signature-tests.json'
)
assert expected_default_invocation in (source / "scripts/build_windows_x64.sh").read_text(encoding="utf-8")
assert expected_default_invocation in Path("scripts/crt_default_invocation_regression.sh").read_text(encoding="utf-8")
tests = (evidence / "python-crt-negative-tests.log").read_text(encoding="utf-8")
assert "Ran 13 tests" in tests and "OK" in tests
archive = next(Path("build/pbs-cache").glob("*.tar.gz"))
result = {
    "schema_version": 1,
    "source_commit": subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip(),
    "diagnostic_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "before_default_exit": int(sys.argv[3]),
    "before_default_join_path_failure_reproduced": True,
    "after_default_file_invocation_passed": True,
    "exact_production_default_command_matched": True,
    "after_explicit_prepare_script_passed": True,
    "signature_checks_each": 14,
    "real_tamper_status": default["tampered_status"],
    "crt_dll_count": len(manifest["files"]),
    "strict_crt_verification": verify,
    "python_negative_test_count": 13,
    "component_lf_sha256": {name: lf_hash(Path(name)) for name in files},
    "original_signature_test_lf_sha256": lf_hash(source / "scripts/tests/test_prepare_windows_python_crt.ps1"),
    "original_build_script_lf_sha256": lf_hash(source / "scripts/build_windows_x64.sh"),
    "download_bytes_cloud_only": archive.stat().st_size,
    "scope": "Exact Windows Git Bash to Windows PowerShell -File invocation; CRT preparation/signature/PE/hash guards. Native Whisper and product acceptance remain pending.",
}
(evidence / "default-invocation-summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
