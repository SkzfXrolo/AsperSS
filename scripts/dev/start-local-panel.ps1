# Argus — panel local (réplica de asperss.onrender.com)
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Web  = Join-Path $Root "web_app"
$EnvFile = Join-Path $Web ".env.local"

if (-not (Test-Path $EnvFile)) {
    $Example = Join-Path $Web ".env.local.example"
    if (Test-Path $Example) {
        Copy-Item $Example $EnvFile
        Write-Host "Creado $EnvFile — edita DATABASE_URL (Render) y vuelve a ejecutar." -ForegroundColor Yellow
    } else {
        Write-Host "Falta .env.local — ver docs/local-dev-render.md" -ForegroundColor Red
    }
    exit 1
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Push-Location $Root
    python -m venv .venv
    & .\.venv\Scripts\pip install -q -r web_app\requirements.txt
    & .\.venv\Scripts\pip install -q python-dotenv
    Pop-Location
}

Push-Location $Web
Write-Host "Panel local: http://127.0.0.1:8080/panel" -ForegroundColor Cyan
& $VenvPython app.py
Pop-Location
