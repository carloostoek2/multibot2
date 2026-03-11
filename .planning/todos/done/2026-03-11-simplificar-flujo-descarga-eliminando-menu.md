---
created: 2026-03-11T04:58:12.482Z
title: Simplificar flujo descarga eliminando menú
area: downloader
files:
  - bot/handlers/download.py
---

## Problem

Actualmente cuando el usuario envía una URL, el bot muestra un menú intermedio preguntando qué quiere hacer (descargar video, audio, etc.) antes de iniciar la descarga. Esto añade fricción innecesaria al flujo de usuario.

## Solution

Eliminar el paso del menú intermedio y ejecutar directamente la descarga del contenido (video o foto) cuando se recibe una URL. El bot debe:

1. Detectar automáticamente si es video o foto (especialmente para Instagram)
2. Descargar directamente sin preguntar al usuario
3. Mantener la lógica de post-procesamiento si es necesario

Archivos a modificar:
- `bot/handlers/download.py` - Handlers de descarga y callbacks del menú
