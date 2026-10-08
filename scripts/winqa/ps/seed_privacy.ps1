# Turn crash reports / backend analytics off before first launch, so deliberate test failures never reach production Sentry.
. $PSScriptRoot\common.ps1
$d = Get-AppDataDir
New-Item -ItemType Directory -Force $d | Out-Null
[IO.File]::WriteAllText((Join-Path $d 'privacy.json'), '{"crash_reports": false, "analytics": false}', (New-Object Text.UTF8Encoding $false))
Write-Host "privacy.json written to $d"
