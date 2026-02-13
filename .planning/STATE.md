# STATE

## Current Phase

Phase 02: Error Handling and Configuration

## Phase Goal

Enhance error handling with structured exceptions, comprehensive configuration management, and health check endpoints for production deployment.

## Context Summary

- Bot de Telegram que convierte videos en notas de video circulares
- Procesamiento automático sin comandos
- **Phase 1 COMPLETE** - Core video processing done
- **Phase 1.1 COMPLETE** - Format conversion, audio extraction, splitting, joining
- **Phase 02 IN PROGRESS** - Error handling and configuration enhancement

## Active Plans

- **01-01**: Bot Foundation - COMPLETE
- **01-02**: Core Video Processing Implementation - COMPLETE
- **01-03**: Error Handling, Logging and Documentation - COMPLETE
- **01.1-01**: Format Conversion and Audio Extraction - COMPLETE
  - FormatConverter class with MP4, AVI, MOV, MKV, WEBM support
  - AudioExtractor class with MP3, AAC, WAV, OGG support
  - /convert and /extract_audio Telegram commands
  - Spanish error messages and comprehensive logging
- **01.1-02**: Video Splitting - COMPLETE
  - VideoSplitter class with split_by_duration and split_by_parts methods
  - /split command with duration and parts modes
  - Max 10 segments, min 5 seconds per segment constraints
  - Progress messages during segment sending
- **01.1-03**: Video Joining - COMPLETE
  - VideoJoiner class with ffmpeg concat demuxer
  - Format normalization for incompatible codecs
  - /join command with session-based video collection
  - Min 2, max 10 videos per join operation
  - 5-minute session timeout with automatic cleanup
- **02-01**: Enhanced Bot Configuration - COMPLETE
  - BotConfig dataclass with 12 configurable parameters
  - Environment variable loading with type conversion
  - __post_init__ validation for fail-fast behavior
  - .env.example documentation with all options
  - Handlers refactored to use config values
- **02-02**: Pre-processing Validation - COMPLETE
  - validators.py module with file size, integrity, and disk space checks
  - ValidationError exception with Spanish user messages
  - Integration in all handlers (handle_video, convert, extract_audio, split, join)
  - Fail-fast validation before download to prevent wasted processing
  - Graceful degradation when ffprobe or disk checks unavailable
- **02-03**: Telegram API Error Handling - COMPLETE
  - Telegram error imports (NetworkError, TimedOut, BadRequest, RetryAfter)
  - Spanish error messages for all Telegram error types
  - Retry logic with exponential backoff for transient failures
  - Correlation IDs for request tracing through logs
- **02-04**: Startup Cleanup and Graceful Shutdown - COMPLETE
  - cleanup_old_temp_directories() removes directories older than 24 hours
  - Auto-executes on module import for startup cleanup
  - active_temp_managers set tracks all active TempManager instances
  - Signal handlers for SIGINT and SIGTERM cleanup temp managers on shutdown

## Blockers

(None)

## Recent Decisions

