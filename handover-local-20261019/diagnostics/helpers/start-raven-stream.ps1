param([Parameter(Mandatory=$true)][string]$JobName)
if ($JobName -notmatch '^(resume-test-a0[12]|full-map-a01)$') {throw 'Unexpected job'}
$ravenTaskName=if ($JobName -eq 'full-map-a01') {'RAVEN-Scene1-FullMap-20261018'} else {'RAVEN-RTX-Diagnostic-20261018'}
$ravenMinutes=if ($JobName -eq 'full-map-a01') {490} else {15}
$ravenRemoteText=@'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenActive=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|kit)\.exe$' -and $_.CommandLine -like '*RAVEN-4060*' })
if ($ravenActive.Count) {throw 'Existing RAVEN process is running'}
$ravenExisting=Get-ScheduledTask -TaskName 'TASKNAME' -ErrorAction SilentlyContinue
if ($ravenExisting.State -eq 'Running') {throw 'Existing task is running'}
$ravenAction=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\launch-raven-stream.py D:\RAVEN-4060\setup\JOBNAME.json' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes MINUTES) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'TASKNAME' -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings -Force | Out-Null
Start-ScheduledTask -TaskName 'TASKNAME'
Get-ScheduledTask -TaskName 'TASKNAME' | Select-Object TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenRemoteText.Replace('TASKNAME',$ravenTaskName).Replace('JOBNAME',$JobName).Replace('MINUTES',[string]$ravenMinutes)
exit $LASTEXITCODE
