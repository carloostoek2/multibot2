---
phase: 06-audio-enhancement
plan: 02
type: execute
subsystem: audio-enhancement
tags: [bass-boost, treble-boost, inline-keyboard, handlers]
dependency_graph:
  requires: ["06-01"]
  provides: ["06-03"]
  affects: []
tech_stack:
  added: []
  patterns:
    - "Inline keyboard 5+5 layout for intensity selection"
    - "Callback data format: bass:N and treble:N"
    - "Shared state keys for enhancement session"
key_files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions:
  - "Intensity 1-10 maps to 2-20dB bass gain and 1.5-15dB treble gain (as defined in AudioEnhancer)"
  - "Keyboard layout: 5 buttons per row (2 rows) for better UX"
  - "Shared state keys (enhance_audio_file_id, enhance_audio_correlation_id, enhance_type) allow only one enhancement session at a time"
  - "Callback pattern '^(bass|treble):\\d+$' handles both enhancement types with single handler"
metrics:
  duration_seconds: 193
  completed_date: "2026-02-19"
  tasks_completed: 4
  commits: 4
---

# Phase 06 Plan 02: Bass/Treble Boost Handlers Summary

## Overview

Implemented `/bass_boost` and `/treble_boost` commands with inline keyboard intensity selection (1-10) for audio enhancement. Users can now apply bass or treble boost effects to audio files with adjustable intensity levels.

## What Was Built

### Command Handlers

**handle_bass_boost_command** (line 2379)
- Validates audio input (message or reply)
- Validates file size using existing validators
- Stores state in `context.user_data` for session management
- Displays inline keyboard with intensity levels 1-10 (5+5 layout)

**handle_treble_boost_command** (line 2441)
- Mirrors bass_boost pattern
- Uses same validation and state storage
- Displays inline keyboard with treble callback data

**handle_intensity_selection** (line 2503)
- Parses callback data (format: "bass:5" or "treble:8")
- Validates intensity range (1-10)
- Full processing flow:
  - Downloads audio with retry logic
  - Validates audio integrity
  - Checks disk space
  - Applies enhancement using AudioEnhancer
  - Sends enhanced audio back to user
  - Cleans up user_data state

### Handler Registration (main.py)

```python
# Command handlers
CommandHandler("bass_boost", handle_bass_boost_command)
CommandHandler("treble_boost", handle_treble_boost_command)

# Callback handler
CallbackQueryHandler(handle_intensity_selection, pattern="^(bass|treble):\d+$")
```

### Help Text Updates

Added to `/start` command output:
- `/bass_boost - Aumenta los bajos del audio (intensidad ajustable)`
- `/treble_boost - Aumenta los agudos del audio (intensidad ajustable)`

## Technical Details

### State Management

Shared state keys in `context.user_data`:
- `enhance_audio_file_id`: Telegram file_id for download
- `enhance_audio_correlation_id`: Request tracing ID
- `enhance_type`: "bass" or "treble"

Note: User can only have one enhancement session at a time (shared keys).

### Callback Data Format

- Bass boost: `bass:1` through `bass:10`
- Treble boost: `treble:1` through `treble:10`

### Error Handling

Uses existing error handling patterns:
- `DownloadError` for download failures
- `ValidationError` for file validation failures
- `AudioEnhancementError` for enhancement failures
- `ProcessingTimeoutError` for timeout handling
- `handle_processing_error` for consistent error messages

## Commits

| Commit | Description |
|--------|-------------|
| fc934d7 | feat(06-02): implement /bass_boost command handler with intensity keyboard |
| 96609e2 | feat(06-02): implement /treble_boost command handler with intensity keyboard |
| f121d94 | feat(06-02): implement intensity selection callback handler |
| 3ff5f14 | feat(06-02): register handlers and update help text |

## Verification Results

- [x] handle_bass_boost_command exists at line 2379
- [x] handle_treble_boost_command exists at line 2441
- [x] handle_intensity_selection exists at line 2503
- [x] Handlers registered in main.py (lines 35, 96, 97, 100)
- [x] Help text updated (lines 262-263)
- [x] Callback pattern `^(bass|treble):\d+$` properly registered

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] All created/modified files exist
- [x] All commits exist in git history
- [x] Handlers follow existing patterns from format conversion
- [x] AudioEnhancer integration works correctly
- [x] Error handling follows existing conventions

## Next Steps

Plan 06-03 (Equalizer Handler) can now be implemented, building on the patterns established in this plan.