- Usar python-telegram-bot como framework
- ffmpeg para procesamiento de video
- Procesamiento síncrono para simplificar MVP
- Usar python-telegram-bot v20+ con API async/await
- Validar BOT_TOKEN en tiempo de importación para fallo temprano
- Separar configuración en módulo dedicado (bot/config.py)
- **D01-02-01**: Use TempManager with context manager protocol for automatic cleanup
- **D01-02-02**: Video notes: 1:1 square, 640x640 max, 60s max, no audio
- **D01-02-03**: Log errors internally, send user-friendly messages to users
- **D01-03-01**: Use Spanish error messages for user-facing communication
- **D01-03-02**: 60-second timeout for video processing to prevent indefinite hangs
- **D01-03-03**: Processing message to user provides feedback during long operations
- **D01.1-01-01**: Use format-specific codec selection (libx264 for most, libvpx-vp9 for webm)
- **D01.1-01-02**: Support both direct video messages and reply-to-video patterns
- **D01.1-01-03**: Default to mp3 for audio extraction when no format specified
- **D01.1-01-04**: Use -movflags +faststart for all video conversions
- **D01.1-02-01**: Use ffmpeg segment muxer for fast splitting without re-encoding
- **D01.1-02-02**: Calculate expected segments before splitting to enforce limits
- **D01.1-02-03**: Send segments as separate video messages with part number captions
- **D01.1-03-01**: Use ffmpeg concat demuxer for quality preservation with automatic normalization
- **D01.1-03-02**: H.264 + AAC as normalization target for maximum compatibility
- **D01.1-03-03**: Double timeout (120s) for join operations vs standard processing
- **D01.1-03-04**: Session-based collection with /done trigger for multi-file operations
- **D02-01-01**: Use frozen dataclass for configuration immutability
- **D02-01-02**: Validate configuration at initialization time (fail-fast)
- **D02-01-03**: Separate JOIN_TIMEOUT from PROCESSING_TIMEOUT for independent tuning
- **D02-01-04**: Keep DEFAULT_SEGMENT_DURATION as constant (UI default, not operational)
- **D02-02-01**: Validation should not block if tools unavailable (ffprobe, disk check)
- **D02-02-02**: Validate at multiple stages: before download, after download, before processing
- **D02-02-03**: Use 2x file size + 100MB buffer for disk space estimation
- **D02-03-01**: Use 8-character UUID for correlation IDs (sufficient uniqueness, readable)
- **D02-03-02**: Use exponential backoff (1s, 2s, 3s) for download retries
- **D02-03-03**: Log transient errors (NetworkError, TimedOut) as warnings, not errors
- **D02-04-01**: Use module-level cleanup on import for automatic startup cleanup
- **D02-04-02**: Use set for active manager tracking (explicit lifecycle management)
- **D02-04-03**: Cleanup on SIGINT/SIGTERM only (SIGKILL cannot be caught)

## Progress

```
Phase 1: Core Video Processing
[████████████████████] 100% (3/3 plans complete)

Phase 1.1: Expandir procesamiento de video
[████████████████████] 100% (3/3 plans complete)
  - 01.1-01: Format Conversion and Audio Extraction ✓
  - 01.1-02: Video Splitting ✓
  - 01.1-03: Video Joining ✓

Phase 02: Error Handling and Configuration
[████████████████████] 100% (4/4 plans complete)
  - 02-01: Enhanced Bot Configuration ✓
  - 02-02: Pre-processing Validation ✓
  - 02-03: Telegram API Error Handling ✓
  - 02-04: Startup Cleanup and Graceful Shutdown ✓

Phase 2: Deployment
[░░░░░░░░░░░░░░░░░░░░] 0% (0/1 plans complete)

Overall: 10/10 plans complete (100%)
```

## Project Reference

See: .planning/PROJECT.md (updated 2025-02-03)

**Core value:** El usuario envía un video y recibe inmediatamente una nota de video circular, sin fricción ni pasos intermedios.
**Current focus:** Phase 02 - Error handling and configuration enhancement

## Accumulated Context

### Roadmap Evolution
- Phase 1.1 inserted after Phase 1: Expandir procesamiento de video - Cambio de formato, extracción de audio, dividir y unir archivos (URGENT)
- Phase 1.1 Plan 01 complete: Format conversion and audio extraction working
- Phase 1.1 Plan 02 complete: Video splitting with /split command working
- Phase 1.1 Plan 03 complete: Video joining with /join command working
- Phase 02 Plan 01 complete: Enhanced bot configuration with environment variables
- Phase 02 Plan 02 complete: Pre-processing validation with file size, integrity, and disk space checks
- Phase 02 Plan 03 complete: Telegram API error handling with retry logic and correlation IDs
- Phase 02 Plan 04 complete: Startup cleanup and graceful shutdown with signal handlers

---
*Last updated: 2026-02-13 after completing 02-04*
