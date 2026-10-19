$ravenCommand=@'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenActive=@(Get-ScheduledTask -TaskName 'RAVEN-*' -ErrorAction SilentlyContinue | Where-Object State -eq Running)
if($ravenActive.Count){throw 'Another RAVEN job is running'}
$ravenProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|kit' -and $_.CommandLine -match 'RAVEN-4060.*(probe-|run_windows_probe|launch-)' })
if($ravenProcesses.Count){throw 'A diagnostic process is still active'}
$ravenWindowExecution=Get-Content 'D:\RAVEN-4060\logs\construction-instancewindows-a01\execution.json' -Raw | ConvertFrom-Json
if($ravenWindowExecution.exit_code -ne 0 -or $ravenWindowExecution.diagnostic_status -ne 'passed'){throw 'Larger real-PhysX windows have not passed'}
$ravenWindowReport=Get-Content 'D:\RAVEN-4060\logs\construction-instancewindows-a01-frames\tile-validation.json' -Raw | ConvertFrom-Json
if(-not $ravenWindowReport.passed -or $ravenWindowReport.formal_gt_approved){throw 'Window result is invalid'}
$ravenFolder='D:\RAVEN-4060\setup\construction-instance-map-v1'
$ravenHashes=Get-Content "$ravenFolder\source-sha256.json" -Raw | ConvertFrom-Json
foreach($ravenEntry in $ravenHashes.PSObject.Properties){
 if((Get-FileHash -LiteralPath (Join-Path $ravenFolder $ravenEntry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ravenEntry.Value){throw "Source hash mismatch: $($ravenEntry.Name)"}
}
if(Test-Path 'D:\RAVEN-4060\logs\construction-instancemap-a01'){throw 'Existing diagnostic must not be overwritten'}
$ravenName='RAVEN-Construction-InstanceMap-20261019'
$ravenAction=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\construction-instance-map-v1\launch-tiles.py D:\RAVEN-4060\setup\construction-instance-map-v1\construction-instancemap-a01.json' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 22) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ravenName -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings | Out-Null
Start-ScheduledTask -TaskName $ravenName
Get-ScheduledTask -TaskName $ravenName | Select TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenCommand
exit $LASTEXITCODE

