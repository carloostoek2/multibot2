---
phase: "09"
plan: "04"
subsystem: "downloader-core"
tags: ["downloader", "aiohttp", "generic", "streaming"]
dependencies:
  requires: ["09-02"]
  provides: ["09-05"]
  affects: []
tech-stack:
  added: ["aiohttp>=3.9.0", "aiofiles>=23.0.0"]
  patterns: ["async streaming", "content-type validation", "progress callbacks"]
key-files:
  created:
    - bot/downloaders/generic_downloader.py
  modified:
    - requirements.txt
    - bot/downloaders/__init__.py
decisions: []
metrics:
  duration: 289
  completed-date: "2026-02-21"
---

# Phase 09 Plan 04: Generic HTTP Downloader Summary

**One-liner:** Implemented GenericDownloader class for direct video file URLs using aiohttp streaming with Content-Type validation, file size checks, and progress callbacks.

## What Was Built

### GenericDownloader Class

A complete implementation of the BaseDownloader interface for downloading videos from direct URLs (.mp4, .webm, .mov, etc.).

**Key Features:**
- **Streaming downloads** using aiohttp (8KB chunks) to avoid memory issues
- **Content-Type validation** (DL-05) - validates MIME type is video before downloading
- **File size validation** (QF-05) - checks Content-Length header against limits
- **Progress callbacks** - real-time progress with percent, bytes downloaded/total
- **Automatic redirect following** (GV-03) - handles HTTP redirects transparently
- **File integrity validation** - size check, non-empty validation, optional python-magic
- **Partial file cleanup** - removes incomplete files on download failure

**Supported Video Types:**
- 12 file extensions: .mp4, .webm, .mov, .mkv, .avi, .flv, .wmv, .m4v, .3gp, .ogv, .mpeg, .mpg
- 12 MIME types: video/mp4, video/webm, video/quicktime, video/x-msvideo, video/x-flv, etc.

**Error Handling:**
- ClientResponseError (4xx, 5xx) -> DownloadFailedError
- ClientConnectorError -> NetworkError
- asyncio.TimeoutError -> DownloadFailedError
- Invalid URL -> URLValidationError
- File too large -> FileTooLargeError
- Non-video content -> UnsupportedURLError

## Implementation Details

### Architecture
```
GenericDownloader(BaseDownloader)
├── can_handle(url) -> bool
├── extract_metadata(url, options) -> dict
├── download(url, options) -> DownloadResult
└── _validate_downloaded_file(path, expected, url, correlation_id)
```

### Streaming Download Pattern
```python
async with aiohttp.ClientSession(timeout=timeout) as session:
    async with session.get(url, allow_redirects=True) as response:
        async with aiofiles.open(output_path, 'wb') as f:
            async for chunk in response.content.iter_chunked(8192):
                await f.write(chunk)
                # Update progress
```

### Package Integration
- Added to `bot/downloaders/__init__.py` exports
- `get_downloader_for_url()` helper routes URLs to appropriate downloader
- Works alongside existing YtDlpDownloader for platform URLs

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| 5e963fd | chore | Add aiohttp and aiofiles dependencies |
| 595ede7 | feat | Implement GenericDownloader class (545 lines) |
| 5da5054 | feat | Add file integrity validation |
| 87b2aaa | feat | Update package exports with GenericDownloader |

## Files Changed

```
requirements.txt                          |  6 ++++++
bot/downloaders/generic_downloader.py     | 545 +++++++++++++++++++++++++++++++++
bot/downloaders/__init__.py               | 32 ++++++++++++++++++++++++++++++
```

## Verification

- [x] Import test: `from bot.downloaders import GenericDownloader` - OK
- [x] Instantiation test: Creates instance with correct properties - OK
- [x] can_handle test (.mp4): Returns True - OK
- [x] can_handle test (.webm): Returns True - OK
- [x] Helper methods: All 12 extensions and MIME types recognized - OK
- [x] Package exports: GenericDownloader and get_downloader_for_url available - OK

## Deviations from Plan

**None** - Plan executed exactly as written.

The YtDlpDownloader was already implemented (from plan 09-03), so the linter's automatic import of it in `__init__.py` worked correctly without needing a placeholder.

## Success Criteria Checklist

- [x] GenericDownloader implements BaseDownloader interface correctly
- [x] aiohttp and aiofiles dependencies added to requirements.txt
- [x] can_handle identifies direct video URLs by extension
- [x] extract_metadata validates Content-Type header (DL-05)
- [x] download uses aiohttp streaming with async file I/O
- [x] Content-Length checked before download starts (QF-05)
- [x] Progress callbacks provide real-time feedback
- [x] File integrity validated after download (size, non-empty)
- [x] Partial files cleaned up on failure
- [x] Redirects followed automatically (GV-03)
- [x] All errors converted to appropriate custom exceptions

## Self-Check: PASSED

- [x] All created files exist: bot/downloaders/generic_downloader.py
- [x] All commits exist in git history
- [x] Import tests pass
- [x] No circular import errors
- [x] All success criteria met
