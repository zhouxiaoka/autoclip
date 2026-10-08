# Launch the installed desktop app the way a user would (interactive desktop session), wait for its backend.
# Falls back to a direct (session 0) launch only if no one is logged on; the result records which mode was used.
param([Parameter(Mandatory=$true)][string]$Label, [int]$TimeoutSec = 150)
. $PSScriptRoot\common.ps1
$inst = Get-AutoClipInstall
if (-not $inst -or -not $inst.Exe) { throw 'AutoClip is not installed' }
$data = Get-AppDataDir
$portFile = Join-Path $data 'backend.port'
Remove-Item -LiteralPath $portFile -Force -ErrorAction SilentlyContinue
$r = [ordered]@{ label = $Label; exe = $inst.Exe; registry_version = $inst.Version; exe_file_version = $inst.ExeFileVersion; exe_product_version = $inst.ExeProductVersion; exe_sha256 = $inst.ExeSha256 }
$session = Get-InteractiveSessionId
$r.interactive_session = $session
$r.launched_at = Now-Iso
$sw = [Diagnostics.Stopwatch]::StartNew()
if ($session) {
  $r.mode = 'scheduled-task-interactive'
  Start-Interactive 'winqa-launch' $inst.Exe '' $inst.Dir
} else {
  $r.mode = 'direct-session0'
  Start-Process -FilePath $inst.Exe -WorkingDirectory $inst.Dir | Out-Null
}
$port = $null
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline -and -not $port) {
  if (Test-Path -LiteralPath $portFile) { $port = (Get-Content -LiteralPath $portFile -Raw).Trim() }
  if (-not $port) { Start-Sleep -Milliseconds 500 }
}
$r.port = $port
$r.port_file_seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1)
if ($port) {
  $h = Wait-Http "http://127.0.0.1:$port/health" 60
  $r.health_status = $(if ($h) { $h.StatusCode } else { $null })
  $r.health_body = $(if ($h) { $h.Content.Substring(0, [Math]::Min(500, $h.Content.Length)) } else { $null })
  $r.healthy_seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1)
}
Start-Sleep 5
$procs = @(Get-AutoClipProcesses $inst.Dir)
$r.processes = $procs
$r.app_sessions = @($procs | Where-Object { $_.name -like 'AutoClip*' } | ForEach-Object { $_.session } | Select-Object -Unique)
$r.celery_processes = @(Test-CeleryProcesses $procs)
$r.python_processes = @($procs | Where-Object { $_.name -like 'python*' }).Count
$r.ok = [bool]$port -and $r.health_status -eq 200
Save-Json ([pscustomobject]$r) "launch-$Label.json"
if (-not $r.ok) {
  $log = Join-Path $data 'logs'
  Get-ChildItem $log -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "--- $($_.Name)"; Get-Content $_.FullName -Tail 40 }
  Write-Error "launch $Label failed"; exit 1
}
