# Video Note Bot

## What This Is

Un bot de Telegram que recibe videos y archivos de audio enviados por usuarios y los procesa automáticamente. Convierte videos a notas de video circulares, y ofrece una "navaja suiza" de procesamiento de audio: conversión de formatos, split/join, efectos profesionales (denoise, compresión, normalización), ecualización, y menús inline contextuales que eliminan la necesidad de aprender comandos.

## Current State

**v3.0 IN PROGRESS** — Downloader milestone

Bot completo con procesamiento automático de videos a video notes y "navaja suiza" de audio. Ahora agregando capacidad de descarga desde YouTube, Instagram, TikTok, Twitter/X, Facebook y URLs genéricas.

- v1.0: 11 planes completados (2 fases) — SHIPPED 2026-02-14
- v2.0: 20 planes completados (6 fases) — SHIPPED 2026-02-21
- v3.0: 4 fases planificadas (54 requisitos) — IN PROGRESS
- ~9,254 líneas de Python
- 115+ commits
- Timeline: Dec 2025 → Feb 2026 (~68 días)

## Core Value

El usuario envía un video, archivo de audio, o URL de video y recibe el resultado procesado inmediatamente, sin fricción. Para usuarios avanzados, comandos poderosos. Para todos, menús inline contextuales que eliminan la curva de aprendizaje.

## Requirements

### Validated (v1.0)

- ✓ CORE-01 — Bot detecta automáticamente cuando un usuario envía un video
- ✓ CORE-02 — Bot descarga el video recibido para procesamiento
- ✓ CORE-03 — Bot convierte el video a formato 1:1 (cuadrado) centrado
- ✓ CORE-04 — Bot envía el resultado como nota de video de Telegram
- ✓ CORE-05 — Proceso completo sin necesidad de comandos del usuario
- ✓ PROC-01 — Videos se recortan a formato circular usando ffmpeg
- ✓ PROC-02 — Duración máxima respetada (60 segundos, truncar si es mayor)
- ✓ PROC-03 — Resolución de salida apropiada para video notes (max 640x640)
- ✓ PROC-04 — Calidad de video razonable manteniendo tamaño de archivo manejable
- ✓ ERR-01 — Notificar al usuario si el video no puede procesarse
- ✓ ERR-02 — Limpiar archivos temporales después de procesamiento
- ✓ ERR-03 — Timeout razonable para evitar bloqueos
- ✓ CONF-01 — Configuración mediante variables de entorno
- ✓ CONF-02 — Logging básico de operaciones

### Validated (v2.0 Navaja Suiza de Audio)

**Voice Notes & Voice Messages:**
- ✓ VN-01 — Convertir MP3 a voice notes de Telegram (OGG Opus)
- ✓ VN-02 — Truncar automáticamente archivos de más de 20 minutos
- ✓ VN-03 — Preservar calidad de audio en conversiones
- ✓ VMP-01 — Detectar automáticamente notas de voz entrantes
- ✓ VMP-02 — Convertir voice messages a MP3 descargable

**Audio Split/Join:**
- ✓ ASJ-01 — Dividir audio en segmentos por duración
- ✓ ASJ-02 — Dividir audio en N segmentos iguales
- ✓ ASJ-03 — Unir múltiples archivos de audio
- ✓ ASJ-04 — Generar archivos numerados secuencialmente
- ✓ ASJ-05 — Aceptar múltiples archivos en secuencia

**Audio Format Conversion:**
- ✓ AFC-01 — Selección de formato de salida vía teclado inline
- ✓ AFC-02 — Soportar MP3, WAV, OGG, AAC, FLAC
- ✓ AFC-03 — Preservar metadatos cuando el formato lo permite

**Audio Enhancement:**
- ✓ AE-01 — Bass boost con intensidad ajustable
- ✓ AE-02 — Treble boost con intensidad ajustable
- ✓ AE-03 — Ecualizador de 3 bandas (bass, mid, treble)
- ✓ AE-04 — Parámetros sin distorsión excesiva

**Audio Effects:**
- ✓ AFX-01 — Reducción de ruido con intensidad ajustable
- ✓ AFX-02 — Compresión de rango dinámico
- ✓ AFX-03 — Normalización EBU R128
- ✓ AFX-04 — Pipeline para combinar efectos

**User Interface:**
- ✓ UI-01 — Menú inline automático para archivos de video
- ✓ UI-02 — Menú inline automático para archivos de audio
- ✓ UI-03 — Menús contextuales sin necesidad de comandos

### Active (v3.0 Downloader)

