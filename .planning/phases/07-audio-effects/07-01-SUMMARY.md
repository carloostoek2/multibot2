---
phase: 07
plan: 01
subsystem: audio-effects
tags: ["audio-effects", "ffmpeg", "denoise", "compress", "normalize", "infrastructure"]
requires: []
provides: ["AudioEffects", "AudioEffectsError"]
affects: []
tech-stack:
  added: []
  patterns: ["ffmpeg audio filters", "method chaining", "context manager"]
key-files:
  created:
    - bot/audio_effects.py
  modified:
    - bot/error_handler.py
decisions:
  - "Effect pipeline uses temp files for intermediate results"
  - "finalize() method required to complete chained effects"
  - "Context manager support for automatic cleanup"
  - "afftdn nr parameter maps strength 1-10 to 0.01-0.5 range"
  - "loudnorm uses LRA=11 for general audio (not speech-specific)"
metrics:
  duration: "18 minutes"
  completed-date: "2026-02-20"
---

# Phase 07 Plan 01: Audio Effects Infrastructure Summary

Professional audio effects infrastructure with noise reduction, dynamic range compression, and loudness normalization using ffmpeg filters.

## What Was Built

### AudioEffects Class (bot/audio_effects.py)

A professional audio effects processor supporting method chaining for effect pipelines:

```python
effects = AudioEffects("input.mp3", "output.mp3")
effects.denoise(strength=5.0).compress(ratio=4.0, threshold=-20.0).normalize(target_lufs=-14.0)
effects.finalize()  # Complete the chain and write output
```

**Effects:**

1. **denoise(strength=5.0)** - FFT-based noise reduction using `afftdn` filter
   - Strength 1-10 maps to noise reduction factor 0.01-0.5
   - Uses noise floor of -70dB for consistent results

2. **compress(ratio=4.0, threshold=-20.0)** - Dynamic range compression using `acompressor` filter
   - Ratio range: 1.0-20.0 (higher = more compression)
   - Threshold range: -60.0 to 0.0 dB
   - Fixed attack=5ms, release=100ms for smooth response

3. **normalize(target_lufs=-14.0)** - EBU R128 loudness normalization using `loudnorm` filter
   - Target range: -23.0 to -5.0 LUFS
   - -14.0 LUFS = streaming standard (Spotify, YouTube)
   - True peak limit at -1dB prevents clipping

**Features:**
- Method chaining for effect pipelines
- Parameter validation with clamping to safe ranges
- Temporary file management for intermediate results
- Context manager support (`with AudioEffects(...) as fx:`)
- Spanish error messages, English logging

### AudioEffectsError (bot/error_handler.py)

New exception class following existing patterns:
- Inherits from `VideoProcessingError`
- Default message: "Error aplicando efecto de audio"
- User-friendly message: "No pude aplicar el efecto de audio. Verifica que el archivo sea válido."

## Key Technical Details

### FFmpeg Filter Syntax

| Effect | Filter | Example |
|--------|--------|---------|
| denoise | afftdn | `afftdn=nf=-70:nr=0.255` |
| compress | acompressor | `acompressor=threshold=-20dB:ratio=4:attack=5:release=100` |
| normalize | loudnorm | `loudnorm=I=-14:TP=-1:LRA=11` |

### Method Chaining Architecture

The class uses internal state to track when effects are chained:
- `_in_chain`: Boolean flag indicating if we're in a pipeline
- `_temp_files`: List of intermediate temporary files
- `_get_input_for_effect()`: Returns appropriate input (original or previous temp)
- `_create_temp_output()`: Creates temp file for intermediate results
- `finalize()`: Moves final result to output path and cleans up

### Usage Patterns

**Single effect:**
```python
effects = AudioEffects("input.mp3", "output.mp3")
effects.denoise(strength=7.0)
effects.finalize()
```

**Chained effects:**
```python
effects = AudioEffects("input.mp3", "output.mp3")
effects.denoise(5.0).compress(4.0, -20.0).normalize(-14.0)
effects.finalize()
```

**Context manager (auto-cleanup):**
```python
with AudioEffects("input.mp3", "output.mp3") as fx:
    fx.denoise(5.0).compress(4.0, -20.0).normalize(-14.0)
    fx.finalize()
```

## Files Created/Modified

| File | Lines | Purpose |
|------|-------|---------|
| bot/audio_effects.py | 436 | AudioEffects class with 3 effect methods |
| bot/error_handler.py | +9 | AudioEffectsError exception class |

## Commits

| Hash | Message |
|------|---------|
| 74cc5ec | feat(07-01): add AudioEffectsError exception class |
| ab0a677 | feat(07-01): create AudioEffects class with denoise, compress, normalize |

## Verification

- [x] All imports work: `from bot.audio_effects import AudioEffects`
- [x] AudioEffects has methods: denoise, compress, normalize
- [x] AudioEffectsError exists in error_handler.py
- [x] Each method has proper parameter validation
- [x] Methods return self for chaining
- [x] ffmpeg filter syntax correct for afftdn, acompressor, loudnorm
- [x] Line count >= 250 (actual: 436 lines)

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] bot/audio_effects.py exists (436 lines)
- [x] bot/error_handler.py contains AudioEffectsError
- [x] Import test passes
- [x] Method chaining test passes
- [x] Parameter validation test passes
- [x] Commit 74cc5ec exists
- [x] Commit ab0a677 exists
