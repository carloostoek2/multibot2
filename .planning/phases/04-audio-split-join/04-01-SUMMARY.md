---
phase: 04-audio-split-join
plan: 01
type: execute
subsystem: audio-processing
tags: [audio, split, ffmpeg, AudioSplitter]
dependency_graph:
  requires: []
  provides: [AudioSplitter, AudioSplitError]
  affects: [bot/audio_splitter.py, bot/error_handler.py, bot/config.py]
tech_stack:
  added: []
  patterns: [ffmpeg segment muxer, pathlib Path, dataclass config]
key_files:
  created:
    - bot/audio_splitter.py
  modified:
    - bot/error_handler.py
    - bot/config.py
decisions: []
metrics:
  duration_minutes: 10
  completed_date: 2026-02-18
  tasks_completed: 3
  files_created: 1
  files_modified: 2
  lines_added: ~300
---

# Phase 04 Plan 01: Audio Split Infrastructure Summary

AudioSplitter class for splitting audio files into segments by duration or number of parts, following VideoSplitter patterns.

## What Was Built

### AudioSplitter Class (`bot/audio_splitter.py`)

A complete audio splitting implementation with:

**Core Methods:**
- `split_by_duration(segment_duration: int) -> List[str]` - Split audio into segments of N seconds each
- `split_by_parts(num_parts: int) -> List[str]` - Divide audio into N equal parts
- `get_audio_duration() -> float` - Get total audio duration using ffprobe

**Features:**
- Supports common formats: MP3, OGG, OGA, WAV, AAC, FLAC, M4A, WMA
- Uses ffmpeg segment muxer with `-c copy` for lossless splitting
- Output naming: `{basename}_part{NNN}.{ext}` (e.g., `audio_part001.mp3`)
- Maximum 20 parts limit, minimum 5 seconds segment duration
- Spanish error messages, English logging

**Error Handling:**
- `AudioSplitError` exception for all operational failures
- Validates input format support
- Checks ffmpeg/ffprobe availability
- Validates segment duration and number of parts

### Configuration (`bot/config.py`)

Added audio split configuration:
- `MAX_AUDIO_SEGMENTS: int = 20` - Maximum parts for audio splitting
- `MIN_AUDIO_SEGMENT_SECONDS: int = 5` - Minimum segment duration
- Environment variable support with validation

### Error Handler (`bot/error_handler.py`)

Added `AudioSplitError` exception class:
- Inherits from `VideoProcessingError`
- Default Spanish message: "No pude dividir el audio"
- Added to `ERROR_MESSAGES` dict with user-friendly message

## Verification Results

All verification criteria met:
- [x] AudioSplitError exists in bot/error_handler.py
- [x] bot/audio_splitter.py has AudioSplitter class
- [x] AudioSplitter has split_by_duration method
- [x] AudioSplitter has split_by_parts method
- [x] Output files follow naming pattern: {name}_part{NNN}.{ext}
- [x] config.MAX_AUDIO_SEGMENTS is defined
- [x] config.MIN_AUDIO_SEGMENT_SECONDS is defined
- [x] All imports work without errors

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| ab579ee | feat(04-01): add AudioSplitError exception class | bot/error_handler.py |
| fedd1c0 | feat(04-01): create AudioSplitter class | bot/audio_splitter.py |
| 0b8f677 | feat(04-01): add audio split configuration | bot/config.py |

## Deviations from Plan

None - plan executed exactly as written.

## Auth Gates

None encountered.

## Self-Check: PASSED

- [x] bot/audio_splitter.py exists (271 lines)
- [x] AudioSplitter class is importable
- [x] All commits exist in git history
- [x] Configuration values accessible via config object
- [x] AudioSplitError properly integrated with error handler