**Core Download:**
- [ ] DL-01 — Bot can detect and parse URLs from supported platforms
- [ ] DL-02 — Bot validates URL format and accessibility before download
- [ ] DL-03 — Bot extracts media metadata (title, duration, uploader, thumbnail)
- [ ] DL-04 — Download infrastructure supports both video and audio extraction
- [ ] DL-05 — Downloaded files are validated for integrity and format
- [ ] DL-06 — Bot auto-detects URLs in any message (no command required)
- [ ] DL-07 — Generic video URL support (any URL containing video file)

**YouTube:**
- [ ] YT-01 — Download YouTube videos (regular, Shorts)
- [ ] YT-02 — Extract audio-only from YouTube videos
- [ ] YT-03 — Support age-restricted content (if technically possible)
- [ ] YT-04 — Handle playlists (optional, single video default)

**Instagram:**
- [ ] IG-01 — Download Instagram posts (single video)
- [ ] IG-02 — Download Instagram Reels
- [ ] IG-03 — Download Instagram Stories (if accessible)

**TikTok:**
- [ ] TT-01 — Download TikTok videos (no watermark preferred)
- [ ] TT-02 — Handle TikTok slideshows with video conversion

**Twitter/X:**
- [ ] TW-01 — Download Twitter/X video posts
- [ ] TW-02 — Handle multiple video variants (quality selection)

**Facebook:**
- [ ] FB-01 — Download Facebook public videos
- [ ] FB-02 — Handle Facebook Reels

**Generic Video URLs:**
- [ ] GV-01 — Detect direct video file URLs (.mp4, .webm, .mov, etc.)
- [ ] GV-02 — Extract video from HTML pages with video tags
- [ ] GV-03 — Follow redirects to find actual video file
- [ ] GV-04 — Validate content-type before download

**Quality & Format:**
- [ ] QF-01 — Download maximum available quality by default
- [ ] QF-02 — Video format preference: MP4 (H.264) for compatibility
- [ ] QF-03 — Audio format preference: MP3 320k or source quality
- [ ] QF-04 — Automatic format conversion if source incompatible
- [ ] QF-05 — File size limits respected (Telegram bot constraints)

**Download Management:**
- [ ] DM-01 — Unlimited concurrent downloads supported
- [ ] DM-02 — Each download tracked with unique correlation ID
- [ ] DM-03 — Downloads isolated in separate temp directories
- [ ] DM-04 — Failed downloads cleaned up automatically
- [ ] DM-05 — Download queue with fair scheduling

**Progress Tracking:**
- [ ] PT-01 — Real-time percentage progress displayed to user
- [ ] PT-02 — Progress updates sent every 5-10% or 3-5 seconds
- [ ] PT-03 — Progress message includes: percentage, downloaded/total size, speed
- [ ] PT-04 — Progress bar visualization (ASCII or emoji)
- [ ] PT-05 — Final "complete" message with file info

**Download UI:**
- [ ] DUI-01 — `/download <url>` command initiates download
- [ ] DUI-02 — Auto-detect URL in any message and offer download menu
- [ ] DUI-03 — Inline menu for format selection (video/audio) when URL detected
- [ ] DUI-04 — Confirmation prompt before large downloads (>50MB)
- [ ] DUI-05 — Cancel button during active download
- [ ] DUI-06 — Recent downloads list (last 5, ephemeral)

**Error Handling:**
- [ ] EH-01 — Graceful handling of unavailable/private content
- [ ] EH-02 — Clear error messages for unsupported URLs
- [ ] EH-03 — Retry logic for transient network failures
- [ ] EH-04 — Timeout handling for stalled downloads
- [ ] EH-05 — Rate limit detection and backoff for platform restrictions

**Integration:**
- [ ] INT-01 — Downloaded videos can be processed to video notes
- [ ] INT-02 — Downloaded audio can be processed with audio tools
- [ ] INT-03 — Inline menu offers "Download + Convert" flow
- [ ] INT-04 — Download history not persisted (privacy)

### Out of Scope

| Feature | Reason |
|---------|--------|
| Múltiples videos simultáneos | Simplifica MVP, procesamiento uno a la vez |
| Panel web de administración | Overkill para funcionalidad simple |
| Base de datos | No es necesario persistir estado |
| Soporte para otros formatos de salida | Solo video notes, requisito específico |
| Procesamiento asíncrono con colas | Overkill para MVP |
| Edición de video (filtros, etc) | Fuera del scope |
| Private/account-required content | Authentication complexity, TOS concerns |
| DRM-protected content | Legal/technical barriers |
| 4K/8K downloads | File size limits, processing time |
| Live stream recording | Technical complexity |

## Context

**Tech Stack:**
- Python 3.10+ con python-telegram-bot v20+
- ffmpeg para procesamiento de video
- python-dotenv para configuración
- yt-dlp para descargas de plataformas (v3.0)
- aiohttp/httpx para descargas concurrentes (v3.0)

