@echo off
REM Version: 1.10
setlocal EnableExtensions
cd /d "%~dp0"

REM 1) If datasette.exe is already in PATH, use it (fastest, avoids python/venv issues)
where datasette >nul 2>&1
if not errorlevel 1 (
  echo [BOOT] Trovato datasette.exe in PATH: uso quello.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch_and_run.ps1" -UseDatasetteExe
  exit /b 0
)

REM 2) Otherwise, use the user-confirmed Python path
set "PYTHON=C:\Users\seste\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON%" (
  echo [ERRORE] Python non trovato: "%PYTHON%"
  pause
  exit /b 1
)

echo [BOOT] Uso Python: "%PYTHON%"

REM Ensure pip exists
echo [BOOT] Verifico pip...
"%PYTHON%" -m pip --version
if errorlevel 1 (
  echo [BOOT] pip non presente: provo ensurepip...
  "%PYTHON%" -m ensurepip --upgrade
  if errorlevel 1 (
    echo [ERRORE] ensurepip fallito.
    pause
    exit /b 1
  )
)

REM Check datasette module (no parentheses in ECHO inside blocks to avoid CMD parsing issues)
echo [BOOT] Verifico se datasette e' installato per questo Python...
"%PYTHON%" -c "import datasette" >nul 2>&1
if errorlevel 1 (
  echo [BOOT] Datasette non trovato per questo Python. Installo user-site...
  "%PYTHON%" -m pip install --user datasette
  if errorlevel 1 (
    echo [ERRORE] Installazione Datasette fallita.
    echo Prova manualmente:
    echo   "%PYTHON%" -m pip install --user datasette
    pause
    exit /b 1
  )
)

REM Run watcher without loading PowerShell profile
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watch_and_run.ps1"

endlocal
