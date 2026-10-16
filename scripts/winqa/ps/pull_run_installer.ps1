param([string]$Run,[int64]$Total,[int]$N=16,[string]$WantZip='',[string]$WantExe='')
# Exit codes: 4 missing/invalid digest; 6 download (HTTP/curl) failure; 7 hash mismatch; 1 any other error.
# R16 #51: report on stderr and exit with the code; the Write-Err*r cmdlet under 'Stop' would abort before exit.
# R21: home-directory scrubbing is redact.py's rule, ported line for line (WIN_PATTERN / POSIX_PATTERN
# copied verbatim, Mask-HomeName == redact._mask); test_pwsh_and_python_redact_identically keeps them equal.
$WinPattern = '\b([a-zA-Z]:)((?:\\*/|\\+u00(?:2[fF]|5[cC])|(?:\\\\)+|(?<![\\/])\\|\\(?!u[0-9a-fA-F]{4}))+)[uU][sS][eE][rR][sS]((?:\\*/|\\+u00(?:2[fF]|5[cC])|(?:\\\\)+|(?<![\\/])\\|\\(?!u[0-9a-fA-F]{4}))+)(?!<user>)((?:\\+u(?!00(?:2[fF]|5[cC]))[0-9a-fA-F]{4}|[^\\/"\r\n<>|*?:])+)'
$PosixPattern = '(?<![\w.\\-])(\\*/|\\+u002[fF])(Users|home)((?:\\*/|\\+u00(?:2[fF]|5[cC])|(?:\\\\)+|(?<![\\/])\\|\\(?!u[0-9a-fA-F]{4}))+)(?!<user>)((?:\\+u(?!00(?:2[fF]|5[cC]))[0-9a-fA-F]{4}|[^\\/"\r\n<>|*?:])+)'
function Mask-HomeName([string]$Name, [string]$Before, [string]$After) {
  if ($Before -ceq "'") { $q = [regex]::Match($Name, "'(?=[ \t]|$)"); if ($q.Success) { return '<user>' + $Name.Substring($q.Index) } }
  if (($After -ceq '/' -or $After -ceq '\') -and ($Name.EndsWith(' ') -or $Name.EndsWith("`t"))) {
    return '<user>' + $Name.Substring($Name.IndexOfAny([char[]]@([char]' ', [char]"`t")))
  }
  return '<user>'
}
function Scrub-Homes([string]$Text) {
  foreach ($kind in 'win', 'posix') {
    $pattern = if ($kind -ceq 'win') { $WinPattern } else { $PosixPattern }
    $src = $Text
    $Text = [regex]::Replace($src, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{
      param($m)
      $before = if ($m.Index -gt 0) { [string]$src[$m.Index - 1] } else { '' }
      $end = $m.Index + $m.Length
      $after = if ($end -lt $src.Length) { [string]$src[$end] } else { '' }
      $g = $m.Groups
      $root = if ($kind -ceq 'win') { $g[1].Value + $g[2].Value + 'Users' + $g[3].Value } else { $g[1].Value + $g[2].Value + $g[3].Value }
      $root + (Mask-HomeName $g[4].Value $before $after)
    })
  }
  return $Text
}
function Fail([int]$Code, [string]$Message) {
  # R20 #120: case-sensitive replace (-creplace), as in Python re.
  $clean = (Scrub-Homes $Message) -creplace 'https?://\S+', '<url>'
  [Console]::Error.WriteLine($clean); exit $Code
}
trap { Fail 1 ("unexpected error: " + $_.Exception.Message) }
if($WantZip -notmatch '^[0-9a-f]{64}$'){ Fail 4 "artifact digest missing or invalid; refusing to download run $Run" }
if($WantExe -and $WantExe -notmatch '^[0-9a-f]{64}$'){ Fail 4 "provenance exe sha256 invalid; refusing to download run $Run" }
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
$inst = if($env:WINQA_INST){ $env:WINQA_INST } else { 'C:\winqa\inst' }
$uf=Join-Path $inst ".url-$Run"; $url=(Get-Content -Raw $uf).Trim(); Remove-Item -Force $uf
$total=$Total; $n=$N; $dir=Join-Path $inst "dl-$Run"
New-Item -ItemType Directory -Force (Join-Path $dir 'parts') | Out-Null
$curl = if($env:WINQA_CURL){ $env:WINQA_CURL } else { Join-Path $env:SystemRoot 'System32\curl.exe' }
$chunk=[math]::Ceiling($total/$n); $sum=0; $httpFail=0
for($round=1; $round -le 4; $round++){
  $procs=@{}
  for($i=0;$i -lt $n;$i++){ $s=$i*$chunk; $e=[math]::Min($total-1,$s+$chunk-1); $p=Join-Path $dir "parts/p$i"
    $have= if(Test-Path $p){(Get-Item $p).Length}else{0}
    # R16 #52: --fail so an HTTP error body (expired signed URL) is never appended to a chunk.
    if($s+$have -le $e){ $procs[$i]=Start-Process -FilePath $curl -ArgumentList @('-s','-L','--fail','--retry','5','--speed-limit','2000','--speed-time','60','-r',"$($s+$have)-$e",'-o',(Join-Path $dir "parts/q$i"),$url) -PassThru -NoNewWindow } }
  foreach($i in $procs.Keys){ $procs[$i].WaitForExit() }
  foreach($i in $procs.Keys){ $q=Join-Path $dir "parts/q$i"
    if($procs[$i].ExitCode -ne 0){ $httpFail++; Remove-Item -Force -ErrorAction SilentlyContinue $q; continue }
    if(Test-Path $q){ $b=[IO.File]::ReadAllBytes($q); $f=[IO.File]::Open((Join-Path $dir "parts/p$i"),'Append'); $f.Write($b,0,$b.Length); $f.Close(); Remove-Item $q } }
  $sum=(Get-ChildItem (Join-Path $dir 'parts') -Filter 'p*' | Measure-Object Length -Sum).Sum
  "round $round bytes=$sum/$total http_failures=$httpFail"; if($sum -eq $total){break}
}
$url=$null
if($sum -ne $total){ Fail 6 "incomplete download $sum/$total, $httpFail curl/HTTP failure(s); signed URL may have expired, rerun to resume" }
$zip=Join-Path $dir 'artifact.zip'; $fs=[IO.File]::Create($zip)
for($i=0;$i -lt $n;$i++){ $b=[IO.File]::ReadAllBytes((Join-Path $dir "parts/p$i")); $fs.Write($b,0,$b.Length) }; $fs.Close()
$zh=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLower(); "zip_sha256=$zh"
if($zh -ne $WantZip){ Remove-Item -Recurse -Force $dir; Fail 7 "zip sha256 mismatch (want $WantZip); bad chunks deleted, rerun downloads fresh" }
Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $dir 'unz') -Force
$exe=Get-ChildItem (Join-Path $dir 'unz') -Recurse -Filter '*-setup.exe' | Select-Object -First 1
if(-not $exe){ Remove-Item -Recurse -Force $dir; Fail 7 'no *-setup.exe in artifact' }
$eh=(Get-FileHash $exe.FullName -Algorithm SHA256).Hash.ToLower(); "exe=$($exe.Name) size=$($exe.Length) sha256=$eh"
if($WantExe -and $eh -ne $WantExe){ Remove-Item -Recurse -Force $dir; Fail 7 "exe sha256 mismatch vs provenance (want $WantExe)" }
# R20 #121: replace only this script's own outputs; never sweep other files in the install folder.
foreach($own in 'candidate-setup.exe','candidate.sha256'){ Remove-Item -LiteralPath (Join-Path $inst $own) -Force -ErrorAction SilentlyContinue }
Move-Item $exe.FullName (Join-Path $inst 'candidate-setup.exe') -Force
Set-Content (Join-Path $inst 'candidate.sha256') "$eh  candidate-setup.exe  run=$Run  name=$($exe.Name)"
Remove-Item -Recurse -Force $dir
if((Get-FileHash (Join-Path $inst 'candidate-setup.exe') -Algorithm SHA256).Hash.ToLower() -ne $eh){ Fail 7 'post-move re-hash failed' }
"VERIFY_OK candidate-setup.exe sha256=$eh"
Get-ChildItem $inst | Select Name,Length,LastWriteTime | Format-Table -Auto | Out-String
