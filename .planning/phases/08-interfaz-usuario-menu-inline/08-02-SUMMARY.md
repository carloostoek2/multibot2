---
phase: 08-interfaz-usuario-menu-inline
plan: 02
subsystem: ui
component: audio-inline-menu
tags: ["inline-keyboard", "audio", "menu", "callback-handlers"]
dependency_graph:
  requires: ["07-audio-effects"]
  provides: ["audio-menu-ui"]
  affects: ["bot/handlers.py", "bot/main.py"]
tech_stack:
  added: []
  patterns: ["inline-keyboard", "callback-routing", "context-state"]
key_files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions:
  - "Audio menu uses callback pattern audio_action:<action> for routing"
  - "Format selection from menu uses separate pattern audio_menu_format:<format>"
  - "Voice note conversion extracted to _handle_audio_menu_voicenote() helper"
  - "Existing effect handlers reused by setting appropriate context.user_data keys"
metrics:
  duration_seconds: 226
  completed_at: "2026-02-20T01:45:19Z"
  commits: 5
  files_modified: 2
  lines_added: ~543
  lines_removed: ~115
---

# Phase 08 Plan 02: Audio Inline Menu Summary

**One-liner:** Implemented contextual inline menu for audio files that displays automatically on upload, providing one-click access to 9 audio processing features without requiring command knowledge.

## What Was Built

### Audio Inline Menu System

When a user sends an audio file to the bot, instead of automatically converting it to a voice note, the bot now displays an inline menu with 9 processing options:

**Menu Layout (4 rows):**
- Row 1: Nota de Voz | Convertir Formato
- Row 2: Bass Boost | Treble Boost | Ecualizar
- Row 3: Reducir Ruido | Comprimir | Normalizar
- Row 4: Pipeline de Efectos

### Implementation Details

**1. Keyboard Generator** (`_get_audio_menu_keyboard()`)
- Returns `InlineKeyboardMarkup` with 9 action buttons
- Callback pattern: `audio_action:<action>`
- Actions: voicenote, convert, bass_boost, treble_boost, equalize, denoise, compress, normalize, effects

**2. Modified Audio Handler** (`handle_audio_file()`)
- Stores `audio_menu_file_id` and `audio_menu_correlation_id` in context
- Displays inline menu instead of auto-processing
- Preserves all existing validation (file size, join session check)

**3. Main Callback Handler** (`handle_audio_menu_callback()`)
- Routes all 9 audio actions to appropriate functionality
- For `voicenote`: Calls helper to convert and send voice note
- For `convert`: Shows format selection keyboard (MP3, WAV, OGG, AAC, FLAC)
- For `bass_boost`/`treble_boost`: Sets context and shows intensity keyboard (1-10)
- For `equalize`: Initializes EQ state and shows 3-band equalizer
- For `denoise`: Sets context and shows strength selection (1-10)
- For `compress`: Sets context and shows compression presets (light/medium/heavy/extreme)
- For `normalize`: Sets context and shows normalization profiles (music/podcast/streaming)
- For `effects`: Initializes pipeline and shows pipeline builder

**4. Format Selection Handler** (`handle_audio_menu_format_selection()`)
- Handles `audio_menu_format:<format>` callbacks
- Downloads, converts, and sends audio in selected format
- Cleans up context.user_data after processing

**5. Voice Note Helper** (`_handle_audio_menu_voicenote()`)
- Downloads audio from stored file_id
- Converts to OGG Opus using VoiceNoteConverter
- Sends as voice note
- Handles all error cases with proper messages

**6. Handler Registration** (main.py)
- Added `CallbackQueryHandler` for `^audio_action:` pattern
- Added `CallbackQueryHandler` for `^audio_menu_format:` pattern

## Deviations from Plan

None - plan executed exactly as written.

## Backward Compatibility

All existing audio commands continue to work:
- `/convert_audio` - Format conversion with inline keyboard
- `/bass_boost` - Bass boost with intensity selection
- `/treble_boost` - Treble boost with intensity selection
- `/equalize` - 3-band equalizer
- `/denoise` - Noise reduction
- `/compress` - Dynamic range compression
- `/normalize` - Loudness normalization
- `/effects` - Effects pipeline builder

The inline menu simply provides an alternative, more discoverable interface.

## Files Modified

| File | Changes |
|------|---------|
| `bot/handlers.py` | Added `_get_audio_menu_keyboard()`, `handle_audio_menu_callback()`, `_handle_audio_menu_voicenote()`, `handle_audio_menu_format_selection()`; Modified `handle_audio_file()` to show menu |
| `bot/main.py` | Imported new handlers, registered callback handlers |

## Commits

1. `db929fa` - feat(08-02): add audio inline menu keyboard generator
2. `ee2f804` - feat(08-02): modify handle_audio_file to show inline menu
3. `9a0317c` - feat(08-02): add audio menu callback handler
4. `201b936` - feat(08-02): add audio format selection callback handler
5. `e733997` - feat(08-02): register audio inline menu handlers

## Self-Check: PASSED

- [x] `_get_audio_menu_keyboard()` exists and returns InlineKeyboardMarkup
- [x] `handle_audio_file()` stores file_id and shows menu
- [x] `handle_audio_menu_callback()` handles all 9 actions
- [x] `handle_audio_menu_format_selection()` handles format callbacks
- [x] Handlers registered in main.py
- [x] All commits successful

## Verification Steps

1. Send an audio file to the bot - should show inline menu with 9 options
2. Click "Nota de Voz" - should convert and send voice note
3. Send another audio and click "Convertir Formato" - should show format options, then convert
4. Send another audio and click "Bass Boost" - should show intensity options, then apply effect
5. Send another audio and click "Pipeline de Efectos" - should show pipeline builder
6. Verify existing commands still work: /convert_audio, /bass_boost, /equalize, /effects, etc.
