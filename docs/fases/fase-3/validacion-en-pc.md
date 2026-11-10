# Validación de la Fase 3 en tu PC (Windows 11)

Lo que la nube no pudo verificar: la separación real con Demucs (pesos y PyTorch bloqueados por el proxy de la nube) y todo lo que depende de tus oídos. Los E2E con audio sintético ya pasaron en Linux sin Docker (`scripts/e2e-nativo.sh`); acá se confirma con el hardware y los archivos reales.

## 1. Preparar

Desde la raíz del repo, en PowerShell:

```powershell
git pull
.\scripts\install.ps1                  # instala worker[...,separation] (Demucs, PyTorch) y baja los pesos de htdemucs_6s (~55 MB)
docker compose up -d --build          # API + Postgres + UI con las migraciones nuevas
.\worker\.venv\Scripts\python -m guitarra_worker   # el worker, en otra ventana
```

Si `install.ps1` avisa que no pudo bajar los pesos, repetilo: es idempotente. Los pesos quedan en `GUITAR_DEMUCS_MODEL_DIR` (por defecto `%USERPROFILE%\GuitarApp\models\demucs`).

## 2. Separación real

1. Elegí una canción ya analizada y reanalizala (todavía no hay botón en la UI):

   ```powershell
   $h = @{ Authorization = "Bearer $((Get-Content .env | Select-String '^GUITAR_API_TOKEN=').ToString().Split('=')[1])" }
   Invoke-RestMethod -Method Post -Headers $h http://localhost:8000/api/v1/songs/<ID>/reanalyze
   ```

   O pegá un link nuevo en Explorar: al terminar el análisis se encola la separación sola.
2. Abrí la canción (`/explorar/canciones/<ID>`). En "Acompañamiento", "Sin guitarra" aparece deshabilitada con el motivo **separando…** mientras corre.
3. **Anotá cuánto tarda** la separación en tu CPU (de que el worker toma el trabajo hasta que la opción se habilita; el log está en `%USERPROFILE%\GuitarApp\logs\worker.log`). Anotá también la duración de la canción.
4. Cuando termine, recargá: "Sin guitarra" debe quedar habilitada (con la marca "experimental").

## 3. Qué escuchar

- **Original a 50 %:** el tono no cambia (suena igual de agudo, solo más lento). Probá también 75 %.
- **Loop de sección:** activá "Repetir sección" y dejá que pase el fin varias veces. El salto de vuelta al inicio no debe tener clic ni cortes notorios.
- **Backing generado** (batería + bajo + acordes): timbres aceptables, volumen parejo y no saturado, que siga los cambios de acorde de la canción. El resaltado de sección y acorde, y el mástil y la tab de la tarjeta de práctica, tienen que moverse con lo que suena.
- **Metrónomo / batería:** clic y batería en tempo; cambiá la velocidad y comprobá que el BPM mostrado coincide con lo que oís.
- **Sin guitarra:** la guitarra se atenúa lo suficiente para tocar encima, y el resto (voz, bajo, batería) no suena roto ni con artefactos molestos. Es experimental: anotá en qué géneros anduvo mejor o peor.

## 4. E2E en tu PC

```powershell
.\scripts\e2e.ps1
```

Levanta un compose aparte, corre los tres recorridos (Fase 1, 2 y 3) y deja capturas en `docs/fases/fase-N/capturas/`. Esperado: 19 tests verdes.

## 5. Qué reportar

- Tiempo de separación en CPU (y duración de la canción).
- Si hubo clic o salto audible en el loop, o cambio de tono a 50 %.
- Calidad de "sin guitarra" (1 a 5, y el tipo de canción) y del backing generado (timbres, volumen).
- Cualquier error del worker (`worker.log`) o del navegador (consola, el aviso de audio bloqueado).
- Si el resaltado de acordes se nota adelantado o atrasado respecto del audio original.
