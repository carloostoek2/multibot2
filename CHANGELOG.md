multibot2 Changelog

Este documento registra cómo ha ido evolucionando el bot y qué problema intentamos resolver con cada cambio.

La idea no es listar cada modificación del código, sino dejar constancia de las decisiones detrás de cada cambio. Las entradas van de la más reciente a la más antigua.

---


Clonar voz usa Seed-VC propio, lo arranca bajo demanda y cae a FreeVC si no está — 2026-10-26

FreeVC en Replicate tarda de 3 a 5 minutos por nota. Ahora el bot puede usar un servidor Seed-VC propio por HTTP (por ejemplo, detrás de un túnel de Colab), que debería tardar menos de un minuto, y Replicate queda como respaldo.

- **`VOICE_CLONE_BACKEND`:** `seedvc`, `replicate` o `auto` (por defecto). En `auto` se usa Seed-VC si `GET /health` responde `ok` con el modelo cargado y, si falla la conversión, se cae a FreeVC en Replicate cuando hay token. Con `seedvc` explícito no hay respaldo: el error llega al usuario.
- **Conexión:** la URL y la clave se leen de archivos en cada llamada (`SEEDVC_URL_FILE` y `SEEDVC_API_KEY_FILE`; por defecto `/home/ubuntu/seedvc-colab/url.txt` y `/home/ubuntu/seedvc-colab/api_key`). URL vacía = Seed-VC apagado. La conversión es `POST {URL}/convert` con la nota y la voz de referencia y la cabecera `X-API-Key`, con plazo de 120 s.
- **`REPLICATE_API_TOKEN` solo se exige si se usa Replicate.** El mensaje de espera depende del backend: «menos de un minuto» con Seed-VC, «3–5 minutos» con Replicate.
- **Arranque bajo demanda:** si Seed-VC no está sano, el bot toca `start_request` (`SEEDVC_START_REQUEST_FILE`) para que el daemon `seedvc-ondemand.service` lo levante, muestra «🔌 Arrancando el motor de voz (~2 min)…» y consulta `state` (`SEEDVC_STATE_FILE`: `down`, `starting`, `up`, `stopping` o `cooldown`) y `/health` cada `SEEDVC_POLL_INTERVAL` s (5) hasta `SEEDVC_START_WAIT` s (150). En `auto` con token, `cooldown` o `stopping` (o `down` pasados `SEEDVC_DOWN_GRACE` s, 15) van directo a Replicate, y si se agota la espera también; el arranque sigue en segundo plano. La espera no bloquea el event loop.
- `httpx` entra en `requirements.txt`, y queda propuesto (no instalado) `deploy/multibot2-local-api.service.proposed`, un unit de la Local Bot API que lee `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` de un `EnvironmentFile` para que no queden en la línea de comandos.
- Commits directos [`303475b`](https://github.com/carloostoek2/multibot2/commit/303475be3c885338db646dad3cf3cfce444408ef), [`17958c5`](https://github.com/carloostoek2/multibot2/commit/17958c5f131941e203991dc7aedd10ba5cab2a2c) (corrige la concatenación del mensaje de espera) y [`b68dd48`](https://github.com/carloostoek2/multibot2/commit/b68dd48a07c9e2ac5835b2942fa58da593c30325).

---


Las actualizaciones se procesan en paralelo y las descargas de Instagram van en fila — 2026-10-19

Una descarga larga (un mensaje con URL o un botón de descarga) bloqueaba el resto de las actualizaciones del bot.

- **Procesamiento concurrente** (`PerUserOrderedUpdateProcessor`, hasta 32 a la vez): callbacks (botones, incluidas las capturas), mensajes con URL y `/download` / `/downloads` corren en paralelo. El resto de los mensajes conserva el orden de llegada por usuario, para que las sesiones de unir, álbum y agrupar imágenes sigan funcionando.
- **Instagram de a una descarga a la vez para todo el bot:** una fila FIFO que se puede cancelar. Cada descarga la ocupa durante la espera en fila, el delay entre descargas, la descarga y la marca de terminado. Mientras espera, el usuario ve «En cola: hay otra descarga de Instagram en curso. Esperando tu turno... (puedes seguir usando el bot)».
- Cancelar funciona mientras se espera en la fila y durante el delay. Las capturas de pantalla no quedan bloqueadas por la fila.
- Commit directo [`81ddf11`](https://github.com/carloostoek2/multibot2/commit/81ddf11f67bf049cfc585ff29d17a6e3f39763c0).

---


Cortar video y audio acepta minutos:segundos — 2026-10-07

Los puntos de corte se leían con `float(message.text)`, así que para pedir el tramo de 5m28s había que calcular 328 a mano.

- Se aceptan segundos (`30`, `30.5`) o `M:SS` / `M:SS.d` (`1:24`, `2:34.5`). El bot repite los tiempos en el formato en que se escribieron.
- El parser vive en `bot/time_parser.py` (`parse_time_value` y `format_time`). Las capturas con tiempos manuales usan el mismo parser, así que también aceptan décimas de segundo.
- Commit directo [`5b3851f`](https://github.com/carloostoek2/multibot2/commit/5b3851f5d964b98883d3b7788b1b228c4adbbb39).

---


Archivos de trabajo en `TEMP_DIR` y chequeo de disco realista para lotes de imágenes; scripts de EC2 — 2026-10-02

En el host EC2, `/tmp` es un tmpfs chico (~3.8 GB) y `tempfile` de Python no lee `TEMP_DIR`, así que los archivos de trabajo caían ahí. Además, el chequeo previo de disco de álbumes y lotes reservaba por imagen `max_incoming_file_size_mb` (2000 MB en modo Local Bot API): un álbum de 5 fotos pedía 30 GB y fallaba con decenas de GB libres.

- Los directorios temporales y `check_disk_space` usan `TEMP_DIR` si está definido; si no, el directorio temporal del sistema.
- El chequeo de álbum, mejorar y ruido reserva 100 MB por imagen (`estimate_image_batch_space`, `IMAGE_BATCH_PER_FILE_MB`).
- Scripts de operación en `scripts/`: `run-local-bot-api.sh` (levanta la Local Bot API en `127.0.0.1:8081` con `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` del `.env`), `ec2-cutover-start.sh` (solo después de detener el bot en Railway: habilita y arranca `multibot2-local-api` y `multibot2-bot`) y `ec2-rollback-stop.sh` (los detiene para volver a Railway).
- Commits directos [`4586162`](https://github.com/carloostoek2/multibot2/commit/458616203c73a3a4c536225ea2b8f2ba8116a612) y [`f40536e`](https://github.com/carloostoek2/multibot2/commit/f40536eb4bfb527023b67ac174df9e1cfb989df5).

---


La voz clonada llega como nota de voz, y el plazo ya no corta un clon que terminó bien — 2026-09-23

FreeVC suele tardar de 2 a 4 minutos o más. En Railway, `VOICE_CLONE_TIMEOUT=180` cancelaba el handler mientras Replicate seguía corriendo: el usuario veía el error de tiempo y el resultado nunca se enviaba.

- **Piso de 300 s:** el plazo efectivo es `max(VOICE_CLONE_TIMEOUT, 300)`, con un warning si el valor configurado es menor. El mensaje de espera dice «Esto puede tardar 3–5 minutos. No canceles.» y el de tiempo agotado sugiere una nota más corta o reintentar.
- **El envío se reintenta** si Telegram falla.
- **Ecualización y nota de voz:** el resultado pasa por un lowshelf +2 dB a 150 Hz y un highshelf −2 dB a 4 kHz (medios planos), se convierte a OGG Opus mono 48 kHz y se envía con `reply_voice`. Si la ecualización o la conversión fallan, se registra un warning y se manda el MP3 como antes.
- Commits directos [`160be17`](https://github.com/carloostoek2/multibot2/commit/160be17a173f2a12ebec9012bcc811bd04ab1390) y [`bcb66f3`](https://github.com/carloostoek2/multibot2/commit/bcb66f384fdb9cdbc95182f22600c1fc384505f5).

---


Pipeline automático para álbumes de imágenes, con interruptor en /config que sobrevive reinicios — 2026-09-30

Los álbumes de fotos tienen ahora un pipeline de un solo paso, y cada usuario decide en `/config` si corre solo al recibir el álbum. La preferencia se guarda en disco, así que sobrevive a los reinicios del bot.

- **Qué hace:** Naturalizar (**Sutil**, ruido 2) → Mejorar (**Equilibrado**) y manda solo el álbum final, sin álbumes intermedios. Aplica a álbumes de 2 a 10 fotos; no a fotos sueltas ni a videos.
- **Automático encendido:** al recibir el álbum (después del debounce) el pipeline corre directo, sin menú.
- **Automático apagado (por defecto):** sale el menú normal de álbum con un botón más, `⚡ Pipeline (Naturalizar + Mejorar)`.
- **La preferencia se guarda en disco** (`bot/user_settings.py`): `data/user_settings/{user_id}.json`, o `$USER_SETTINGS_DIR/{user_id}.json` si la variable está definida. La clave es `album_auto_pipeline` (apagada si no existe) y se escribe de forma atómica. `user_data` de PTB solo sirve de caché en memoria.
- **Railway:** montar un volumen y definir `USER_SETTINGS_DIR=/data/user_settings` para que la preferencia sobreviva a los redeploys (documentado en `.env.example`).
- Los `file_id` del álbum final quedan como resultado vigente del menú, igual que en el cambio de encadenado del 2026-09-30.
- PR [#5](https://github.com/carloostoek2/multibot2/pull/5).

---


Las acciones de imagen encadenadas trabajan sobre el último resultado — 2026-09-30

Después de una acción de imagen, «¿Quieres hacer algo más…?» → «Volver al menú» aplicaba la siguiente acción otra vez sobre la imagen **original**, no sobre el resultado. Los handlers nunca actualizaban el `file_id` del menú, y como `TempManager` borra los archivos locales, el `file_id` de Telegram es lo único que dura.

- Después de cada acción que modifica la imagen (comprimir, convertir, redimensionar, mejorar, ruido), los `file_id` de lo que se mandó pasan a ser los del menú (`image_menu_file_id(s)`). Es el mismo patrón que ya usaba el menú de video.
- Los originales se guardan una sola vez en `image_menu_original_file_ids`.
- En lotes, `_send_images_in_albums` devuelve los `file_id` del álbum en el orden de envío, y mejorar y ruido en lote los usan.
- **Fuera de alcance:** el «algo más» de audio y el encadenado de las sesiones de agrupar imágenes.
- PR [#4](https://github.com/carloostoek2/multibot2/pull/4).

---


Clonar voz pasa a voz a voz con FreeVC — 2026-09-17

El primer clonador transcribía la nota con Whisper y la volvía a decir con OpenVoice. Ahora la conversión es directa de voz a voz con FreeVC 24 kHz en Replicate, que conserva el ritmo de la nota original.

- Modelo fijado por versión: `jagilley/free-vc:e4f2ff8a1d3779a2411e119dfad7d451d5f3314a8cd7003a88f88ce4c3b18d95`, con `model_type` = `FreeVC (24kHz)`.
- La nota de Telegram (OGG) se convierte a WAV con ffmpeg antes de enviarla.
- Se quitó todo el camino de Whisper y OpenVoice.
- `VOICE_CLONE_TIMEOUT` sube de 180 a 300 s por defecto: FreeVC puede tardar unos minutos.
- `/voz_ref` y el menú de nota de voz no cambian.
- PR [#3](https://github.com/carloostoek2/multibot2/pull/3).

---


Clonar voz fallaba con 404: modelos de Replicate fijados por versión — 2026-09-17

«Clonar voz» respondía «No pude transcribir la nota de voz.». En los logs de Railway, `replicate.run("openai/whisper")` daba 404: los modelos sin versión fijada ya no se resolvían en Replicate.

- Whisper y OpenVoice quedan fijados por hash de versión, con una prueba que exige que sigan fijados.
- Este camino quedó reemplazado ese mismo día por FreeVC (PR #3).
- PR [#2](https://github.com/carloostoek2/multibot2/pull/2).

---


Las notas de voz muestran un menú, y llega la clonación de voz — 2026-09-16

Antes, cada nota de voz pasaba sola por el pipeline de podcast. Ahora el bot pregunta qué hacer con ella.

- **Menú de nota de voz:** 🎧 **Convertir y normalizar** (el mismo pipeline de antes: OGA → MP3, normalizar a −16 LUFS, bass boost 4), 🗣️ **Clonar voz** y ❌ **Cancelar**.
- **`/voz_ref`:** respondiendo a un audio o nota de voz (o adjuntándolo) se guarda la voz de referencia del usuario en `data/voice_refs/{user_id}/reference.mp3` (fuera de git). `VOICE_REFS_DIR` permite ponerla en un volumen; si no persiste, hay que repetir `/voz_ref` tras cada redeploy.
- **Clonación** con Replicate: en esta versión, Whisper para transcribir y OpenVoice v2 (`chenxwh/openvoice`, español nativo) para decir el texto con la voz de referencia. Reemplazado después por FreeVC (PR #3).
- **Configuración:** `REPLICATE_API_TOKEN` es opcional. El bot arranca sin él y «Clonar voz» responde con un error claro en español. `VOICE_CLONE_TIMEOUT` (180 s en esta versión).
- La lógica pesada vive en `bot/voice_clone.py`, fuera de `handlers.py`.
- PR [#1](https://github.com/carloostoek2/multibot2/pull/1).
