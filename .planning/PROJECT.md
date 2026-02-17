# Video Note Bot

## What This Is

Un bot de Telegram que recibe videos enviados por usuarios y los convierte automáticamente en notas de video (video notes) circulares de Telegram, sin necesidad de comandos ni interacción adicional. Incluye funcionalidades avanzadas de procesamiento: cambio de formato, extracción de audio, división y unión de videos.

## Current State

**v1.0 SHIPPED** — 2026-02-14

Bot funcional con procesamiento automático de videos a video notes, manejo robusto de errores, y configuración completa vía variables de entorno.

- 11 planes completados (3 fases)
- ~2,971 líneas de Python
- 56 commits
- Timeline: 62 días

## Core Value

El usuario envía un video y recibe inmediatamente una nota de video circular, sin fricción ni pasos intermedios.

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

### Active (Next Milestone)

- [ ] FEAT-01 — Soporte para videos enviados como archivo (document)
- [ ] FEAT-02 — Barra de progreso mientras se procesa el video
- [ ] FEAT-03 — Estadísticas de uso
- [ ] FEAT-04 — Opción de ajustar el punto de recorte

### Out of Scope

| Feature | Reason |
|---------|--------|
| Múltiples videos simultáneos | Simplifica MVP, procesamiento uno a la vez |
| Panel web de administración | Overkill para funcionalidad simple |
| Base de datos | No es necesario persistir estado |
| Soporte para otros formatos de salida | Solo video notes, requisito específico |
| Procesamiento asíncrono con colas | Overkill para MVP |
| Edición de video (filtros, etc) | Fuera del scope |

## Context

**Tech Stack:**
- Python 3.10+ con python-telegram-bot v20+
- ffmpeg para procesamiento de video
- python-dotenv para configuración

**Arquitectura:**
- Procesamiento síncrono (un video a la vez)
- TempManager con context manager para limpieza automática
- BotConfig dataclass para configuración type-safe
- Validación pre-procesamiento (tamaño, integridad, disco)
- Manejo de errores con retry logic y correlation IDs

**Estado Técnico:**
- 11 planes completados en 3 fases
- Código estable, probado en Android/Termux
- Manejo de errores robusto para producción
- Documentación de configuración completa (.env.example)

## Constraints

- **Tech stack**: Python con python-telegram-bot
- **Procesamiento**: ffmpeg para manipulación de video
- **Hosting**: Funciona en entornos con recursos limitados
- **Formato de salida**: Video note de Telegram (circular, 1:1)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
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

## Current Milestone: v2.0 Navaja Suiza de Audio

**Goal:** Expandir el bot con comandos completos de procesamiento de audio, convirtiéndolo en una herramienta versátil tipo "navaja suiza" para archivos de audio.

**Target features:**
- Conversión MP3 → nota de audio de Telegram (voice note)
- Split/Join de archivos de audio
- Conversión entre formatos (MP3, WAV, OGG, AAC, FLAC)
- Audio enhancement: boost de bajos, boost de agudos, ecualización
- Efectos: reducción de ruido, compresión, normalización
- Conversión automática de notas de voz recibidas → MP3

## Next Milestone Goals (Future)

**v2.1 Ideas:**
- Soporte para videos como documentos (no solo video messages)
- Barra de progreso durante procesamiento
- Estadísticas básicas de uso
- Ajuste del punto de recorte (centrado/arriba/abajo)

---

*Last updated: 2026-02-14 after starting v2.0 milestone*
</content>