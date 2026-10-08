# Close the app (main window process first; the Windows Job Object should take the backend tree with it).
param([string]$Label = 'stop')
. $PSScriptRoot\common.ps1
$inst = Get-AutoClipInstall
$dir = $(if ($inst) { $inst.Dir } else { '' })
$before = @(Get-AutoClipProcesses $dir)
$main = @($before | Where-Object { $_.name -like 'AutoClip*' })
foreach ($m in $main) { Stop-Process -Id $m.pid -Force -ErrorAction SilentlyContinue }
Start-Sleep 4
$orphans = @(Get-AutoClipProcesses $dir)
$left = @($orphans | ForEach-Object { "$($_.name)#$($_.pid)" })
foreach ($o in $orphans) { Stop-Process -Id $o.pid -Force -ErrorAction SilentlyContinue }
Unregister-ScheduledTask -TaskName 'winqa-launch' -Confirm:$false -ErrorAction SilentlyContinue
Save-Json ([pscustomobject]@{ label = $Label; killed_main = @($main | ForEach-Object { "$($_.name)#$($_.pid)" }); backend_left_after_main_killed = $left }) "stop-$Label.json"
