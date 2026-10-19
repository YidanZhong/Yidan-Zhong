$ravenCommand=@'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenTasks=@(Get-ScheduledTask -TaskName 'RAVEN-*' -ErrorAction SilentlyContinue | Where-Object State -eq Running)
if(@($ravenTasks | Where-Object TaskName -ne 'RAVEN-Construction-InstanceMap-20261019').Count){throw 'Unexpected task active; refusing continuation watcher'}
$ravenName='RAVEN-ConstructionInstanceBatches-20261019'
if(Get-ScheduledTask -TaskName $ravenName -ErrorAction SilentlyContinue){throw 'Continuation task already exists'}
if(Test-Path D:\RAVEN-4060\logs\construction-instance-continuation-wait-20261019){throw 'Existing continuation wait evidence must be preserved'}
$ravenAction=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\wait-initial-instance-map.py' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 130) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ravenName -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings | Out-Null
Start-ScheduledTask -TaskName $ravenName
Get-ScheduledTask -TaskName $ravenName | Select-Object TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenCommand
exit $LASTEXITCODE
