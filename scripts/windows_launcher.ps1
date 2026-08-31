# AutoClip Windows app-mode launcher.
# Starts the backend + Celery worker + frontend dev server (only if not
# already running), waits for backend/frontend to become healthy, then
# opens the UI in a chromeless Edge "app" window so it looks/feels like a
# standalone desktop app. On window close, stops whichever of
# backend/worker/frontend this script started.

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$logsDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

# Defensively make sure ffmpeg is on PATH for this process tree even if the
# process that launched us (e.g. a not-yet-refreshed Explorer session) is
# still carrying a PATH from before ffmpeg was installed.
$ffmpegBin = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages') `
    -Filter 'ffmpeg.exe' -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty DirectoryName
if ($ffmpegBin -and ($env:Path -notlike "*$ffmpegBin*")) {
    $env:Path = "$ffmpegBin;$env:Path"
}

function Test-Port([int]$port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect('127.0.0.1', $port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(300)
        if ($ok -and $client.Connected) { $client.Close(); return $true }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Wait-Port([int]$port, [int]$timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $port) { return $true }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

$backendProc = $null
$celeryProc = $null
$frontendProc = $null

$venvPython = Join-Path $root 'venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONPATH = $root

# --- Backend (FastAPI/uvicorn on :8000) ---
if (-not (Test-Port 8000)) {
    $backendProc = Start-Process -FilePath $venvPython `
        -ArgumentList '-m', 'uvicorn', 'backend.main:app', '--port', '8000' `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logsDir 'backend.out.log') `
        -RedirectStandardError (Join-Path $logsDir 'backend.err.log')
}
Wait-Port 8000 30 | Out-Null

# --- Celery worker (consumes the video-processing task queue; without this
#     nothing ever actually processes, it just sits queued forever) ---
$celeryRunning = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'celery' -and $_.CommandLine -match 'worker' }
if (-not $celeryRunning) {
    $celeryProc = Start-Process -FilePath $venvPython `
        -ArgumentList '-m', 'celery', '-A', 'backend.celery_app', 'worker', `
            '--loglevel=info', '--pool=solo', `
            '-Q', 'celery,processing,video,notification,maintenance,upload' `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logsDir 'celery.out.log') `
        -RedirectStandardError (Join-Path $logsDir 'celery.err.log')
}

# --- Frontend (Vite dev server on :3000, proxies /api to :8000) ---
if (-not (Test-Port 3000)) {
    $frontendDir = Join-Path $root 'frontend'
    $npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $npmCmd) { $npmCmd = 'npm.cmd' }
    $frontendProc = Start-Process -FilePath $npmCmd -ArgumentList 'run', 'dev' `
        -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logsDir 'frontend.out.log') `
        -RedirectStandardError (Join-Path $logsDir 'frontend.err.log')
}
Wait-Port 3000 30 | Out-Null

# --- App window (isolated profile so it opens as its own process, not a tab
#     in whatever Edge window the user already has open) ---
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if (-not (Test-Path $edge)) {
    $edge = 'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
}
$profileDir = Join-Path $env:LOCALAPPDATA 'AutoClipAppWindow'

Start-Process -FilePath $edge -ArgumentList `
    "--app=http://localhost:3000", `
    "--user-data-dir=$profileDir", `
    "--window-size=1280,860" `
    -Wait

# --- Cleanup: only stop what we started ---
foreach ($proc in @($backendProc, $celeryProc, $frontendProc)) {
    if ($proc -and -not $proc.HasExited) {
        try { Start-Process -FilePath 'taskkill.exe' -ArgumentList '/F', '/T', '/PID', $proc.Id -WindowStyle Hidden -Wait } catch {}
    }
}
