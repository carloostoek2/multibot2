---
phase: 03-voice-notes-voice-message-processing
plan: 02
type: execute
subsystem: handlers
completed_date: 2026-02-18
duration_seconds: 101
tasks_completed: 2
tasks_total: 2
deviations: 0
key-decisions:
  - "VoiceConversionError already exists from previous work - no new commit needed"
tech-stack:
  added: []
  patterns:
    - "TempManager context manager for automatic cleanup"
    - "Correlation ID logging for request tracing"
    - "Error handling via handle_processing_error"
key-files:
  created: []
  modified:
    - bot/handlers.py
    - bot/error_handler.py
---

# Phase 3 Plan 2: Voice Note Handler Implementation - Summary

## One-liner

Implemented `handle_audio_file` handler to convert MP3/OGG/WAV/AAC audio files to Telegram voice notes (OGG Opus format) with automatic truncation for files exceeding 20 minutes.

## What Was Built

### Task 1: handle_audio_file Handler

Added `handle_audio_file` function to `bot/handlers.py` that:

- Processes audio files sent as Telegram documents (MP3, OGG, WAV, AAC)
- Validates file size against `MAX_AUDIO_FILE_SIZE_MB` config
- Downloads audio with retry logic using `_download_with_retry`
- Validates audio integrity using `validate_audio_file`
- Checks disk space before processing
- Converts to OGG Opus voice note format using `VoiceNoteConverter`
- Sends result as voice note via `reply_voice`
- Handles errors with `handle_processing_error` (Spanish messages)
- Uses `TempManager` context manager for automatic cleanup
- Logs with correlation IDs for request tracing

**Key implementation details:**
- Follows exact pattern of `handle_video` and `handle_extract_audio_command`
- Generates safe filenames: `input_{user_id}_{file_unique_id}.mp3`
- Checks duration and logs warning if truncation will occur (>20 min)
- Deletes "Procesando..." message on success/error
- Handles `DownloadError`, `ValidationError`, `VoiceConversionError`, `ProcessingTimeoutError`

### Task 2: VoiceConversionError

`VoiceConversionError` class already existed in `bot/error_handler.py` from previous work:

```python
class VoiceConversionError(VideoProcessingError):
    """Exception raised when audio to voice note conversion fails."""

    def __init__(self, message: str = "Error convirtiendo audio a nota de voz"):
        self.message = message
        super().__init__(self.message)
```

With corresponding error message:
```python
VoiceConversionError: "No pude convertir el audio a nota de voz. Verifica que el archivo sea válido.",
```

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| 3778b75 | feat(03-02): implement handle_audio_file handler | bot/handlers.py |

## Verification

All verification criteria met:

- [x] `handle_audio_file` exists in `bot/handlers.py`
- [x] Uses `TempManager` as context manager
- [x] Validates audio with `validate_audio_file`
- [x] Uses `VoiceNoteConverter` for conversion
- [x] Sends result as `reply_voice`
- [x] Handles errors with `handle_processing_error`
- [x] `VoiceConversionError` exists in `error_handler.py`
- [x] Error messages in Spanish

## Deviations from Plan

None - plan executed exactly as written.

Note: Task 2 (`VoiceConversionError`) was already implemented in a previous iteration, so no new commit was needed for it.

## Self-Check: PASSED

- [x] `handle_audio_file` function exists and imports correctly
- [x] `VoiceConversionError` class exists and imports correctly
- [x] Commit 3778b75 exists in git history
- [x] All verification tests pass
