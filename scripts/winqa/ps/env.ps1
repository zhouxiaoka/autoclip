# Record OS / machine / runtime facts and the SHA-256 of the installers as they sit on the VM.
param([string]$PrevInstaller, [string]$CandInstaller)
. $PSScriptRoot\common.ps1
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$wv2 = $null
foreach ($k in 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
               'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
               'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') {
  $v = (Get-ItemProperty $k -ErrorAction SilentlyContinue).pv
  if ($v) { $wv2 = $v; break }
}
$disk = Get-PSDrive C
function Get-InstallerInfo($p) { if ($p -and (Test-Path -LiteralPath $p)) { [pscustomobject]@{ path = $p; bytes = (Get-Item -LiteralPath $p).Length; sha256 = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() } } }
Save-Json ([pscustomobject]@{
  collected_at = Now-Iso
  hostname = $env:COMPUTERNAME
  os_caption = $os.Caption; os_version = $os.Version; os_build = "$($cv.CurrentBuild).$($cv.UBR)"; display_version = $cv.DisplayVersion
  os_arch = $os.OSArchitecture; os_language = ($os.MUILanguages -join ',')
  manufacturer = $cs.Manufacturer; model = $cs.Model; hypervisor_present = $cs.HypervisorPresent
  cpu = $cpu.Name; logical_cpus = $cs.NumberOfLogicalProcessors; ram_gb = [Math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
  webview2 = $wv2
  c_free_gb = [Math]::Round($disk.Free / 1GB, 1)
  interactive_session = Get-InteractiveSessionId
  powershell = $PSVersionTable.PSVersion.ToString()
  timezone = (Get-TimeZone).Id
  installers = @((Get-InstallerInfo $PrevInstaller), (Get-InstallerInfo $CandInstaller))
}) 'env.json'
