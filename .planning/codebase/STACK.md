# Technology Stack

**Analysis Date:** 2026-02-11

## Languages

**Primary:**
- Python 3.x - All application code

**Secondary:**
- Shell (Bash) - Runtime execution via `run.py` shebang

## Runtime

**Environment:**
- Python 3.x (asyncio-based)

**Package Manager:**
- pip (Python standard)
- Lockfile: Not present (requirements.txt uses loose versioning)

## Frameworks

**Core:**
- python-telegram-bot v20.0+ - Telegram Bot API wrapper with async support
- python-dotenv v1.0.0+ - Environment variable management

**Testing:**
- Not detected

**Build/Dev:**
- Not detected

## Key Dependencies

**Critical:**
- `python-telegram-bot>=20.0` - Core framework for Telegram bot functionality
  - Provides `Application`, `CommandHandler`, `MessageHandler`, `filters`
  - Async/await support via `asyncio`
  - File download and upload capabilities

**Infrastructure:**
- `python-dotenv>=1.0.0` - Loads environment variables from `.env` file

**System Dependencies:**
- FFmpeg - External binary required for video processing
  - Must be installed separately and available in PATH
  - Used for video transcoding, cropping, scaling
  - Required codecs: libx264 (video), aac (audio)

## Configuration

**Environment:**
- Loaded from `.env` file via python-dotenv
- Required variable: `BOT_TOKEN` (Telegram Bot API token)
- Validation: Raises `ValueError` if `BOT_TOKEN` is missing

**Build:**
- No build configuration detected
- No bundling or compilation steps

**Application:**
- Logging configured in `bot/main.py` with basic format
- Log level: INFO
- Timeout settings: 60 seconds for video processing (defined in `bot/handlers.py`)

## Platform Requirements

**Development:**
- Python 3.x with asyncio support
- FFmpeg installed and in PATH
- pip for package installation

**Production:**
- Same as development
- Environment variables configured
- Write access for temporary file storage (video processing)

---

*Stack analysis: 2026-02-11*
