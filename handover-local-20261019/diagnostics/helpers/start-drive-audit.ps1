param([Parameter(Mandatory=$true)][string]$JobName)
if ($JobName -notmatch '^[a-z0-9-]+$') {throw 'Invalid diagnostic job name'}
$ravenRemoteText = @'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$name='RAVEN-DriveAudit-20261019'
$existing=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if ($existing -and $existing.State -eq 'Running') {throw 'Existing diagnostic still running'}
$action=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\drive-audit-v1\launch-drive-audit.py D:\RAVEN-4060\setup\drive-audit-v1\JOBNAME.json' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$principal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 7) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $name
Get-ScheduledTask -TaskName $name | Select-Object TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenRemoteText.Replace('JOBNAME',$JobName)
exit $LASTEXITCODE
