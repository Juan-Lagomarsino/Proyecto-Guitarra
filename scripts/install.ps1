# Prepara el worker de análisis (y, más adelante, el Rig) en Windows. Idempotente.
# 'Continue' a propósito (ver el comentario en e2e.ps1): los fallos se detectan por $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$workerDir = Join-Path $root 'worker'
$venvPython = Join-Path $workerDir '.venv\Scripts\python.exe'
$envFile = Join-Path $root '.env'
$cacheDir = if ($env:GUITAR_CACHE_DIR) { $env:GUITAR_CACHE_DIR } else { Join-Path $HOME 'GuitarApp\cache' }
$logsDir = Join-Path (Split-Path -Parent $cacheDir) 'logs'

function Install-WorkerVenv {
    if (-not (Test-Path $venvPython)) {
        Write-Host 'Creando worker\.venv con Python 3.12 ...'
        & py -3.12 -m venv (Join-Path $workerDir '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el venv (¿está instalado Python 3.12 y el lanzador py?)' }
    }
    Write-Host 'Instalando worker[dev] en modo editable ...'
    & $venvPython -m pip install --quiet --disable-pip-version-check -e "$workerDir[dev]"
    if ($LASTEXITCODE -ne 0) { throw 'pip install del worker falló' }
}

function Update-SessionPath {
    # winget actualiza el PATH del registro, pero no el de esta sesión: lo releemos.
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = $machine + ';' + $user
}

function Test-FfmpegInstalled {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { return $true }
    & winget list --id Gyan.FFmpeg -e *> $null
    return ($LASTEXITCODE -eq 0)
}

function Install-Ffmpeg {
    Update-SessionPath
    if (Test-FfmpegInstalled) {
        Write-Host 'ffmpeg ya está instalado.'
        return
    }
    Write-Host 'Instalando ffmpeg con winget ...'
    & winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    # Códigos de winget que no son fallas: 0 (instalado), -1978335189 (0x8A15002B, ya instalado
    # y sin actualización disponible) y -1978335212 (0x8A150014, no hay nada que instalar).
    $okCodes = @(0, -1978335189, -1978335212)
    if ($okCodes -notcontains $LASTEXITCODE) { throw "winget no pudo instalar ffmpeg ($LASTEXITCODE)" }
    Update-SessionPath
}

function Update-YtDlp {
    # Lo usa T06 cuando yt-dlp entre como dependencia: YouTube cambia seguido y hay que actualizarlo.
    $ytDlp = Join-Path $workerDir '.venv\Scripts\yt-dlp.exe'
    if (-not (Test-Path $ytDlp)) { return }
    & $ytDlp -U
    if ($LASTEXITCODE -ne 0) { Write-Warning 'yt-dlp -U falló (no es bloqueante).' }
}

function New-WorkerFolders {
    foreach ($dir in @($cacheDir, $logsDir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Host "Carpeta lista: $dir"
    }
}

function Test-WorkerToken {
    $hasToken = $env:GUITAR_WORKER_TOKEN -or
        ((Test-Path $envFile) -and (Select-String -Path $envFile -Pattern '^\s*GUITAR_WORKER_TOKEN\s*=\s*\S' -Quiet))
    if (-not $hasToken) {
        Write-Warning "Falta GUITAR_WORKER_TOKEN en $envFile. El worker no arranca sin él."
    }
}

try {
    Install-WorkerVenv
    Install-Ffmpeg
    Update-YtDlp
    New-WorkerFolders
    Test-WorkerToken
    Write-Host 'Listo.'
    exit 0
} catch {
    Write-Error $_
    exit 1
}
