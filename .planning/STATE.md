# STATE

## Current Milestone

**v3.0: Downloader** — IN PROGRESS

Bot con capacidad de descarga desde YouTube, Instagram, TikTok, Twitter/X, Facebook y URLs genéricas.

## Current Position

**Phase:** 10-platform-handlers — IN PROGRESS

**Plan:** 10-03

**Status:** TikTok and Twitter/X platform handlers complete. 3/N plans in Phase 10.

**Last activity:** 2026-02-21 — Completed 10-03: TikTokDownloader with watermark-free option and slideshow detection, TwitterDownloader with quality selection and tweet metadata

## Progress

```
v3.0 Downloader
[████░░░░░░░░░░░░░░░░] 25% (1/4 phases)

Phase 9:  Downloader Core Infrastructure    [██████████] 100% (4/4 plans) — COMPLETE
Phase 10: Platform Handlers                 [██████░░░░] 60% (3/5 plans)
Phase 11: Download Management & Progress    [░░░░░░░░░░] 0% (0/N plans)
Phase 12: Integration & Polish              [░░░░░░░░░░] 0% (0/N plans)
```

## Accumulated Context

**v1.0 SHIPPED (2026-02-14):**
- Bot de Telegram que convierte videos en notas de video circulares
- Procesamiento automático sin comandos
- Funcionalidades avanzadas: conversión de formato, extracción de audio, split/join de video
- Configuración completa vía variables de entorno
- Manejo robusto de errores con retry logic y graceful shutdown
- ~2,971 LOC, 56 commits

**v2.0 SHIPPED (2026-02-21):**
- Herramienta versátil de procesamiento de audio tipo "navaja suiza"
- 6 phases (3-8), 20 plans, ~9,254 LOC
- Voice notes, split/join, format conversion (5 formats)
- Audio enhancement: bass/treble boost, 3-band EQ
- Professional effects: denoise, compress, normalize, pipeline
- Inline contextual menus with Cancel/Back navigation
- Timeline: Dec 2025 → Feb 2026

**v3.0 IN PROGRESS:**
- Downloader capabilities for popular platforms
- Auto-detection of URLs without commands
- Generic video URL support
- Concurrent downloads with progress tracking
- Integration with existing video/audio tools

## Active Plans

**09-01: URL Auto-Detection Infrastructure** — COMPLETE
- URLDetector class with entity extraction and regex fallback
- Platform detection (YouTube, Instagram, TikTok, Twitter/X, Facebook)
- Generic video URL detection (.mp4, .webm, .mov)
- Download configuration with Telegram limits (50MB)
- yt-dlp format strings configurable via environment

**09-02: Base Downloader Architecture** — COMPLETE
- BaseDownloader abstract class with async contract
- DownloadOptions frozen dataclass with validation
- Comprehensive exception hierarchy (7 exception types)
- User-friendly Spanish error messages
- Correlation ID support for request tracing (DM-02)

**09-03: yt-dlp Downloader** — COMPLETE
- YtDlpDownloader class implementing BaseDownloader
- Support for 1000+ platforms (YouTube, Instagram, TikTok, Twitter/X, Facebook)
- Thread pool async pattern for non-blocking operations
- Real-time progress hooks via asyncio.run_coroutine_threadsafe
- Pre-download file size validation (QF-05)
- Audio extraction via FFmpegExtractAudio postprocessor (QF-03)
- Proper error handling with correlation IDs (EH-01, EH-03)

**09-04: Generic HTTP Downloader** — COMPLETE
- GenericDownloader class for direct video file URLs (.mp4, .webm, .mov, etc.)
- aiohttp streaming downloads (8KB chunks) with async file I/O
- Content-Type validation before download (DL-05)
- File size validation from Content-Length header (QF-05)
- Real-time progress callbacks with percent/bytes
- File integrity validation (size check, non-empty, optional python-magic)
- Automatic cleanup of partial files on failure
- 12 video extensions and MIME types supported

**10-01: YouTube Platform Handler** — COMPLETE
- YouTubeDownloader extends YtDlpDownloader with platform-specific features
- YouTube Shorts detection via `is_youtube_shorts()` function
- Enhanced metadata extraction (view_count, like_count, upload_date, tags, categories)
- Age-restricted content detection with Spanish error messages
- View count formatting for display (1.2M views, 500K views)
- Aspect ratio hints for Shorts (9:16 vertical format)
- Support for all YouTube URL formats (watch, shorts, youtu.be, embed)

**10-02: Instagram Platform Handler** — COMPLETE
- InstagramDownloader extends YtDlpDownloader with Instagram-specific features
- Content type detection: POST (`/p/`), REEL (`/reel/`, `/reels/`), STORY (`/stories/`)
- Enhanced metadata extraction (username, caption, likes_count, comments_count, view_count)
- Aspect ratio hints for Reels (9:16 vertical format)
- Spanish error messages for private content, expired stories, rate limiting
- Helper functions: `is_instagram_reel()`, `is_instagram_story()`, `extract_shortcode()`
- Human-readable count formatting (1.5K, 2.3M)

