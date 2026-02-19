---
phase: 06-audio-enhancement
plan: 01
type: execute
subsystem: audio-enhancement
tags: [audio, enhancement, ffmpeg, bass, treble, equalizer]
dependency_graph:
  requires: []
  provides: [audio-enhancement-infrastructure]
  affects: []
tech-stack:
  added: []
  patterns: [ffmpeg-filters, subprocess, pathlib]
key-files:
  created:
    - bot/audio_enhancer.py
  modified:
    - bot/error_handler.py
decisions:
  - "Use ffmpeg bass filter for bass boost (simpler than firequalizer)"
  - "Use ffmpeg treble filter for treble boost"
  - "Use chained equalizer filters for 3-band EQ"
  - "Output to MP3 format for maximum compatibility"
  - "Intensity 1-10 maps to 2-20dB for bass, 1.5-15dB for treble"
  - "EQ gain -10 to +10 maps to -15 to +15dB"
metrics:
  duration: "13 minutes"
  completed_date: "2026-02-19"
  tasks_completed: 3
  files_created: 1
  files_modified: 1
  lines_added: ~310
---

# Phase 06 Plan 01: Audio Enhancement Infrastructure Summary

## One-Liner

Created AudioEnhancer class with bass boost, treble boost, and 3-band equalizer using ffmpeg audio filters.

## What Was Built

### AudioEnhancer Class (`bot/audio_enhancer.py`)

A comprehensive audio enhancement module providing three main enhancement methods:

1. **bass_boost(intensity: float = 5.0)**
   - Uses ffmpeg `bass=gain=X` filter
   - Intensity range: 1.0 to 10.0 (clamped)
   - Gain mapping: intensity * 2 (2-20dB boost)
   - Enhances low frequencies around 100-200Hz

2. **treble_boost(intensity: float = 5.0)**
   - Uses ffmpeg `treble=gain=X` filter
   - Intensity range: 1.0 to 10.0 (clamped)
   - Gain mapping: intensity * 1.5 (1.5-15dB boost)
   - Enhances high frequencies around 3000-10000Hz

3. **equalize(bass: float = 0, mid: float = 0, treble: float = 0)**
   - Uses chained ffmpeg `equalizer` filters
   - 3-band configuration:
     - Bass: 125Hz (20-250Hz range)
     - Mid: 1000Hz (250Hz-4kHz range)
     - Treble: 8000Hz (4kHz-20kHz range)
   - Gain range: -10 to +10 per band (maps to -15 to +15dB)

### AudioEnhancementError (`bot/error_handler.py`)

- New exception class inheriting from `VideoProcessingError`
- Default Spanish message: "Error aplicando mejora de audio"
- User-friendly message: "No pude aplicar la mejora de audio. Verifica que el archivo sea válido."

## Key Design Decisions

1. **Output Format**: MP3 at 192k bitrate for maximum compatibility
2. **Filter Selection**: Used simpler `bass` and `treble` filters instead of `firequalizer` for reliability
3. **Parameter Validation**: All intensity/gain parameters are clamped to safe ranges
4. **Error Handling**: Spanish user messages, English debug logging (consistent with codebase)
5. **Code Structure**: Follows the same pattern as `AudioFormatConverter` class

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `bot/audio_enhancer.py` | 298 | Created |
| `bot/error_handler.py` | +9 | Added AudioEnhancementError |

## Commits

- `4f194f9`: feat(06-01): add AudioEnhancementError exception class
- `51cc53a`: feat(06-01): create AudioEnhancer class with bass and treble boost

## Verification Results

- [x] All imports work: `from bot.audio_enhancer import AudioEnhancer`
- [x] AudioEnhancer has methods: bass_boost, treble_boost, equalize
- [x] AudioEnhancementError exists in error_handler.py
- [x] Each method has proper intensity/band parameter validation
- [x] ffmpeg filter syntax is correct for bass, treble, and equalizer
- [x] Code follows existing patterns from audio_format_converter.py

## Deviations from Plan

None - plan executed exactly as written.

## Next Steps

This infrastructure enables:
- `/bass_boost` command handler (Plan 06-02)
- `/treble_boost` command handler (Plan 06-02)
- `/equalize` command handler with inline keyboard (Plan 06-03)

## Self-Check: PASSED

- [x] Created files exist: bot/audio_enhancer.py
- [x] Modified files updated: bot/error_handler.py
- [x] Commits exist: 4f194f9, 51cc53a
- [x] All verification checks pass
