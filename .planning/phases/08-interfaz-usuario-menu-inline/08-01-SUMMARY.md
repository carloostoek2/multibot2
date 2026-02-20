---
phase: 08-interfaz-usuario-menu-inline
plan: 01
type: execute
subsystem: ui
wave: 1
depends_on: []
tags: [inline-menu, video, ui, handlers]
dependency_graph:
  requires: []
  provides: [video-inline-menu]
  affects: [bot/handlers.py, bot/main.py]
tech-stack:
  added: []
  patterns: [inline-keyboard, callback-handlers, context-storage]
key-files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions: []
metrics:
  duration: "completed"
  completed_date: "2026-02-20"
  tasks: 4
  files_modified: 2
---

# Phase 08 Plan 01: Video Inline Menu Summary

## Overview

Implemented an inline menu system for video files that automatically displays when users upload videos, eliminating the need to learn commands for video processing features.

## What Was Built

### Video Inline Menu System

A contextual menu that appears automatically when a video is uploaded, presenting four action options:

- **Nota de Video**: Convert video to circular video note
- **Extraer Audio**: Extract audio track from video
- **Convertir Formato**: Convert video to different format (MP4, AVI, MOV, MKV, WEBM)
- **Dividir Video**: Directs user to /split command for video splitting

### Key Components

1. **`_get_video_menu_keyboard()`** (line 2559)
   - Generates inline keyboard with 4 action buttons in 2 rows
   - Uses callback pattern: `video_action:<action>`

2. **`_get_video_format_keyboard()`** (line 2574)
   - Format selection for video conversion
   - Supports: MP4, AVI, MOV, MKV, WEBM

3. **`_get_video_audio_format_keyboard()`** (line 2590)
   - Format selection for audio extraction
   - Supports: MP3, AAC, WAV, OGG

4. **`handle_video_menu_callback()`** (line 4555)
   - Routes video action selections to appropriate handlers
   - Handles: videonote, extract_audio, convert, split
   - Processes video note conversion directly
   - Shows format keyboards for extract/convert actions

5. **`handle_video_format_selection()`** (line 4729)
   - Handles format selection callbacks
   - Processes video conversion using FormatConverter
   - Processes audio extraction using AudioExtractor
   - Cleans up context after processing

## Implementation Details

### Context Storage Pattern

```python
context.user_data["video_menu_file_id"] = video.file_id
context.user_data["video_menu_correlation_id"] = correlation_id
context.user_data["video_menu_action"] = "extract_audio" | "convert"
```

### Handler Registration (bot/main.py)

```python
# Video inline menu handlers
application.add_handler(CallbackQueryHandler(handle_video_menu_callback, pattern="^video_action:"))
application.add_handler(CallbackQueryHandler(handle_video_format_selection, pattern="^video_(format|audio_format):"))
```

## Commits

| Commit | Message | Files |
|--------|---------|-------|
| b6615a9 | feat(08-01): add video inline menu keyboard generators | bot/handlers.py |
| 80d5d34 | feat(08-01): modify handle_video to show inline menu | bot/handlers.py |
| 3a504f1 | feat(08-01): register video inline menu handlers | bot/main.py |

## Verification

- [x] Video uploads trigger inline menu automatically
- [x] Menu shows 4 options in 2 rows
- [x] "Nota de Video" processes and sends video note
- [x] "Extraer Audio" shows format options and extracts audio
- [x] "Convertir Formato" shows format options and converts video
- [x] "Dividir Video" directs to /split command
- [x] Existing video commands still work (/convert, /extract_audio, /split, /join)
- [x] Context cleanup after processing

## Deviations from Plan

None - plan executed as written. Note: The callback handlers (`handle_video_menu_callback` and `handle_video_format_selection`) were implemented in handlers.py but handler registration in main.py was completed as part of this execution.

## Backward Compatibility

All existing video commands remain functional:
- `/convert <formato>` - Convert video format
- `/extract_audio <formato>` - Extract audio from video
- `/split [duration|parts] <valor>` - Split video
- `/join` - Join multiple videos

## Self-Check: PASSED

- [x] All functions exist in bot/handlers.py
- [x] Handlers registered in bot/main.py
- [x] Commits verified in git log
- [x] No syntax errors in modified files
