---
phase: "01"
plan: "02"
subsystem: "video-processing"
tags: ["ffmpeg", "telegram", "video", "python-telegram-bot"]

dependency_graph:
  requires: ["01-01"]
  provides: ["Video processing pipeline", "Telegram handlers", "Temp file management"]
  affects: ["02-deployment"]

tech-stack:
  added: ["ffmpeg"]
  patterns: ["Context manager for resource cleanup", "Static factory methods"]

file-tracking:
  created:
    - "bot/temp_manager.py"
    - "bot/video_processor.py"
    - "bot/handlers.py"
  modified:
    - "bot/main.py"

decisions:
  - id: "D01-02-01"
    context: "Temporary file management"
    decision: "Use TempManager with context manager protocol for automatic cleanup"
    rationale: "Ensures temp files are cleaned up even if processing fails or raises exceptions"
  - id: "D01-02-02"
    context: "Video format requirements"
    decision: "Crop to 1:1 square centered, scale to 640x640 max, limit 60s, no audio"
    rationale: "Telegram video notes require square format, max 640x640, and don't support audio"
  - id: "D01-02-03"
    context: "Error handling strategy"
    decision: "Log errors internally, send user-friendly messages to users"
    rationale: "Don't expose internal errors to users, but inform them when something goes wrong"

metrics:
  duration: "~15 minutes"
  completed: "2025-02-03"
---

# Phase 01 Plan 02: Core Video Processing Implementation Summary

**One-liner:** Implemented complete video processing pipeline: TempManager for temp files, VideoProcessor with ffmpeg for 1:1 square conversion, and Telegram handlers for download/process/send flow.

## What Was Built

### TempManager (`bot/temp_manager.py`)
- Creates unique temporary directories using `tempfile.mkdtemp`
- Provides `get_temp_path()` for safe file path generation
- `cleanup()` removes directory with error handling
- Context manager support (`__enter__`, `__exit__`) for automatic cleanup
- Safe filename handling to prevent directory traversal attacks

### VideoProcessor (`bot/video_processor.py`)
- `VideoProcessor` class with `process()` method
- Static `process_video()` shortcut method
- ffmpeg command with video note specifications:
  - Center crop to 1:1 square: `crop=ih:ih`
  - Scale to max 640x640: `scale=640:640:force_original_aspect_ratio=decrease`
  - Duration limit: `-t 60`
  - Quality: `-crf 23`, `-preset medium`
  - Format: MP4 with `yuv420p` pixel format
  - Audio removed: `-an`
- ffmpeg availability check via `shutil.which()`
- Comprehensive error handling with logging

### Telegram Handlers (`bot/handlers.py`)
- `handle_video()`: Async handler for video messages
  - Downloads video from Telegram to temp file
  - Processes with VideoProcessor
  - Sends result as circular video note
  - Error handling with user-friendly messages
- `start()`: Welcome message with usage instructions
- TempManager used as context manager for automatic cleanup

### Updated main.py
- Imports handlers from `bot.handlers`
- Registers `/start` command handler
- Registers video message handler

## Key Implementation Details

### Video Processing Pipeline
1. User sends video to bot
2. `handle_video` receives update
3. `TempManager` creates temp directory
4. Video downloaded via `video.get_file().download_to_drive()`
5. `VideoProcessor.process_video()` converts to 1:1 format
6. Processed video sent as `reply_video_note()`
7. `TempManager` auto-cleans on context exit

### ffmpeg Parameters Explained
```bash
ffmpeg -y -i input.mp4 -t 60 \
  -vf "crop=ih:ih,scale=640:640:force_original_aspect_ratio=decrease" \
  -c:v libx264 -preset medium -crf 23 \
  -pix_fmt yuv420p -movflags +faststart -an \
  output.mp4
```
- `crop=ih:ih`: Crops to square using height as both dimensions (centered by default)
- `scale=640:640:force_original_aspect_ratio=decrease`: Fits within 640x640 maintaining aspect
- `-t 60`: Limits output to 60 seconds
- `-an`: Removes audio (video notes don't have audio)

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All verification criteria passed:
- [x] TempManager crea y limpia directorios temporales
- [x] VideoProcessor ejecuta ffmpeg con parámetros correctos
- [x] Handler integra descarga, procesamiento y envío
- [x] Todos los imports funcionan correctamente
- [x] Manejo de errores implementado

## Success Criteria Verification

1. [x] Videos se descargan desde Telegram a archivos temporales
2. [x] ffmpeg procesa videos a formato 1:1 cuadrado centrado
3. [x] Duración limitada a 60 segundos
4. [x] Resolución máxima 640x640
5. [x] Resultado se envía como video note circular
6. [x] Archivos temporales se limpian después del procesamiento

## Artifacts Verification

| File | Lines | Min Lines | Exports | Status |
|------|-------|-----------|---------|--------|
| `bot/temp_manager.py` | 53 | 30 | `TempManager` | ✓ |
| `bot/video_processor.py` | 112 | 50 | `VideoProcessor`, `process_video` | ✓ |
| `bot/handlers.py` | 82 | 40 | `handle_video` | ✓ |

## Key Links Verification

- [x] `bot/handlers.py` → `bot/video_processor.py` via `VideoProcessor.process_video()`
- [x] `bot/handlers.py` → `bot/temp_manager.py` via `TempManager` context manager
- [x] `bot/video_processor.py` → `bot/temp_manager.py` via temp directory paths

## Commits

| Commit | Description |
|--------|-------------|
| `f48985d` | feat(01-02): create TempManager for temporary file handling |
| `20d3e94` | feat(01-02): implement VideoProcessor with ffmpeg |
| `a9473bb` | feat(01-02): create Telegram handlers and update main.py |

## Next Steps

The core video processing functionality is complete. The bot can now:
1. Receive videos from Telegram users
2. Process them to video note format (1:1 square, 640x640 max, 60s max)
3. Send them back as circular video notes
4. Clean up temporary files automatically

Ready for Phase 02: Deployment.
