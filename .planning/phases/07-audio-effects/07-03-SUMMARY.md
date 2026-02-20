---
phase: 07
code: audio-effects
plan: 03
subsystem: audio-effects
tags: [audio, effects, normalize, loudness, ebu-r128]
dependency_graph:
  requires: [07-01]
  provides: []
  affects: []
tech_stack:
  added: []
  patterns: [telegram-bot, inline-keyboard, callback-handlers, ffmpeg-loudnorm]
key_files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions: []
metrics:
  duration_minutes: 25
  completed_date: 2026-02-20
---

# Phase 07 Plan 03: Normalize Handler Summary

## Overview

Implemented the `/normalize` command with inline keyboard preset selection for EBU R128 loudness normalization. This provides users with professional loudness normalization to standardize audio volume levels for different use cases (podcast, music, streaming).

## What Was Built

### Command Handler
- **`handle_normalize_command`**: Displays inline keyboard with 3 normalization presets
  - Music/General (-14 LUFS): For general playback, streaming platforms like Spotify/YouTube
  - Podcast/Voice (-16 LUFS): For voice content, podcasts
  - Streaming/Broadcast (-23 LUFS): For broadcast standards, platforms like Apple Podcasts

### Callback Handler
- **`handle_normalize_selection`**: Processes preset selection and applies normalization
  - Downloads audio file with retry logic
  - Validates audio integrity
  - Checks disk space
  - Applies EBU R128 normalization using `AudioEffects.normalize(target_lufs)`
  - Sends normalized audio with success message including LUFS value and use case

### Integration
- Registered handlers in `bot/main.py`
- Added `/normalize` to help text
- Follows existing patterns for state storage (`effect_audio_file_id`, `effect_audio_correlation_id`, `effect_type`)
- Proper error handling with Spanish user messages and English logging

## Key Features

1. **Inline Keyboard UI**: 3 buttons (1 per row) for clear preset selection
2. **LUFS Mapping**:
   - music → -14.0 LUFS
   - podcast → -16.0 LUFS
   - streaming → -23.0 LUFS
3. **Success Messages**: Include preset name, LUFS value, and use case description
4. **Error Handling**: Covers download, validation, processing, and timeout errors
5. **TempManager**: Automatic cleanup of temporary files

## Files Modified

| File | Changes |
|------|---------|
| `bot/handlers.py` | Added `handle_normalize_command` and `handle_normalize_selection` functions (~238 lines) |
| `bot/main.py` | Added imports, CommandHandler, and CallbackQueryHandler for normalize |

## Commits

| Hash | Message |
|------|---------|
| `28ad31d` | feat(07-03): implement /normalize command handler with preset selection |
| `12d3cd6` | feat(07-03): register normalize handlers and update help text |

## Verification

- [x] `handle_normalize_command` exists with preset keyboard (music/podcast/streaming)
- [x] `handle_normalize_selection` processes callbacks and applies normalization
- [x] Presets map to correct LUFS values: music=-14, podcast=-16, streaming=-23
- [x] Callback pattern `^normalize:` properly registered
- [x] Command listed in help text
- [x] Handlers follow existing patterns from audio effects
- [x] `AudioEffects.normalize` integration works correctly

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] Created/modified files exist and contain expected content
- [x] Commits exist with proper messages
- [x] Handlers follow existing code patterns
- [x] Integration with AudioEffects.normalize verified
- [x] Help text includes /normalize command

## Next Steps

Phase 07 (Audio Effects) is now complete with:
- 07-01: Audio Effects Infrastructure (denoise, compress, normalize)
- 07-02: Denoise and Compress Handlers
- 07-03: Normalize Handler (this plan)
