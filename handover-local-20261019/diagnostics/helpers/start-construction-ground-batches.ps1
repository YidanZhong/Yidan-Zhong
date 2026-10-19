$ravenCommand = @'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenRunning=@(Get-ScheduledTask -TaskName 'RAVEN-*' -ErrorAction SilentlyContinue | Where-Object State -eq Running)
if($ravenRunning.Count){throw 'Another RAVEN task is still running; refusing overlapping queue'}
$ravenName='RAVEN-ConstructionGroundBatches-20261019'
if(Get-ScheduledTask -TaskName $ravenName -ErrorAction SilentlyContinue){throw 'Finite queue already registered; inspect instead of replaying'}
if(Test-Path D:\RAVEN-4060\logs\construction-ground-batches-20261019){throw 'Existing queue output must remain unchanged'}
$ravenAction=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\run-construction-ground-batches.py D:\RAVEN-4060\setup\construction-ground-batches.json' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 105) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ravenName -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings | Out-Null
Start-ScheduledTask -TaskName $ravenName
Get-ScheduledTask -TaskName $ravenName | Select-Object TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenCommand
exit $LASTEXITCODE
