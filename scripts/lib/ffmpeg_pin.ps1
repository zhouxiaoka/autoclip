# Reads a pinned-ffmpeg env file; same rule as read_ffmpeg_pin in
# scripts/lib/ffmpeg_pin.sh (scripts/tests/test_ffmpeg_pin_reader.py runs one
# sample set through both):
#   - the file must not start with a UTF-8 BOM (rejected, not stripped);
#   - one trailing CR per line is dropped (CRLF checkouts);
#   - empty lines and lines whose first character is '#' are skipped;
#   - every other line must match ^(KEY1|KEY2|...)=[!-~]+$ (case-sensitive,
#     value = printable ASCII without spaces);
#   - each key must appear exactly once.
# Returns an ordered dictionary KEY -> value; throws on any violation.
param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string[]]$Keys
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "${Path}: not found" }
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Path).ProviderPath)
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    throw "${Path}: starts with a UTF-8 BOM; save it without BOM"
}
$re = '^(' + (($Keys | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')=([!-~]+)$'
$pin = [ordered]@{}
$n = 0
foreach ($line in ([System.Text.Encoding]::UTF8.GetString($bytes) -split "`n")) {
    $n++
    if ($line.EndsWith("`r", [System.StringComparison]::Ordinal)) { $line = $line.Substring(0, $line.Length - 1) }
    if ($line -eq '' -or $line.StartsWith('#', [System.StringComparison]::Ordinal)) { continue }
    $m = [regex]::Match($line, $re)
    if (-not $m.Success) { throw "${Path}:${n}: not KEY=value with a known key and no spaces" }
    $key = $m.Groups[1].Value
    if ($pin.Contains($key)) { throw "${Path}:${n}: $key set more than once" }
    $pin[$key] = $m.Groups[2].Value
}
foreach ($key in $Keys) {
    if (-not $pin.Contains($key)) { throw "${Path}: $key missing" }
}
$pin
