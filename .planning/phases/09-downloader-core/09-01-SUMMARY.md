---
phase: 09-downloader-core
plan: 01
subsystem: downloader
tags: ["url-detection", "config", "infrastructure"]
requires: []
provides: ["url-detection", "download-config"]
affects: ["bot/downloaders"]
tech-stack:
  added: []
  patterns: ["enum-based-classification", "dataclass-config", "static-methods"]
key-files:
  created:
    - bot/downloaders/__init__.py
    - bot/downloaders/url_detector.py
  modified:
    - bot/config.py
decisions:
  - "Use URLType enum for classification (PLATFORM, GENERIC_VIDEO, UNKNOWN)"
  - "Extract URLs from entities first, regex as fallback"
  - "50MB Telegram limit enforced in config validation"
  - "yt-dlp format strings configurable via environment"
metrics:
  duration: "30 minutes"
  completed: "2026-02-21"
---

# Phase 9 Plan 1: URL Auto-Detection Infrastructure Summary

**One-liner:** Implemented URL auto-detection and validation infrastructure with entity extraction, platform classification, and download configuration.

## What Was Built

### 1. Downloaders Package Structure (`bot/downloaders/`)

Created the foundation package for all downloader-related functionality:

- **`__init__.py`** - Package exports and common types
  - `DownloadError` - Base exception for download operations
  - `URLDetectionError` - Exception for URL extraction failures
  - `UnsupportedURLError` - Exception for unsupported URL types
  - `DownloadResult` - Dataclass for download operation results
  - Exports for `URLDetector`, `URLType`, `detect_urls`, `classify_url`

### 2. URL Detection and Classification (`bot/downloaders/url_detector.py`)

Implemented comprehensive URL detection for Telegram messages:

**URLType Enum:**
- `PLATFORM` - YouTube, Instagram, TikTok, Twitter/X, Facebook
- `GENERIC_VIDEO` - Direct video file URLs (.mp4, .webm, .mov, etc.)
- `UNKNOWN` - Non-video URLs

**URLDetector Class:**
- `extract_urls(message_text, entities)` - Extracts URLs from message entities (url, text_link) with regex fallback
- `classify_url(url)` - Classifies URLs by platform or generic video type
- `is_supported(url)` - Checks if URL can be handled
- `validate_url(url)` - Validates URL structure

**Platform Detection Patterns:**
- YouTube: `youtube.com`, `youtu.be`, `youtube.com/shorts`
- Instagram: `instagram.com/p/`, `/reel/`, `/reels/`, `/stories/`
- TikTok: `tiktok.com/@`, `vm.tiktok.com`, `vt.tiktok.com`
- Twitter/X: `twitter.com`, `x.com`
- Facebook: `facebook.com/watch`, `fb.watch`, `/reel/`, `/video`

**Generic Video Extensions:**
`.mp4`, `.webm`, `.mov`, `.avi`, `.mkv`, `.flv`, `.wmv`

### 3. Download Configuration (`bot/config.py`)

Extended `BotConfig` with download-specific settings:

**File Size Limits:**
- `DOWNLOAD_MAX_SIZE_MB` - 50MB (Telegram bot upload limit)
- `DOWNLOAD_MAX_SIZE_GENERIC_MB` - 50MB for generic HTTP downloads

**Timeout Settings:**
- `DOWNLOAD_TIMEOUT` - 300 seconds (5 minutes)
- `DOWNLOAD_METADATA_TIMEOUT` - 30 seconds for metadata extraction

**Quality Settings (yt-dlp format strings):**
- `DOWNLOAD_VIDEO_FORMAT` - `best[filesize<50M]/best`
- `DOWNLOAD_AUDIO_FORMAT` - `bestaudio[filesize<50M]/bestaudio`
- `DOWNLOAD_AUDIO_QUALITY` - `320` (MP3 bitrate)
- `DOWNLOAD_VIDEO_PREFERENCE` - `mp4` (preferred container)

**Concurrent Download Settings:**
- `DOWNLOAD_MAX_CONCURRENT` - 5 (semaphore limit)

**Retry Settings:**
- `DOWNLOAD_MAX_RETRIES` - 3
- `DOWNLOAD_RETRY_DELAY` - 2 seconds between retries

**Validation:**
- DOWNLOAD_MAX_SIZE_MB must be <= 50 (Telegram limit)
- Timeout values must be positive
- DOWNLOAD_MAX_CONCURRENT must be >= 1
- All settings configurable via environment variables

## Key Design Decisions

1. **Entity-first extraction:** URLs are extracted from Telegram entities (url, text_link) first, with regex fallback for plain text. This correctly handles hidden URLs behind clickable text.

2. **Simple domain matching:** Platform detection uses simple regex patterns rather than complex URL validation. yt-dlp will handle actual URL validation during extraction.

3. **Telegram limits enforced:** Config validation ensures file size limits respect Telegram's 50MB bot upload limit.

4. **Configurable format strings:** yt-dlp format strings are configurable via environment variables for flexibility.

## Deviations from Plan

None - plan executed exactly as written.

## Test Coverage

All verification tests pass:
- Import test: `from bot.downloaders import URLDetector` works
- Extraction test: Entity extraction (url, text_link) works correctly
- Classification test: All 5 platforms + generic video detected correctly
- Config test: All download settings accessible with correct defaults
- Integration check: No circular imports with existing modules

## Commits

| Commit | Description |
|--------|-------------|
| 23be21e | feat(09-01): create downloaders package structure |
| 8eadb8d | feat(09-01): implement URL detection and classification |
| 6968d54 | feat(09-01): add download configuration settings |

## Next Steps

This plan provides the foundation for:
- Plan 09-02: Generic video downloader (HTTP-based)
- Plan 09-03: yt-dlp integration for platform downloads
- Plan 09-04: Download progress tracking and management

The URL detector can now be integrated into message handlers to auto-detect URLs without requiring explicit `/download` commands.

---

## Self-Check: PASSED

- [x] bot/downloaders/__init__.py exists and is importable
- [x] bot/downloaders/url_detector.py exists with all required exports
- [x] bot/config.py has all download-related fields
- [x] All commits exist in git history
- [x] No breaking changes to existing functionality
