---
phase: 05-audio-format-conversion
plan: 01
type: execute
subsystem: audio
completed: 2026-02-19
duration: 15
tasks_completed: 2
tasks_total: 2
deviations: 0
key-decisions:
  - "Error handling follows existing pattern: Spanish messages, English logging"
  - "Format detection uses ffprobe format_name field for reliability"
  - "Codec settings optimized: MP3 at 192k (quality 2), FLAC compression level 5"
tags: ["audio", "conversion", "ffmpeg", "formats"]
requires: []
provides: ["05-02"]
affects:
  - bot/audio_format_converter.py
  - bot/error_handler.py
tech-stack:
  added: []
  patterns:
    - "AudioFormatConverter follows AudioExtractor pattern from format_processor.py"
    - "Static _check_ffmpeg() method for dependency validation"
    - "Module-level utility functions for format detection"
created:
  - bot/audio_format_converter.py
modified:
  - bot/error_handler.py
---

# Phase 05 Plan 01: Audio Format Conversion Infrastructure

**Audio format converter with automatic format detection supporting MP3, WAV, OGG, AAC, and FLAC.**

## What Was Built

### AudioFormatConverter Class
Core conversion engine at `/data/data/com.termux/files/home/repos/multibot2/bot/audio_format_converter.py`:

- **convert(output_format: str) -> bool**: Main conversion method with proper error handling
- **SUPPORTED_FORMATS dict**: Configuration for each format with codec, bitrate, and extra options
- **_check_ffmpeg()**: Static method to verify ffmpeg availability
- **get_supported_formats()**: Returns list of supported formats

### Format Configurations

| Format | Codec | Bitrate | Extra Options |
|--------|-------|---------|---------------|
| MP3 | libmp3lame | 192k | -q:a 2, -map_metadata 0, -id3v2_version 3 |
| WAV | pcm_s16le | None | -map_metadata 0 |
| OGG | libvorbis | 192k | -map_metadata 0 |
| AAC | aac | 192k | -map_metadata 0 |
| FLAC | flac | None | -map_metadata 0, -compression_level 5 |

### Format Detection
**detect_audio_format(file_path: str) -> Optional[str]**:
- Uses ffprobe to detect actual format from file contents
- Maps ffprobe format names to supported formats
- Handles comma-separated format strings (e.g., "mp3,mp2,mpa")
- Returns None if detection fails

### Error Handling
**AudioFormatConversionError** added to error_handler.py:
- Inherits from VideoProcessingError
- Default Spanish message: "Error convirtiendo el formato del audio"
- User-friendly message: "No pude convertir el formato del audio. Verifica que el formato sea válido."

## Commits

| Hash | Message | Files |
|------|---------|-------|
| b814699 | feat(05-01): add AudioFormatConversionError exception | bot/error_handler.py |
| 8612ce6 | feat(05-01): create AudioFormatConverter class | bot/audio_format_converter.py |

## Verification

```python
# All imports work
from bot.audio_format_converter import (
    AudioFormatConverter,
    detect_audio_format,
    get_supported_audio_formats
)

# Supported formats
get_supported_audio_formats()  # ['mp3', 'wav', 'ogg', 'aac', 'flac']
```

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] bot/audio_format_converter.py exists (238 lines)
- [x] bot/error_handler.py contains AudioFormatConversionError
- [x] All imports verified working
- [x] Both commits exist in git history

## Next Steps

Plan 05-02 will build on this infrastructure to create the `/convert_audio` command handler that uses AudioFormatConverter for user-facing audio format conversion.