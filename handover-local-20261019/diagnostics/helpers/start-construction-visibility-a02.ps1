$ravenCommand=@'
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenActive=@(Get-ScheduledTask -TaskName 'RAVEN-*' -ErrorAction SilentlyContinue | Where-Object State -eq Running)
if($ravenActive.Count){throw 'Another RAVEN job is running'}
$ravenProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|kit' -and $_.CommandLine -match 'RAVEN-4060.*(probe-|run_windows_probe|launch-)' })
if($ravenProcesses.Count){throw 'A diagnostic process is still active'}
$ravenFolder='D:\RAVEN-4060\setup\construction-visibility-v2'
$ravenHashes=Get-Content "$ravenFolder\source-sha256.json" -Raw | ConvertFrom-Json
foreach($ravenEntry in $ravenHashes.PSObject.Properties){
 if((Get-FileHash -LiteralPath (Join-Path $ravenFolder $ravenEntry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ravenEntry.Value){throw "Source hash mismatch: $($ravenEntry.Name)"}
}
if(Test-Path 'D:\RAVEN-4060\logs\construction-visibility-a02'){throw 'Existing diagnostic must not be overwritten'}
$ravenName='RAVEN-Construction-Visibility-A02-20261019'
$ravenAction=New-ScheduledTaskAction -Execute 'C:\Users\sophi\anaconda3\pythonw.exe' -Argument 'D:\RAVEN-4060\setup\construction-visibility-v2\launch-tiles.py D:\RAVEN-4060\setup\construction-visibility-v2\construction-visibility-a02.json' -WorkingDirectory 'D:\RAVEN-4060\isaac45'
$ravenPrincipal=New-ScheduledTaskPrincipal -UserId 'sophi' -LogonType Interactive -RunLevel Limited
$ravenSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 16) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ravenName -Action $ravenAction -Principal $ravenPrincipal -Settings $ravenSettings | Out-Null
Start-ScheduledTask -TaskName $ravenName
Get-ScheduledTask -TaskName $ravenName | Select TaskName,State | ConvertTo-Json
'@
& "$PSScriptRoot\Invoke-RavenRemote.ps1" -CommandText $ravenCommand
exit $LASTEXITCODE

