# Phase 9: Downloader Core Infrastructure - Research

**Researched:** 2026-02-21
**Domain:** Media Downloading (yt-dlp, Telegram Bot API, Async Processing)
**Confidence:** HIGH

## Summary

Phase 9 establishes the foundation for media downloading in a Telegram bot environment. The core technology is **yt-dlp**, the community-maintained fork of youtube-dl with active development and broad platform support. For a Python-based aiogram 3.x bot, the architecture must handle URL auto-detection, async download processing, metadata extraction, and Telegram's file size constraints.

The standard approach uses yt-dlp's Python API (not CLI subprocess) for metadata extraction via `extract_info(url, download=False)`, followed by controlled downloads with progress hooks. For generic video URLs (direct .mp4, .webm files), standard HTTP libraries (aiohttp) are more appropriate than yt-dlp. Telegram Bot API imposes strict limits: 50MB upload limit for bots using the standard API, 20MB limit for `getFile` downloads.

**Primary recommendation:** Use yt-dlp Python API for platform-specific URLs, aiohttp for generic video URLs, implement async download workers with progress callbacks, and enforce Telegram file size limits before download begins.

---

## User Constraints (from Prior Decisions)

### Locked Decisions
1. **yt-dlp for platform downloads** — Mature library, broad platform support
2. **Auto-detect URLs in messages** — No /download command required
3. **Generic video URL support** — Any URL with video file downloadable
4. **Unlimited concurrent downloads** — Individual tracking per download
5. **Real-time progress (5-10%)** — Visual feedback with percentage bar

### Claude's Discretion
- Download worker architecture (queue vs direct)
- Progress reporting implementation details
- Error message formatting
- File cleanup strategy

### Deferred Ideas (OUT OF SCOPE)
- Specific platform handlers (YouTube, Instagram, TikTok, Twitter/X, Facebook) — these are Phase 10+
- Advanced post-processing beyond format conversion
- Download history/persistence

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yt-dlp | >=2026.2.4 | Platform video downloading | Industry standard, 1000+ sites, active development, Python API |
| aiohttp | >=3.9.0 | Generic video URL downloading | Native async, efficient for direct file downloads |
| aiofiles | >=23.0.0 | Async file operations | Non-blocking file I/O for large downloads |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ffmpeg-python | >=0.2.0 | Format conversion wrapper | When format conversion needed post-download |
| python-magic | >=0.4.27 | File type validation | Validate downloaded file integrity |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yt-dlp | youtube-dl | yt-dlp is actively maintained, youtube-dl is stale |
| yt-dlp | gallery-dl | gallery-dl better for galleries/albums, yt-dlp better for video platforms |
| aiohttp | httpx | httpx has sync+async, aiohttp is lighter and proven for file downloads |

**Installation:**
```bash
pip install yt-dlp aiohttp aiofiles
# Optional but recommended:
pip install ffmpeg-python python-magic
```

---

## Architecture Patterns

### Recommended Project Structure
```
bot/
├── __init__.py
├── downloaders/
│   ├── __init__.py          # Downloader exports
│   ├── base.py              # Base downloader interface
│   ├── ytdlp_downloader.py  # yt-dlp implementation
│   ├── generic_downloader.py # Direct HTTP implementation
│   └── url_detector.py      # URL detection and routing
├── handlers.py              # Message handlers (URL auto-detect)
└── ...
```

### Pattern 1: URL Detection and Routing
**What:** Detect URLs in messages, classify by type (platform vs generic), route to appropriate downloader.
**When to use:** All URL-containing messages that might have downloadable media.
**Example:**
```python
# Source: aiogram docs + Telegram Bot API
from aiogram import Router, F
from aiogram.types import Message
import re

URL_PATTERN = re.compile(r'https?://\S+')

@router.message(F.text.regexp(URL_PATTERN))
async def handle_url_message(message: Message):
    urls = URL_PATTERN.findall(message.text)
    for url in urls:
        downloader = get_downloader_for_url(url)  # Route to yt-dlp or generic
        await process_download(message, url, downloader)
```

