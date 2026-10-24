@echo off
chcp 65001 >nul
setlocal
set "PYW=%~dp0RVC\runtime\pythonw.exe"

if not exist "%PYW%" (
  echo [ERROR] Runtime not found: %PYW%
  echo The package is incomplete. Please re-extract the archive.
  pause
  exit /b 1
)
start "" /D "%~dp0" "%PYW%" "%~dp0launcher.py"
