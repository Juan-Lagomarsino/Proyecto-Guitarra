# Corre las pruebas E2E contra un compose aislado (proyecto "guitarra-e2e"):
# volumen, puertos y token propios. No toca los datos reales del compose por defecto.
# 'Continue' a propósito: en Windows PowerShell 5.1, con 'Stop', el progreso que docker escribe
# en stderr se vuelve error terminante si se redirige la salida. Los fallos se detectan por $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$project = 'guitarra-e2e'
$envFile = Join-Path $root '.env.e2e'
$compose = @('compose', '-p', $project, '--env-file', $envFile, '-f', (Join-Path $root 'docker-compose.yml'))
$baseUrl = 'http://127.0.0.1:18000'
$exitCode = 1

function Invoke-Compose {
    & docker @compose @args
    if ($LASTEXITCODE -ne 0) { throw "docker compose $args falló ($LASTEXITCODE)" }
}

try {
    Invoke-Compose down -v --remove-orphans
    Invoke-Compose up -d --build

    Write-Host "Esperando $baseUrl/api/v1/health ..."
    $ready = $false
    for ($i = 0; $i -lt 90 -and -not $ready; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "$baseUrl/api/v1/health" -UseBasicParsing -TimeoutSec 3
            $ready = $r.StatusCode -eq 200
        } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw 'La API no respondió /health a tiempo.' }

    Push-Location (Join-Path $root 'e2e')
    try {
        if (-not (Test-Path 'node_modules')) { npm ci; if ($LASTEXITCODE -ne 0) { throw 'npm ci falló' } }
        npx playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar Chromium' }
        $env:E2E_BASE_URL = $baseUrl
        npx playwright test
        $exitCode = $LASTEXITCODE
    } finally { Pop-Location }
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    $exitCode = 1
} finally {
    & docker @compose down -v --remove-orphans
}
exit $exitCode
