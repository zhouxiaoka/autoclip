# From SSH: run ui_capture.ps1 in the interactive session and wait for its output.
param([string]$Label = 'ui')
. $PSScriptRoot\common.ps1
$json = Join-Path $Out "ui-$Label.json"
Remove-Item -LiteralPath $json -Force -ErrorAction SilentlyContinue
if (-not (Get-InteractiveSessionId)) { Write-Host 'no interactive session; skipping UI capture'; exit 0 }
Start-Interactive 'winqa-ui' 'powershell.exe' "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\winqa\ps\ui_capture.ps1 -Label $Label"
$deadline = (Get-Date).AddSeconds(40)
while (-not (Test-Path -LiteralPath $json) -and (Get-Date) -lt $deadline) { Start-Sleep 1 }
if (Test-Path -LiteralPath $json) { Get-Content -LiteralPath $json -Raw } else { Write-Host 'ui capture timed out' }
