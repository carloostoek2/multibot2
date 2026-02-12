# External Integrations

**Analysis Date:** 2026-02-11

## APIs & External Services

**Telegram Bot API:**
- Service: Telegram Bot Platform
- Purpose: Receiving messages, sending video notes, handling commands
- SDK: `python-telegram-bot` (v20.0+)
- Auth: `BOT_TOKEN` environment variable
- Features used:
  - Polling for updates (`application.run_polling()`)
  - Command handlers (`/start`)
  - Message handlers (video filter)
  - File download (`video.get_file()`)
  - Video note replies (`message.reply_video_note()`)
  - Error handling middleware

## Data Storage

**Databases:**
- Not used - Stateless bot architecture

**File Storage:**
- Local filesystem only
- Temporary directory: Created via `tempfile.mkdtemp(prefix="videonote_")`
- Input videos: Downloaded to temp storage
- Output videos: Processed and immediately sent
- Cleanup: Automatic via `TempManager` context manager

**Caching:**
- Not used

## Authentication & Identity

**Auth Provider:**
- Telegram Bot API token-based authentication
- Token format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
- Validation: Runtime check in `bot/config.py`

## Monitoring & Observability

**Error Tracking:**
- Custom error handling in `bot/error_handler.py`
- Logging to stdout/stderr
- User-friendly error messages in Spanish

**Logs:**
- Python standard logging module
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Loggers per module (`__name__`)
- Levels used: DEBUG, INFO, WARNING, ERROR, EXCEPTION

## CI/CD & Deployment

**Hosting:**
- Not specified - designed to run anywhere Python is supported

**CI Pipeline:**
- Not detected

## Environment Configuration

**Required env vars:**
- `BOT_TOKEN` - Telegram Bot API authentication token

**Secrets location:**
- `.env` file (loaded via python-dotenv)
- `.env.example` provided as template
- `.gitignore` should exclude `.env` (verify this)

## Webhooks & Callbacks

**Incoming:**
- Telegram Bot API webhook/polling endpoint
- Video message handler (`handle_video` in `bot/handlers.py`)
- Start command handler (`start` in `bot/handlers.py`)

**Outgoing:**
- Telegram Bot API sendVideoNote endpoint
- File download from Telegram servers

## System Dependencies

**FFmpeg:**
- Required for video processing
- Command-line tool (not a Python package)
- Installation: System package manager (apt, brew, etc.)
- Version requirements: Not specified (should support libx264 and aac)
- Validation: Runtime check in `VideoProcessor._check_ffmpeg()`

---

*Integration audit: 2026-02-11*
