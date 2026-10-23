# Registra (o actualiza) la tarea programada "Guitarra Worker": arranca el worker al iniciar sesión.
# Sin privilegios elevados, para el usuario actual. Con -Remove la borra. Idempotente.
param([switch]$Remove)

$ErrorActionPreference = 'Continue'
$taskName = 'Guitarra Worker'
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root 'worker\.venv\Scripts\pythonw.exe'

if ($Remove) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Tarea '$taskName' eliminada."
    } else {
        Write-Host "La tarea '$taskName' no existe."
    }
    exit 0
}

if (-not (Test-Path $pythonw)) {
    Write-Error "No existe $pythonw. Corré primero .\scripts\install.ps1"
    exit 1
}

$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $pythonw -Argument '-m guitarra_worker' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
if (-not $?) { Write-Error 'No se pudo registrar la tarea.'; exit 1 }
Write-Host "Tarea '$taskName' registrada: corre al iniciar sesión ($user)."
exit 0
