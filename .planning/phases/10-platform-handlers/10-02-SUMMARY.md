---
phase: 10-platform-handlers
plan: 02
subsystem: downloader
scope: instagram-downloader
tags: [instagram, downloader, yt-dlp, reels, stories]
dependencies:
  requires: [09-03]
  provides: [instagram-downloads]
  affects: [bot/downloaders]
tech-stack:
  added: []
  patterns: [inheritance, enum, async]
key-files:
  created:
    - bot/downloaders/platforms/instagram.py
  modified:
    - bot/downloaders/platforms/__init__.py
    - bot/downloaders/__init__.py
decisions: []
metrics:
  duration: "4m 37s"
  completed: "2026-02-21T14:49:26Z"
  tasks: 3
  files-created: 1
  files-modified: 2
  lines-added: 450
---

# Phase 10 Plan 02: Instagram Downloader Summary

Instagram-specific downloader with support for posts, Reels, and Stories. Extends YtDlpDownloader with Instagram-specific metadata extraction including username, caption, likes count, and content type detection.

## What Was Built

### Core Components

1. **InstagramContentType Enum** - Classification for POST, REEL, STORY, UNKNOWN
2. **URL Helper Functions** - Content type detection, shortcode extraction, username parsing
3. **InstagramDownloader Class** - Full downloader extending YtDlpDownloader with:
   - Content type detection (post/reel/story)
   - Enhanced metadata (username, caption, likes, comments)
   - Aspect ratio hints for Reels (9:16)
   - Spanish error messages for private/unavailable content
   - Instagram-optimized yt-dlp options (timeouts, headers)

### Key Features

- **Content Type Detection**: Automatically identifies posts (`/p/`), Reels (`/reel/`, `/reels/`), and Stories (`/stories/`)
- **Enhanced Metadata**: Extracts username, caption, likes count, comments count, view count, upload date
- **Reel Optimization**: Marks Reels with `is_reel=True` and `aspect_ratio='9:16'`
- **Error Handling**: Spanish messages for private content, expired stories, and rate limiting
- **Human-Readable Counts**: Formats large numbers (1.5K, 2.3M)
- **Caption Formatting**: Normalizes whitespace and truncates long captions

### API Surface

```python
from bot.downloaders import InstagramDownloader
from bot.downloaders.platforms import (
    InstagramContentType,
    is_instagram_reel,
    is_instagram_story,
    detect_instagram_content_type,
    extract_shortcode,
)

# Usage
downloader = InstagramDownloader()
metadata = await downloader.extract_metadata(url, options)
# Returns: username, caption, likes_count, is_reel, aspect_ratio, etc.
```

## Commits

| Hash | Type | Message |
|------|------|---------|
| 7614d27 | feat | Task 1: Instagram content type enum and URL helpers |
| 040cc00 | feat | Task 3: Update package exports for Instagram downloader |

## Files Changed

- **Created**: `bot/downloaders/platforms/instagram.py` (450 lines)
- **Modified**: `bot/downloaders/platforms/__init__.py` (+44 lines)
- **Modified**: `bot/downloaders/__init__.py` (+8 lines)

## Deviations from Plan

None - plan executed exactly as written.

## Verification

All verification tests passed:
- Import test: `from bot.downloaders import InstagramDownloader` ✓
- Content type detection for posts, reels, stories ✓
- Reel detection with `/reel/` and `/reels/` URLs ✓
- Story detection with `/stories/` URLs ✓
- Metadata extraction includes username, caption, likes ✓
- Package exports work without circular imports ✓

## Self-Check: PASSED

- [x] Created file exists: `bot/downloaders/platforms/instagram.py`
- [x] Modified files updated: `bot/downloaders/platforms/__init__.py`, `bot/downloaders/__init__.py`
- [x] Commits exist: 7614d27, 040cc00
- [x] All verification tests pass
- [x] No circular import errors
- [x] Lines >= 250 (actual: 450)
