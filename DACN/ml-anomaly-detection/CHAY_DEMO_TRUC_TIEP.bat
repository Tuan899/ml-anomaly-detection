@echo off
setlocal
set "projectRoot=%~dp0"
set "demoPython="
for %%P in ("%projectRoot%.venv\Scripts\python.exe" "%projectRoot%..\.venv\Scripts\python.exe" "%projectRoot%..\..\.venv\Scripts\python.exe") do (
  if not defined demoPython if exist "%%~P" (
    "%%~P" "%projectRoot%scripts\run_live_demo.py" --check >nul 2>&1
    if not errorlevel 1 set "demoPython=%%~P"
  )
)
if not defined demoPython (
  python "%projectRoot%scripts\run_live_demo.py" --check >nul 2>&1
  if not errorlevel 1 set "demoPython=python"
)
if not defined demoPython (
  echo No complete Python environment found. Install requirements.txt first.
  pause
  exit /b 1
)
"%demoPython%" "%projectRoot%scripts\run_live_demo.py" %*
set "demoExitCode=%ERRORLEVEL%"
if not "%demoExitCode%"=="0" pause
exit /b %demoExitCode%
