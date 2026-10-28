param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8010,
    [switch]$SkipInstall,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'

if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Visit an existing ModelGate instance or use -Port <number>."
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    & python -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Creating the Python virtual environment failed.' }
}

if (-not $SkipInstall) {
    & $pythonPath -m pip install -r (Join-Path $backendPath 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installing backend dependencies failed.' }

    Push-Location $frontendPath
    try {
        if (Test-Path -LiteralPath 'package-lock.json') { & npm.cmd ci }
        else { & npm.cmd install }
        if ($LASTEXITCODE -ne 0) { throw 'Installing frontend dependencies failed.' }
    } finally { Pop-Location }
}

if (-not $SkipBuild) {
    Push-Location $frontendPath
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Building the frontend failed.' }
    } finally { Pop-Location }
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'dist/index.html'))) {
    throw 'The frontend build is missing. Run this script without -SkipBuild.'
}

Write-Host "ModelGate Demo: http://127.0.0.1:$Port"
Write-Host 'Use Ctrl+C to stop the server. This is a local demonstration with simulated providers.'
Push-Location $backendPath
try {
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'The demo server stopped with an error.' }
} finally { Pop-Location }
