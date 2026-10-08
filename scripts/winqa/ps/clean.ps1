# Idempotent reset: stop AutoClip, uninstall silently, remove install dir, user data, WebView2 profile, temp smoke dirs.
. $PSScriptRoot\common.ps1
$result = [ordered]@{ started_at = Now-Iso; stopped = @(); uninstalled = $null; removed = @() }
$inst = Get-AutoClipInstall
$dir = $(if ($inst) { $inst.Dir } else { Join-Path $env:LOCALAPPDATA 'AutoClip Desktop' })
$result.stopped = @(Stop-AutoClip $dir | ForEach-Object { "$($_.name)#$($_.pid)" })
Get-ScheduledTask -TaskName 'winqa-*' -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue
if ($inst -and $inst.Uninstall) {
  $un = ($inst.Uninstall -replace '"', '')
  if (Test-Path -LiteralPath $un) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $un -ArgumentList '/S' -Wait -PassThru
    # NSIS uninstallers copy themselves to %TEMP% and return early; wait for the registry entry to go.
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-AutoClipInstall) -and (Get-Date) -lt $deadline) { Start-Sleep 1 }
    $result.uninstalled = [ordered]@{ version = $inst.Version; exit_code = $p.ExitCode; seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1); registry_gone = -not (Get-AutoClipInstall) }
  }
}
Start-Sleep 2
# NSIS remembers the last install dir in HKCU\Software\<publisher>\<product>; a stale value (e.g. an old QA folder)
# silently redirects the next "clean" install there. Drop it so every run installs to the default per-user location.
$result.install_dir_key = (Get-ItemProperty 'HKCU:\Software\autoclip\AutoClip Desktop' -ErrorAction SilentlyContinue).'(default)'
Remove-Item 'HKCU:\Software\autoclip' -Recurse -Force -ErrorAction SilentlyContinue
[Environment]::SetEnvironmentVariable('HF_ENDPOINT', $null, 'User'); [Environment]::SetEnvironmentVariable('HF_HUB_DISABLE_XET', $null, 'User')  # undo hf_mirror.ps1 workaround
$paths = @($dir, 'C:\AutoClipQA', (Join-Path $env:LOCALAPPDATA 'com.autoclip.desktop'), (Join-Path $env:APPDATA 'AutoClip'),
           (Join-Path $env:APPDATA 'com.autoclip.desktop'), (Join-Path $env:LOCALAPPDATA 'AutoClip'))
$paths += @(Get-ChildItem $env:TEMP -Directory -Filter 'autoclip-*' -ErrorAction SilentlyContinue | ForEach-Object FullName)
foreach ($p in $paths) {
  if ($p -and (Test-Path -LiteralPath $p)) {
    Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue
    $result.removed += [pscustomobject]@{ path = $p; gone = -not (Test-Path -LiteralPath $p) }
  }
}
Get-ChildItem $Out -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
$result.left_processes = @(Get-AutoClipProcesses $dir)
$result.left_install = [bool](Get-AutoClipInstall) -or (Test-Path 'HKCU:\Software\autoclip')
$result.finished_at = Now-Iso
Save-Json ([pscustomobject]$result) 'clean.json'
if ($result.left_install -or $result.left_processes.Count) { Write-Error 'clean incomplete'; exit 1 }
