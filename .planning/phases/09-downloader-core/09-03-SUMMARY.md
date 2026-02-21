---
phase: "09"
plan: "03"
subsystem: "downloader-core"
tags: ["yt-dlp", "downloader", "video", "youtube", "instagram", "tiktok"]
requires: ["09-02"]
provides: ["09-04", "09-05", "10-01", "10-02", "10-03", "10-04", "10-05"]
affects: ["bot/downloaders/ytdlp_downloader.py", "bot/downloaders/__init__.py", "requirements.txt"]
tech-stack:
  added: ["yt-dlp>=2026.2.4"]
  patterns: ["thread-pool-async", "progress-hooks", "postprocessor-chain"]
key-files:
  created:
    - "bot/downloaders/ytdlp_downloader.py"
  modified:
    - "bot/downloaders/__init__.py"
    - "requirements.txt"
decisions:
  - "Use yt-dlp's extract_info with process=False for fast can_handle checks"
  - "Run all yt-dlp operations in thread pool to avoid blocking event loop"
  - "Use asyncio.run_coroutine_threadsafe for progress callbacks from worker threads"
  - "Pre-download file size validation to prevent wasted bandwidth"
  - "Format selection string includes filesize filter: best[filesize<50M]/best"
metrics:
  duration: "20 minutes"
  tasks: 4
  files-created: 1
  files-modified: 2
  lines-added: 558
---

# Phase 9 Plan 3: yt-dlp Downloader Implementation Summary

**One-liner:** Implemented YtDlpDownloader class for downloading videos from 1000+ platforms (YouTube, Instagram, TikTok, Twitter/X, Facebook) using yt-dlp's Python API with proper async handling.

## What Was Built

### YtDlpDownloader Class (`bot/downloaders/ytdlp_downloader.py`)

A complete downloader implementation that:

1. **Implements BaseDownloader Interface**
   - `name` property: "yt-dlp Downloader"
   - `supported_platforms`: YouTube, Instagram, TikTok, Twitter/X, Facebook, 1000+ sites
   - `can_handle()`: Uses yt-dlp's extract_info with process=False for fast URL validation
   - `extract_metadata()`: Extracts title, duration, uploader, thumbnail, filesize, formats, description
   - `download()`: Full download with progress callbacks and audio extraction

2. **Async Architecture**
   - All yt-dlp operations run in thread pool via `asyncio.to_thread()`
   - Event loop reference stored in `__init__` for thread-safe progress callbacks
   - Progress hooks use `asyncio.run_coroutine_threadsafe()` to schedule callbacks

3. **File Size Validation (QF-05)**
   - Pre-download size check using metadata extraction
   - Format selection string: `best[filesize<50M]/best` prefers files under 50MB
   - Raises `FileTooLargeError` with formatted size information

4. **Audio Extraction (QF-03)**
   - FFmpegExtractAudio postprocessor for audio-only downloads
   - Configurable codec (mp3, m4a, etc.) and bitrate (320k, 192k, etc.)

5. **Error Handling (EH-01, EH-03)**
   - `ExtractorError` → `MetadataExtractionError`
   - `DownloadError` → `DownloadFailedError` or `NetworkError`
   - All errors include correlation ID for request tracing (DM-02)

### Package Integration (`bot/downloaders/__init__.py`)

- Added `YtDlpDownloader` to imports
- Updated `get_downloader_for_url()` to use YtDlpDownloader as fallback
- Added to `__all__` exports

### Dependencies (`requirements.txt`)

- Added `yt-dlp>=2026.2.4` for platform video downloads
- Added `aiohttp>=3.9.0` and `aiofiles>=23.0.0` for async HTTP operations
- Added `ffmpeg-python>=0.2.0` for audio extraction

## Key Implementation Details

### Thread Pool Pattern
```python
# All yt-dlp operations run in thread pool
def _check() -> bool:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=False, process=False)
        return True

return await asyncio.to_thread(_check)
```

### Progress Hook Pattern
```python
def _hook(d: dict) -> None:
    progress = {
        'percent': downloaded / total * 100,
        'status': d['status'],
        'correlation_id': correlation_id,
    }
    asyncio.run_coroutine_threadsafe(callback(progress), self._loop)
```

### Format Selection Strategy
```python
# Prefer formats under 50MB, fallback to best available
video_format: str = "best[filesize<50M]/best"
audio_format: str = "bestaudio[filesize<50M]/bestaudio"
```

## Verification Results

All tests passed:
- Import test: `from bot.downloaders import YtDlpDownloader` ✓
- Instantiation test: Properties correctly set ✓
- can_handle test: YouTube URLs supported, invalid URLs rejected ✓
- DownloadOptions test: Format strings include filesize limits ✓

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] `/data/data/com.termux/files/home/repos/multibot2/bot/downloaders/ytdlp_downloader.py` exists (558 lines)
- [x] `/data/data/com.termux/files/home/repos/multibot2/bot/downloaders/__init__.py` exports YtDlpDownloader
- [x] `/data/data/com.termux/files/home/repos/multibot2/requirements.txt` contains yt-dlp>=2026.2.4
- [x] Import test passes: `from bot.downloaders import YtDlpDownloader`
- [x] All commits created and verified

## Commits

- `3d4fb3c`: feat(09-03): implement YtDlpDownloader class
- `bc9e3c1`: feat(09-03): export YtDlpDownloader from package

## Next Steps

Plan 09-04 (Generic HTTP Downloader) can now proceed. YtDlpDownloader provides the platform-specific download capability that will be used alongside GenericDownloader for direct video URLs.