**10-03: TikTok and Twitter/X Platform Handlers** — COMPLETE
- TikTokDownloader extends YtDlpDownloader with watermark-free option and slideshow detection
- Watermark-free preference via format string `best[format_id!*=watermark]/best`
- Enhanced metadata: author, stats (plays, likes, shares, comments), music info, aspect ratio (9:16)
- TwitterDownloader extends YtDlpDownloader with quality selection and tweet metadata
- Tweet metadata: tweet_id, username, tweet_text, engagement stats (replies, retweets, likes, views)
- Video variants list for quality selection with `select_best_variant()` helper
- GIF detection and support for both twitter.com and x.com domains
- Spanish error messages for restricted/deleted content

## Decisions Made

**v3.0 Decisions (Validated):**
1. **yt-dlp for platform downloads** — Mature library, broad platform support
2. **Auto-detect URLs in messages** — No /download command required
3. **Generic video URL support** — Any URL with video file downloadable
4. **Unlimited concurrent downloads** — Individual tracking per download
5. **Real-time progress (5-10%)** — Visual feedback with percentage bar

**09-01 Implementation Decisions:**
6. **URLType enum classification** — PLATFORM, GENERIC_VIDEO, UNKNOWN types
7. **Entity-first extraction** — Extract from Telegram entities before regex fallback
8. **Simple domain matching** — Use simple patterns, let yt-dlp handle complex validation
9. **Config validation** — Enforce Telegram 50MB limit at configuration level

**09-02 Implementation Decisions:**
10. **Frozen dataclass for DownloadOptions** — Immutability prevents accidental mutation
11. **8-character correlation IDs** — Sufficient uniqueness with readability
12. **Spanish user messages** — Align with existing bot language
13. **URLDetectionError alias** — Maintains backwards compatibility with existing code

**09-03 Implementation Decisions:**
14. **Thread pool for yt-dlp operations** — All yt-dlp calls via asyncio.to_thread() to avoid blocking
15. **process=False for can_handle** — Fast URL validation without full metadata extraction
16. **run_coroutine_threadsafe for progress** — Thread-safe callback scheduling from worker threads
17. **Pre-download size check** — Extract metadata first to validate size before downloading
18. **Format string with filesize filter** — `best[filesize<50M]/best` prefers Telegram-compatible sizes

**09-04 Implementation Decisions:**
19. **aiohttp for generic downloads** — Lighter than httpx, purpose-built for async HTTP
20. **HEAD request before GET** — Extract metadata (size, content-type) without downloading
21. **8KB chunk size** — Balance between memory usage and I/O efficiency
22. **MIME type + extension fallback** — Check Content-Type header, fall back to URL extension
23. **Generic first in routing** — Faster check for direct video URLs before trying yt-dlp

**10-01 Implementation Decisions:**
24. **Extend YtDlpDownloader for platform handlers** — Reuse thread pool, progress hooks, base metadata
25. **Regex-first URL detection** — Fast pattern matching before yt-dlp validation
26. **Aspect ratio hints for Shorts** — Signal 9:16 format for downstream processing
27. **Spanish error messages** — Consistent with existing bot language for age-restricted content
28. **View count formatting** — Human-readable display format (1.2M, 500K)

**10-02 Implementation Decisions:**
29. **Content type enum for Instagram** — POST, REEL, STORY classification via InstagramContentType
30. **Shortcode extraction** — Parse unique identifiers from various Instagram URL patterns
31. **Extended metadata extraction** — Re-extract with yt-dlp for Instagram-specific fields (likes, comments)
32. **Instagram-specific HTTP headers** — Custom User-Agent to avoid blocks
33. **Caption formatting utility** — Normalize whitespace and truncate for display

**10-03 Implementation Decisions:**
34. **Watermark-free format preference** — Use `best[format_id!*=watermark]/best` for best-effort watermark removal
35. **Slideshow detection via album/carousel** — Check for `album`, `carousel`, `image_list` keys in yt-dlp info
36. **Video variants sorted by height** — Sort by resolution descending for quality selection
37. **select_best_variant() helper** — Choose best quality under size limit for Telegram compatibility
38. **GIF detection via format string** — Check for 'gif' in formats list
39. **Support both Twitter domains** — Handle twitter.com and x.com URLs identically

## Blockers

(None)

## Next Actions

1. ~~Phase 9: Downloader Core Infrastructure~~ DONE (4/4 plans)
2. ~~10-01: YouTube Platform Handler~~ DONE
3. ~~10-02: Instagram Platform Handler~~ DONE
4. ~~10-03: TikTok and Twitter/X Platform Handlers~~ DONE
5. **10-04: Facebook Platform Handler** — Next step

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)
See: .planning/REQUIREMENTS.md (v3.0 requirements)
See: .planning/ROADMAP.md (v3.0 phases 9-12)

**Core value:** El usuario envía un video, archivo de audio, o URL de video y recibe el resultado procesado inmediatamente, sin fricción.

**Current focus:** v3.0 Downloader — Descargas desde plataformas populares

---

*Last updated: 2026-02-21 after completing 10-03*
