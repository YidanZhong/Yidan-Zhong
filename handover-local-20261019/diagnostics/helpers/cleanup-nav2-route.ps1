$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|kit)\.exe$' -and $_.CommandLine -match 'jackal-route-a|launch-raven-probe|isaac45' } | Select-Object ProcessId,Name,CommandLine)
if ($ravenProcesses.Count -gt 0) {throw 'Diagnostic process still running'}
$ravenTask=Get-ScheduledTask -TaskName RAVEN-RTX-Diagnostic-20261018 -ErrorAction SilentlyContinue
if ($ravenTask.State -eq 'Running') {throw 'Diagnostic task still running'}
$ravenRosProcesses=@(wsl.exe -d RAVEN-Ubuntu-22.04 --exec pgrep -af 'probe_nav2_wsl_peer|run_nav2_smoke|/opt/ros/humble/lib/nav2_')
$ravenRosAbsent=($LASTEXITCODE -eq 1)
if (-not $ravenRosAbsent) {throw ('ROS processes still active: '+($ravenRosProcesses -join ' '))}
if ($ravenTask) {Unregister-ScheduledTask -TaskName RAVEN-RTX-Diagnostic-20261018 -Confirm:$false}
Remove-NetFirewallRule -Name RAVEN-ROS42-WSL-20261018
Remove-NetFirewallHyperVRule -Name RAVEN-ROS42-HyperV-20261018
wsl.exe --terminate RAVEN-Ubuntu-22.04
@{checked_at=(Get-Date -Format o);processes=$ravenProcesses;task_removed=$true;temporary_firewall_rules_removed=$true;ros_processes_absent=$ravenRosAbsent;isolated_wsl_stopped=($LASTEXITCODE -eq 0);vpn_configuration_changed=$false} | ConvertTo-Json | Set-Content D:\RAVEN-4060\logs\nav2-route-cleanup-20261018.json -Encoding UTF8
Get-Content D:\RAVEN-4060\logs\nav2-route-cleanup-20261018.json
