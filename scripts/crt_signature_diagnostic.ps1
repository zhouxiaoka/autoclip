# Read only: inspect official Visual Studio release CRTs; do not alter trust,
# PATH, system DLLs, candidate source or redistributable installation.
param([Parameter(Mandatory=$true)][string]$OutputFile,
      [Parameter(Mandatory=$true)][string]$SourceDir)
$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    schema_version = 1
    utc = [DateTime]::UtcNow.ToString('o')
    powershell = $PSVersionTable.PSVersion.ToString()
    powershell_edition = $PSVersionTable.PSEdition
    os_version = [Environment]::OSVersion.VersionString
    source_commit = (& git -C $SourceDir rev-parse HEAD)
    files = @()
    errors = @()
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
try {
    if (-not (Test-Path -LiteralPath $vswhere)) { throw 'Official vswhere.exe missing' }
    $installations = @(& $vswhere -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)
    if ($LASTEXITCODE -ne 0) { throw 'vswhere failed' }
    $result['installations'] = $installations
    foreach ($installation in $installations) {
        $redist = Join-Path $installation 'VC\Redist\MSVC'
        if (-not (Test-Path -LiteralPath $redist)) { continue }
        foreach ($versionDir in Get-ChildItem -LiteralPath $redist -Directory) {
            $x64 = Join-Path $versionDir.FullName 'x64'
            if (-not (Test-Path -LiteralPath $x64)) { continue }
            foreach ($folder in Get-ChildItem -LiteralPath $x64 -Directory -Filter 'Microsoft.VC*.CRT') {
                if ($folder.Name -notmatch '^Microsoft\.VC\d+\.CRT$') { continue }
                foreach ($dll in Get-ChildItem -LiteralPath $folder.FullName -File -Filter '*.dll') {
                    $row = [ordered]@{name=$dll.Name; path=$dll.FullName; redist_version=$versionDir.Name}
                    try {
                        $v = [Diagnostics.FileVersionInfo]::GetVersionInfo($dll.FullName)
                        $row['file_version'] = [version]::new($v.FileMajorPart, $v.FileMinorPart, $v.FileBuildPart, $v.FilePrivatePart).ToString()
                        $signature = Get-AuthenticodeSignature -LiteralPath $dll.FullName
                        $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
                        $row['signature_status'] = $signature.Status.ToString()
                        $row['signature_status_message'] = $signature.StatusMessage
                        $row['signature_type'] = $signature.SignatureType.ToString()
                        $row['is_os_binary'] = $signature.IsOSBinary
                        $row['signer_subject'] = $subject
                        $row['signer_issuer'] = if ($signature.SignerCertificate) { $signature.SignerCertificate.Issuer } else { $null }
                        $row['signer_simple_name'] = if ($signature.SignerCertificate) { $signature.SignerCertificate.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) } else { $null }
                        $row['signer_thumbprint'] = if ($signature.SignerCertificate) { $signature.SignerCertificate.Thumbprint } else { $null }
                        $row['signer_not_before'] = if ($signature.SignerCertificate) { $signature.SignerCertificate.NotBefore.ToUniversalTime().ToString('o') } else { $null }
                        $row['signer_not_after'] = if ($signature.SignerCertificate) { $signature.SignerCertificate.NotAfter.ToUniversalTime().ToString('o') } else { $null }
                        $row['timestamp_subject'] = if ($signature.TimeStamperCertificate) { $signature.TimeStamperCertificate.Subject } else { $null }
                        $row['current_guard_status_valid'] = $signature.Status -eq 'Valid'
                        $row['current_guard_subject_match'] = [bool]($subject -match '(^|,\s*)CN=Microsoft Corporation(,|$)')
                        $bytes = [IO.File]::ReadAllBytes($dll.FullName)
                        if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x4d -or $bytes[1] -ne 0x5a) { throw 'Invalid MZ header' }
                        $pe = [BitConverter]::ToUInt32($bytes, 0x3c)
                        if ($pe + 26 -gt $bytes.Length -or [BitConverter]::ToUInt32($bytes, $pe) -ne 0x4550) { throw 'Invalid PE header' }
                        $row['pe_machine'] = '0x{0:x4}' -f [BitConverter]::ToUInt16($bytes, $pe + 4)
                        $row['pe_optional_magic'] = '0x{0:x4}' -f [BitConverter]::ToUInt16($bytes, $pe + 24)
                        $row['sha256'] = (Get-FileHash -LiteralPath $dll.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                        $row['size'] = $dll.Length
                    } catch {
                        $row['error_type'] = $_.Exception.GetType().FullName
                        # Only official runner paths are inspected. No credentials/user inputs.
                        $row['error_message'] = $_.Exception.Message
                    }
                    $result.files += $row
                    Write-Host ($row | ConvertTo-Json -Compress)
                }
            }
        }
    }
    if (-not $result.files.Count) { throw 'No official x64 Visual Studio CRT DLLs found' }
} catch {
    $result.errors += @{type=$_.Exception.GetType().FullName; message=$_.Exception.Message}
} finally {
    $result | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $OutputFile -Encoding utf8
}
if ($result.errors.Count) { throw 'Read-only CRT discovery failed; see diagnostic JSON' }
