# Quick Task: Video-Audio Merge & Interactive Split

## Objective
Integrate merge and split functionality into inline menus with interactive FSM flows.

## Task Description
Add user-friendly interactive flows for:
1. **Merge Video with Audio** — Combine video file with separate audio track
2. **Split Video by Time Range** — Interactive start/end time selection
3. **Split Audio by Time Range** — Interactive start/end time selection

## Implementation Summary

### 1. Video-Audio Merge
**File:** `bot/video_merger.py` (NEW)
- `VideoAudioMerger` class with `merge()` method
- Supports volume adjustment and audio trimming
- Replaces or adds audio tracks to videos

**Handler:** `handle_merge_audio_received()` in `bot/handlers.py`
- Triggered when user selects "Merge con Audio" from video menu
- Prompts user to send audio file
- Downloads both files, merges, sends result

**Menu Integration:**
```
Video Menu:
[Nota de Video] [Extraer Audio]
[Convertir Formato] [Dividir Video]
[Merge con Audio] ← NEW
```

### 2. Interactive Video Split
**File:** `bot/split_processor.py` (MODIFIED)
- Added `split_by_time_range(start_time, end_time)` method
- Extracts segment without re-encoding (stream copy)
- Validates time ranges and duration limits

**Handlers:** `bot/handlers.py` (NEW)
- `handle_video_split_start()` — Downloads video, shows duration
- `handle_video_split_start_time()` — Receives start time input
- `handle_video_split_end_time()` — Receives end time, processes cut
- `handle_split_text_input()` — Routes text messages to active session

**FSM Flow:**
```
1. User selects "Dividir Video"
2. Bot: "Duración: 2m 30s. Envía tiempo de inicio"
3. User: "30"
4. Bot: "✅ Inicio: 30s. Envía tiempo final"
5. User: "60"
6. Bot: Processes and sends segment (30s-60s)
```

### 3. Interactive Audio Split
**File:** `bot/audio_splitter.py` (MODIFIED)
- Added `split_by_time_range(start_time, end_time)` method
- Same pattern as video split

**Handlers:** `bot/handlers.py` (NEW)
- `handle_audio_split_start()` — Downloads audio, shows duration
- `handle_audio_split_start_time()` — Receives start time input
- `handle_audio_split_end_time()` — Receives end time, processes cut

**Menu Integration:**
```
Audio Menu:
[Nota de Voz] [Convertir Formato]
[Bass Boost] [Treble Boost] [Ecualizar]
[Reducir Ruido] [Comprimir] [Normalizar]
[Dividir Audio] [Unir Audios] ← NEW
[Pipeline de Efectos]
```

### 4. Error Handling
**File:** `bot/error_handler.py` (MODIFIED)
- Added `VideoMergeError` exception
- User-friendly Spanish error messages

### 5. Main Registration
**File:** `bot/main.py` (MODIFIED)
- Registered `handle_split_text_input` MessageHandler
- Filters: `TEXT & ~COMMAND` to avoid interfering with commands

## Files Changed
- `bot/video_merger.py` — NEW (278 lines)
- `bot/split_processor.py` — MODIFIED (+78 lines)
- `bot/audio_splitter.py` — MODIFIED (+77 lines)
- `bot/error_handler.py` — MODIFIED (+9 lines)
- `bot/handlers.py` — MODIFIED (+704 lines)
- `bot/main.py` — MODIFIED (+7 lines)

**Total:** +1,153 lines, -14 lines

## Testing Checklist
- [ ] Video merge with audio file
- [ ] Video split with valid time range
- [ ] Video split with invalid times (validation)
- [ ] Audio split with valid time range
- [ ] Audio split with decimal times (e.g., 30.5)
- [ ] Cancel during split session
- [ ] Session timeout handling

## State Updates Required
- Update `.planning/STATE.md` — Add quick task to "Quick Tasks Completed" table
- Update `.planning/ROADMAP.md` — Note feature addition to v2.0 capabilities

## Commit Message
```
feat: add video-audio merge and interactive split FSM

- New VideoAudioMerger class for merging video with audio tracks
- Interactive FSM for video splitting by time range (start/end times)
- Interactive FSM for audio splitting by time range (start/end times)
- Add split_by_time_range() method to VideoSplitter and AudioSplitter
- New inline menu options: 'Merge con Audio', 'Dividir Audio'
- Updated video and audio menus with split functionality
- Text input handler for split session time inputs
- VideoMergeError exception for merge failures
- Updated /start command with inline menu information

Features:
- Users can now merge video with separate audio files
- Interactive split flow: bot asks for start time, then end time
- Validation for time ranges and duration limits
- Automatic cleanup of session state after processing
```

---

*Created: 2026-02-23*
*Status: COMPLETE*
*Commit: 53ad0ac*
