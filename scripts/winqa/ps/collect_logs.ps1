# Copy the app logs (shared read: the running app keeps them open) and zip them to C:\winqa\out\app-logs.zip.
# Runs with -File: the old inline `powershell -Command -` block spanned several lines and, with no
# trailing blank line, PowerShell never executed it, so app-logs/ came back empty (RC156 Win QA).
param([string]$Label = 'logs')
. $PSScriptRoot\common.ps1
$ErrorActionPreference = 'Continue'
$sources = [ordered]@{
  'backend' = Join-Path (Get-AppDataDir) 'logs'
  'desktop' = Join-Path $env:LOCALAPPDATA 'com.autoclip.desktop\logs'
  'desktop-roaming' = Join-Path $env:APPDATA 'com.autoclip.desktop\logs'
}
$t = Join-Path $env:TEMP 'winqa-logs'
Remove-Item -Recurse -Force $t -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $t | Out-Null
$zip = Join-Path $Out 'app-logs.zip'
Remove-Item -Force $zip -ErrorAction SilentlyContinue
$r = [ordered]@{ label = $Label; at = (Now-Iso); sources = @(); copied = 0; failed = @(); zip = $null }
foreach ($name in $sources.Keys) {
  $d = $sources[$name]
  $files = @(Get-ChildItem -LiteralPath $d -File -Recurse -ErrorAction SilentlyContinue)
  $r.sources += [pscustomobject]@{ name = $name; exists = (Test-Path -LiteralPath $d); files = $files.Count }
  foreach ($f in $files) {
    $rel = $f.FullName.Substring($d.Length).TrimStart('\')
    $dest = Join-Path (Join-Path $t $name) $rel
    try {
      New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
      $i = [IO.File]::Open($f.FullName, 'Open', 'Read', 'ReadWrite,Delete')
      try { $o = [IO.File]::Create($dest); try { $i.CopyTo($o) } finally { $o.Close() } } finally { $i.Close() }
      $r.copied++
    } catch { $r.failed += "$name\$rel" }
  }
}
if ($r.copied -gt 0) {
  try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($t, $zip)
    $r.zip = (Get-Item $zip).Length
  } catch { $r.failed += "zip: $($_.Exception.Message)" }
}
Remove-Item -Recurse -Force $t -ErrorAction SilentlyContinue
Save-Json ([pscustomobject]$r) "collect-logs-$Label.json"
