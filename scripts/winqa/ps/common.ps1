# Shared helpers for the AutoClip Windows QA harness (dot-sourced). ASCII only: PS 5.1 reads BOM-less files as ANSI.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$WinQA = Split-Path -Parent $PSScriptRoot   # C:\winqa on the test machine (scripts live in C:\winqa\ps)
$Out = Join-Path $WinQA 'out'
New-Item -ItemType Directory -Force $Out | Out-Null

# R29 point 2: a result that cannot be written is a failure of the producer (exit 4), never a silent success.
function Save-Json($obj, [string]$name) {
  $p = Join-Path $Out $name
  try { [IO.File]::WriteAllText($p, ($obj | ConvertTo-Json -Depth 10), (New-Object Text.UTF8Encoding $false)) }
  catch { [Console]::Error.WriteLine("WINQA_E_SAVE $name"); exit 4 }
  Write-Host "saved $p"
}

# R29 point 2: one exit rule for every producer: ok -> 0, otherwise the given code (default 1).
function Exit-WithResult($ok, [int]$code = 1) { if ($ok) { exit 0 } else { exit $code } }

function Now-Iso { (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz') }

function Get-AutoClipInstall {
  $key = Get-ChildItem HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall -ErrorAction SilentlyContinue |
    Get-ItemProperty | Where-Object { $_.DisplayName -like 'AutoClip*' } | Select-Object -First 1
  if (-not $key) { return $null }
  $dir = ([string]$key.InstallLocation -replace '"', '').TrimEnd('\')
  if (-not $dir) { $dir = Split-Path ([string]$key.UninstallString -replace '"', '') }
  $exe = Get-ChildItem -LiteralPath $dir -Filter *.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notmatch 'uninstall' } | Select-Object -First 1
  [pscustomobject]@{
    Dir = $dir; DisplayName = $key.DisplayName; Version = $key.DisplayVersion
    Uninstall = $key.UninstallString; Exe = $(if ($exe) { $exe.FullName } else { $null })
    ExeFileVersion = $(if ($exe) { $exe.VersionInfo.FileVersion } else { $null })
    ExeProductVersion = $(if ($exe) { $exe.VersionInfo.ProductVersion } else { $null })
    ExeSha256 = $(if ($exe) { (Get-FileHash -LiteralPath $exe.FullName -Algorithm SHA256).Hash.ToLower() } else { $null })
  }
}

function Get-AppDataDir { Join-Path $env:APPDATA 'AutoClip' }

function Get-InteractiveSessionId {
  # Session of the logged-on user desktop (explorer.exe). Null when nobody is logged on.
  $ex = Get-CimInstance Win32_Process -Filter "Name='explorer.exe'" | Where-Object { $_.SessionId -gt 0 } |
    Select-Object -First 1
  if ($ex) { return [int]$ex.SessionId } else { return $null }
}

# All processes that belong to AutoClip: exe under install dir, AutoClip*.exe, and every descendant of those.
function Get-AutoClipProcesses([string]$dir) {
  $all = @(Get-CimInstance Win32_Process)
  $root = $null
  if ($dir) { $root = [IO.Path]::GetFullPath($dir).TrimEnd('\') + '\' }
  $seed = @($all | Where-Object {
    ($_.Name -like 'AutoClip*') -or ($root -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase))
  })
  $ids = New-Object 'System.Collections.Generic.HashSet[int]'
  foreach ($p in $seed) { [void]$ids.Add([int]$p.ProcessId) }
  do {
    $added = $false
    foreach ($p in $all) {
      if (-not $ids.Contains([int]$p.ProcessId) -and $ids.Contains([int]$p.ParentProcessId) -and $p.Name -ne 'conhost.exe') {
        [void]$ids.Add([int]$p.ProcessId); $added = $true
      }
    }
  } while ($added)
  @($all | Where-Object { $ids.Contains([int]$_.ProcessId) } | ForEach-Object {
    [pscustomobject]@{
      pid = [int]$_.ProcessId; ppid = [int]$_.ParentProcessId; name = $_.Name; session = [int]$_.SessionId
      path = $_.ExecutablePath; started = $(if ($_.CreationDate) { $_.CreationDate.ToString('s') } else { $null })
      command_line = $(if ($_.CommandLine) { $_.CommandLine.Substring(0, [Math]::Min(400, $_.CommandLine.Length)) } else { $null })
    }
  })
}

function Test-CeleryProcesses($procs) {
  @($procs | Where-Object { $_.command_line -and $_.command_line -match '(?i)celery' })
}

function Stop-AutoClip([string]$dir) {
  $procs = Get-AutoClipProcesses $dir
  foreach ($p in ($procs | Sort-Object { $_.name -notlike 'AutoClip*' })) {
    Stop-Process -Id $p.pid -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep 2
  return $procs
}

# Run a program inside the interactive desktop session through a one-shot scheduled task.
# SSH sessions live in session 0 (no desktop); Task Scheduler with LogonType Interactive
# starts the program in the session where the user is logged on (RDP/console).
function Start-Interactive([string]$task, [string]$exe, [string]$arguments = '', [string]$workdir = '') {
  Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
  if ($arguments) { $action = New-ScheduledTaskAction -Execute $exe -Argument $arguments }
  else { $action = New-ScheduledTaskAction -Execute $exe }
  if ($workdir) { $action.WorkingDirectory = $workdir }
  $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskName $task
}

function Wait-Http([string]$url, [int]$timeoutSec) {
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 5
      if ($r.StatusCode -eq 200) { return $r }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  return $null
}
