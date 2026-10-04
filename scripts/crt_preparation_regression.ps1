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
& $SignatureTests -PrepareScript $FixedScript -OfficialDll (Join-Path $pythonDir 'concrt140.dll') -Report (Join-Path $OutputDir 'actual-signature-regressions.json')
$probe = @'
import hashlib,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'scripts'))
from windows_desktop_crt import imported_dlls
root=Path(sys.argv[2]); rows=[]
names=[entry['name'] for entry in json.loads((root/'windows-crt.json').read_text(encoding='utf-8-sig'))['files']]
names += ['python.exe',*[path.name for path in root.glob('python3*.dll')]]
for name in names:
 data=(root/name).read_bytes(); pe=struct.unpack_from('<I',data,0x3c)[0]; optional=pe+24
 section_count=struct.unpack_from('<H',data,pe+6)[0]; optional_size=struct.unpack_from('<H',data,pe+20)[0]
 header_size=struct.unpack_from('<I',data,optional+60)[0]
 sections=[struct.unpack_from('<IIII',data,optional+optional_size+i*40+8) for i in range(section_count)]
 row={'name':name,'sha256':hashlib.sha256(data).hexdigest(),'machine':hex(struct.unpack_from('<H',data,pe+4)[0]),
      'characteristics':hex(struct.unpack_from('<H',data,pe+22)[0]),'section_count':section_count,
      'header_size':header_size,'optional_size':optional_size,'file_size':len(data),
      'raw_sections_in_bounds':all(not size or (raw>=header_size and raw+size<=len(data)) for _,_,size,raw in sections)}
 for index,label in [(1,'imports'),(13,'delay_imports')]:
  rva,size=struct.unpack_from('<II',data,optional+112+index*8);row[label+'_rva']=rva;row[label+'_size']=size
 try: row['parsed_imports']=imported_dlls(data)
 except ValueError as e: row['parser_error']=str(e)
 rows.append(row)
Path(sys.argv[3]).write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows))
'@
$probeScript = Join-Path $env:RUNNER_TEMP 'crt-pe-directory-probe.py'
$probe | Set-Content -LiteralPath $probeScript -Encoding utf8
& (Join-Path $pythonDir 'python.exe') -B $probeScript $SourceDir $pythonDir (Join-Path $OutputDir 'actual-pe-imports.json')
if ($LASTEXITCODE -ne 0) { throw 'Read-only actual PE directory probe failed' }
& (Join-Path $pythonDir 'python.exe') -B (Join-Path $SourceDir 'scripts/windows_python_crt.py') --python-dir $pythonDir --report (Join-Path $OutputDir 'actual-crt-verify.json')
if ($LASTEXITCODE -ne 0) { throw 'Actual bundled CRT version/hash/x64/import verification failed' }
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
