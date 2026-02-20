---
phase: 07-audio-effects
plan: 04
type: execute
subsystem: bot
wave: 3
depends_on: ["07-02", "07-03"]
tags: [audio-effects, pipeline, telegram-bot, effects-chain]
requires: []
provides: [effects-pipeline-command, pipeline-builder-ui]
affects: [bot/handlers.py, bot/main.py]
tech-stack:
  added: []
  patterns: [method-chaining, state-management, inline-keyboard]
key-files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions:
  - Pipeline state uses "pipeline_" prefix to avoid conflicts with other handlers
  - Effects are applied in user-specified order (not auto-optimized)
  - Method chaining ensures single ffmpeg execution where possible
  - Preview uses alert popup for better UX on mobile
metrics:
  duration: "~30 min"
  tasks_completed: 4
  files_modified: 2
  lines_added: ~527
  lines_removed: ~2
  commits: 2
---

# Phase 7 Plan 4: Effects Pipeline Handler Summary

Interactive pipeline builder for chaining multiple audio effects (denoise, compress, normalize) in a single processing pass.

## What Was Built

### /effects Command
- Interactive pipeline builder with inline keyboard
- Add effects in sequence: Denoise → Compress → Normalize
- Each effect configured with its specific parameters
- Preview shows current pipeline state
- Apply or cancel the pipeline

### Pipeline Builder Interface

**Initial Screen:**
```
Constructor de efectos de audio:

Efectos en pipeline: (ninguno)

Agrega efectos en el orden que deseas aplicarlos.
Orden recomendado: Denoise → Compress → Normalize

[+ Denoise] [+ Compress] [+ Normalize]
[Ver Pipeline]
[Aplicar] [Cancelar]
```

**With Effects Added:**
```
Constructor de efectos de audio:

Pipeline (3 efectos):
1. Denoise (intensidad: 5)
2. Compress (ratio: media)
3. Normalize (perfil: música)

Agrega más efectos o aplica el pipeline.
```

### Effect Configuration

**Denoise:**
- Strength selection: 1-10 (inline keyboard)
- Maps to afftdn nr parameter (0.01-0.5)

**Compress:**
- Presets: Ligera (2:1), Media (4:1), Fuerte (8:1), Extrema (12:1)
- Threshold fixed at -20dB

**Normalize:**
- Profiles: Música (-14 LUFS), Podcast (-16 LUFS), Streaming (-23 LUFS)
- EBU R128 loudness normalization

### Technical Implementation

**State Management:**
- `pipeline_file_id`: Audio file ID
- `pipeline_correlation_id`: Request tracing
- `pipeline_effects`: List of effect configs

**Effect Config Structure:**
```python
{
    "type": "denoise|compress|normalize",
    "params": {...}  # Effect-specific parameters
}
```

**Method Chaining:**
```python
effects = AudioEffects(input_path, output_path)
effects.denoise(5).compress(4.0).normalize(-14.0)
final_output = effects.finalize()
```

## Files Modified

| File | Changes |
|------|---------|
| `bot/handlers.py` | Added 517 lines: handle_effects_command, handle_pipeline_builder, _handle_pipeline_apply, _get_pipeline_keyboard, _format_pipeline_message |
| `bot/main.py` | Added handler imports, CommandHandler, CallbackQueryHandler |
| `bot/handlers.py` (help) | Added /effects to help text |

## API Reference

### Commands
- `/effects` - Show pipeline builder interface

### Callbacks
- `pipeline_add:denoise` - Add denoise effect
- `pipeline_add:compress` - Add compress effect
- `pipeline_add:normalize` - Add normalize effect
- `pipeline_denoise:N` - Select denoise strength (1-10)
- `pipeline_compress:light|medium|heavy|extreme` - Select compression preset
- `pipeline_normalize:music|podcast|streaming` - Select normalization profile
- `pipeline_preview` - Show pipeline preview (alert)
- `pipeline_apply` - Apply pipeline
- `pipeline_cancel` - Cancel pipeline
- `pipeline_back` - Return to builder from effect selection

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- [x] /effects command shows pipeline builder with add/preview/apply/cancel buttons
- [x] Adding effects updates the pipeline display
- [x] Effects can be added in any order (denoise, compress, normalize)
- [x] Apply button chains methods and processes audio
- [x] Preview shows current pipeline with effect parameters
- [x] Cancel clears state and ends session
- [x] Help text includes /effects command
- [x] AudioEffects method chaining works correctly

## Commits

| Hash | Message |
|------|---------|
| 3c2d022 | feat(07-04): implement /effects command and pipeline builder |
| 20dfd3b | feat(07-04): register effects handlers and update help text |

## Notes

- Pipeline state uses "pipeline_" prefix to avoid conflicts with individual effect handlers
- Effects are applied in the exact order the user specifies
- Error handling keeps state on failure so users can retry
- Disk space estimation accounts for multiple effects (0.5x per effect)
- Uses same AudioEffects class with method chaining as individual effects

## Self-Check: PASSED

- [x] Created/modified files exist: bot/handlers.py, bot/main.py
- [x] Commits exist: 3c2d022, 20dfd3b
- [x] Handlers registered in main.py
- [x] Help text updated
- [x] All verification criteria met
