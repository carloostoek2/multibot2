---
phase: 04-audio-split-join
plan: 03
type: execute
subsystem: telegram-bot
tags: [handlers, commands, audio, split, join]
dependency_graph:
  requires:
    - 04-01 (AudioSplitter class)
    - 04-02 (AudioJoiner class)
  provides:
    - Telegram command handlers for /split_audio and /join_audio
  affects:
    - bot/handlers.py
    - bot/main.py
tech_stack:
  added:
    - AudioSplitter integration
    - AudioJoiner integration
  patterns:
    - Session-based state management (context.user_data)
    - Command routing for shared /done and /cancel
key-files:
  created: []
  modified:
    - bot/handlers.py
    - bot/main.py
decisions:
  - "Shared /done and /cancel commands route based on session state (video first, then audio)"
  - "handle_audio_file routes to handle_join_audio_file when join_audio_session is active"
  - "Spanish user messages following existing convention"
  - "Config-based limits: MAX_AUDIO_SEGMENTS=20, MIN_AUDIO_SEGMENT_SECONDS=5"
metrics:
  duration: 318
  completed_date: 2026-02-18
---

# Phase 04 Plan 03: Audio Split/Join Handlers Summary

Telegram command handlers for `/split_audio` and `/join_audio` commands, enabling users to split audio files into segments and join multiple audio files together.

## What Was Built

### Command Handlers

1. **`/split_audio`** - Split audio files into segments
   - `/split_audio duration 30` - Split into 30-second segments
   - `/split_audio parts 5` - Split into 5 equal parts
   - `/split_audio` - Split into 60-second segments (default)

2. **`/join_audio`** - Join multiple audio files
   - `/join_audio` - Start join session
   - Send audio files one by one during session
   - `/done` - Complete and join all collected files
   - `/cancel` - Cancel session and cleanup

### Implementation Details

**bot/handlers.py additions:**
- `handle_split_audio_command()` - Main split handler with duration/parts modes
- `handle_join_audio_start()` - Initialize audio join session
- `handle_join_audio_file()` - Collect audio files during session
- `handle_join_audio_done()` - Complete audio joining
- `handle_join_audio_cancel()` - Cancel audio join session
- `_get_audio_from_message()` - Helper to extract audio from message or reply
- Updated `handle_join_done()` and `handle_join_cancel()` to route to audio handlers
- Updated `handle_audio_file()` to route to join handler when session active
- Updated `start()` help text with new commands

**bot/main.py additions:**
- Imports for all new handlers
- Handler registration for `/split_audio` and `/join_audio`
- Comments documenting shared `/done` and `/cancel` routing

### Session State Structure

```python
context.user_data["join_audio_session"] = {
    "audios": [],           # List of file paths
    "temp_mgr": TempManager(),
    "last_activity": time,
}
```

### Configuration Used

- `MAX_AUDIO_SEGMENTS` (default: 20) - Maximum segments for split
- `MIN_AUDIO_SEGMENT_SECONDS` (default: 5) - Minimum segment duration
- `JOIN_MAX_AUDIO_FILES` (default: 20) - Maximum files for join
- `JOIN_MIN_AUDIO_FILES` (default: 2) - Minimum files for join
- `JOIN_SESSION_TIMEOUT` (default: 300s) - Session timeout
- `JOIN_AUDIO_TIMEOUT` (default: 120s) - Join operation timeout

## Commits

| Commit | Description |
|--------|-------------|
| ce068aa | feat(04-03): implement /split_audio command handler |
| 6fef4e0 | feat(04-03): implement /join_audio command handlers |
| 47bc9d0 | feat(04-03): register audio split/join handlers and update help text |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- [x] `handle_split_audio_command` exists in bot/handlers.py
- [x] `handle_join_audio_start` exists in bot/handlers.py
- [x] `handle_join_audio_file` exists in bot/handlers.py
- [x] `handle_join_audio_done` exists in bot/handlers.py
- [x] `handle_join_audio_cancel` exists in bot/handlers.py
- [x] Handlers are registered in bot/main.py
- [x] `/start` help text includes new commands
- [x] All imports work without errors (Python syntax check passed)

## Self-Check: PASSED

All files verified to exist:
- bot/handlers.py - Modified with new handlers
- bot/main.py - Modified with handler registrations

All commits verified:
- ce068aa - Found in git log
- 6fef4e0 - Found in git log
- 47bc9d0 - Found in git log
