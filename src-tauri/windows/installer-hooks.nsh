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

; Tauri 模板先调 PREINSTALL / PREUNINSTALL 钩子，再查主程序是否在运行（CheckIfAppIsRunning）。
; 钩子如果先杀后端，主程序又结束不了（用户在弹窗点取消，或静默安装时 Restart Manager
; 结束不了另一个会话里的主程序 → Abort），就会留下「界面还在、后端已死」的应用（RC156 Win QA #4）。
; 所以钩子里先确认主程序已退出，再清理残留进程。模板随后那次检查找不到进程，不起作用。
; CheckIfAppIsRunning 来自模板的 utils.nsh（已在钩子之前 include），标签按插入行号区分，可重复插入。

; 覆盖安装只会写入本版的文件，从不清理目录：旧版有、新版删掉的后端源码会一直留在
; resources\backend 里，可能被 import（RC156 Win QA #2）。确认主程序已退出、残留进程已结束后，
; 整个删掉这个目录，随后由模板写入本版文件。
; 只删安装目录下的后端源码：用户数据（项目、设置、日志、Whisper 运行时和模型）在 %APPDATA%\AutoClip，
; 不受影响；后端以 PYTHONDONTWRITEBYTECODE=1 运行，这里没有运行时生成的文件。
; resources\python 体积大且有 #224 的文件占用风险，暂不整目录删除。
!macro AUTOCLIP_REMOVE_OLD_BACKEND
  ${If} "$INSTDIR" != ""
  ${AndIf} ${FileExists} "$INSTDIR\resources\backend\*.*"
    RMDir /r "$INSTDIR\resources\backend"
  ${EndIf}
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro CheckIfAppIsRunning "$INSTDIR\${MAINBINARYNAME}.exe" "${PRODUCTNAME}"
  !insertmacro AUTOCLIP_KILL_BUNDLED_PROCESSES
  !insertmacro AUTOCLIP_REMOVE_OLD_BACKEND
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro CheckIfAppIsRunning "$INSTDIR\${MAINBINARYNAME}.exe" "${PRODUCTNAME}"
  !insertmacro AUTOCLIP_KILL_BUNDLED_PROCESSES
!macroend

; 卸载时删除用户数据（RC156 Win QA #15）。模板的「删除应用数据」勾选框只删
; $APPDATA\com.autoclip.desktop 和 $LOCALAPPDATA\com.autoclip.desktop（WebView 数据），
; 项目、设置、API 密钥所在的 %APPDATA%\AutoClip 一直留着，与隐私说明不符。
; 破坏性操作，条件全部满足才删，而且只删这一个目录（不用通配符，不碰上级目录）：
;   - 不是更新：模板的 /UPDATE（$UpdateMode = 1）一律不删；
;   - 不是安装器发起的「安装前卸载」：用户自己运行的卸载程序会先把自己复制到 %TEMP% 再运行，
;     安装器则带 _?= 原地运行（$EXEDIR = $INSTDIR），这种升级卸载一律不删；
;   - 图形界面：只看用户是否勾选（默认不勾选，不勾选就保留数据）；
;   - 静默（/S）或被动（/P）卸载：勾选框不出现，只有显式传入 /DELETEAPPDATA 才删。
!macro AUTOCLIP_DELETE_USER_DATA
  Push $R8
  Push $R9
  StrCpy $R9 0
  ${If} $UpdateMode <> 1
  ${AndIf} "$EXEDIR" != "$INSTDIR"
    ${If} ${Silent}
    ${OrIf} $PassiveMode = 1
      ClearErrors
      ${GetOptions} $CMDLINE "/DELETEAPPDATA" $R8
      ${IfNot} ${Errors}
        StrCpy $R9 1
      ${EndIf}
    ${ElseIf} $DeleteAppDataCheckboxState = 1
      StrCpy $R9 1
    ${EndIf}
  ${EndIf}
  ${If} $R9 = 1
    SetShellVarContext current
    ${If} "$APPDATA" != ""
    ${AndIf} ${FileExists} "$APPDATA\AutoClip\*.*"
      DetailPrint "Deleting AutoClip data: $APPDATA\AutoClip"
      RMDir /r "$APPDATA\AutoClip"
    ${EndIf}
  ${EndIf}
  Pop $R9
  Pop $R8
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  !insertmacro AUTOCLIP_DELETE_USER_DATA
!macroend

; 卸载确认页顶部说明：默认保留数据，勾选才会永久删除（文字在 windows/lang/*.nsh）。
; 钩子在模板的页面定义之前被 include，MUI_UNPAGE_CONFIRM 插入时读取并清除这个定义。
!define MUI_UNCONFIRMPAGE_TEXT_TOP "$(autoclipUninstallNote)"