**Arquitectura:**
- Procesamiento síncrono (un video a la vez)
- TempManager con context manager para limpieza automática
- BotConfig dataclass para configuración type-safe
- Validación pre-procesamiento (tamaño, integridad, disco)
- Manejo de errores con retry logic y correlation IDs
- Descargas concurrentes con tracking individual (v3.0)

**Estado Técnico:**
- 31 planes completados en 8 fases (v1.0 + v2.0)
- Código estable, probado en Android/Termux
- Manejo de errores robusto para producción
- Documentación de configuración completa (.env.example)
- ~9,254 LOC Python, 115+ commits
- Audio: 5 formatos soportados, 7 efectos profesionales, 3 herramientas de mejora
- UI: 13 acciones vía menú inline contextual

## Constraints

- **Tech stack**: Python con python-telegram-bot
- **Procesamiento**: ffmpeg para manipulación de video
- **Hosting**: Funciona en entornos con recursos limitados
- **Formato de salida**: Video note de Telegram (circular, 1:1)
- **Descargas**: Respetar TOS de plataformas, solo contenido público

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| **v3.0 Decisions** |||
| yt-dlp para plataformas | Librería madura, soporte amplio | Pending |
| Auto-detección de URLs | UX sin fricción, no requiere comando | Pending |
| URLs genéricas soportadas | Cualquier video descargable | Pending |
| Descargas concurrentes | Unlimited con tracking individual | Pending |
| Progreso en tiempo real | Feedback visual cada 5-10% | Pending |
| **v2.0 Decisions** |||
| Voice bitrate 24k | Optimized for speech transmission | ✓ Good |
| MP3 bitrate 192k | Good quality, widely compatible | ✓ Good |
| Max voice duration 20 min | Telegram voice note hard limit | ✓ Good |
| Method chaining for effects | Single ffmpeg execution where possible | ✓ Good |
| Effect pipeline with temp files | Clean intermediate results | ✓ Good |
| Inline contextual menus | No commands needed for basic use | ✓ Good |
| Universal cancel callback | Consistent UX across all flows | ✓ Good |
| **v1.0 Decisions** |||
| python-telegram-bot v20+ | Librería estable para bots con async/await | ✓ Good |
| ffmpeg | Standard para procesamiento de video | ✓ Good |
| Procesamiento síncrono | Simplifica MVP, un video a la vez | ✓ Good |
| TempManager con context manager | Limpieza automática de archivos temporales | ✓ Good |
| Video notes formato 1:1 640x640 | Restricciones técnicas de Telegram | ✓ Good |
| Mensajes de error en español | Usuarios hispanohablantes | ✓ Good |
| Timeout de 60 segundos | Prevenir bloqueos indefinidos | ✓ Good |
| Format-specific codec selection | Optimal quality per format | ✓ Good |
| BotConfig frozen dataclass | Inmutabilidad y validación | ✓ Good |
| Pre-processing validation | Fail-fast, mejor UX | ✓ Good |
| Exponential backoff retries | Resilience contra fallos | ✓ Good |
| Correlation IDs para tracing | Debugging en producción | ✓ Good |

## Completed Milestones

### v2.0 Navaja Suiza de Audio — SHIPPED 2026-02-21

**Delivered:** Herramienta versátil de procesamiento de audio con 20 planes en 6 fases, menús inline contextuales, y navegación UX completa.

**Key accomplishments:**
- Voice Notes & Voice Message Processing (bidirectional conversion)
- Audio Split/Join commands
- Audio Format Conversion (5 formats with metadata preservation)
- Audio Enhancement (bass/treble boost, 3-band EQ)
- Professional Audio Effects (denoise, compress, normalize, pipeline)
- Inline Menu Interface (13 actions, no commands needed)
- Navigation UX (Cancel/Back buttons on all submenus)

### v1.0 MVP — SHIPPED 2026-02-14

**Delivered:** Bot de Telegram para conversión automática de videos a notas de video circulares.

**Key accomplishments:**
- Core video processing automation
- Format conversion & audio extraction
- Video split/join
- Error handling & configuration

## Current Milestone

### v3.0 Downloader — IN PROGRESS

**Goal:** Agregar capacidad de descarga desde YouTube, Instagram, TikTok, Twitter/X, Facebook y URLs genéricas con detección automática de URLs, descargas concurrentes, y progreso en tiempo real.

**Target features:**
- Auto-detección de URLs sin comando
- Soporte para 5+ plataformas principales
- URLs genéricas con archivos de video
- Descargas concurrentes ilimitadas
- Progreso en tiempo real (porcentaje)
- Integración con herramientas existentes

---

*Last updated: 2026-02-21 after starting v3.0 Downloader milestone*
