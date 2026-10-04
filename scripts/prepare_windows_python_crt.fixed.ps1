# Bundle official release CRT DLLs beside portable python.exe; never install a
# machine-wide redistributable or copy DLLs from System32 / developer PATH.
param([Parameter(Mandatory = $true)][string]$PythonDir)
$ErrorActionPreference = 'Stop'

function Test-OfficialMicrosoftCrtSignature($Signature) {
    if (-not $Signature -or $Signature.Status -ne 'Valid' -or -not $Signature.SignerCertificate) {
        return $false
    }
    # These two identities were verified on the official VS release CRTs.
    # Keep Authenticode trust mandatory and require Microsoft's organization
    # in the real certificate subject and issuer, not a manifest declaration.
    $subject = $Signature.SignerCertificate.Subject
    $issuer = $Signature.SignerCertificate.Issuer
    if ($subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)' -or
        $issuer -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') { return $false }
    return [bool](
        ($subject -match '(^|,\s*)CN=Microsoft Corporation(,|$)' -and
         $issuer -match '(^|,\s*)CN=Microsoft Code Signing PCA 2011(,|$)') -or
        ($subject -match '(^|,\s*)CN=Microsoft Windows Software Compatibility Publisher(,|$)' -and
         $issuer -match '(^|,\s*)CN=Microsoft Windows Third Party Component CA 2013(,|$)')
    )
}

$destination = (Resolve-Path $PythonDir).Path
if (-not (Test-Path (Join-Path $destination 'python.exe'))) { throw 'Portable python.exe missing' }
$required = @('concrt140.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
              'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll',
              'vcruntime140.dll', 'vcruntime140_1.dll')
$minimum = [version]'14.44.35211.0'
foreach ($name in @('vcruntime140.dll', 'vcruntime140_1.dll')) {
    $existing = Join-Path $destination $name
    if (-not (Test-Path $existing)) { throw "Portable Python runtime missing $name" }
    $v = [Diagnostics.FileVersionInfo]::GetVersionInfo($existing)
    $version = [version]::new($v.FileMajorPart, $v.FileMinorPart, $v.FileBuildPart, $v.FilePrivatePart)
    if ($version -gt $minimum) { $minimum = $version }
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path $vswhere)) { throw 'Official Visual Studio discovery tool missing' }
$installations = @(& $vswhere -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)
if ($LASTEXITCODE -ne 0) { throw 'Visual Studio discovery failed' }
$candidates = @(
    foreach ($installation in $installations) {
        $redist = Join-Path $installation 'VC\Redist\MSVC'
        if (Test-Path $redist) {
            foreach ($versionDir in Get-ChildItem $redist -Directory) {
                foreach ($folder in Get-ChildItem (Join-Path $versionDir.FullName 'x64') -Directory -Filter 'Microsoft.VC*.CRT' -ErrorAction SilentlyContinue) {
                    if ($folder.Name -match '^Microsoft\.VC\d+\.CRT$') { $folder }
                }
            }
        }
    }
)
$selected = $null
$files = $null
# Select a complete signed release set by its DLL version, not filesystem order.
foreach ($folder in $candidates) {
    $core = Join-Path $folder.FullName 'msvcp140.dll'
    if (-not (Test-Path $core)) { continue }
    $v = [Diagnostics.FileVersionInfo]::GetVersionInfo($core)
    $version = [version]::new($v.FileMajorPart, $v.FileMinorPart, $v.FileBuildPart, $v.FilePrivatePart)
    if ($version -lt $minimum -or ($selected -and $version -le $selected.Version)) { continue }
    $dlls = @(Get-ChildItem $folder.FullName -File -Filter '*.dll')
    if (@($required | Where-Object { $_ -notin $dlls.Name }).Count) { continue }
    $entries = @(
        foreach ($dll in $dlls) {
            if ($dll.Name -notmatch '^(msvcp140(?:_[a-z0-9_]+)?|vcruntime140(?:_[a-z0-9_]+)?|concrt140|vccorlib140)\.dll$') {
                throw "Unexpected file in official release CRT folder: $($dll.Name)"
            }
            $info = [Diagnostics.FileVersionInfo]::GetVersionInfo($dll.FullName)
            $fileVersion = [version]::new($info.FileMajorPart, $info.FileMinorPart, $info.FileBuildPart, $info.FilePrivatePart)
            if ($fileVersion -ne $version) { throw 'Mixed Visual C++ runtime versions' }
            $signature = Get-AuthenticodeSignature -LiteralPath $dll.FullName
            if (-not (Test-OfficialMicrosoftCrtSignature $signature)) {
                $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { 'missing' }
                $issuer = if ($signature.SignerCertificate) { $signature.SignerCertificate.Issuer } else { 'missing' }
                $detail = $signature.StatusMessage.Replace($dll.FullName, $dll.Name)
                throw "Official CRT signature rejected: $($dll.Name); status=$($signature.Status); subject=$subject; issuer=$issuer; detail=$detail"
            }
            # Check the PE machine before copying: x64 redist paths alone are insufficient.
            $bytes = [IO.File]::ReadAllBytes($dll.FullName)
            if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) { throw 'Invalid CRT PE image' }
            $pe = [BitConverter]::ToUInt32($bytes, 0x3c)
            if ($pe + 6 -gt $bytes.Length -or [BitConverter]::ToUInt32($bytes, $pe) -ne 0x4550 -or
                [BitConverter]::ToUInt16($bytes, $pe + 4) -ne 0x8664) { throw 'CRT DLL is not Windows x64' }
            @{ name = $dll.Name.ToLowerInvariant(); sha256 = (Get-FileHash $dll.FullName -Algorithm SHA256).Hash.ToLowerInvariant();
               size = $dll.Length; file_version = $fileVersion.ToString(); architecture = 'x64';
               signature_status = $signature.Status.ToString(); signer = 'Microsoft Corporation';
               signer_subject = $signature.SignerCertificate.Subject; signer_issuer = $signature.SignerCertificate.Issuer;
               signature_type = $signature.SignatureType.ToString() }
        }
    )
    $selected = @{ Folder = $folder; Version = $version }
    $files = $entries
}
if (-not $selected) { throw "No complete official x64 CRT >= $minimum available in Visual Studio Redist" }
foreach ($entry in $files) {
    Copy-Item (Join-Path $selected.Folder.FullName $entry.name) (Join-Path $destination $entry.name) -Force
    if ((Get-FileHash (Join-Path $destination $entry.name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw 'Bundled CRT copy digest mismatch'
    }
}
$manifest = @{ schema_version = 1; source = 'visual-studio-redist'; architecture = 'x64';
              version = $selected.Version.ToString(); minimum_version = $minimum.ToString();
              files = @($files | Sort-Object name) }
$manifest | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $destination 'windows-crt.json') -Encoding utf8
Write-Host "Bundled $($files.Count) signed Microsoft x64 CRT DLLs $($selected.Version) beside portable python.exe"
