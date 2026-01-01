# neo-datasette version: 1.6
# Fix PowerShell variable parsing error and stabilize watcher

param(
  [switch]$UseDatasetteExe
)

$ErrorActionPreference = "Stop"

$p      = $PSScriptRoot
$port   = 8015
$python = "C:\Users\seste\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$dbPath = Join-Path $p "data\cassaforte.db"

$pluginsDir   = Join-Path $p "plugins"
$templatesDir = Join-Path $p "templates"
$staticDir    = Join-Path $p "static"
$customDir    = Join-Path $staticDir "custom"

$debounceMs = 800

$script:dsProc = $null
$script:restartScheduled = $false

function Get-PortOwners($Port) {
  $pids = @()
  try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
      if ($c.OwningProcess) { $pids += [int]$c.OwningProcess }
    }
  } catch {
    $lines = (netstat -ano | Select-String -Pattern (":$Port\s+"))
    foreach ($ln in $lines) {
      $parts = ($ln -split "\s+") | Where-Object { $_ -ne "" }
      if ($parts.Count -ge 1) { $pids += [int]$parts[-1] }
    }
  }
  $pids | Sort-Object -Unique
}

function Stop-AnyProcessOnPort($Port) {
  $pids = Get-PortOwners $Port
  foreach ($pid in $pids) {
    try {
      if ($pid -and $pid -ne 0) {
        Write-Host ("[WATCHER] Porta {0} occupata da PID {1}: termino..." -f $Port, $pid)
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
      }
    } catch {}
  }
}

function Stop-Datasette {
  if ($script:dsProc -and !$script:dsProc.HasExited) {
    try {
      Write-Host ("[WATCHER] Stop Datasette (PID {0})..." -f $script:dsProc.Id)
      Stop-Process -Id $script:dsProc.Id -Force -ErrorAction SilentlyContinue
    } catch {}
  }
  $script:dsProc = $null
  Stop-AnyProcessOnPort $port
}

function Start-Datasette {
  Write-Host "[WATCHER] Avvio Datasette..."
  Stop-AnyProcessOnPort $port

  if ($UseDatasetteExe) {
    $exe = (Get-Command datasette -ErrorAction Stop).Source
    $args = @(
      "serve", $dbPath,
      "--host", "0.0.0.0",
      "--port", "$port",
      "--plugins-dir", $pluginsDir,
      "--template-dir", $templatesDir,
      "--static", ("static:" + $staticDir),
      "--static", ("custom:" + $customDir)
    )
    $script:dsProc = Start-Process -NoNewWindow -PassThru $exe -ArgumentList $args
  } else {
    $args = @(
      "-m", "datasette", "serve", $dbPath,
      "--host", "0.0.0.0",
      "--port", "$port",
      "--plugins-dir", $pluginsDir,
      "--template-dir", $templatesDir,
      "--static", ("static:" + $staticDir),
      "--static", ("custom:" + $customDir)
    )
    $script:dsProc = Start-Process -NoNewWindow -PassThru $python -ArgumentList $args
  }

  Write-Host ("[WATCHER] Datasette avviato (PID {0})" -f $script:dsProc.Id)
}

function Schedule-Restart {
  if ($script:restartScheduled) { return }
  $script:restartScheduled = $true
  Start-Sleep -Milliseconds $debounceMs
  $script:restartScheduled = $false
  Write-Host "[WATCHER] Cambiamento rilevato, riavvio Datasette..."
  Stop-Datasette
  Start-Datasette
}

Start-Datasette

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $p
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true
$watcher.NotifyFilter = [IO.NotifyFilters]'FileName, LastWrite, DirectoryName'

$action = { Schedule-Restart }

Register-ObjectEvent $watcher Changed -Action $action | Out-Null
Register-ObjectEvent $watcher Created -Action $action | Out-Null
Register-ObjectEvent $watcher Deleted -Action $action | Out-Null
Register-ObjectEvent $watcher Renamed -Action $action | Out-Null

Write-Host "[WATCHER] Attivo. CTRL+C per uscire."
try {
  while ($true) { Start-Sleep 1 }
} finally {
  Stop-Datasette
}
