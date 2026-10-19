$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenActive=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(python|pythonw|kit)\.exe$' -and $_.CommandLine -like '*RAVEN-4060*'})
if($ravenActive.Count){throw 'Existing RAVEN process running'}
if(Test-Path D:\RAVEN-4060\logs\full-post-a01){throw 'Run already exists'}
$ravenAction=New-ScheduledTaskAction -Execute C:\Users\sophi\anaconda3\pythonw.exe -Argument 'D:\RAVEN-4060\setup\full-post-v1\launch-full-post.py' -WorkingDirectory D:\RAVEN-4060\isaac45
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId sophi -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 65) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName RAVEN-FullMap-Postprocess-20261019 -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings -Force | Out-Null
Start-ScheduledTask -TaskName RAVEN-FullMap-Postprocess-20261019
Get-ScheduledTask -TaskName RAVEN-FullMap-Postprocess-20261019 | Select-Object TaskName,State | ConvertTo-Json
