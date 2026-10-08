# Run a Python helper with the INSTALLED app's bundled Python (same runtime users get).
param([Parameter(Mandatory=$true)][string]$Script, [Parameter(ValueFromRemainingArguments=$true)]$Rest)
. $PSScriptRoot\common.ps1
$inst = Get-AutoClipInstall
if (-not $inst) { throw 'AutoClip is not installed' }
$res = Join-Path $inst.Dir 'resources'
$env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONDONTWRITEBYTECODE = '1'
$env:WINQA_RESOURCES = $res; $env:WINQA_OUT = $Out
& (Join-Path $res 'python\python.exe') -B $Script @Rest
exit $LASTEXITCODE
