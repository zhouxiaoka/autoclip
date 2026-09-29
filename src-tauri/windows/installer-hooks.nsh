; AutoClip NSIS 钩子（tauri.windows.conf.json → bundle.windows.nsis.installerHooks）
;
; 覆盖安装 / 卸载前，结束安装目录里残留的 python.exe、ffmpeg.exe、ffprobe.exe。
; 1.4.0 及更早的版本没有 Job Object，主程序退出后后端进程树可能还活着，
; 占着 resources\python\*.pyd，安装器就会报「无法打开要写入的文件 _asyncio.pyd」（#224）。
; 新版的 Job Object 只对新版本运行时生效，执行升级的是用户手上的旧版，所以要在安装器里兜底。
;
; 只按可执行文件路径匹配安装目录，不会误杀用户自己的 Python / ffmpeg。
; 安装目录通过环境变量传给 PowerShell，避免路径里的特殊字符被 PowerShell 解析。
; NSIS 字符串用反引号包裹；$$ 在 NSIS 里是字面量 $。

!macro AUTOCLIP_KILL_BUNDLED_PROCESSES
  System::Call 'Kernel32::SetEnvironmentVariable(t "AUTOCLIP_INSTDIR", t "$INSTDIR")i'
  nsExec::ExecToLog `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$$root = [IO.Path]::GetFullPath($$env:AUTOCLIP_INSTDIR).TrimEnd([char]92) + [char]92; Get-CimInstance Win32_Process | Where-Object { $$_.ExecutablePath -and $$_.ExecutablePath.StartsWith($$root, [StringComparison]::OrdinalIgnoreCase) -and @('python.exe','pythonw.exe','ffmpeg.exe','ffprobe.exe') -contains $$_.Name.ToLower() } | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
  Pop $0
  ; 给系统一点时间释放文件句柄
  Sleep 800
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro AUTOCLIP_KILL_BUNDLED_PROCESSES
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro AUTOCLIP_KILL_BUNDLED_PROCESSES
!macroend
