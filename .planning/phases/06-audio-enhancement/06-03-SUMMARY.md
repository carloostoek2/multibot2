---
phase: 06-audio-enhancement
plan: 03
type: execute
subsystem: audio-enhancement
tags: [equalizer, 3-band-eq, audio-processing, telegram-bot]
dependency_graph:
  requires: ["06-01"]
  provides: ["equalizer-handler"]
  affects: ["bot/handlers.py", "bot/main.py"]
tech-stack:
  added: []
  patterns: [inline-keyboard, callback-handlers, state-management]
key-files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions: []
metrics:
  duration: "20 minutes"
  completed_date: "2026-02-19"
---

# Phase 06 Plan 03: Equalizer Handler Summary

**One-liner:** Interactive 3-band equalizer (bass/mid/treble) with inline keyboard adjustments for fine-grained audio frequency control.

## What Was Built

### Overview
Implemented `/equalize` command that provides users with an interactive 3-band equalizer interface. Users can independently adjust bass, mid, and treble bands using +/- buttons, preview current settings, and apply the equalization when ready.

### Key Features
- **3-band equalizer:** Independent control of bass (125Hz), mid (1000Hz), and treble (8000Hz) frequency bands
- **Interactive inline keyboard:** +/- buttons for each band with real-time value display
- **Value range:** -10 to +10 (maps to -15dB to +15dB actual gain)
- **Step size:** 2 units per button press for smooth adjustment
- **Reset button:** Clear all adjustments back to zero
- **Apply button:** Process audio with current equalizer settings
- **State management:** User session data stored in `context.user_data` with `eq_` prefix

### Architecture

```
User sends /equalize
    ↓
handle_equalize_command()
    - Validates audio input
    - Initializes eq_bass=0, eq_mid=0, eq_treble=0
    - Shows inline keyboard with current values
    ↓
User clicks +/- buttons
    ↓
handle_equalizer_adjustment()
    - Parses callback_data (eq_bass_up, eq_mid_down, etc.)
    - Applies step (+/- 2) with clamping to [-10, +10]
    - Updates message inline with new values
    ↓
User clicks "Aplicar"
    ↓
_handle_equalizer_apply()
    - Downloads audio file
    - Calls AudioEnhancer.equalize(bass, mid, treble)
    - Sends processed audio
    - Clears session state
```

## Implementation Details

### Files Modified

| File | Changes |
|------|---------|
| `bot/handlers.py` | Added `_get_equalizer_keyboard()`, `handle_equalize_command()`, `handle_equalizer_adjustment()`, `_handle_equalizer_apply()` |
| `bot/main.py` | Imported equalizer handlers, registered CommandHandler and CallbackQueryHandler |

### Code Statistics
- **Added:** ~345 lines in handlers.py
- **Modified:** 8 lines in main.py (imports + handler registration)

### Key Functions

```python
# Generate equalizer keyboard layout
def _get_equalizer_keyboard(bass: int, mid: int, treble: int) -> InlineKeyboardMarkup

# Handle /equalize command
async def handle_equalize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None

# Handle +/- button callbacks
async def handle_equalizer_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None

# Apply equalization and send result
async def _handle_equalizer_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, bass: int, mid: int, treble: int) -> None
```

### Inline Keyboard Layout
```
[Bass]  [-] [0] [+]
[Mid]   [-] [0] [+]
[Treble][-] [0] [+]
[Reset] [Aplicar]
```

### State Management
- `eq_file_id`: Audio file ID for retrieval
- `eq_correlation_id`: Request tracing ID
- `eq_bass`: Current bass value (-10 to +10)
- `eq_mid`: Current mid value (-10 to +10)
- `eq_treble`: Current treble value (-10 to +10)

## Verification Steps

1. **Command handler exists:**
   ```bash
   grep -n "def handle_equalize_command" bot/handlers.py
   # Output: 2738:async def handle_equalize_command(...)
   ```

2. **Adjustment handler exists:**
   ```bash
   grep -n "def handle_equalizer_adjustment" bot/handlers.py
   # Output: 2789:async def handle_equalizer_adjustment(...)
   ```

3. **Apply logic integrated:**
   ```bash
   grep "eq_apply" bot/handlers.py
   # Shows callback handling and _handle_equalizer_apply call
   ```

4. **Handlers registered:**
   ```bash
   grep -n "equalize" bot/main.py
   # Shows imports and handler registration
   ```

5. **Help text updated:**
   ```bash
   grep "equalize" bot/handlers.py | head -1
   # Output: /equalize - Ecualizador de 3 bandas (bass, mid, treble)
   ```

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Checklist

- [x] `handle_equalize_command` exists with interactive 3-band equalizer keyboard
- [x] `handle_equalizer_adjustment` handles up/down/reset/apply callbacks
- [x] Bass, mid, treble values clamped to -10..+10 range
- [x] Step size of 2 for incremental adjustments
- [x] Inline message updates show current values
- [x] Apply button triggers `AudioEnhancer.equalize()` with current values
- [x] Help text includes `/equalize` command description
- [x] All state stored in `context.user_data` with `eq_` prefix

## Commits

| Hash | Message |
|------|---------|
| 9949a28 | feat(06-03): implement /equalize command with 3-band equalizer interface |
| 3fccd51 | feat(06-03): register equalize handlers and update help text |

## Notes

- Equalizer uses ffmpeg `equalizer` filter with three bands at 125Hz, 1000Hz, and 8000Hz
- Gain values are mapped: input (-10 to +10) -> dB (-15 to +15)
- Output format is MP3 at 192kbps for maximum compatibility
- Error handling follows existing pattern: Spanish messages, English logging
- On error, state is preserved so user can retry
