$ravenCommand = @'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenRunning=@(Get-ScheduledTask -TaskName 'RAVEN-*' -ErrorAction SilentlyContinue | Where-Object State -eq Running)
if($ravenRunning.Count){throw 'Another RAVEN task is still running; refusing overlapping queue'}
$ravenProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|kit' -and $_.CommandLine -match 'RAVEN-4060.*(probe-|run_windows_probe|launch-)' })
if($ravenProcesses.Count){throw 'A diagnostic process is still active'}
$ravenInitial=Get-Content 'D:\RAVEN-4060\logs\construction-instancemap-a01\execution.json' -Raw | ConvertFrom-Json
if($ravenInitial.exit_code -ne 0 -or $ravenInitial.diagnostic_status -ne 'passed'){throw 'Initial fresh-map batch has not passed'}
$ravenName='RAVEN-ConstructionInstanceBatches-20261019'
if(Get-ScheduledTask -TaskName $ravenName -ErrorAction SilentlyContinue){throw 'Finite queue already registered; inspect instead of replaying'}
if(Test-Path D:\RAVEN-4060\logs\construction-instance-batches-20261019){throw 'Existing queue output must remain unchanged'}
$ravenAction=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\run-construction-instance-batches.py D:\RAVEN-4060\setup\construction-instance-batches.json' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 105) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ravenName -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings | Out-Null
Start-ScheduledTask -TaskName $ravenName
Get-ScheduledTask -TaskName $ravenName | Select-Object TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenCommand
exit $LASTEXITCODE
