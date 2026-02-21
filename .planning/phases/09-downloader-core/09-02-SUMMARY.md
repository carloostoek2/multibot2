---
phase: 09-downloader-core
plan: 02
type: execute
subsystem: downloader
status: complete
tags: ["downloader", "base-class", "exceptions", "abc", "types"]
dependency_graph:
  requires: ["09-01"]
  provides: ["09-03", "09-04", "10-01", "10-02"]
  affects: ["bot/downloaders"]
tech_stack:
  added: ["abc", "dataclasses", "uuid", "typing"]
  patterns: ["Abstract Base Class", "Frozen Dataclass", "Exception Hierarchy"]
key_files:
  created:
    - bot/downloaders/exceptions.py
    - bot/downloaders/base.py
  modified:
    - bot/downloaders/__init__.py
decisions:
  - "Frozen dataclass for DownloadOptions prevents accidental mutation"
  - "8-character correlation IDs provide sufficient uniqueness with readability"
  - "Spanish user messages align with existing bot language"
  - "URLDetectionError alias maintains backwards compatibility"
metrics:
  duration_minutes: 25
  completed_date: "2026-02-21"
  lines_of_code: 769
  test_coverage: "verified via Python import tests"
---

# Phase 09 Plan 02: Base Downloader Architecture Summary

**Abstract base class and exception hierarchy providing the foundation for all downloader implementations.**

## Overview

This plan establishes the foundational architecture for the downloader system. It creates a consistent contract that all downloader implementations (yt-dlp, generic HTTP) must follow, ensuring they can be used interchangeably by higher-level code.

## Deliverables

### 1. Exception Hierarchy (`bot/downloaders/exceptions.py`)

Comprehensive exception hierarchy with user-friendly Spanish messages:

| Exception | Purpose | User Message |
|-----------|---------|--------------|
| `DownloadError` | Base exception with correlation ID support | Generic error message |
| `URLValidationError` | Malformed or invalid URLs | "La URL parece ser inválida..." |
| `MetadataExtractionError` | Cannot fetch video info | "No pude obtener información del video..." |
| `FileTooLargeError` | Exceeds Telegram 50MB limit | "El archivo es muy grande (X MB)..." |
| `UnsupportedURLError` | Valid but unsupported platform | Lists supported platforms |
| `DownloadFailedError` | Failed after all retries | "La descarga falló después de X intentos..." |
| `NetworkError` | Transient network failures | "Error de red. Reintentando..." |

All exceptions support:
- Correlation IDs for request tracing (DM-02)
- URL preservation for debugging
- Both technical details (logs) and user-friendly messages

### 2. DownloadOptions Dataclass (`bot/downloaders/base.py`)

Frozen dataclass encapsulating all download configuration:

**Output Settings:**
- `output_path`: Directory for downloaded files
- `filename`: Custom filename (auto-generated if None)

**Quality Settings (per QF-01, QF-02, QF-03, QF-05):**
- `video_format`: yt-dlp format string (default: "best[filesize<50M]/best")
- `audio_format`: yt-dlp audio format string
- `preferred_quality`: Quality preference ("best", "720p", etc.)
- `max_filesize`: Maximum file size (50MB Telegram limit)

**Format Preferences:**
- `output_format`: Preferred container ("mp4")
- `audio_codec`: Audio codec ("mp3")
- `audio_bitrate`: Audio bitrate ("320k")

**Download Mode (per DL-04):**
- `extract_audio`: Download audio only
- `keep_video`: Keep video when extracting audio

**Retry Settings (per EH-03):**
- `max_retries`: 3 attempts
- `retry_delay`: 2 seconds between retries

**Timeout Settings:**
- `metadata_timeout`: 30 seconds
- `download_timeout`: 300 seconds (5 minutes)

**Features:**
- `from_config()`: Create from bot.config values
- `with_overrides()`: Create modified instances
- Validation in `__post_init__` (enforces 50MB limit)

### 3. BaseDownloader Abstract Class (`bot/downloaders/base.py`)

Abstract base class defining the downloader contract:

**Abstract Methods (must implement):**
- `can_handle(url: str) -> bool`: Check if downloader can handle URL
- `extract_metadata(url, options) -> dict`: Extract metadata without downloading
- `download(url, options) -> DownloadResult`: Perform actual download

**Abstract Properties:**
- `name`: Human-readable downloader name
- `supported_platforms`: List of supported platform names

**Concrete Utility Methods:**
- `validate_url(url)`: Basic URL validation
- `check_filesize(size, max_size)`: Raise FileTooLargeError if needed
- `format_duration(seconds)`: Format as "MM:SS" or "HH:MM:SS"
- `format_filesize(bytes)`: Format as "X MB" or "X GB"
- `_generate_correlation_id()`: 8-character unique ID
- `_sanitize_filename(title)`: Clean filename for filesystem
- `_is_valid_url(url)`: URL format validation

### 4. Package Exports (`bot/downloaders/__init__.py`)

Clean public API:

```python
from bot.downloaders import (
    BaseDownloader,
    DownloadOptions,
    DownloadResult,
    DownloadError,
    URLValidationError,
    # ... all exceptions
    URLDetector,
    URLType,
    TELEGRAM_MAX_FILE_SIZE,
)
```

## Verification Results

All verification tests passed:

1. **Abstract class test**: BaseDownloader cannot be instantiated directly
2. **Subclass test**: Test subclass implementing all abstract methods works
3. **Exception test**: All exception types raise correctly with user messages
4. **Options test**: DownloadOptions validation works (rejects >50MB)
5. **Import test**: All exports work from `bot.downloaders`

```bash
$ python -c "from bot.downloaders import BaseDownloader, DownloadOptions; print('OK')"
OK
```

## Deviations from Plan

**None** - Plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| c6d427e | feat(09-02): create downloader exception hierarchy |
| 51eb6af | feat(09-02): create BaseDownloader and DownloadOptions |
| ab8c153 | feat(09-02): update package exports |

## Self-Check: PASSED

- [x] `bot/downloaders/exceptions.py` exists (273 lines)
- [x] `bot/downloaders/base.py` exists (496 lines)
- [x] `bot/downloaders/__init__.py` updated
- [x] All commits exist in git history
- [x] All classes importable from bot.downloaders
- [x] Abstract class cannot be instantiated
- [x] Validation rejects invalid values

## Next Steps

This plan provides the foundation for:
- **09-03**: yt-dlp downloader implementation
- **09-04**: Generic HTTP downloader implementation
- **10-01, 10-02**: Platform-specific handlers

All downloader implementations will inherit from `BaseDownloader` and use `DownloadOptions` for configuration.
