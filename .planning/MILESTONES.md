# Milestones: Video Note Bot

## v1.0 MVP — SHIPPED 2026-02-14

**Phases:** 1-2 (including 1.1)
**Plans:** 11 total (3 + 3 + 5)
**Commits:** 56
**Lines of Code:** ~2,971 Python
**Timeline:** 2025-12-14 → 2026-02-14 (62 days)

### Delivered

Bot de Telegram que recibe videos y los convierte automáticamente en notas de video circulares, con funcionalidades avanzadas de procesamiento y manejo robusto de errores.

### Key Accomplishments

1. **Core Video Processing** — Bot automáticamente detecta videos, los procesa a formato circular 1:1, y envía como video notes sin comandos
2. **Format Conversion & Audio Extraction** — Comandos /convert y /extract_audio para transformar videos entre formatos y extraer audio
3. **Video Splitting & Joining** — Comandos /split y /join para dividir videos en segmentos y unir múltiples archivos
4. **Configuration Management** — BotConfig dataclass con 12 parámetros configurables vía variables de entorno, validación fail-fast
5. **Pre-processing Validation** — Validación de tamaño de archivo, integridad de video (ffprobe), y espacio en disco
6. **Error Handling & Resilience** — Manejo de errores de Telegram API, retry logic con exponential backoff, correlation IDs para tracing
7. **Resource Management** — Limpieza automática de archivos temporales, graceful shutdown con signal handlers

### Archive

- [v1.0 Roadmap](milestones/v1.0-ROADMAP.md)
- [v1.0 Requirements](milestones/v1.0-REQUIREMENTS.md)

### Git Tag

```
v1.0
```

---

*For current status, see .planning/ROADMAP.md*

## v2.0 Navaja Suiza de Audio — SHIPPED 2026-02-21

**Phases:** 3-8 (6 phases)
**Plans:** 20 total
**Commits:** 59 feature commits
**Lines of Code:** ~9,254 Python
**Timeline:** 2026-02-18 → 2026-02-20 (2 days active development)

### Delivered

Herramienta versátil de procesamiento de audio tipo "navaja suiza" para archivos de audio en Telegram, con menús inline contextuales que eliminan la necesidad de aprender comandos.

### Key Accomplishments

1. **Voice Notes & Voice Message Processing** — MP3 ↔ OGG Opus bidirectional conversion with automatic truncation for 20+ min files
2. **Audio Split/Join** — `/split_audio` to divide by duration or N parts, `/join_audio` to merge multiple files
3. **Audio Format Conversion** — Support for MP3, WAV, OGG, AAC, FLAC with metadata preservation (ID3/Vorbis tags)
4. **Audio Enhancement** — `/bass_boost` and `/treble_boost` with intensity 1-10, `/equalize` with 3-band EQ
5. **Professional Audio Effects** — `/denoise` (FFT noise reduction), `/compress` (dynamic range), `/normalize` (EBU R128 loudness)
6. **Effects Pipeline** — `/effects` command to chain multiple effects (denoise → compress → normalize)
7. **Inline Menu Interface** — Automatic contextual menus for video/audio files with 13 action options, no commands needed
8. **Navigation UX** — Universal Cancel/Back buttons on all submenus with full context cleanup

### Archive

- [v2.0 Roadmap](milestones/v2.0-ROADMAP.md)
- [v2.0 Requirements](milestones/v2.0-REQUIREMENTS.md)

### Git Tag

```
v2.0
```

---

