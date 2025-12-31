# Version: 1.12
# Bugfix: remove invalid base_url setting for Datasette serve

$p = $PSScriptRoot
$port = 8015
$python = "C:\Users\seste\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$dbPath = Join-Path $p "data\cassaforte.db"

function Start-Datasette {
    Write-Host "[WATCHER] Avvio Datasette..."
    Start-Process -NoNewWindow $python `
        "-m datasette serve `"$dbPath`" --host 0.0.0.0 --port $port --plugins-dir plugins --template-dir templates --static custom:static/custom"
}

function Stop-Datasette {
    Get-Process datasette -ErrorAction SilentlyContinue | Stop-Process -Force
}

Start-Datasette

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $p
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true

Register-ObjectEvent $watcher Changed -Action {
    Write-Host "[WATCHER] Cambiamento rilevato, riavvio Datasette..."
    Stop-Datasette
    Start-Datasette
} | Out-Null

Write-Host "[WATCHER] Attivo. CTRL+C per uscire."
while ($true) { Start-Sleep 1 }
