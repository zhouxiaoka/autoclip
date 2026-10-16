param([string]$Run,[int64]$Total,[int]$N=16,[string]$WantZip='',[string]$WantExe='')
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
# R15/E9: without the artifact digest the download cannot be verified; refuse before touching anything.
if($WantZip -notmatch '^[0-9a-f]{64}$'){ Write-Error "artifact digest missing or invalid; refusing to download run $Run"; exit 4 }
$uf="C:\winqa\inst\.url-$Run"; $url=(Get-Content -Raw $uf).Trim(); Remove-Item -Force $uf
$total=$Total; $n=$N; $wantZip=$WantZip; $wantExe=$WantExe
$inst='C:\winqa\inst'; $dir="$inst\dl-$Run"
New-Item -ItemType Directory -Force "$dir\parts" | Out-Null
$curl=Join-Path $env:SystemRoot 'System32\curl.exe'; $chunk=[math]::Ceiling($total/$n)
for($round=1; $round -le 4; $round++){
  $procs=@()
  for($i=0;$i -lt $n;$i++){ $s=$i*$chunk; $e=[math]::Min($total-1,$s+$chunk-1); $p="$dir\parts\p$i"
    $have= if(Test-Path $p){(Get-Item $p).Length}else{0}
    if($s+$have -le $e){ $procs+=Start-Process -FilePath $curl -ArgumentList @('-s','-L','--retry','5','--speed-limit','2000','--speed-time','60','-r',"$($s+$have)-$e",'-o',"$dir\parts\q$i",$url) -PassThru -WindowStyle Hidden } }
  if($procs){ $procs | Wait-Process }
  for($i=0;$i -lt $n;$i++){ $q="$dir\parts\q$i"; if(Test-Path $q){ $b=[IO.File]::ReadAllBytes($q); $f=[IO.File]::Open("$dir\parts\p$i",'Append'); $f.Write($b,0,$b.Length); $f.Close(); Remove-Item $q } }
  $sum=(Get-ChildItem "$dir\parts" -Filter 'p*' | Measure-Object Length -Sum).Sum
  "round $round bytes=$sum/$total"; if($sum -eq $total){break}
}
$url=$null
if($sum -ne $total){ throw "incomplete download $sum/$total (rerun to resume)" }
$zip="$dir\artifact.zip"; $fs=[IO.File]::Create($zip)
for($i=0;$i -lt $n;$i++){ $b=[IO.File]::ReadAllBytes("$dir\parts\p$i"); $fs.Write($b,0,$b.Length) }; $fs.Close()
$zh=(Get-FileHash $zip -Algorithm SHA256).Hash.ToLower(); "zip_sha256=$zh"
if($wantZip -and $zh -ne $wantZip){ throw "zip sha256 mismatch (want $wantZip)" }
Expand-Archive -LiteralPath $zip -DestinationPath "$dir\unz" -Force
$exe=Get-ChildItem "$dir\unz" -Recurse -Filter '*-setup.exe' | Select-Object -First 1
$eh=(Get-FileHash $exe.FullName -Algorithm SHA256).Hash.ToLower(); "exe=$($exe.Name) size=$($exe.Length) sha256=$eh"
if($wantExe -and $eh -ne $wantExe){ throw "exe sha256 mismatch vs provenance (want $wantExe)" }
Get-ChildItem $inst -File | Where-Object { $_.Name -ne 'prev-setup.exe' -and $_.Name -notlike '.url-*' } | Remove-Item -Force
Move-Item $exe.FullName "$inst\candidate-setup.exe" -Force
Set-Content "$inst\candidate.sha256" "$eh  candidate-setup.exe  run=$Run  name=$($exe.Name)"
Remove-Item -Recurse -Force $dir
if((Get-FileHash "$inst\candidate-setup.exe" -Algorithm SHA256).Hash.ToLower() -ne $eh){ throw 'post-move re-hash failed' }
"VERIFY_OK candidate-setup.exe sha256=$eh"
Get-ChildItem $inst | Select Name,Length,LastWriteTime | Format-Table -Auto | Out-String
