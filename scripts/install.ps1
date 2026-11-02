# Prepara el worker de análisis (y, más adelante, el Rig) en Windows. Idempotente.
# 'Continue' a propósito (ver el comentario en e2e.ps1): los fallos se detectan por $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$workerDir = Join-Path $root 'worker'
$venvPython = Join-Path $workerDir '.venv\Scripts\python.exe'
$envFile = Join-Path $root '.env'
$cacheDir = if ($env:GUITAR_CACHE_DIR) { $env:GUITAR_CACHE_DIR } else { Join-Path $HOME 'GuitarApp\cache' }
$logsDir = Join-Path (Split-Path -Parent $cacheDir) 'logs'

function Install-TorchCpu {
    # torch CPU desde el índice de PyTorch (el de PyPI trae CUDA, GBs de más). Solo si falta.
    & $venvPython -c 'import torch' 2>$null
    if ($LASTEXITCODE -eq 0) { return }
    Write-Host 'Instalando torch (CPU) ...'
    & $venvPython -m pip install --quiet --disable-pip-version-check torch==2.14.1 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'pip install de torch falló' }
}

function Install-BeatThisWeights {
    # Pesos de beat_this: host oficial con reintentos y, si está caído, el espejo safetensors.
    # La lógica vive en guitarra_worker.adapters.beat_this_weights (testeada); ruta por
    # GUITAR_BEAT_THIS_CHECKPOINT, por defecto GuitarApp\models.
    Write-Host 'Preparando los pesos de beat_this ...'
    & $venvPython -m guitarra_worker.adapters.beat_this_weights
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron bajar los pesos de beat_this (ni del host oficial ni del espejo)' }
}

function Install-DemucsWeights {
    # Pesos de htdemucs_6s (separación de pistas, ADR 0015) con reintentos, en
    # GUITAR_DEMUCS_MODEL_DIR (por defecto GuitarApp\models\demucs). Idempotente. Si falla no
    # bloquea: el worker sigue y los trabajos de separación fallan diciendo cómo instalarlo.
    Write-Host 'Preparando los pesos de Demucs (htdemucs_6s, ~55 MB) ...'
    & $venvPython -m guitarra_worker.adapters.demucs
    if ($LASTEXITCODE -ne 0) { Write-Warning 'No se pudieron bajar los pesos de Demucs; reintentá scripts\install.ps1. La separación (acompañamiento sin guitarra) no va a andar hasta entonces.' }
}

function Install-WorkerVenv {
    if (-not (Test-Path $venvPython)) {
        Write-Host 'Creando worker\.venv con Python 3.12 ...'
        & py -3.12 -m venv (Join-Path $workerDir '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el venv (¿está instalado Python 3.12 y el lanzador py?)' }
    }
    Install-TorchCpu
    Write-Host 'Instalando worker[dev,analysis,separation] en modo editable ...'
    $coreDir = Join-Path (Split-Path -Parent $workerDir) 'core'
    & $venvPython -m pip install --quiet --disable-pip-version-check -e $coreDir
    if ($LASTEXITCODE -ne 0) { throw 'pip install de core falló' }
    & $venvPython -m pip install --quiet --disable-pip-version-check -e "$workerDir[dev,analysis,separation]"
    if ($LASTEXITCODE -ne 0) { throw 'pip install del worker falló' }
}

function Install-Riffs {
    # Transcripcion de riffs (ADR 0017): basic-pitch 0.4.0 SIN dependencias (declara tensorflow, que
    # no existe para Python 3.12) y sus dependencias livianas (extra riffs: onnxruntime, etc.).
    # Idempotente. Si falla no bloquea: el worker sigue y la etapa de riffs se saltea.
    $workerDir = Join-Path $root 'worker'
    & $venvPython -m pip install --quiet --disable-pip-version-check -e "$workerDir[riffs]"
    if ($LASTEXITCODE -eq 0) {
        & $venvPython -m pip install --quiet --disable-pip-version-check basic-pitch==0.4.0 --no-deps
    }
    if ($LASTEXITCODE -ne 0) { Write-Warning 'No se pudo instalar basic-pitch; reintenta scripts\install.ps1. Los riffs se saltean hasta entonces.' }
}

function Install-Btc {
    # BTC (acordes, MIT) no es un paquete: se clona en un commit fijo. Los parches de compatibilidad
    # (yaml.safe_load, np.float) los aplica el adaptador al cargarlo, así el clon queda limpio.
    $btcCommit = '2682317be668032e6e4b269ded36adaa2ad57df0'
    $btcDir = if ($env:GUITAR_BTC_DIR) { $env:GUITAR_BTC_DIR } else { Join-Path $cacheDir 'btc' }
    if (-not (Test-Path (Join-Path $btcDir '.git'))) {
        Write-Host "Clonando BTC en $btcDir ..."
        & git clone --quiet https://github.com/jayg996/BTC-ISMIR19.git $btcDir
        if ($LASTEXITCODE -ne 0) { throw 'git clone de BTC falló' }
    }
    $head = (& git -C $btcDir rev-parse HEAD).Trim()
    if ($head -ne $btcCommit) {
        Write-Host "Fijando BTC en $btcCommit ..."
        & git -C $btcDir fetch --quiet origin $btcCommit
        & git -C $btcDir checkout --quiet $btcCommit
        if ($LASTEXITCODE -ne 0) { throw "No se pudo fijar BTC en $btcCommit" }
    }
    $weights = Join-Path $btcDir 'test\btc_model_large_voca.pt'
    if (-not (Test-Path $weights)) { throw "BTC no trae los pesos esperados: $weights" }
    Write-Host "BTC listo en $btcDir"
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
    # YouTube cambia seguido: yt-dlp (instalado como librería en el venv) se actualiza en cada corrida.
    $python = Join-Path $workerDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { return }
    & $python -m pip install -U yt-dlp
    if ($LASTEXITCODE -ne 0) { Write-Warning 'pip install -U yt-dlp falló (no es bloqueante).' }
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
    Install-Riffs
    Install-Btc
    Install-Ffmpeg
    Update-YtDlp
    New-WorkerFolders
    Install-BeatThisWeights
    Install-DemucsWeights
    Test-WorkerToken
    Write-Host 'Listo.'
    exit 0
} catch {
    Write-Error $_
    exit 1
}
