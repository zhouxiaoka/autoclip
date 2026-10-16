# R29 #323/#414 point 4: the ONLY remote entry. The ssh command line is the fixed string
#   powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\winqa\ps\entry.ps1
# and carries no variable part, so cmd (%VAR%) and PowerShell ($(), quotes) never see a value.
# stdin line 1: {"op": ..., "args": {...}, "has_key": bool}; line 2: the key, only when has_key (op "py" only).
# Exactly these lines are read (ReadLine, never ReadToEnd). Unknown op, unknown or wrongly typed argument, a
# truncated or non-JSON request, or a missing key line -> "WINQA_E_REQUEST <code>" on stderr, exit 64. Values
# reach target scripts by splatting and Python by a JSON line on its own stdin (py/argshim.py), never by argv text.
# ASCII only (PS 5.1).
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
function Reject([int]$code) { [Console]::Error.WriteLine("WINQA_E_REQUEST $code"); exit 64 }

$NAME = '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
# script -> allowed parameter -> 's' (string) or 'b' (switch)
$PS_OPS = @{
  'clean' = @{}; 'seed_privacy' = @{}; 'collect_logs' = @{ Label = 's' }
  'env' = @{ PrevInstaller = 's'; CandInstaller = 's' }
  'install' = @{ Installer = 's'; Label = 's'; ExpectVersion = 's'; Marker = 's'; LockLeftover = 'b'; Interactive = 'b' }
  'launch' = @{ Label = 's' }; 'stop' = @{ Label = 's' }; 'ui_probe' = @{ Label = 's' }
  'smoke' = @{ LaunchDesktop = 'b'; WithAsr = 'b' }; 'hf_mirror' = @{ On = 'b'; Off = 'b' }
}
$PY_OPS = @('winqa_probe', 'winqa_real', 'export_evidence')

$line = [Console]::In.ReadLine()
if ($null -eq $line -or $line.Length -eq 0) { Reject 1 }
try { $req = $line | ConvertFrom-Json } catch { Reject 2 }
if ($null -eq $req -or $req -isnot [pscustomobject]) { Reject 2 }
foreach ($p in $req.PSObject.Properties) { if (@('op', 'args', 'has_key') -notcontains $p.Name) { Reject 3 } }
if ($req.op -isnot [string] -or $req.has_key -isnot [bool] -or $req.args -isnot [pscustomobject]) { Reject 3 }
$key = $null
if ($req.has_key) {
  if ($req.op -ne 'py') { Reject 4 }
  $key = [Console]::In.ReadLine()
  if ($null -eq $key -or $key.Length -eq 0) { Reject 5 }
}
$a = $req.args
function Arg-Names { @($a.PSObject.Properties | ForEach-Object { $_.Name }) }
function Need-Name($v) { if ($v -isnot [string] -or $v -notmatch $NAME) { Reject 6 }; $v }
function Only([string[]]$allowed) { foreach ($n in (Arg-Names)) { if ($allowed -notcontains $n) { Reject 7 } } }
$Inst = Join-Path $Root 'inst'

switch -Exact ($req.op) {
  'ps' {
    Only @('script', 'params')
    $script = Need-Name $a.script
    if (-not $PS_OPS.ContainsKey($script)) { Reject 8 }
    $spec = $PS_OPS[$script]; $params = @{}
    if ($null -ne $a.params) {
      if ($a.params -isnot [pscustomobject]) { Reject 9 }
      foreach ($p in $a.params.PSObject.Properties) {
        if (-not $spec.ContainsKey($p.Name)) { Reject 10 }
        if ($spec[$p.Name] -eq 'b') { if ($p.Value -isnot [bool]) { Reject 11 }; $params[$p.Name] = [switch]$p.Value }
        else { if ($p.Value -isnot [string] -or $p.Value -match '[\x00-\x1f]') { Reject 11 }; $params[$p.Name] = $p.Value }
      }
    }
    & (Join-Path $PSScriptRoot "$script.ps1") @params
    exit $LASTEXITCODE
  }
  'py' {
    Only @('script', 'args')
    $script = Need-Name $a.script
    if ($PY_OPS -notcontains $script) { Reject 8 }
    $argv = @($a.args)
    foreach ($v in $argv) { if ($v -isnot [string] -or $v -match '[\x00]') { Reject 11 } }
    if ($env:WINQA_ENTRY_TEST_PYTHON) { $py = $env:WINQA_ENTRY_TEST_PYTHON }   # tests only: no installed app on CI
    else {
      . $PSScriptRoot\common.ps1
      $inst = Get-AutoClipInstall
      if (-not $inst) { [Console]::Error.WriteLine('WINQA_E_NOT_INSTALLED'); exit 65 }
      $res = Join-Path $inst.Dir 'resources'; $py = Join-Path $res 'python\python.exe'
      $env:WINQA_RESOURCES = $res; $env:WINQA_OUT = Join-Path $Root 'out'
    }
    $env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONDONTWRITEBYTECODE = '1'
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $py
    $psi.Arguments = '-B "' + (Join-Path (Join-Path $Root 'py') 'argshim.py') + '"'   # fixed text, no value in it
    $psi.UseShellExecute = $false; $psi.RedirectStandardInput = $true
    $proc = [Diagnostics.Process]::Start($psi)
    $enc = New-Object Text.UTF8Encoding $false
    $w = New-Object IO.StreamWriter($proc.StandardInput.BaseStream, $enc)
    $w.NewLine = "`n"
    $w.WriteLine((@{ script = (Join-Path (Join-Path $Root 'py') "$script.py"); args = $argv } | ConvertTo-Json -Compress -Depth 4))
    if ($null -ne $key) { $w.WriteLine($key); $key = $null }
    $w.Close()
    $proc.WaitForExit()
    exit $proc.ExitCode
  }
  'hash' {
    Only @('file')
    $f = Join-Path $Inst (Need-Name $a.file)
    if (Test-Path -LiteralPath $f) { (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLower() }
    exit 0
  }
  'make_parts' {
    Only @('dst', 'names')
    $d = Join-Path $Inst ('parts-' + (Need-Name $a.dst))
    New-Item -ItemType Directory -Force $d | Out-Null
    foreach ($n in @($a.names)) { $f = Join-Path $d (Need-Name $n); if (-not (Test-Path -LiteralPath $f)) { New-Item -ItemType File $f | Out-Null } }
    exit 0
  }
  'merge_parts' {
    Only @('dst', 'names')
    $dst = Need-Name $a.dst; $d = Join-Path $Inst "parts-$dst"
    $o = [IO.File]::Create((Join-Path $Inst $dst))
    try { foreach ($n in @($a.names)) { $i = [IO.File]::OpenRead((Join-Path $d (Need-Name $n))); try { $i.CopyTo($o) } finally { $i.Close() } } }
    finally { $o.Close() }
    exit 0
  }
  'remove_parts' { Only @('dst'); Remove-Item -Recurse -Force (Join-Path $Inst ('parts-' + (Need-Name $a.dst))); exit 0 }
  default { Reject 8 }
}
