---
created: 2026-03-11T04:59:50.915Z
title: Incluir caption original en descargas Instagram
area: downloader
files:
  - bot/handlers/download.py
  - bot/services/platform/instagram.py
---

## Problem

Cuando se descargan reels o fotos de Instagram, el bot no incluye el caption original del post en el mensaje que se envía a Telegram. Esto hace que se pierda el contexto del contenido descargado.

## Solution

Extraer el caption del post de Instagram y enviarlo como caption del archivo en Telegram:

1. Modificar `InstagramDownloader` para extraer el caption del post
2. Propagar el caption a través del flujo de descarga
3. Usar el caption original al enviar el archivo a Telegram con `send_video`/`send_photo`
4. Asegurar que el caption no exceda el límite de caracteres de Telegram (1024 caracteres)
5. Opcional: incluir el username del autor en el caption

Archivos a modificar:
- `bot/services/platform/instagram.py` - Extraer caption del metadata
- `bot/handlers/download.py` - Incluir caption al enviar el archivo
