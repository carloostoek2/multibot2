---
phase: 05-audio-format-conversion
plan: 03
type: execute
subsystem: audio
completed: 2026-02-19
duration: 10
tasks_completed: 1
tasks_total: 1
deviations: 0
key-decisions:
  - "Metadata extraction uses ffprobe with JSON output for structured parsing"
  - "Field mapping handles case variations (TITLE, Title, title)"
  - "WAV format marked as limited metadata support (INFO chunks only)"
tags: ["audio", "metadata", "ffmpeg", "id3", "vorbis"]
requires: ["05-01"]
provides: []
affects:
  - bot/audio_format_converter.py
tech-stack:
  added: []
  patterns:
    - "extract_metadata follows ffprobe JSON pattern from audio utilities"
    - "has_metadata_support uses format whitelist approach"
    - "_log_metadata_preservation integrates with existing logger"
created: []
modified:
  - bot/audio_format_converter.py
---

# Phase 05 Plan 03: Metadata Preservation in Audio Conversion

**Audio format converter enhanced with metadata preservation using ffmpeg -map_metadata and ffprobe extraction.**

## What Was Built

### Enhanced AudioFormatConverter

Updated `/data/data/com.termux/files/home/repos/multibot2/bot/audio_format_converter.py` with metadata preservation:

#### New Helper Functions

**extract_metadata(file_path: str) -> Optional[Dict[str, str]]**:
- Uses ffprobe with JSON output to extract metadata tags
- Maps common fields: title, artist, album, year, genre, comment
- Handles case variations (TITLE, Title, title)
- Returns None if no metadata or extraction fails

**has_metadata_support(format_name: str) -> bool**:
- Returns True for MP3, FLAC, OGG, AAC (full metadata support)
- Returns False for WAV (limited INFO chunk support)
- Used for logging warnings when metadata cannot be fully preserved

#### Enhanced convert() Method

- Added `_log_metadata_preservation()` call after format validation
- Logs when metadata is being preserved (info level)
- Logs metadata fields found in source (debug level)
- Warns if target format has limited metadata support

#### Format Configurations (Already Present)

| Format | Metadata Flags |
|--------|----------------|
| MP3 | -map_metadata 0, -id3v2_version 3 |
| WAV | -map_metadata 0 |
| OGG | -map_metadata 0 |
| AAC | -map_metadata 0 |
| FLAC | -map_metadata 0, -compression_level 5 |

### Exports Updated

```python
__all__ = [
    "AudioFormatConverter",
    "detect_audio_format",
    "extract_metadata",        # NEW
    "get_supported_audio_formats",
    "has_metadata_support",    # NEW
]
```

## Commits

| Hash | Message | Files |
|------|---------|-------|
| 0b9fda2 | feat(05-03): add metadata preservation to AudioFormatConverter | bot/audio_format_converter.py |

## Verification

```python
# All imports work
from bot.audio_format_converter import (
    AudioFormatConverter,
    detect_audio_format,
    extract_metadata,
    get_supported_audio_formats,
    has_metadata_support
)

# Metadata support check
has_metadata_support('mp3')   # True
has_metadata_support('flac')  # True
has_metadata_support('wav')   # False (limited support)

# Metadata extraction (if ffprobe available)
metadata = extract_metadata('/path/to/audio.mp3')
# Returns: {'title': 'Song Name', 'artist': 'Artist Name', ...}
```

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] bot/audio_format_converter.py exists with metadata functions
- [x] extract_metadata() function implemented with ffprobe
- [x] has_metadata_support() function implemented
- [x] _log_metadata_preservation() method added to class
- [x] __all__ exports updated
- [x] -map_metadata 0 present in all format configurations
- [x] -id3v2_version 3 present for MP3 format
- [x] Commit 0b9fda2 exists in git history
- [x] Python syntax validated
- [x] All imports verified working

## Metadata Preservation Behavior

### Supported Formats
- **MP3**: Full ID3v2.3 tag support via -id3v2_version 3
- **FLAC**: Vorbis comments preserved
- **OGG**: Vorbis comments preserved
- **AAC**: Metadata preserved (format dependent)

### Limited Support
- **WAV**: INFO chunks only (limited metadata capacity)

### Logging
- Info: "Metadata will be preserved for {format} output"
- Warning: "Metadata preservation limited for {format}"
- Debug: Individual metadata fields found in source
