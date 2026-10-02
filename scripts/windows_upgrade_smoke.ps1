# Windows 覆盖升级 + 安装后冒烟。desktop-build.yml 的 smoke-windows-x64 和 windows-install-smoke.yml 共用。
#
#   pwsh scripts/windows_upgrade_smoke.ps1 -NewInstaller <本次构建的 setup.exe>
#
# 1. 静默安装上一个正式版（GitHub latest release，需要 GH_TOKEN）
# 2. 用安装目录里的 python.exe 起一个进程占住 _asyncio.pyd，模拟旧版残留后端（#224）
# 3. 静默覆盖安装新包：安装器必须结束残留进程，并写入新文件
# 4. 用安装目录自带的 Python 跑 scripts/verify_windows_install.py
param(
  [Parameter(Mandatory = $true)][string]$NewInstaller,
  [string]$Report = 'windows-smoke.json'
)
$ErrorActionPreference = 'Stop'
$repo = $env:GITHUB_REPOSITORY

function Get-InstallDir {
  $key = Get-ChildItem HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall |
    Get-ItemProperty | Where-Object DisplayName -like 'AutoClip*' | Select-Object -First 1
  if (-not $key) { throw '注册表里找不到 AutoClip 安装记录' }
  # NSIS 写的 InstallLocation 带引号，例如 "C:\Users\<user>\AppData\Local\AutoClip Desktop"
  $dir = ($key.InstallLocation -replace '"', '').TrimEnd('\')
  if (-not $dir) { $dir = Split-Path ($key.UninstallString -replace '"', '') }
  if (-not (Test-Path (Join-Path $dir 'resources\python\python.exe'))) {
    throw "安装目录里找不到 resources\python\python.exe: $dir"
  }
  return @{ Dir = $dir; Version = $key.DisplayVersion }
}

Write-Host '==> 安装上一个正式版'
$prev = gh release view --repo $repo --json tagName -q .tagName
gh release download $prev --repo $repo --pattern '*x64-setup.exe' --dir old --clobber
$old = Get-ChildItem old\*x64-setup.exe | Select-Object -First 1
$p = Start-Process $old.FullName -ArgumentList '/S' -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "旧版 $prev 安装失败: $($p.ExitCode)" }
$install = Get-InstallDir
Write-Host "旧版 $prev 安装到 $($install.Dir)（$($install.Version)）"

Write-Host '==> 模拟旧版残留后端占住 _asyncio.pyd'
$py = Join-Path $install.Dir 'resources\python\python.exe'
$lock = Start-Process $py -ArgumentList '-c', '"import asyncio, time; time.sleep(900)"' -PassThru -WindowStyle Hidden
Start-Sleep 3
if ($lock.HasExited) { throw '模拟残留进程没起来' }
Write-Host "残留 python.exe PID=$($lock.Id)"

Write-Host '==> 静默覆盖安装新包'
$p = Start-Process (Resolve-Path $NewInstaller).Path -ArgumentList '/S' -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "覆盖安装失败: $($p.ExitCode)" }
if (Get-Process -Id $lock.Id -ErrorAction SilentlyContinue) {
  Stop-Process -Id $lock.Id -Force
  throw '安装器没有结束残留的 python.exe'
}
$install = Get-InstallDir
$marker = Join-Path $install.Dir 'resources\backend\core\local_origin_guard.py'
if (-not (Test-Path $marker)) { throw '覆盖安装后仍是旧文件（新版文件没写进去）' }
Write-Host "从 $prev 覆盖升级到 $($install.Version) 成功，残留进程已被安装器结束"

Write-Host '==> 安装后运行时冒烟'
$res = Join-Path $install.Dir 'resources'
# 和桌面端启动后端时一样：强制 UTF-8，否则中文输出在 cp1252 控制台上直接报错
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& (Join-Path $res 'python\python.exe') -B scripts\verify_windows_install.py --resources $res --report $Report --launch-desktop
if ($LASTEXITCODE -ne 0) { throw "安装后冒烟失败: $LASTEXITCODE" }

Write-Host '==> 验证安装包内 SenseVoice 组件及真实离线转写'
& (Join-Path $res 'python\python.exe') -B scripts\verify_sensevoice.py --resources $res --report windows-sensevoice-installed.json
if ($LASTEXITCODE -ne 0) { throw "安装包 SenseVoice 验证失败: $LASTEXITCODE" }
