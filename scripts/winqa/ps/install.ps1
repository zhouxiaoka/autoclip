# Silent NSIS install (/S), timed. With -LockLeftover, also start a bundled python.exe holding _asyncio.pyd (CI #224 case)
# on top of whatever AutoClip is already running, then check the installer ended them and wrote new files.
param([Parameter(Mandatory=$true)][string]$Installer, [Parameter(Mandatory=$true)][string]$Label,
      [string]$ExpectVersion = '', [string]$Marker = '', [switch]$LockLeftover, [switch]$Interactive)
. $PSScriptRoot\common.ps1
$r = [ordered]@{ label = $Label; installer = $Installer; installer_sha256 = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLower() }
$before = Get-AutoClipInstall
$r.before_version = $(if ($before) { $before.Version } else { $null })
$r.lock_pid = $null
if ($LockLeftover -and $before) {
  $py = Join-Path $before.Dir 'resources\python\python.exe'
  $lock = Start-Process $py -ArgumentList '-c', '"import asyncio, time; time.sleep(900)"' -PassThru -WindowStyle Hidden
  Start-Sleep 3
  $r.lock_pid = $lock.Id; $r.lock_started = -not $lock.HasExited
}
$r.running_before = @(Get-AutoClipProcesses $(if ($before) { $before.Dir } else { '' }))
$r.started_at = Now-Iso
$sw = [Diagnostics.Stopwatch]::StartNew()
if ($Interactive -and (Get-InteractiveSessionId)) {
  # Run the installer in the logged-on user's desktop session (same session as the running app), like a user would.
  $r.mode = 'scheduled-task-interactive'
  Start-Interactive 'winqa-install' $Installer '/S'
  Start-Sleep 2
  $deadline = (Get-Date).AddSeconds(900)
  while ((Get-ScheduledTask -TaskName 'winqa-install').State -eq 'Running' -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
  $r.seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1)
  $r.exit_code = (Get-ScheduledTaskInfo -TaskName 'winqa-install').LastTaskResult
  Unregister-ScheduledTask -TaskName 'winqa-install' -Confirm:$false -ErrorAction SilentlyContinue
} else {
  $r.mode = 'ssh-session0'
  $p = Start-Process -FilePath $Installer -ArgumentList '/S' -Wait -PassThru
  $r.seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1)
  $r.exit_code = $p.ExitCode
}
$r.finished_at = Now-Iso
Start-Sleep 2
$after = Get-AutoClipInstall
$r.after = $after
$r.still_alive_from_before = @($r.running_before | Where-Object { Get-Process -Id $_.pid -ErrorAction SilentlyContinue } | ForEach-Object { "$($_.name)#$($_.pid)" })
if ($r.lock_pid -and (Get-Process -Id $r.lock_pid -ErrorAction SilentlyContinue)) { Stop-Process -Id $r.lock_pid -Force; $r.lock_killed_by_installer = $false }
elseif ($r.lock_pid) { $r.lock_killed_by_installer = $true }
if ($after -and $Marker) { $r.marker = $Marker; $r.marker_present = Test-Path -LiteralPath (Join-Path $after.Dir $Marker) }
if ($after) {
  $r.python_exe = Test-Path -LiteralPath (Join-Path $after.Dir 'resources\python\python.exe')
  $r.ffmpeg_exe = Test-Path -LiteralPath (Join-Path $after.Dir 'resources\ffmpeg\ffmpeg.exe')
  # Stale files a plain overwrite would leave behind (deleted in 1.5.6).
  $r.stale_files = @('resources\backend\core\celery_minimal.py', 'resources\backend\core\celery_app_fixed.py', 'resources\backend\execute_real_pipeline.py') |
    Where-Object { Test-Path -LiteralPath (Join-Path $after.Dir $_) }
}
# NSIS install log is not written in /S mode; record Application event-log errors during the install window.
$r.app_errors = @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Level = 2; StartTime = (Get-Date).AddSeconds(-($r.seconds + 10)) } -ErrorAction SilentlyContinue |
  Select-Object -First 10 | ForEach-Object { "$($_.ProviderName): $($_.Message)".Substring(0, [Math]::Min(300, "$($_.ProviderName): $($_.Message)".Length)) })
$r.ok = ($r.exit_code -eq 0) -and $after -and ((-not $ExpectVersion) -or $after.Version -eq $ExpectVersion) -and ($r.still_alive_from_before.Count -eq 0) -and ((-not $Marker) -or $r.marker_present)
Save-Json ([pscustomobject]$r) "install-$Label.json"
if (-not $r.ok) { Write-Error "install $Label failed"; exit 1 }
