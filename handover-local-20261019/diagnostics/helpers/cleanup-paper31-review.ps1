$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|kit)\.exe$' -and $_.CommandLine -match 'paper31-review-a|launch-raven-probe|isaac45' } | Select-Object ProcessId,Name,CommandLine)
if ($ravenProcesses.Count -gt 0) {throw 'Diagnostic process still running'}
$ravenTask=Get-ScheduledTask -TaskName RAVEN-RTX-Diagnostic-20261018 -ErrorAction SilentlyContinue
if ($ravenTask.State -eq 'Running') {throw 'Diagnostic task still running'}
if ($ravenTask) {Unregister-ScheduledTask -TaskName RAVEN-RTX-Diagnostic-20261018 -Confirm:$false}
@{checked_at=(Get-Date -Format o);processes=$ravenProcesses;task_removed=$true;wsl_started=$false;network_rules_created=$false;vpn_configuration_changed=$false} | ConvertTo-Json | Set-Content D:\RAVEN-4060\logs\paper31-review-cleanup-20261018.json -Encoding UTF8
Get-Content D:\RAVEN-4060\logs\paper31-review-cleanup-20261018.json
