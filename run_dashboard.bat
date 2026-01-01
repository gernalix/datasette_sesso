@echo off
REM neo-datasette version: 1.11
REM Minimal launcher: no pip checks, no auto-install.
setlocal EnableExtensions
cd /d "%~dp0"
set PYTHONUTF8=1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch_and_run.ps1"

endlocal
