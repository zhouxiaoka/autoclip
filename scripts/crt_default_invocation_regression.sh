#!/bin/bash
# Disposable Windows runner only; reproduce the Git Bash build invocation.
set -euo pipefail
SOURCE_DIR="$(cd "$1" && pwd)"
EVIDENCE_DIR="$(cygpath -u "$RUNNER_TEMP")/crt-default-invocation-evidence"
mkdir -p "$EVIDENCE_DIR"
PBS_TRIPLE="x86_64-pc-windows-msvc"
PORTABLE_PY_REL="python.exe"
source scripts/lib/desktop_build_common.sh
prepare_portable_python
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/prepare_windows_python_crt.ps1 \
    -PythonDir "$PYTHON_DIR" > "$EVIDENCE_DIR/preparation.log" 2>&1
set +e
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$SOURCE_DIR/scripts/tests/test_prepare_windows_python_crt.ps1" \
    -OfficialDll "$PYTHON_DIR/concrt140.dll" -Report build/before-default-signatures.json \
    > "$EVIDENCE_DIR/before-default.log" 2>&1
before_status=$?
set -e
if [ "$before_status" -eq 0 ] || ! grep -q 'Join-Path : Cannot bind argument' "$EVIDENCE_DIR/before-default.log"; then
    cat "$EVIDENCE_DIR/before-default.log"
    echo 'Original production default invocation failure was not reproduced'
    exit 1
fi
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/tests/test_prepare_windows_python_crt.ps1 \
    -OfficialDll "$PYTHON_DIR/concrt140.dll" -Report build/python-crt-signature-tests.json \
    > "$EVIDENCE_DIR/after-default.log" 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/tests/test_prepare_windows_python_crt.ps1 \
    -PrepareScript scripts/prepare_windows_python_crt.ps1 \
    -OfficialDll "$PYTHON_DIR/concrt140.dll" -Report build/python-crt-signature-tests-explicit.json \
    > "$EVIDENCE_DIR/after-explicit.log" 2>&1
"$PORTABLE_PY" -B scripts/windows_python_crt.py --python-dir "$PYTHON_DIR" \
    --report build/python-crt.json > "$EVIDENCE_DIR/verifier.log" 2>&1
"$PORTABLE_PY" -B -m unittest discover -s scripts/tests -p 'test_windows*crt.py' \
    > "$EVIDENCE_DIR/python-crt-negative-tests.log" 2>&1
cp build/python-crt-signature-tests.json "$EVIDENCE_DIR/actual-default-signatures.json"
cp build/python-crt-signature-tests-explicit.json "$EVIDENCE_DIR/actual-explicit-signatures.json"
cp build/python-crt.json "$EVIDENCE_DIR/actual-crt-verify.json"
cp "$PYTHON_DIR/windows-crt.json" "$EVIDENCE_DIR/windows-crt.json"
"$PORTABLE_PY" -B scripts/crt_default_invocation_summary.py "$SOURCE_DIR" "$EVIDENCE_DIR" "$before_status"
cat "$EVIDENCE_DIR/after-default.log"
cat "$EVIDENCE_DIR/after-explicit.log"
cat "$EVIDENCE_DIR/verifier.log"
cat "$EVIDENCE_DIR/python-crt-negative-tests.log"
