---
phase: 12-integration-polish
plan: 01
type: summary
subsystem: download-handlers
tags: [download, handlers, telegram, ui]
dependency_graph:
  requires: [11-05]
  provides: [12-02, 12-03, 12-04]
  affects: []
tech-stack:
  added: []
  patterns: [telegram-bot, inline-keyboards, callback-handlers]
key-files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions: []
metrics:
  duration: 38375
  completed_date: 2026-02-24
---

# Phase 12 Plan 01: Download Command and URL Detection Summary

## One-Liner

Implemented /download command and automatic URL detection with inline menus for format selection, large file confirmation prompts, and progress tracking integration.

## What Was Built

### 1. Download Command Handler (`handle_download_command`)
- Accepts `/download <url>` command with URL validation
- Shows format selection menu (Video/Audio) via inline keyboard
- Validates URL format and supported platforms before showing menu
- Stores URL and correlation_id in user context

### 2. URL Detection Handler (`handle_url_detection`)
- Automatically detects URLs in any text message using URLDetector
- Extracts URLs from message entities and plain text
- Shows inline menu with format options when supported URL detected
- Silently ignores non-video URLs and unsupported platforms

### 3. Format Selection Callback (`handle_download_format_callback`)
- Handles `download:video:{correlation_id}` and `download:audio:{correlation_id}` callbacks
- Extracts metadata using PlatformRouter to check file size
- Shows confirmation prompt for files >50MB (Telegram limit)
- Proceeds directly for small files or when size unknown

### 4. Large Download Confirmation (`handle_download_confirm_callback`)
- Handles `download:confirm:{correlation_id}` callback
- Shows file size warning with confirm/cancel options
- Starts download after user confirmation

### 5. Download Cancellation (`handle_download_cancel_callback`)
- Handles `download:cancel:{correlation_id}` callback
- Cancels active download via DownloadFacade
- Cleans up user_data entries

### 6. Download Execution (`_start_download`)
- Uses DownloadFacade for actual download
- Integrates ProgressTracker for real-time updates
- Shows cancel button during active download
- Handles errors with Spanish messages per existing convention

### 7. Post-Download Menu (`_send_downloaded_file_with_menu`)
- Sends downloaded file (video or audio based on format selection)
- Shows video menu keyboard for video downloads (Convert to Video Note, Extract Audio, etc.)
- Integrates with existing video processing pipeline

### 8. Handler Registration (main.py)
- CommandHandler for `/download` registered before message handlers
- CallbackQueryHandlers with regex patterns for download callbacks
- MessageHandler for URL detection after command handlers

## Key Implementation Details

### Handler Registration Order (Critical)
```python
# Commands first
CommandHandler("download", handle_download_command)

# Download callbacks (specific patterns)
CallbackQueryHandler(handle_download_format_callback, pattern="^download:(video|audio):")
CallbackQueryHandler(handle_download_confirm_callback, pattern="^download:confirm:")
CallbackQueryHandler(handle_download_cancel_callback, pattern="^download:cancel:")

# URL detection (text messages with URLs)
MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_detection)
```

### Size Checking Flow
```python
# Extract metadata using PlatformRouter
router = PlatformRouter()
route_result = await router.route(url)
metadata = await route_result.downloader.get_metadata(url)
size = metadata.get('filesize') or metadata.get('filesize_approx', 0)

if size > TELEGRAM_MAX_FILE_SIZE:  # 50MB
    # Show confirmation keyboard
else:
    # Proceed directly
```

### Progress Tracking Integration
```python
tracker = ProgressTracker(
    min_update_interval=3.0,
    min_percent_change=5.0,
    on_update=lambda p: asyncio.create_task(progress_callback(p))
)
```

## Files Modified

| File | Changes |
|------|---------|
| `bot/handlers.py` | +518 lines: Added 7 new handler functions and keyboard helpers |
| `bot/main.py` | +17 lines: Added imports and handler registrations |

## Commits

| Hash | Message |
|------|---------|
| db3bd67 | feat(12-01): add URL detection and download command handlers |
| f9fa0d9 | feat(12-01): register download handlers in main.py |

## Verification

- [x] `/download <url>` command shows format selection menu
- [x] URL in message shows inline menu with download options
- [x] Format selection triggers size check via PlatformRouter
- [x] Files >50MB show confirmation prompt
- [x] Cancel button available during active download
- [x] Progress updates shown during download
- [x] Downloaded files sent to user on completion
- [x] Post-download menu offers video processing options
- [x] Spanish error messages per existing convention
- [x] Handler registration order correct

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] All created/modified files exist
- [x] All commits recorded
- [x] Syntax validation passed
- [x] Import validation passed
- [x] Handler registration verified

## Next Steps

Plan 12-02 (Download Progress UI) can now build on these handlers to enhance the progress display with more detailed information and visual elements.
