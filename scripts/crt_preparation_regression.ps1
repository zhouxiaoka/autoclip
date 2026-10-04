# Run only on a disposable Windows runner. Portable Python download stays there.
param([Parameter(Mandatory=$true)][string]$SourceDir,
      [Parameter(Mandatory=$true)][string]$FixedScript,
      [Parameter(Mandatory=$true)][string]$SignatureTests,
      [Parameter(Mandatory=$true)][string]$OutputDir)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$archive = Join-Path $env:RUNNER_TEMP 'crt-probe-python.tar.gz'
$url = 'https://github.com/astral-sh/python-build-standalone/releases/download/20260510/cpython-3.13.13+20260510-x86_64-pc-windows-msvc-install_only.tar.gz'
& curl.exe --fail --location --retry 2 $url --output $archive
if ($LASTEXITCODE -ne 0) { throw 'Portable Python download failed' }
$scratch = Join-Path $env:RUNNER_TEMP 'crt-probe-portable'
New-Item -ItemType Directory -Path $scratch -Force | Out-Null
& tar.exe -xzf $archive -C $scratch
if ($LASTEXITCODE -ne 0) { throw 'Portable Python extraction failed' }
$pythonDir = Join-Path $scratch 'python'
$beforeDir = Join-Path $env:RUNNER_TEMP 'crt-probe-before'
Copy-Item -LiteralPath $pythonDir -Destination $beforeDir -Recurse
$beforeFailed = $false
$beforeError = $null
try {
    & (Join-Path $SourceDir 'scripts/prepare_windows_python_crt.ps1') -PythonDir $beforeDir *>&1 |
        Out-File (Join-Path $OutputDir 'before-original.log')
} catch {
    $beforeError = $_.Exception.Message
    $beforeError | Out-File (Join-Path $OutputDir 'before-original.log') -Append
    $beforeFailed = $beforeError -like 'Official CRT signature invalid: concrt140.dll*'
}
if (-not $beforeFailed) { throw "Original failure was not reproduced: $beforeError" }
& $FixedScript -PythonDir $pythonDir *>&1 | Out-File (Join-Path $OutputDir 'after-fixed.log')
Copy-Item (Join-Path $pythonDir 'windows-crt.json') (Join-Path $OutputDir 'windows-crt.json')
& (Join-Path $pythonDir 'python.exe') -B (Join-Path $SourceDir 'scripts/windows_python_crt.py') --python-dir $pythonDir --report (Join-Path $OutputDir 'actual-crt-verify.json')
if ($LASTEXITCODE -ne 0) { throw 'Actual bundled CRT version/hash/x64/import verification failed' }
& $SignatureTests -PrepareScript $FixedScript -OfficialDll (Join-Path $pythonDir 'concrt140.dll') -Report (Join-Path $OutputDir 'actual-signature-regressions.json')
& (Join-Path $pythonDir 'python.exe') -B -m unittest discover -s (Join-Path $SourceDir 'scripts/tests') -p 'test_windows_python_crt.py' *>&1 |
    Out-File (Join-Path $OutputDir 'python-crt-negative-tests.log')
if ($LASTEXITCODE -ne 0) { throw 'CRT manifest negative regressions failed' }
@{schema_version=1; source_commit=(& git -C $SourceDir rev-parse HEAD);
  fixed_script_sha256=(Get-FileHash -LiteralPath $FixedScript -Algorithm SHA256).Hash.ToLowerInvariant();
  portable_archive_sha256=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant();
  portable_download_bytes=(Get-Item -LiteralPath $archive).Length;
  before_failed=$beforeFailed; before_error=$beforeError; after_passed=$true;
  powershell=$PSVersionTable.PSVersion.ToString();
  scope='Official actual Windows CRT deployment/signature/PE/hash checks; not Whisper inference or native product acceptance'} |
    ConvertTo-Json -Depth 5 | Set-Content (Join-Path $OutputDir 'preparation-regression-summary.json') -Encoding utf8
Write-Host 'Actual Windows original failure reproduced and fixed deployment verified'
