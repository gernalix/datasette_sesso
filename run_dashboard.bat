@echo off
REM neo-datasette version: 1.6
setlocal EnableExtensions
cd /d "%~dp0"

set PYTHONUTF8=1

where datasette >nul 2>&1
if not errorlevel 1 (
  echo [BOOT] Trovato datasette.exe in PATH: uso quello.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch_and_run.ps1" -UseDatasetteExe
  exit /b 0
)

set PYTHON=C:\Users\seste\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist "%PYTHON%" (
  echo [ERRORE] Python non trovato: "%PYTHON%"
  exit /b 1
)

echo [BOOT] Uso Python: "%PYTHON%"
echo [BOOT] Verifico pip...
"%PYTHON%" -m pip --version || exit /b 1

echo [BOOT] Verifico se datasette e' installato per questo Python...
"%PYTHON%" -c "import datasette" >nul 2>&1
if errorlevel 1 (
  echo [BOOT] Datasette non trovato. Installo...
  "%PYTHON%" -m pip install --user datasette || exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch_and_run.ps1"
endlocal
