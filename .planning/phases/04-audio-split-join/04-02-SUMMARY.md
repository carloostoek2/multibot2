---
phase: 04-audio-split-join
plan: 02
subsystem: audio
completed: 2026-02-18
tags: [audio, join, ffmpeg, concat]
dependency_graph:
  requires: [error_handler, config]
  provides: [audio_joiner]
  affects: []
tech_stack:
  added: []
  patterns: [ffmpeg concat demuxer, codec normalization]
key_files:
  created:
    - bot/audio_joiner.py
  modified:
    - bot/error_handler.py
    - bot/config.py
decisions:
  - "MP3 192k normalization for incompatible formats - consistent with MP3_BITRATE config"
  - "ffmpeg concat demuxer with -c copy for lossless joining when codecs match"
  - "Spanish error messages following existing convention"
  - "English logging following video_processor.py pattern"
  - "20 max audio files - same as MAX_AUDIO_SEGMENTS for consistency"
metrics:
  duration: 11 minutes
  tasks_completed: 3
  files_created: 1
  files_modified: 2
  lines_added: ~356
---

# Phase 04 Plan 02: Audio Join Summary

**One-liner:** AudioJoiner class for concatenating multiple audio files with automatic format normalization.

## What Was Built

### AudioJoiner Class (`bot/audio_joiner.py`)

A complete audio joining implementation following VideoJoiner patterns:

**Core Methods:**
- `add_audio(audio_path)` - Add audio files to the join list
- `join_audios()` - Concatenate all added files into single output
- `get_input_count()` - Get number of audio files in join list
- `clear_audios()` - Clear the join list

**Format Handling:**
- `_need_normalization()` - Detects codec mismatches between input files
- `_normalize_audios()` - Converts incompatible files to MP3 192k
- Supports MP3, OGG, WAV, AAC, FLAC formats
- Uses `-c copy` for lossless concatenation when codecs match
- Uses libmp3lame encoder for normalization

**Error Handling:**
- Raises `AudioJoinError` for all operational failures
- Spanish error messages for users
- English logging for debugging
- Proper exception chaining with `from e`

### AudioJoinError Exception (`bot/error_handler.py`)

- Inherits from `VideoProcessingError`
- Default message: "No pude unir los archivos de audio"
- Added to ERROR_MESSAGES dict with user-friendly Spanish message

### Configuration (`bot/config.py`)

New audio join configuration fields:
- `JOIN_MAX_AUDIO_FILES: int = 20` - Maximum audio files to join
- `JOIN_MIN_AUDIO_FILES: int = 2` - Minimum audio files required
- `JOIN_AUDIO_TIMEOUT: int = 120` - Timeout for join operation in seconds

All fields validated at startup with proper error messages.

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| 4aabce5 | feat(04-02): add AudioJoinError exception class |
| 4ec201b | feat(04-02): create AudioJoiner class |
| b06df0c | feat(04-02): add audio join configuration |

## Verification Results

- [x] AudioJoinError exists in bot/error_handler.py
- [x] bot/audio_joiner.py has AudioJoiner class
- [x] AudioJoiner has add_audio method
- [x] AudioJoiner has join_audios method
- [x] AudioJoiner handles format normalization when needed
- [x] config.JOIN_MAX_AUDIO_FILES is defined
- [x] config.JOIN_MIN_AUDIO_FILES is defined
- [x] config.JOIN_AUDIO_TIMEOUT is defined
- [x] All imports work without errors

## Self-Check: PASSED

All files verified to exist:
- FOUND: bot/audio_joiner.py
- FOUND: bot/error_handler.py (modified)
- FOUND: bot/config.py (modified)

All commits verified:
- FOUND: 4aabce5
- FOUND: 4ec201b
- FOUND: b06df0c
