param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8012,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$backendPath = Join-Path $projectRoot 'backend'

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
    throw 'Missing .env. Copy .env.example to .env and set MASTER_KEY first.'
}
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Visit the existing ModelGate API or choose another port."
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & python -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Creating the Python virtual environment failed.' }
}
if (-not $SkipInstall) {
    & $pythonPath -m pip install -r (Join-Path $backendPath 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installing backend dependencies failed.' }
}

Write-Host "ModelGate API: http://127.0.0.1:$Port"
Write-Host 'Start the frontend separately with: cd frontend; npm run dev'
Write-Host 'Use Ctrl+C to stop the API.'
Push-Location $backendPath
try {
    & $pythonPath -m uvicorn app.prod_main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'The ModelGate API stopped with an error.' }
} finally { Pop-Location }
