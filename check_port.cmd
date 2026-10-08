@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$matches = netstat -ano -p udp | Select-String ':47831\s'; if (-not $matches) { Write-Host '[INFO] No UDP 47831 listener is currently visible'; exit 0 }; Write-Host '[INFO] UDP 47831 may have multiple listeners by design (SO_REUSEADDR + multicast).'; foreach ($match in $matches) { Write-Host $match.Line }"
exit /b %errorlevel%
