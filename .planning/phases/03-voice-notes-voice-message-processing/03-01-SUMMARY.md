---
phase: 03
plan: 01
name: audio-processing-infrastructure
subsystem: voice-notes
phase_name: voice-notes-voice-message-processing
tags: [audio, ffmpeg, voice-notes, opus, mp3]
dependency_graph:
  requires: []
  provides: ["VoiceNoteConverter", "VoiceToMp3Converter", "audio-validation"]
  affects: ["03-02", "03-03"]
tech_stack:
  added: [ffmpeg libopus, ffprobe]
  patterns: [subprocess, pathlib, static methods]
key_files:
  created:
    - bot/audio_processor.py
  modified:
    - bot/config.py
    - bot/validators.py
decisions:
  - "Voice bitrate 24k optimized for speech transmission"
  - "MP3 bitrate 192k for good quality voice playback"
  - "Max voice duration 20 minutes (Telegram limit)"
  - "Error messages in Spanish (consistent with validators)"
  - "Logging in English (consistent with codebase)"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-02-18"
  tasks: 3
  files_created: 1
  files_modified: 2
  lines_added: ~560
---

# Phase 03 Plan 01: Audio Processing Infrastructure Summary

**One-liner:** Created dual-direction audio conversion infrastructure with MP3-to-voice-note (OGG Opus) and voice-note-to-MP3 converters, plus validation and configuration support.

## What Was Built

### bot/audio_processor.py (336 lines, created)

Core audio processing module with two converter classes:

**VoiceNoteConverter**
- Converts MP3 and other audio formats to Telegram voice note format (OGG Opus)
- Uses `libopus` codec with 24k bitrate optimized for voice
- Automatically truncates audio exceeding 20 minutes (Telegram limit)
- Validates ffmpeg availability before processing
- Returns `bool` indicating success/failure

**VoiceToMp3Converter**
- Converts voice notes (OGG Opus) back to MP3 format
- Uses `libmp3lame` codec with 192k bitrate for quality voice playback
- Preserves metadata during conversion
- Returns `bool` indicating success/failure

**Utility Functions**
- `get_audio_duration()`: Uses ffprobe to get audio duration with Spanish error messages
- `is_opus_ogg()`: Validates if file is valid OGG Opus format

### bot/config.py (modified)

Added audio-specific configuration fields:
- `MAX_VOICE_DURATION_MINUTES: int = 20` - Telegram voice note limit
- `MAX_AUDIO_FILE_SIZE_MB: int = 20` - File size limit for audio files
- `VOICE_BITRATE: str = "24k"` - Optimized bitrate for voice transmission
- `MP3_BITRATE: str = "192k"` - Quality bitrate for MP3 conversion

All values are configurable via environment variables with sensible defaults.

### bot/validators.py (modified)

Added audio validation functions following existing video validation patterns:

- `get_audio_duration(file_path) -> Tuple[Optional[float], Optional[str]]`
  - Returns duration in seconds or Spanish error message
  - Handles FileNotFoundError for ffprobe gracefully

- `validate_audio_file(file_path) -> Tuple[bool, Optional[str]]`
  - Validates file exists, not empty, has audio stream
  - Returns Spanish error messages for all failure cases

- `validate_audio_duration(file_path, max_minutes) -> Tuple[bool, Optional[str]]`
  - Checks duration against maximum limit
  - Returns: "El audio es demasiado largo (máximo {max_minutes} minutos)"

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| 24k bitrate for voice | Optimized for speech, efficient transmission, Telegram-compatible |
| 192k bitrate for MP3 | Good quality for voice playback, widely compatible |
| Truncate at 20 min | Telegram voice note hard limit, graceful handling |
| Spanish error messages | Consistent with existing validators.py convention |
| English logging | Consistent with video_processor.py and format_processor.py |
| Frozen dataclass | Maintains immutability, fail-fast validation in `__post_init__` |

## API Usage Examples

```python
from bot.audio_processor import VoiceNoteConverter, VoiceToMp3Converter
from bot.validators import validate_audio_file, validate_audio_duration
from bot.config import config

# Convert MP3 to voice note
converter = VoiceNoteConverter("input.mp3", "output.ogg")
success = converter.process()

# Convert voice note to MP3
converter = VoiceToMp3Converter("voice.ogg", "output.mp3")
success = converter.process()

# Validate audio file
is_valid, error = validate_audio_file("audio.mp3")
if not is_valid:
    print(f"Error: {error}")  # Spanish error message

# Check duration
duration, error = get_audio_duration("audio.mp3")
```

## Verification Results

All verification criteria passed:
- [x] bot/audio_processor.py has VoiceNoteConverter and VoiceToMp3Converter
- [x] Both classes have process() method that returns bool
- [x] VoiceNoteConverter truncates audio > 20 minutes
- [x] VoiceNoteConverter uses codec libopus and formato OGG
- [x] VoiceToMp3Converter uses codec libmp3lame
- [x] bot/config.py has MAX_VOICE_DURATION_MINUTES = 20
- [x] bot/config.py has VOICE_BITRATE and MP3_BITRATE
- [x] bot/validators.py has get_audio_duration using ffprobe
- [x] bot/validators.py has validate_audio_file
- [x] All validations return messages in Spanish

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| 6c52395 | feat(03-01): create audio processor with voice note converters |
| 072a49c | feat(03-01): add audio configuration to config.py |
| fde50ed | feat(03-01): add audio validation functions to validators.py |

## Self-Check: PASSED

- [x] bot/audio_processor.py exists (336 lines)
- [x] bot/config.py contains audio configuration
- [x] bot/validators.py contains audio validation functions
- [x] All imports work without errors
- [x] All commits exist in git history
- [x] Code follows existing patterns (video_processor.py, format_processor.py)

## Next Steps

This infrastructure enables:
- Plan 03-02: Voice note command handlers (/voicenote, /mp3)
- Plan 03-03: Voice message processing pipeline

The converters provide the core conversion logic, validators ensure input quality, and configuration allows runtime tuning of audio parameters.
