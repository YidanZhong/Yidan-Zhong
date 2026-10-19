$ravenCommand=@'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenName='RAVEN-IndependentDiagnostics-20261019'
if(Get-ScheduledTask -TaskName $ravenName -ErrorAction SilentlyContinue){throw 'Existing task must not be replaced'}
if(Test-Path D:\RAVEN-4060\logs\independent-diagnostics-20261019){throw 'Existing diagnostic output must not be replaced'}
$ravenPreflight=Get-Content D:\RAVEN-4060\setup\independent-diagnostics-preflight.json -Raw | ConvertFrom-Json
if(-not $ravenPreflight.passed){throw 'Preflight not passed'}
$ravenAction=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\run-independent-diagnostics.py D:\RAVEN-4060\setup\independent-diagnostics.json' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 130) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ravenName -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings | Out-Null
Start-ScheduledTask -TaskName $ravenName
Get-ScheduledTask -TaskName $ravenName | Select-Object TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenCommand
exit $LASTEXITCODE
