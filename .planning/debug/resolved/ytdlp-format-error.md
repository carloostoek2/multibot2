---
status: resolved
trigger: "ytdlp-format-error: Bot fails to download YouTube video with error 'Requested format is not available'. Error occurs repeatedly even after multiple fixes attempted."
created: 2026-03-05T00:00:00Z
updated: 2026-03-05T00:00:00Z
---

## Current Focus

hypothesis: The error is caused by 'player_client: [web]' in extractor_args in YouTubeDownloader._build_ydl_options()

test: Confirmed - removing player_client fixes the issue

expecting: Removing or changing player_client will fix the download

next_action: Fix the code by removing player_client from extractor_args

## Symptoms

expected: Bot should download YouTube videos successfully
actual: All attempts fail with "Requested format is not available" error
errors: MetadataExtractionError: Unexpected error during extraction: ERROR: [youtube] kDfR4yI9TSY: Requested format is not available
reproduction:
1. User sends URL: https://youtu.be/kDfR4yI9TSY
2. Bot selects format "video" (not audio)
3. extract_metadata() is called with format "bestvideo+bestaudio/best"
4. Error occurs immediately
5. Retry handler attempts 4 times with exponential backoff, all fail

timeline: Issue started recently, multiple attempted fixes have not resolved it

## Eliminated

- hypothesis: The format string is wrong
  evidence: Tested "bestvideo+bestaudio/best" manually - it works fine for the same video
  timestamp: 2026-03-05

- hypothesis: extract_metadata() passes wrong format
  evidence: Code review shows extract_metadata() does NOT pass any format option to yt-dlp
  timestamp: 2026-03-05

- hypothesis: Empty cookies file causes the error
  evidence: Code already checks for empty cookies files and skips them
  timestamp: 2026-03-05

## Evidence

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/downloaders/ytdlp_downloader.py extract_metadata() method
  found: extract_metadata() does NOT pass any format option to yt-dlp. It only uses quiet=True and no_warnings=True
  implication: The "Requested format is not available" error is NOT coming from a format specification in extract_metadata()

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/downloaders/ytdlp_downloader.py _build_ydl_options() method
  found: Format is set via ydl_opts["format"] = options.video_format (line 435), which defaults to "bestvideo+bestaudio/best"
  implication: Format is only specified during download(), not during extract_metadata()

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/downloaders/base.py DownloadOptions default values
  found: video_format: str = "bestvideo+bestaudio/best" (line 84)
  implication: This is the format string being used

- timestamp: 2026-03-05T00:00:00Z
  checked: bot/config.py
  found: DOWNLOAD_VIDEO_FORMAT: str = "bestvideo+bestaudio/best" (line 62), loaded from env with same default
  implication: The format string is consistent across config and DownloadOptions

- timestamp: 2026-03-05T00:00:00Z
  checked: Manual test with yt-dlp for video kDfR4yI9TSY
  found: Both metadata extraction and download work perfectly with "bestvideo+bestaudio/best" format
  implication: The format string is correct and the video is accessible

- timestamp: 2026-03-05T00:00:00Z
  checked: DownloadFacade.to_download_options()
  found: Does NOT pass video_format or audio_format when creating DownloadOptions
  implication: Default values from DownloadOptions are used, which are correct

- timestamp: 2026-03-05T00:00:00Z
  checked: YouTubeDownloader._build_ydl_options() in bot/downloaders/platforms/youtube.py
  found: Sets extractor_args = {'youtube': {'skip': ['unavailable'], 'player_client': ['web']}}
  implication: The 'player_client': ['web'] is causing the format error

- timestamp: 2026-03-05T00:00:00Z
  checked: Tested different player_client values
  found: 'web' and 'ios' fail with format error, 'android' and 'tv_embedded' work
  implication: The web client doesn't provide formats compatible with 'bestvideo+bestaudio/best'

## Resolution

root_cause: The YouTubeDownloader._build_ydl_options() method sets 'player_client': ['web'] in extractor_args. The web client doesn't provide the separate video and audio streams needed for the 'bestvideo+bestaudio/best' format selection, causing yt-dlp to fail with "Requested format is not available".

fix: Removed the 'player_client' setting from extractor_args in YouTubeDownloader._build_ydl_options(), allowing yt-dlp to automatically select the best available client.

verification: Ran the facade download test and confirmed it succeeds - video downloads correctly with metadata.

files_changed:
  - bot/downloaders/platforms/youtube.py
