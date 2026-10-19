param([ValidatePattern('^full-map-a[0-9]{2}$')][string]$JobName='full-map-a02')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenTask=Get-ScheduledTask -TaskName 'RAVEN-Scene1-FullMap-20261018' -ErrorAction SilentlyContinue
$ravenProgress=$null
$ravenExecution=$null
$ravenResource=$null
if(Test-Path D:\RAVEN-4060\logs\full-scene-map-20261018\progress.json){$ravenProgress=Get-Content D:\RAVEN-4060\logs\full-scene-map-20261018\progress.json -Raw | ConvertFrom-Json}
$ravenJobPath="D:\RAVEN-4060\logs\$JobName"
if(Test-Path "$ravenJobPath\execution.json"){$ravenExecution=Get-Content "$ravenJobPath\execution.json" -Raw | ConvertFrom-Json}
if(Test-Path "$ravenJobPath\resources.jsonl"){$ravenResource=Get-Content "$ravenJobPath\resources.jsonl" -Tail 1 | ConvertFrom-Json}
$ravenProcesses=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(python|pythonw|kit)\.exe$' -and $_.CommandLine -like "*$JobName*"} | Select-Object ProcessId,Name)
$ravenTiles=@()
if($ravenProgress){$ravenTiles=@(Get-ChildItem D:\RAVEN-4060\logs\full-scene-map-20261018\tiles -Filter '*.json' | Sort-Object Name | Select-Object -First $ravenProgress.completed_tiles | ForEach-Object {Get-Content $_.FullName -Raw | ConvertFrom-Json})}
@{observed_at=(Get-Date -Format o);job_name=$JobName;task_state=[string]$ravenTask.State;processes=$ravenProcesses;progress=$ravenProgress;execution=$ravenExecution;latest_resource=$ravenResource;completed_records=$ravenTiles} | ConvertTo-Json -Depth 30 | Set-Content D:\RAVEN-4060\logs\full-map-snapshot.json -Encoding UTF8
Get-Content D:\RAVEN-4060\logs\full-map-snapshot.json
