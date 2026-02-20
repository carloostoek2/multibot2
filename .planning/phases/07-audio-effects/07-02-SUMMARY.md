---
phase: 07-audio-effects
plan: 02
type: execute
subsystem: audio-effects
tags: [denoise, compress, effects, handlers]
dependency_graph:
  requires: ["07-01"]
  provides: ["07-03"]
  affects: []
tech-stack:
  added: []
  patterns: [inline-keyboard, callback-handlers, audio-effects]
key-files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions: []
metrics:
  duration: "15 minutes"
  completed_date: "2026-02-20"
  tasks_completed: 4
  files_modified: 2
  commits: 4
---

# Phase 07 Plan 02: Denoise and Compress Handlers Summary

## One-Liner

Implemented /denoise and /compress commands with inline keyboard parameter selection for professional audio effects processing using AudioEffects class.

## What Was Built

### User-Facing Commands

**1. /denoise Command**
- Reduces background noise from audio files using FFT-based noise reduction
- Shows inline keyboard with strength levels 1-10 (5+5 layout)
- Strength 1 = subtle noise reduction, Strength 10 = aggressive noise reduction
- Maps strength to afftdn filter's nr parameter (0.01-0.5 range)

**2. /compress Command**
- Applies dynamic range compression to audio files
- Shows inline keyboard with 4 compression presets:
  - Compresión ligera (light) -> ratio 2.0
  - Compresión media (medium) -> ratio 4.0
  - Compresión fuerte (heavy) -> ratio 8.0
  - Compresión extrema (extreme) -> ratio 12.0
- Uses acompressor filter with threshold -20.0 dB

### Technical Implementation

**handle_denoise_command()**
- Validates audio input using _get_audio_from_message()
- Stores state in context.user_data: effect_audio_file_id, effect_audio_correlation_id, effect_type
- Creates inline keyboard with callback_data format: "denoise:1" through "denoise:10"
- Follows existing pattern from handle_bass_boost_command

**handle_compress_command()**
- Same validation and state storage pattern as denoise
- Creates inline keyboard with callback_data format: "compress:light", "compress:medium", etc.
- Maps presets to ratio values for AudioEffects.compress()

**handle_effect_selection()**
- Unified callback handler for both denoise and compress
- Parses callback data format: "effect_type:parameter"
- For denoise: validates strength is 1-10 integer
- For compress: maps preset to ratio value (2.0, 4.0, 8.0, 12.0)
- Full processing flow:
  1. Downloads audio with _download_with_retry()
  2. Validates with validate_audio_file()
  3. Checks disk space with check_disk_space()
  4. Applies effect using AudioEffects class with timeout
  5. Sends processed audio document
  6. Cleans up user_data state
- Error handling with handle_processing_error() for consistent error messages

**Handler Registration (main.py)**
- CommandHandler("denoise", handle_denoise_command)
- CommandHandler("compress", handle_compress_command)
- CallbackQueryHandler(handle_effect_selection, pattern="^(denoise|compress):")

## Key Implementation Details

### State Management
- Shared state keys for both effects (user can only have one effect session at a time):
  - effect_audio_file_id: Stores Telegram file_id
  - effect_audio_correlation_id: Request tracing
  - effect_type: "denoise" or "compress"

### Integration with AudioEffects
- Uses AudioEffects.denoise(strength) for noise reduction
- Uses AudioEffects.compress(ratio, threshold=-20.0) for compression
- Output format: MP3 at 192k bitrate for compatibility

### User Experience
- Spanish messages consistent with existing handlers
- Inline keyboard provides intuitive parameter selection
- Processing feedback messages during effect application
- Success confirmation with applied parameters

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| dbe29b6 | feat | implement /denoise command handler |
| 01485a9 | feat | implement /compress command handler |
| a493b87 | feat | implement effect selection callback handler |
| 0de1c75 | feat | register handlers and update help text |

## Verification

```bash
# Verify handlers exist
grep -n "def handle_denoise_command" bot/handlers.py
grep -n "def handle_compress_command" bot/handlers.py
grep -n "def handle_effect_selection" bot/handlers.py

# Verify handlers registered
grep -n "denoise\|compress" bot/main.py

# Verify help text updated
grep -n "denoise\|compress" bot/handlers.py | head -5
```

## Self-Check: PASSED

- [x] handle_denoise_command exists with strength keyboard (1-10)
- [x] handle_compress_command exists with ratio preset keyboard
- [x] handle_effect_selection processes callbacks and applies effects
- [x] Callback pattern "^(denoise|compress):" properly registered
- [x] Both commands listed in help text
- [x] Handlers follow existing patterns from audio enhancement
- [x] AudioEffects integration works correctly
- [x] All 4 tasks committed individually
- [x] SUMMARY.md created with substantive content

## Next Steps

Plan 07-03: Normalize Handler - Implement /normalize command for EBU R128 loudness normalization.
