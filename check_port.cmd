@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$matches = netstat -ano -p udp | Select-String ':47831\s'; if (-not $matches) { Write-Host '[FREE] UDP 47831 is not in use'; exit 0 }; foreach ($match in $matches) { if ($match.Line -match '^\s*UDP\s+(\S+:47831)\s+\S+\s+(\d+)') { $pidValue = [int]$Matches[2]; $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue; Write-Host ('[IN USE] {0} PID={1} Process={2}' -f $Matches[1], $pidValue, $process.ProcessName) } }"
exit /b %errorlevel%