### Pattern 2: Async Download with Progress Hooks
**What:** Use yt-dlp's progress hooks with asyncio to provide non-blocking downloads with progress updates.
**When to use:** Platform downloads where progress feedback is required.
**Example:**
```python
# Source: yt-dlp YoutubeDL.py + asyncio patterns
import yt_dlp
import asyncio
from typing import Callable

class YtDlpDownloader:
    def __init__(self, progress_callback: Callable[[dict], None]):
        self.progress_callback = progress_callback
        self._loop = asyncio.get_event_loop()

    async def download(self, url: str, output_path: str):
        def _hook(d):
            if d['status'] == 'downloading':
                asyncio.run_coroutine_threadsafe(
                    self.progress_callback({
                        'percent': d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100,
                        'speed': d.get('speed'),
                        'eta': d.get('eta')
                    }),
                    self._loop
                )

        ydl_opts = {
            'format': 'best[filesize<50M]/best',  # Telegram limit
            'outtmpl': output_path,
            'progress_hooks': [_hook],
        }

        # Run yt-dlp in thread pool (it's blocking)
        return await asyncio.to_thread(self._download_sync, url, ydl_opts)

    def _download_sync(self, url: str, opts: dict):
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.download([url])
```

### Pattern 3: Metadata Extraction Without Download
**What:** Extract video info (title, duration, size) before downloading to validate and present to user.
**When to use:** All downloads — validate URL, check file size, show preview before committing.
**Example:**
```python
# Source: yt-dlp YoutubeDL.py source code
import yt_dlp

async def extract_metadata(url: str) -> dict:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False, process=True)
            return {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader'),
                'thumbnail': info.get('thumbnail'),
                'filesize': info.get('filesize') or info.get('filesize_approx'),
                'formats': info.get('formats', []),
            }

    return await asyncio.to_thread(_extract)
```

