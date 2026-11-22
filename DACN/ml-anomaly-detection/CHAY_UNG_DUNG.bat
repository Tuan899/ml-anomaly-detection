@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_app.ps1" %*
set "launchExitCode=%ERRORLEVEL%"
if not "%launchExitCode%"=="0" pause
exit /b %launchExitCode%
