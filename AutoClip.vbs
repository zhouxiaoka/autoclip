' Double-click launcher: starts AutoClip and opens it in an app window,
' with no visible console/terminal.
Dim fso, scriptDir, ps1Path
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
ps1Path = scriptDir & "\scripts\windows_launcher.ps1"

CreateObject("WScript.Shell").Run _
    "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1Path & """", _
    0, False
