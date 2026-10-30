multibot2 Changelog

Este documento registra cómo ha ido evolucionando el bot y qué problema intentamos resolver con cada cambio.

La idea no es listar cada modificación del código, sino dejar constancia de las decisiones detrás de cada cambio. Las entradas van de la más reciente a la más antigua.

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
