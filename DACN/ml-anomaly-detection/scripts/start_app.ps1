param(
    [switch]$Check,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workspaceRoot = Split-Path $projectRoot -Parent
$parentRoot = Split-Path $workspaceRoot -Parent
$pythonCandidates = @(
    (Join-Path $projectRoot '.venv\Scripts\python.exe'),
    (Join-Path $workspaceRoot '.venv\Scripts\python.exe'),
    (Join-Path $parentRoot '.venv\Scripts\python.exe')
)
$systemPython = Get-Command python -ErrorAction SilentlyContinue
if ($systemPython) { $pythonCandidates += $systemPython.Source }

# Validate each environment: an existing .venv may still be incomplete.
$dependencyProbe = @'
import sys
assert sys.version_info >= (3, 10), 'Python 3.10 or newer is required'
import fastapi, httpx, matplotlib, numpy, pandas, pymysql, plotly
import multipart, docx, pptx, sklearn, scipy, seaborn, streamlit, uvicorn, pydantic
from packaging.version import Version
assert Version(streamlit.__version__) >= Version('1.65.0'), 'Streamlit >= 1.65.0 is required'
assert Version(pydantic.__version__) >= Version('2.0'), 'Pydantic >= 2.0 is required'
'@
$pythonExe = $null
foreach ($candidate in ($pythonCandidates | Select-Object -Unique)) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $probeOk = $false
        try {
            & $candidate -c $dependencyProbe *> $null
            $probeOk = $LASTEXITCODE -eq 0
        } catch { $probeOk = $false }
        if ($probeOk) {
            $pythonExe = $candidate
            break
        }
        Write-Host "Skipping incomplete Python environment: $candidate"
    }
}
if (-not $pythonExe) {
    Write-Host 'No working Python environment was found. Run these commands first:'
    Write-Host "  cd `"$projectRoot`""
    Write-Host '  python -m venv .venv'
    Write-Host '  .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
    exit 1
}
Write-Host "Python: $pythonExe"
if ($Check) {
    Write-Host 'Dependencies OK. Run CHAY_UNG_DUNG.bat to open the application.'
    exit 0
}

$backendUrl = 'http://127.0.0.1:8000'
$backendProcess = $null
$oldApiUrl = $env:ANOMALY_API_URL
$exitCode = 1
$frontendPrivateEnvironment = @{}

function Test-Backend {
    try {
        $health = Invoke-RestMethod "$backendUrl/health" -TimeoutSec 2
        $schema = Invoke-RestMethod "$backendUrl/openapi.json" -TimeoutSec 2
        # Windows PowerShell 5 may decode the title's UTF-8 separator differently.
        return ($health.status -eq 'ok' `
            -and $schema.info.title -like 'ANOMALY LAB*DBMS Monitoring API' `
            -and '/detect' -in $schema.paths.PSObject.Properties.Name `
            -and '/monitor/health' -in $schema.paths.PSObject.Properties.Name `
            -and '/monitor/catalog' -in $schema.paths.PSObject.Properties.Name `
            -and '/monitor/faults/live' -in $schema.paths.PSObject.Properties.Name `
            -and '/monitor/demo/alert' -in $schema.paths.PSObject.Properties.Name `
            -and '/monitor/assistant/chat' -in $schema.paths.PSObject.Properties.Name)
    } catch { return $false }
}

function Find-FreePort([int]$firstPort) {
    for ($port = $firstPort; $port -lt ($firstPort + 10); $port++) {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
        try {
            $listener.Server.ExclusiveAddressUse = $true
            $listener.Start()
            return $port
        } catch {
            # A port can be unavailable even when Windows does not list a listener.
        } finally { $listener.Stop() }
    }
    throw "No free local port found from $firstPort to $($firstPort + 9)."
}

Push-Location $projectRoot
try {
    $frontendPort = Find-FreePort 8501
    $frontendUrl = "http://127.0.0.1:$frontendPort"
    # Reuse the matching API even when an older service occupies port 8000.
    # Starting another monitoring worker against the same SQLite store would
    # create independent replay controllers, so prefer the running current API.
    $backendReady = $false
    foreach ($candidatePort in 8000..8009) {
        $backendUrl = "http://127.0.0.1:$candidatePort"
        if (Test-Backend) {
            $backendReady = $true
            break
        }
    }
    if ($backendReady) {
        Write-Host "Using the existing ANOMALY LAB backend at $backendUrl."
    } else {
        $backendPort = Find-FreePort 8000
        $backendUrl = "http://127.0.0.1:$backendPort"
        if ($backendPort -ne 8000) {
            Write-Host "Port 8000 is unavailable; using backend port $backendPort."
        }
        $logDirectory = Join-Path $projectRoot '.runtime'
        New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
        $backendProcess = Start-Process -FilePath $pythonExe `
            -ArgumentList @('-m', 'uvicorn', 'backend.api:app', '--host', '127.0.0.1', '--port', $backendPort) `
            -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $logDirectory 'backend.out.log') `
            -RedirectStandardError (Join-Path $logDirectory 'backend.err.log')
        $ready = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            if ($backendProcess.HasExited) { break }
            if (Test-Backend) { $ready = $true; break }
            Start-Sleep -Milliseconds 250
        }
        if (-not $ready) {
            throw "Backend failed to start. See $logDirectory\backend.err.log"
        }
    }
    $env:ANOMALY_API_URL = $backendUrl
    Write-Host "Application: $frontendUrl"
    Write-Host "API:         $backendUrl/docs"
    Write-Host 'Keep this window open. Press Ctrl+C to stop the application.'
    # AI/SMTP credentials belong to the backend, never its frontend child.
    foreach ($entry in (Get-ChildItem Env: | Where-Object {
        $_.Name -like 'OPENAI_*' -or $_.Name -like 'SMTP_*' -or $_.Name -like 'ALERT_EMAIL_*' `
        -or $_.Name -in @('ANOMALY_AI_ENABLED', 'ANOMALY_EMAIL_ENABLED')
    })) {
        $frontendPrivateEnvironment[$entry.Name] = $entry.Value
        [System.Environment]::SetEnvironmentVariable($entry.Name, $null, 'Process')
    }
    $headless = if ($NoBrowser) { 'true' } else { 'false' }
    & $pythonExe -m streamlit run (Join-Path $projectRoot 'frontend\app.py') `
        --server.address 127.0.0.1 --server.port $frontendPort --server.headless $headless `
        --server.runOnSave true `
        --browser.gatherUsageStats false
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    # Only stop the backend created by this launcher, never an existing service.
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
    }
    $env:ANOMALY_API_URL = $oldApiUrl
    foreach ($name in $frontendPrivateEnvironment.Keys) {
        [System.Environment]::SetEnvironmentVariable($name, $frontendPrivateEnvironment[$name], 'Process')
    }
    Pop-Location
}
exit $exitCode
