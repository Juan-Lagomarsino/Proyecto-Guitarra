# Validación de la Fase 5 en tu PC (Windows 11)

Lo que la nube no pudo verificar: la transcripción de riffs sobre **audio real** (basic-pitch sobre la pista de guitarra de Demucs) y qué tan buena sale la tab. Los umbrales de basic-pitch se eligieron con riffs sintéticos (ADR 0017) y hay que reajustarlos con guitarra real. Lo demás (esquema, digitación, editor de tab, aprendizaje, E2E con un resultado grabado) ya pasó en Linux sin Docker.

## 1. Preparar

Desde la raíz del repo, en PowerShell:

```powershell
git pull
.\scripts\install.ps1                  # worker[...,separation,riffs]: Demucs (+ pesos htdemucs_6s) y basic-pitch (onnxruntime, sin TensorFlow)
docker compose up -d --build          # API + Postgres + UI con las migraciones nuevas (0007 y 0008)
.\worker\.venv\Scripts\python -m guitarra_worker   # el worker, en otra ventana
```

`install.ps1` es idempotente. Si avisa que no pudo instalar basic-pitch, repetilo: sin él la etapa de riffs se saltea (el resto de la app sigue igual). Sin Demucs tampoco hay riffs automáticos: salen de la pista `guitar` de la separación.

## 2. Riffs reales

1. Elegí 2 o 3 canciones con un riff de guitarra claro y poco tapado por otros instrumentos, por ejemplo la intro de "Flaca" (Andrés Calamaro), "De música ligera" (Soda Stereo) o "Boys Don't Cry" (The Cure). Si ya las tenés analizadas, reanalizalas (todavía no hay botón en la UI):

   ```powershell
   $h = @{ Authorization = "Bearer $((Get-Content .env | Select-String '^GUITAR_API_TOKEN=').ToString().Split('=')[1])" }
   Invoke-RestMethod -Method Post -Headers $h http://localhost:8000/api/v1/songs/<ID>/reanalyze
   ```

   O pegá el link en Explorar. Al terminar el análisis se encola la separación, y los riffs salen al final de esa etapa. **Anotá cuánto tarda** (separación + transcripción) y la duración de la canción; el log está en `%USERPROFILE%\GuitarApp\logs\worker.log`.
2. Abrí la canción (`/explorar/canciones/<ID>`), elegí **Eléctrica** y recorré las secciones. Solo las secciones candidatas (la intro y las de pocas notas simultáneas) traen riff. Cada riff aparece con su tab y el mástil; las notas de baja confianza se ven con otro color y borde punteado, con la leyenda "poco seguro".
3. **Compará con una tab de referencia** (la de Songsterr, Ultimate Guitar o la del libro del disco) y anotá, por canción: cuántas notas son correctas, cuántas faltan, cuántas sobran (fantasmas) y si las que marcó como dudosas son justo las que fallan. Fijate también si la digitación (cuerda y traste) es una que podrías tocar cómodo.

## 3. Medir con la referencia y reajustar umbrales

Con la pista `guitar` que deja Demucs (la caché del worker, en `%USERPROFILE%\GuitarApp\cache`) y la tab de referencia pasada a tiempos (formatos en `spikes/riffs/README.md`; E2 = 40, A2 = 45, E4 = 64):

```powershell
cd spikes\riffs
.\.venv\Scripts\python medir_audio_real.py C:\ruta\guitar.wav riff.tsv --desde 42.0 --hasta 50.5 --lista
.\.venv\Scripts\python medir_audio_real.py C:\ruta\guitar.wav riff.tsv --barrido
```

(Si no tenés el venv del spike, se arma según ese README.) `--lista` muestra las notas estimadas junto a las de referencia; `--barrido` prueba la grilla de umbrales de basic-pitch.

Anotá:

- F1 (sin offsets; onset ±50 ms, altura exacta) con los umbrales actuales (`onset_threshold=0.7`, `frame_threshold=0.4`, `minimum_note_length=58` ms).
- La combinación de umbrales que dio el mejor F1 en el barrido y cuánto mejora. Si es otra distinta de la actual (el 0.7 está en el borde de la grilla y la guitarra real ataca más suave), se cambia en la configuración del worker, no en el código.
- Si hay muchas notas fantasma en pasajes monofónicos: es el caso que reabre pYIN como filtro (ver ADR 0017, "No se combina con pYIN").

## 4. Corregir y verificar que se aprende

1. En una canción con riff, tocá **Editar tab**, elegí una nota y cambiale la cuerda (misma altura, otra posición) o el traste; guardá. La sección queda con **"Riff editado por vos"**. "Volver a la automática" descarta tu versión (lo aprendido no se borra).
2. Repetí con 3 o 4 notas, idealmente en una canción con capo y en otra sin capo.
3. Mirá lo aprendido:

   ```powershell
   Invoke-RestMethod -Headers $h http://localhost:8000/api/v1/preferences/fingering
   ```

   Tienen que aparecer las alturas que corregiste, con la posición elegida (`cuerda,traste` absolutos, los del mástil) y las zonas de la mano.
4. Analizá una canción **nueva** (otro link) o reanalizá otra con riff: las posiciones que elegiste deberían repetirse para las mismas alturas, aunque esa canción tenga otro capo. Anotá si se nota y si te parece mejor que antes.
5. **Formas de acorde:** en "Editar sección", abrí "Elegir forma del acorde N", elegí otra forma (abierta, cejilla, power chord) y guardá. Después `GET /api/v1/preferences/chord-shapes` tiene que mostrarla. Reanalizá otra canción con ese acorde: la forma elegida figura como "Preferida" en el selector y es la que arma el análisis.

## 5. E2E en tu PC

```powershell
.\scripts\e2e.ps1
```

Levanta un compose aparte, corre los cuatro recorridos (Fases 1, 2, 3 y 5) y deja capturas en `docs/fases/fase-N/capturas/`. Esperado: 24 tests verdes. El de Fase 5 (`zzz-riffs.spec.ts`) usa un resultado de separación simulado (no el worker real) con un riff de baja confianza.

## 6. Qué reportar

- F1 de la transcripción con los umbrales actuales y con los mejores del barrido (por canción), y los umbrales que recomendarías.
- Tiempo de separación + transcripción por canción (y su duración).
- Calidad de la tab contra la referencia (correctas, faltantes, fantasmas) y si la confianza baja marca bien lo dudoso.
- Si lo aprendido (digitación y formas de acorde) se nota en el próximo análisis.
- Cualquier error del worker (`worker.log`), de la API o del navegador (consola).
- Si el editor de tab te resulta cómodo para corregir (en la PC y en el celular, a 375 px).
