@echo off
setlocal
set "TRIGGER=CTRL+WIN:F12"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$group='239.255.77.77'; $port=47831; $iface=[System.Net.IPAddress]::Parse('127.0.0.1'); $udp=New-Object System.Net.Sockets.UdpClient([System.Net.Sockets.AddressFamily]::InterNetwork); try { $udp.MulticastLoopback=$true; $udp.Ttl=0; $udp.Client.SetSocketOption([System.Net.Sockets.SocketOptionLevel]::IP,[System.Net.Sockets.SocketOptionName]::MulticastInterface,$iface.GetAddressBytes()); $msg='TRIGGER|%TRIGGER%'; $bytes=[System.Text.Encoding]::UTF8.GetBytes($msg); [void]$udp.Send($bytes,$bytes.Length,$group,$port); Write-Host ('[PASS] Sent {0} to {1}:{2} via 127.0.0.1' -f $msg,$group,$port) } finally { $udp.Dispose() }"
exit /b %errorlevel%
