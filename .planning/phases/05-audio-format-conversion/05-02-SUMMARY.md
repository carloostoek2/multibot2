---
phase: 05-audio-format-conversion
plan: 02
type: execute
subsystem: audio
completed: 2026-02-19
duration: 5
tasks_completed: 2
tasks_total: 2
deviations: 0
key-decisions:
  - "Inline keyboard layout: 3 + 2 buttons (MP3, WAV, OGG in first row; AAC, FLAC in second)"
  - "Callback data format: format:mp3, format:wav, etc."
  - "Input format detection prevents unnecessary conversion when source equals target"
  - "User data keys: convert_audio_file_id and convert_audio_correlation_id"
tags: ["audio", "conversion", "telegram", "handlers", "inline-keyboard"]
requires: ["05-01"]
provides: []
affects:
  - bot/handlers.py
  - bot/main.py
tech-stack:
  added: []
  patterns:
    - "Inline keyboard for format selection following Telegram Bot API patterns"
    - "Callback query handlers with pattern matching"
    - "Session state stored in context.user_data"
created: []
modified:
  - bot/handlers.py
  - bot/main.py
---

# Phase 05 Plan 02: Audio Format Conversion Handlers

**User-facing /convert_audio command with inline keyboard format selection for converting audio files between MP3, WAV, OGG, AAC, and FLAC formats.**

## What Was Built

### Command Handler: handle_convert_audio_command
Located at line 2163 in `/data/data/com.termux/files/home/repos/multibot2/bot/handlers.py`:

- **Input validation**: Checks for audio file in message or reply
- **File size validation**: Uses existing validate_file_size before processing
- **State storage**: Stores file_id and correlation_id in context.user_data
- **Inline keyboard**: 5 format buttons arranged in 2 rows (3 + 2 layout)
- **Spanish user messages**: "Envía /convert_audio respondiendo a un archivo de audio..."

### Callback Handler: handle_format_selection
Located at line 2219 in `/data/data/com.termux/files/home/repos/multibot2/bot/handlers.py`:

- **Callback parsing**: Extracts format from "format:mp3" style callback_data
- **File download**: Uses context.bot.get_file() with _download_with_retry
- **Format detection**: Uses detect_audio_format to check input format
- **Same-format check**: Prevents conversion if input == output format
- **Conversion flow**: Downloads, validates, converts, sends, cleans up
- **Error handling**: Uses AudioFormatConversionError with Spanish messages

### Handler Registration in main.py

```python
# Command handler
application.add_handler(CommandHandler("convert_audio", handle_convert_audio_command))

# Callback handler with pattern matching
application.add_handler(CallbackQueryHandler(handle_format_selection, pattern="^format:"))
```

### Help Text Update

Added to help text in handlers.py:
```
/convert_audio - Convierte un audio a otro formato (MP3, WAV, OGG, AAC, FLAC)
```

## User Flow

1. User sends `/convert_audio` command (replying to audio or with audio attached)
2. Bot validates audio file and shows inline keyboard with format options
3. User clicks desired format button
4. Bot downloads audio, detects input format
5. If input != output, bot converts and sends converted file
6. Success message confirms conversion

## Inline Keyboard Layout

```
[MP3] [WAV] [OGG]
[AAC] [FLAC]
```

## Commits

| Hash | Message | Files |
|------|---------|-------|
| 4776196 | feat(05-02): implement handle_convert_audio_command and handle_format_selection handlers | bot/handlers.py |
| e98fc51 | feat(05-02): register audio conversion handlers and update help text | bot/main.py, bot/handlers.py |

## Verification

```python
# Handlers exist and are properly registered
from bot.handlers import handle_convert_audio_command, handle_format_selection
from bot.main import main  # Includes handler registration

# Help text includes command
# /convert_audio - Convierte un audio a otro formato (MP3, WAV, OGG, AAC, FLAC)

# Inline keyboard has 5 format buttons
# Callback pattern: ^format:
```

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] handle_convert_audio_command exists in handlers.py (line 2163)
- [x] handle_format_selection callback handler exists (line 2219)
- [x] Both handlers imported and registered in main.py
- [x] Help text includes /convert_audio command
- [x] Format selection uses inline keyboard with 5 format options
- [x] Callback pattern "^format:" properly registered
- [x] Both commits exist in git history

## Next Steps

Plan 05-03 will complete the audio format conversion phase with any additional features or refinements needed for the audio conversion functionality.
