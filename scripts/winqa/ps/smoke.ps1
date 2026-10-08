# CI-equivalent installed-runtime smoke (desktop-build.yml smoke-windows-x64) with the bundled Python.
# Uses its own temp data dir; close the interactive app first.
#   default      : backend started by bundled python (-m backend.desktop_main) from SSH (session 0)
#   -LaunchDesktop: verify script launches the installed autoclip-desktop.exe; run inside the logged-on
#                  desktop session via scheduled task (from session 0 the exe never prints PORT=, see README)
param([switch]$LaunchDesktop, [switch]$WithAsr)
. $PSScriptRoot\common.ps1
$inst = Get-AutoClipInstall
if (-not $inst) { throw 'AutoClip is not installed' }
$res = Join-Path $inst.Dir 'resources'
$py = Join-Path $res 'python\python.exe'
$runs = @()
function Run([string]$name, [string]$argline, [switch]$InSession) {
  $log = Join-Path $Out "$name.log"
  $cmd = Join-Path $Out "$name.cmd"
  $codeFile = Join-Path $Out "$name.exitcode"
  Remove-Item $log, "$log.err", $codeFile -ErrorAction SilentlyContinue
  $body = "@echo off`r`nset PYTHONUTF8=1`r`nset PYTHONIOENCODING=utf-8`r`ncd /d C:\winqa\repo`r`n`"$py`" -B $argline > `"$log`" 2> `"$log.err`"`r`necho %ERRORLEVEL% > `"$codeFile`"`r`n"
  [IO.File]::WriteAllText($cmd, $body, [Text.Encoding]::ASCII)
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $mode = 'ssh-session0'
  if ($InSession -and (Get-InteractiveSessionId)) {
    $mode = 'scheduled-task-interactive'
    Start-Interactive "winqa-$name" 'cmd.exe' "/c `"$cmd`""
    $deadline = (Get-Date).AddSeconds(1800)
    while (-not (Test-Path $codeFile) -and (Get-Date) -lt $deadline) { Start-Sleep 2 }
    Unregister-ScheduledTask -TaskName "winqa-$name" -Confirm:$false -ErrorAction SilentlyContinue
  } else {
    & cmd.exe /c "`"$cmd`""
  }
  $code = $(if (Test-Path $codeFile) { [int](Get-Content $codeFile -Raw).Trim() } else { -1 })
  $script:runs += [pscustomobject]@{ name = $name; mode = $mode; exit_code = $code; seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1); log = "$name.log" }
  Write-Host "$name ($mode) exit=$code"
}
Run 'verify_windows_install' "scripts\verify_windows_install.py --resources `"$res`" --report `"$Out\windows-smoke.json`""
if ($LaunchDesktop) {
  Run 'verify_windows_install_desktop' "scripts\verify_windows_install.py --resources `"$res`" --report `"$Out\windows-smoke-desktop.json`" --launch-desktop" -InSession
}
if ($WithAsr) {
  Run 'verify_sensevoice' "scripts\verify_sensevoice.py --resources `"$res`" --report `"$Out\windows-sensevoice-installed.json`""
  Run 'verify_whisper_recovery' "scripts\verify_whisper_recovery.py --resources `"$res`" --report `"$Out\windows-whisper-installed.json`""
}
Save-Json ([pscustomobject]@{ runs = $runs }) 'smoke.json'
if (@($runs | Where-Object exit_code -ne 0).Count) { exit 1 }
