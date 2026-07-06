# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- **Local**: `.env` at project root, loaded via `python-dotenv`
- **Production**: Railway (see `railway.toml`, `docker/railway-entrypoint.sh`)
- **Python**: 3.11, entry point: `run.py` → `bot.main:main()`
- **Config**: `bot/config.py` — `BotConfig` frozen dataclass; all env vars validated at startup. Singleton `config` at module level.

## Key Env Vars

| Variable | Purpose |
|----------|---------|
| `BOT_TOKEN` | Telegram bot token (required) |
| `TELEGRAM_LOCAL_MODE` | Self-hosted Bot API for >50MB files (default: false) |
| `TELEGRAM_API_BASE_URL` | Local Bot API URL (required if local mode) |
| `COOKIES_FILE` | Path to cookies.txt for yt-dlp/gallery-dl auth |
| `COOKIES_CONTENT_BASE64` | Base64-encoded cookies for Railway (decoded at startup) |
| `LOG_LEVEL` | Python logging level (default: INFO) |

## Running Tests

```bash
pytest tests/                          # All tests
pytest tests/unit/                     # Unit tests only
pytest tests/unit/test_audio_effects_pitch.py -v  # Single file
```

- Framework: `pytest` + `pytest-asyncio` (no `conftest.py`, no `pytest.ini`, no `pyproject.toml`)
- Tests use `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`) and `SimpleNamespace` for light mocks
- Use `pytest.mark.asyncio` for async test functions
- Dependencies are in `requirements.txt` (no `pyproject.toml`)

## Architecture

### Handler Layer

All Telegram handlers live in `bot/handlers.py` (~12,000 lines). Each handler is an `async` function accepting `(update: Update, context: ContextTypes.DEFAULT_TYPE)`. Handlers generate an 8-char `correlation_id` (UUID hex prefix) at the top for request tracing — logged as `[{correlation_id}]`.

Per-user state is stored in `context.user_data` dict. Callback flows use `InlineKeyboardMarkup` with string `callback_data` patterns.

### Handler Registration (`bot/main.py`)

`main.py` builds the `Application`, registers handlers, and starts polling. Rules for ordering:

- Commands first, then callback queries (most specific → least specific), then message handlers
- Cancel/back navigation callbacks go before action callbacks
- Each `CallbackQueryHandler` uses a `pattern="^regex$"` to match callback data

To add a handler: import the function from `bot.handlers`, add the handler registration in `main.py` at the right specificity position.

### Download System (`bot/downloaders/`)

Self-contained package. Flow:

```
URL → URLDetector → PlatformRouter → platform-specific BaseDownloader
    → DownloadLifecycle (isolated temp dir, state machine)
    → DownloadManager (asyncio semaphore concurrency) → DownloadResult
```

- **`DownloadFacade`**: unified API (`start`/`stop`/`download`), used by handlers
- **`download_url()`**: convenience one-off call
- **Platform routers**: `platforms/youtube.py`, `instagram.py`, `tiktok.py`, `twitter.py`, `facebook.py`
- **Fallback chain**: platform handlers → generic video → yt-dlp → HTML extractor
- **`RetryHandler`**: exponential backoff with jitter
- **`ProgressTracker`**: throttled progress callbacks

### Processing Modules

Each processor follows the same pattern:

```
class XxxProcessor:
    def __init__(self, input_path, output_path)
    def _validate_input(self): ...   # check file exists, ffmpeg available
    def process(self, **params): ... # returns self for chaining
```

- `bot/audio_effects.py` — `AudioEffects`: denoise, compress, normalize, stereo_3d, pitch_shift (method chaining with intermediate temp files)
- `bot/audio_enhancer.py` — `AudioEnhancer`: bass boost, treble boost, 3-band EQ
- `bot/image_processor.py` — `ImageProcessor`: Pillow-based operations (enhance, noise, etc.)
- `bot/video_processor.py`, `bot/video_merger.py`, `bot/format_processor.py`, `bot/audio_processor.py`
- `bot/screenshot_processor.py`, `bot/validators.py`

### Error Handling (`bot/error_handler.py`)

Custom exception hierarchy: `VideoProcessingError` → `DownloadError`, `FFmpegError`, `ProcessingTimeoutError`, etc. A global `error_handler` callback is registered on the Application. All user-facing messages are in Spanish.

### Temp File Management (`bot/temp_manager.py`)

`TempManager` provides scoped temp directories. `active_temp_managers` global set is cleaned up on `SIGINT`/`SIGTERM` (registered in `main.py`).

### Telegram Client Modes (`bot/telegram_client.py`)

Cloud mode (standard Bot API, 50MB limit) vs Local mode (self-hosted `telegram-bot-api`, 2000MB limit). Local mode requires `TELEGRAM_LOCAL_MODE=true` and `TELEGRAM_API_BASE_URL`.

## Cookies for Authenticated Downloads

Local dev: `COOKIES_FILE=cookies.txt` at project root.

Railway production (no persistent volumes): encode cookies as `COOKIES_CONTENT_BASE64=<base64>`. `BotConfig._setup_cookies_from_base64()` decodes to `/tmp/cookies.txt` at startup. Priority: base64 > file path > no cookies.

## Docker / Railway

- `Dockerfile`: multi-stage, installs ffmpeg + telegram-bot-api binary + Deno (for yt-dlp JS extractors) + nightly yt-dlp
- `docker/railway-entrypoint.sh`: updates yt-dlp nightly, starts local Bot API server if `TELEGRAM_LOCAL_MODE=true`, then runs the bot
- `docker-compose.yml`: local dev with local API mode, 2000MB upload limit
- `railway.toml`: DOCKERFILE builder, `ON_FAILURE` restart (max 10)

## Planning Docs

`.planning/` contains `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and per-phase artifacts in `.planning/phases/`. Consult these for feature context and implementation history.
