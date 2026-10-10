@echo off
setlocal
"%ProgramFiles%\KiCad\9.0\bin\python.exe" -B "%~dp0phone_trigger_test.py" %*
exit /b %errorlevel%
