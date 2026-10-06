# Exercise the actual production signature predicate plus a real tampered DLL.
# No system changes, test certificate installs or execution of mutated images.
param([string]$PrepareScript,
      [Parameter(Mandatory=$true)][string]$OfficialDll,
      [Parameter(Mandatory=$true)][string]$Report)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 has no PSScriptRoot while parameter defaults bind.
# Resolve the optional production script only after entering the script body.
if (-not $PrepareScript) {
    $PrepareScript = Join-Path $PSScriptRoot '..\prepare_windows_python_crt.ps1'
}
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile((Resolve-Path $PrepareScript).Path, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'Production CRT script does not parse' }
$definition = $ast.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Test-OfficialMicrosoftCrtSignature'
}, $true)
if (-not $definition) { throw 'Production CRT signature predicate missing' }
Invoke-Expression $definition.Extent.Text
$checks = @()
function Check($Name, $Passed) {
    $script:checks += @{name=$Name; passed=[bool]$Passed}
    if (-not $Passed) { throw "CRT signature regression failed: $Name" }
}
function Signature($Status, $Subject, $Issuer) {
    return [pscustomobject]@{Status=$Status; SignerCertificate=[pscustomobject]@{Subject=$Subject; Issuer=$Issuer}}
}
$corp = 'CN=Microsoft Corporation, O=Microsoft Corporation, C=US'
$compat = 'CN=Microsoft Windows Software Compatibility Publisher, O=Microsoft Corporation, C=US'
$codeCA = 'CN=Microsoft Code Signing PCA 2011, O=Microsoft Corporation, C=US'
$compatCA = 'CN=Microsoft Windows Third Party Component CA 2013, O=Microsoft Corporation, C=US'
Check 'observed Microsoft Corporation identity' (Test-OfficialMicrosoftCrtSignature (Signature 'Valid' $corp $codeCA))
Check 'observed Microsoft compatibility publisher identity' (Test-OfficialMicrosoftCrtSignature (Signature 'Valid' $compat $compatCA))
foreach ($status in @('NotSigned', 'HashMismatch', 'NotTrusted', 'UnknownError')) {
    Check "reject $status despite allowed identity" (-not (Test-OfficialMicrosoftCrtSignature (Signature $status $compat $compatCA)))
}
Check 'reject non-Microsoft organization' (-not (Test-OfficialMicrosoftCrtSignature (Signature 'Valid' $compat.Replace('O=Microsoft Corporation', 'O=Other Corporation') $compatCA)))
Check 'reject unobserved publisher CN' (-not (Test-OfficialMicrosoftCrtSignature (Signature 'Valid' $compat.Replace('CN=Microsoft Windows Software Compatibility Publisher', 'CN=Other Publisher') $compatCA)))
Check 'reject non-Microsoft issuer organization' (-not (Test-OfficialMicrosoftCrtSignature (Signature 'Valid' $compat $compatCA.Replace('O=Microsoft Corporation', 'O=Other Corporation'))))
Check 'reject unexpected CA despite Microsoft organization' (-not (Test-OfficialMicrosoftCrtSignature (Signature 'Valid' $compat $compatCA.Replace('CN=Microsoft Windows Third Party Component CA 2013', 'CN=Other CA'))))
Check 'reject missing certificate' (-not (Test-OfficialMicrosoftCrtSignature ([pscustomobject]@{Status='Valid'; SignerCertificate=$null})))
$real = Get-AuthenticodeSignature -LiteralPath $OfficialDll
Check 'actual official DLL is trusted Microsoft' (Test-OfficialMicrosoftCrtSignature $real)
$temp = Join-Path ([IO.Path]::GetTempPath()) ('autoclip-crt-tampered-' + [Guid]::NewGuid().ToString('N') + '.dll')
try {
    $bytes = [IO.File]::ReadAllBytes($OfficialDll)
    if ($bytes.Length -le 0x1000) { throw 'Official DLL too small for signature mutation test' }
    $bytes[0x1000] = $bytes[0x1000] -bxor 1
    [IO.File]::WriteAllBytes($temp, $bytes)
    $tampered = Get-AuthenticodeSignature -LiteralPath $temp
    Check 'real byte-tampered signature is invalid' ($tampered.Status -ne 'Valid')
    Check 'reject real byte-tampered Microsoft DLL' (-not (Test-OfficialMicrosoftCrtSignature $tampered))
    @{schema_version=1; powershell=$PSVersionTable.PSVersion.ToString(); checks=$checks;
      official_status=$real.Status.ToString(); official_subject=$real.SignerCertificate.Subject;
      official_issuer=$real.SignerCertificate.Issuer; tampered_status=$tampered.Status.ToString()} |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Report -Encoding utf8
} finally {
    Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
}
Write-Host "Passed $($checks.Count) CRT signature checks including real byte tampering"
