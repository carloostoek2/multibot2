---
phase: 10-platform-handlers
plan: "05"
subsystem: downloader
tags: [router, routing, platform-selection, integration]
dependency_graph:
  requires: ["10-01", "10-02", "10-03", "10-04"]
  provides: ["platform-routing", "auto-downloader-selection"]
  affects: ["bot/downloaders/__init__.py"]
tech_stack:
  added: []
  patterns: [priority-based-routing, adapter-pattern, lazy-loading]
key_files:
  created:
    - bot/downloaders/platform_router.py
  modified:
    - bot/downloaders/__init__.py
    - bot/downloaders/url_detector.py
decisions:
  - "Priority-based routing: platform-specific > generic > yt-dlp > HTML"
  - "Downloader caching for performance optimization"
  - "Lazy import of platform checkers to avoid circular dependencies"
  - "HTML extractor adapter to make it BaseDownloader-compatible"
metrics:
  duration_minutes: 25
  tasks_completed: 3
  files_created: 1
  files_modified: 2
  lines_of_code: 302
  commits: 3
  completion_date: "2026-02-21"
---

# Phase 10 Plan 05: Platform Router Summary

Platform router with intelligent URL-to-downloader routing and priority-based selection.

## Overview

Implemented the `PlatformRouter` class that automatically selects the appropriate downloader for any given URL. The router integrates all platform handlers (YouTube, Instagram, TikTok, Twitter/X, Facebook) and provides a unified interface for URL-to-downloader routing with priority-based selection and fallback mechanisms.

## What Was Built

### 1. PlatformRouter Class (`bot/downloaders/platform_router.py`)

A comprehensive router with priority-based routing:

- **RouteResult dataclass**: Structured result containing downloader, platform name, confidence level, and selection reason
- **Priority-based routing system**:
  1. Platform-specific handlers (YouTube, Instagram, TikTok, Twitter/X, Facebook) - high confidence
  2. Generic video URL handler for direct video links - high confidence
  3. yt-dlp fallback for other supported platforms - medium confidence
  4. HTML extractor for web pages that might contain videos - low confidence
- **Downloader caching**: Instances cached by platform for performance
- **Platform identification**: Extracts platform name from yt-dlp metadata
- **_HTMLExtractorAdapter**: Internal adapter making HTMLVideoExtractor compatible with BaseDownloader

### 2. URL Detector Enhancements (`bot/downloaders/url_detector.py`)

Enhanced URL classification with platform identification:

- **`classify_url_enhanced()`**: Returns tuple of `(URLType, platform_name)`
- **`_get_platform_checkers()`**: Lazy import function to avoid circular dependencies
- Platform identification for YouTube, Instagram, TikTok, Twitter/X, Facebook

### 3. Package Integration (`bot/downloaders/__init__.py`)

Updated package exports with clean public API:

- Added `PlatformRouter`, `RouteResult` exports
- Added convenience functions: `get_downloader_for_url()`, `route_url()`
- Added `classify_url_enhanced` to URL detector exports
- Updated module docstring with Quick Start examples

## Key Features

| Feature | Description |
|---------|-------------|
| **Automatic Routing** | URL automatically routed to correct downloader |
| **Priority System** | Platform-specific handlers checked first, then fallbacks |
| **Confidence Levels** | High (platform match), Medium (yt-dlp), Low (HTML) |
| **Downloader Caching** | Platform downloader instances cached for reuse |
| **Convenience Functions** | `route_url()` and `get_downloader_for_url()` for simple usage |
| **HTML Page Support** | Can extract and download videos from HTML pages |

## Usage Examples

```python
from bot.downloaders import PlatformRouter, route_url, get_downloader_for_url

# Method 1: Using PlatformRouter directly
router = PlatformRouter()
result = await router.route('https://youtube.com/watch?v=...')
print(f"Platform: {result.platform}, Confidence: {result.confidence}")
download_result = await result.downloader.download(url, options)

# Method 2: Using route_url convenience function
result = await route_url('https://instagram.com/p/...')
download_result = await result.downloader.download(url, options)

# Method 3: Using get_downloader_for_url for simple cases
downloader = await get_downloader_for_url('https://tiktok.com/...')
download_result = await downloader.download(url, options)
```

## Routing Behavior

| URL Type | Selected Downloader | Confidence |
|----------|---------------------|------------|
| YouTube URLs | YouTubeDownloader | high |
| Instagram URLs | InstagramDownloader | high |
| TikTok URLs | TikTokDownloader | high |
| Twitter/X URLs | TwitterDownloader | high |
| Facebook URLs | FacebookDownloader | high |
| Direct video URLs (.mp4, etc.) | GenericDownloader | high |
| Other yt-dlp supported | YtDlpDownloader | medium |
| HTML pages with videos | HTMLExtractorAdapter | low |
| Unsupported | Raises UnsupportedURLError | - |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check

```bash
# Check created files exist
[ -f "bot/downloaders/platform_router.py" ] && echo "FOUND: bot/downloaders/platform_router.py" || echo "MISSING"

# Check commits exist
git log --oneline --all | grep -q "467aa80" && echo "FOUND: 467aa80" || echo "MISSING"
git log --oneline --all | grep -q "3618761" && echo "FOUND: 3618761" || echo "MISSING"
git log --oneline --all | grep -q "0187154" && echo "FOUND: 0187154" || echo "MISSING"
```

## Self-Check: PASSED

## Commits

| Hash | Message |
|------|---------|
| 467aa80 | feat(10-05): implement PlatformRouter with priority-based routing |
| 3618761 | feat(10-05): update URL detector with platform patterns |
| 0187154 | feat(10-05): update package exports with router integration |

## Performance Considerations

- **Downloader caching**: Platform downloader instances are cached to avoid repeated instantiation
- **Lazy imports**: Platform checkers imported lazily to avoid circular dependencies and reduce startup time
- **Fast path**: Platform-specific URL patterns checked first before attempting yt-dlp validation

## Next Steps

The platform router is complete and ready for integration with:
- Download management system (Phase 11)
- Telegram bot message handlers (Phase 12)
- Progress tracking and concurrent downloads
