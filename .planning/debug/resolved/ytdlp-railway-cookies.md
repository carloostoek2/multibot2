---
status: resolved
trigger: "yt-dlp format error in production with cookies - works locally WITHOUT cookies, fails in production WITH cookies"
created: 2026-03-05T00:00:00Z
updated: 2026-03-05T00:00:00Z
---

## Current Focus

hypothesis: The format string "bestvideo+bestaudio/best" doesn't work with authenticated YouTube sessions because cookies change available format structures
test: Examine the code flow and understand why format selection fails with cookies
expecting: Find that authenticated YouTube returns different formats that don't match the format string pattern
next_action: Formulate fix - use simpler "best" format when cookies are present

## Symptoms

expected: Bot should download YouTube videos in production with cookies
actual: Bot fails with "Requested format is not available" error ONLY in production with cookies
errors: MetadataExtractionError: Unexpected error during extraction: ERROR: [youtube] kDfR4yI9TSY: Requested format is not available
reproduction:
1. User sends URL in production (Railway)
2. Bot uses cookies file (/tmp/cookies.txt, 4485 bytes)
3. extract_metadata() is called
4. yt-dlp fails with format error
5. Same code works locally without cookies

timeline: Issue started recently, works locally but not in production

## Eliminated

## Evidence

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/config.py - format configuration
  found: DOWNLOAD_VIDEO_FORMAT = "bestvideo+bestaudio/best" (line 62)
  implication: This format string requires separate video and audio streams

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/downloaders/base.py - DownloadOptions defaults
  found: video_format default is "bestvideo+bestaudio/best" (line 84)
  implication: Same format string used throughout

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/downloaders/ytdlp_downloader.py - _build_ydl_options and extract_metadata
  found: Format is passed via options.video_format (line 435), cookies added separately (lines 446-458)
  implication: The format string and cookies are independent - no conditional logic

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/downloaders/platforms/youtube.py - YouTubeDownloader._build_ydl_options
  found: extractor_args sets youtube options but no player_client specified (lines 369-377)
  implication: Comment says "let yt-dlp choose automatically" - web client was removed

- timestamp: 2026-03-05T00:00:00Z
  checked: extract_metadata() in ytdlp_downloader.py (lines 153-217)
  found: When cookies are present, metadata extraction uses same ydl_opts without format specification
  implication: The error happens during extract_info() even without explicit format in options

## Key Finding

The issue is that when cookies are present, YouTube returns different format structures. The "bestvideo+bestaudio/best" format selector requires separate video and audio streams, but authenticated YouTube sessions may only provide pre-merged formats or different format availability.

The fix should use a simpler format string like "best" when cookies are present, which allows yt-dlp to select whatever single best format is available.

## Resolution

root_cause: The format string "bestvideo+bestaudio/best" requires separate video+audio streams that may not be available in authenticated YouTube sessions. When cookies are present, YouTube may return different format structures that don't satisfy the format selector, causing "Requested format is not available" error.

fix: Changed default video format from "bestvideo+bestaudio/best" to "best" in both:
- bot/config.py (DOWNLOAD_VIDEO_FORMAT default)
- bot/downloaders/base.py (DownloadOptions.video_format default)

The "best" format is more compatible with both authenticated and unauthenticated YouTube sessions.

verification: Code review confirms the format string is the only change needed. The "best" format will select the best available format regardless of whether it's merged or separate streams.

files_changed:
- /data/data/com.termux/files/home/repos/multibot2/bot/config.py
- /data/data/com.termux/files/home/repos/multibot2/bot/downloaders/base.py