### Pattern 4: Generic Video URL Download
**What:** For direct video file URLs (.mp4, .webm, .mov), use aiohttp with streaming and progress tracking.
**When to use:** URLs ending in video extensions or Content-Type: video/* responses.
**Example:**
```python
# Source: aiohttp docs + Python asyncio patterns
import aiohttp
import aiofiles
from pathlib import Path

async def download_generic_video(
    url: str,
    output_path: str,
    progress_callback: Callable[[int, int], None],
    max_size: int = 50 * 1024 * 1024  # 50MB
) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()

            total = int(response.headers.get('content-length', 0))
            if total > max_size:
                raise FileTooLargeError(f"File size {total} exceeds limit {max_size}")

            downloaded = 0
            async with aiofiles.open(output_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    await progress_callback(downloaded, total)

    return output_path
```

### Anti-Patterns to Avoid
- **Running yt-dlp in main thread:** yt-dlp is blocking; always use `asyncio.to_thread()` or thread pool
- **Downloading before size check:** Always extract metadata first to check filesize against Telegram limits
- **Storing downloads in memory:** Stream to disk; don't buffer large files in RAM
- **Ignoring format selection:** Without format selection, yt-dlp may download unnecessarily large files

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Platform video downloading | Custom scrapers for YouTube, Instagram, etc. | yt-dlp | Sites change constantly; yt-dlp has 1000+ extractors, active maintenance, handles rate limits, cookies, geo-restriction |
| URL validation regex | Complex regex for all platforms | yt-dlp `suitable()` + simple regex for generics | yt-dlp extractors have `_VALID_URL` patterns; don't duplicate |
| Format conversion | Direct ffmpeg subprocess calls | yt-dlp postprocessors or ffmpeg-python | yt-dlp handles format selection, merging, metadata; ffmpeg-python provides clean Python API |
| File type detection | Extension-based guessing | python-magic | libmagic identifies actual file content, not just extensions |
| Progress tracking | Manual byte counting in loops | yt-dlp progress hooks / aiohttp content.iter_chunked() | Built-in solutions handle edge cases (resumes, redirects, compression) |

**Key insight:** Video downloading is a domain of constant change. Sites modify their anti-bot measures, URL schemes, and delivery formats regularly. A custom solution requires ongoing maintenance that dwarfs the initial development effort. yt-dlp's community maintenance is its primary value.

---

## Common Pitfalls

### Pitfall 1: File Size Limit Violations
**What goes wrong:** Download completes successfully but Telegram rejects the file because it exceeds 50MB (standard API) or 20MB (getFile).
**Why it happens:** yt-dlp downloads the best quality by default, which often exceeds Telegram limits.
**How to avoid:**
1. Extract metadata first with `extract_info()`
2. Check `filesize` or `filesize_approx` before downloading
3. Use format selection to limit size: `'format': 'best[filesize<50M]/best'`
4. For generic URLs, check Content-Length header before streaming

**Warning signs:** Download succeeds but `send_video`/`send_document` raises `BadRequest: file is too big`

### Pitfall 2: Blocking the Event Loop
**What goes wrong:** Bot becomes unresponsive during downloads because yt-dlp runs in the main thread.
**Why it happens:** yt-dlp performs network I/O and processing synchronously.
**How to avoid:**
```python
# WRONG
with yt_dlp.YoutubeDL(opts) as ydl:
    ydl.download([url])  # Blocks entire bot

# CORRECT
await asyncio.to_thread(download_sync, url, opts)  # Runs in thread pool
```

**Warning signs:** Other users' messages not processed during downloads; high latency on simple commands

### Pitfall 3: Incomplete Downloads
**What goes wrong:** File appears downloaded but is corrupted or truncated.
**Why it happens:** Network interruption, process termination, or partial content handling.
**How to avoid:**
1. Validate file integrity with size check or hash when available
2. Use python-magic to verify file type matches extension
3. Implement retry logic for transient failures
4. Clean up partial files on failure

**Warning signs:** FFmpeg errors when processing "downloaded" files; files that won't play

### Pitfall 4: Rate Limiting and Blocking
**What goes wrong:** IP gets temporarily blocked by platforms (especially YouTube) causing 429/403 errors.
**Why it happens:** Too many requests, missing cookies/User-Agent, or detected as bot.
**How to avoid:**
1. Use yt-dlp's built-in rate limiting: `'sleep_interval_requests': 1`
2. Set realistic User-Agent: `'user_agent': 'Mozilla/5.0 ...'`
3. Pass cookies from browser for authenticated content: `'cookiesfrombrowser': ('firefox',)`
4. Handle `ExtractorError` gracefully with user-friendly messages

**Warning signs:** HTTP 429/403 errors; "Sign in to confirm you're not a bot" messages

### Pitfall 5: URL Entity Extraction Errors
**What goes wrong:** URLs in messages are not properly extracted, especially with `text_link` entities (clickable text with hidden URL).
**Why it happens:** Only checking `message.text` for URLs misses `text_link` entities where the visible text differs from the URL.
**How to avoid:**
```python
# Check both plain text URLs and text_link entities
urls = []
if message.entities:
    for entity in message.entities:
        if entity.type == 'url':
            urls.append(entity.extract_from(message.text))
        elif entity.type == 'text_link':
            urls.append(entity.url)
```

**Warning signs:** URLs with custom link text (e.g., "Click here") not detected

---

## Code Examples

### URL Detection in aiogram 3.x
```python
# Source: aiogram docs + Telegram Bot API
from aiogram import Router, F
from aiogram.types import Message
import re

router = Router()
URL_REGEX = re.compile(r'https?://\S+')

@router.message(F.text.regexp(URL_REGEX))
async def handle_url(message: Message):
    """Handle messages containing URLs."""
    urls = []

    # Extract from entities (handles text_link)
    if message.entities:
        for entity in message.entities:
            if entity.type == 'url':
                urls.append(entity.extract_from(message.text))
            elif entity.type == 'text_link':
                urls.append(entity.url)

    # Fallback to regex for any missed URLs
    if not urls:
        urls = URL_REGEX.findall(message.text)

    for url in urls:
        await process_url(message, url)
```

### Format Selection for Telegram Compatibility
```python
# Source: yt-dlp docs + Telegram Bot API limits
ydl_opts = {
    # Prefer MP4/H.264 for video compatibility
    'format': 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best',
    'format_sort': ['res', 'codec:h264'],

    # Audio extraction options
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],
}
```

### Progress Hook with Telegram Updates
```python
# Source: yt-dlp source + aiogram patterns
from aiogram.types import Message
import asyncio

class DownloadProgressTracker:
    def __init__(self, message: Message, update_interval: float = 5.0):
        self.message = message
        self.update_interval = update_interval
        self.last_update = 0
        self._loop = asyncio.get_event_loop()

    def _create_hook(self):
        def hook(d):
            if d['status'] != 'downloading':
                return

            now = asyncio.get_event_loop().time()
            if now - self.last_update < self.update_interval:
                return

            self.last_update = now
            percent = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100

            # Schedule update in main thread
            asyncio.run_coroutine_threadsafe(
                self._update_message(percent),
                self._loop
            )

        return hook

    async def _update_message(self, percent: float):
        bar_length = 20
        filled = int(bar_length * percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        await self.message.edit_text(f"Downloading: [{bar}] {percent:.1f}%")
```

### Error Handling for yt-dlp
```python
# Source: yt-dlp source code patterns
import yt_dlp
from yt_dlp.utils import ExtractorError, DownloadError

async def safe_download(url: str, opts: dict) -> dict:
    """Download with comprehensive error handling."""
    def _download():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {'success': True, 'info': info}
        except ExtractorError as e:
            if 'unavailable' in str(e).lower():
                return {'success': False, 'error': 'Content unavailable or private'}
            elif 'geo' in str(e).lower():
                return {'success': False, 'error': 'Content blocked in your region'}
            else:
                return {'success': False, 'error': f'Extraction failed: {e}'}
        except DownloadError as e:
            return {'success': False, 'error': f'Download failed: {e}'}
        except Exception as e:
            return {'success': False, 'error': f'Unexpected error: {e}'}

    return await asyncio.to_thread(_download)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| youtube-dl | yt-dlp | 2021+ | yt-dlp actively maintained, faster updates, more sites |
| subprocess calls to yt-dlp | Python API (YoutubeDL class) | Always preferred | Better error handling, progress hooks, no shell escaping issues |
| urllib/requests for downloads | aiohttp for async | Python 3.7+ | Non-blocking I/O, better for concurrent downloads |
| Synchronous file I/O | aiofiles | Modern asyncio | Prevents blocking on disk writes during download |
| Manual cookie handling | yt-dlp `--cookies-from-browser` | yt-dlp feature | Automatic authenticated downloads |

**Deprecated/outdated:**
- youtube-dl: Effectively unmaintained as of 2021, use yt-dlp
- pytube: Unreliable, frequent breaking changes, use yt-dlp
- you-get: Less active than yt-dlp, fewer sites supported

---

## Open Questions

1. **Concurrent Download Limit Strategy**
   - What we know: Unlimited concurrent downloads requested, but Telegram API and system resources impose practical limits
   - What's unclear: Whether to implement semaphore-based limiting or queue-based processing
   - Recommendation: Start with asyncio.Semaphore(5) for downloads, monitor resource usage, adjust based on deployment environment

2. **Partial Download Resumption**
   - What we know: yt-dlp supports `--continue` for resuming interrupted downloads
   - What's unclear: Whether to implement resumption for failed downloads or restart fresh
   - Recommendation: Implement simple retry (3 attempts) without resumption for Phase 9; add resumption if network instability becomes an issue

3. **Cookie Handling for Private Content**
   - What we know: yt-dlp can extract cookies from browsers
   - What's unclear: Whether users expect to download private/authenticated content
   - Recommendation: Document limitation in Phase 9; add cookie configuration in later phase if requested

---

## Sources

### Primary (HIGH confidence)
- yt-dlp GitHub repository (YoutubeDL.py source) - Python API patterns, progress hooks, error handling
- yt-dlp pyproject.toml - Dependencies, Python version requirements (>=3.10)
- yt-dlp README.md - Installation, format selection, postprocessors
- Python 3.14 asyncio subprocess docs - Async patterns, thread safety warnings
- aiogram 3.x docs - MessageEntity types, magic filters, URL detection

### Secondary (MEDIUM confidence)
- Telegram Bot API docs - File size limits (50MB upload, 20MB getFile)
- Telegram Bot FAQ - Rate limiting guidance (1 msg/sec in chats, 20/min in groups)
- yt-dlp FAQ - Common errors (403/429 handling, ffmpeg codec issues)

### Tertiary (LOW confidence)
- Community patterns for yt-dlp + aiogram integration (not verified with official sources)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - yt-dlp is de facto standard, aiohttp is proven for async HTTP
- Architecture: HIGH - Patterns verified with official source code and documentation
- Pitfalls: HIGH - Derived from yt-dlp source code error handling and Telegram API documentation

**Research date:** 2026-02-21
**Valid until:** 2026-05-21 (yt-dlp releases frequently; verify format selection options haven't changed)
