$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$ravenWslIp=(wsl.exe -d RAVEN-Ubuntu-22.04 -- hostname -I).Trim().Split(' ')[0]
$ravenRoute=(wsl.exe -d RAVEN-Ubuntu-22.04 -- ip -4 route show default).Trim().Split(' ')
$ravenHostIp=$ravenRoute[2]
if ($ravenWslIp -notmatch '^172\.\d+\.\d+\.\d+$' -or $ravenHostIp -notmatch '^172\.\d+\.\d+\.\d+$') {throw 'Expected inspected WSL NAT network'}
$ravenTemplate=@'
<?xml version="1.0" encoding="UTF-8" ?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <transport_descriptors><transport_descriptor>
    <transport_id>RavenUdp</transport_id><type>UDPv4</type>
    <interfaceWhiteList><address>LOCAL_IP</address></interfaceWhiteList>
    <maxInitialPeersRange>32</maxInitialPeersRange>
  </transport_descriptor></transport_descriptors>
  <participant profile_name="raven_nat_udp" is_default_profile="true"><rtps>
    <builtin><initialPeersList>
      <locator><udpv4><address>HOST_IP</address></udpv4></locator>
      <locator><udpv4><address>WSL_IP</address></udpv4></locator>
    </initialPeersList></builtin>
    <userTransports><transport_id>RavenUdp</transport_id></userTransports>
    <useBuiltinTransports>false</useBuiltinTransports>
  </rtps></participant>
</profiles>
'@
$ravenXml=$ravenTemplate.Replace('HOST_IP',$ravenHostIp).Replace('WSL_IP',$ravenWslIp)
[IO.File]::WriteAllText('D:\RAVEN-4060\setup\fastdds-windows.xml',$ravenXml.Replace('LOCAL_IP',$ravenHostIp))
[IO.File]::WriteAllText('D:\RAVEN-4060\setup\fastdds-wsl.xml',$ravenXml.Replace('LOCAL_IP',$ravenWslIp))
$ravenRule='RAVEN-ROS42-WSL-20261018'
if (Get-NetFirewallRule -Name $ravenRule -ErrorAction SilentlyContinue) {throw 'Refusing to replace existing firewall rule'}
New-NetFirewallRule -Name $ravenRule -DisplayName 'RAVEN domain 42 from isolated WSL' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 17900-18149 -LocalAddress $ravenHostIp -RemoteAddress $ravenWslIp -Profile Any | Out-Null
$ravenHvRule='RAVEN-ROS42-HyperV-20261018'
New-NetFirewallHyperVRule -Name $ravenHvRule -DisplayName 'RAVEN domain 42 from Windows host' -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol UDP -LocalPorts 17900-18149 -RemoteAddresses $ravenHostIp -Action Allow | Out-Null
@{host_ip=$ravenHostIp;wsl_ip=$ravenWslIp;domain=42;windows_rule=$ravenRule;hyperv_rule=$ravenHvRule;checked_at=(Get-Date -Format o)} | ConvertTo-Json | Set-Content D:\RAVEN-4060\logs\ros-bridge-network-20261018.json -Encoding UTF8
Get-Content D:\RAVEN-4060\logs\ros-bridge-network-20261018.json
