# Architecture

**Analysis Date:** 2026-02-17

## Pattern Overview

**Overall:** Layered architecture with clear separation of concerns

**Key Characteristics:**
- Handler layer processes Telegram updates and orchestrates workflows
- Processor layer contains pure business logic (ffmpeg operations)
- Service layer provides cross-cutting concerns (temp management, config, validation)
- Error handling is centralized with domain-specific exceptions
- All file operations use context managers for automatic cleanup

## Layers

**Handler Layer:**
- Purpose: Process Telegram updates, validate input, coordinate processing
- Location: `bot/handlers.py`
- Contains: Command handlers, message handlers, workflow orchestration
- Depends on: Processors, TempManager, ConfigService, Validators, ErrorHandler
- Used by: Telegram Application (python-telegram-bot)

**Processor Layer:**
- Purpose: Pure ffmpeg-based media processing without Telegram dependencies
- Location: `bot/video_processor.py`, `bot/format_processor.py`, `bot/split_processor.py`, `bot/join_processor.py`
- Contains: VideoProcessor, FormatConverter, AudioExtractor, VideoSplitter, VideoJoiner
- Depends on: ffmpeg CLI, filesystem
- Used by: Handler layer via asyncio.run_in_executor

**Service Layer:**
- Purpose: Cross-cutting infrastructure concerns
- Location: `bot/temp_manager.py`, `bot/config.py`, `bot/validators.py`
- Contains: TempManager, BotConfig, validation functions
- Depends on: Environment variables, filesystem, ffprobe
- Used by: All layers

**Error Handling Layer:**
- Purpose: Centralized error handling with user-friendly Spanish messages
- Location: `bot/error_handler.py`
- Contains: Custom exceptions, error handler, processing error handler
- Depends on: python-telegram-bot error types
- Used by: All handlers

## Data Flow

**Video Processing Flow:**

1. User sends video -> `handle_video()` in `bot/handlers.py`
2. Validate file size -> `validators.validate_file_size()`
3. Send "processing" message to user
4. Create TempManager context -> `temp_manager.TempManager()`
5. Download video -> `_download_with_retry()`
6. Validate video integrity -> `validators.validate_video_file()`
7. Check disk space -> `validators.check_disk_space()`
8. Process with ffmpeg -> `VideoProcessor.process()` via run_in_executor
9. Send result -> `update.message.reply_video_note()`
10. Cleanup -> TempManager context exit

**Command Processing Flow:**

1. User sends command with video -> `handle_*_command()`
2. Extract video from message or reply -> `_get_video_from_message()`
3. Same validation and processing flow as video handling
4. Send result in appropriate format

**Join Session Flow:**

1. `/join` command -> `handle_join_start()` creates session in `context.user_data`
2. Videos sent during session -> `handle_join_video()` adds to session list
3. `/done` command -> `handle_join_done()` processes all videos
4. `/cancel` command -> `handle_join_cancel()` cleans up session

## Key Abstractions

**TempManager:**
- Purpose: Automatic cleanup of temporary files
- Location: `bot/temp_manager.py`
- Pattern: Context manager with `__enter__`/`__exit__`
- Usage: `with TempManager() as temp_mgr:`
- Features: Subdirectory creation, file tracking, global cleanup on shutdown

**VideoProcessor Pattern:**
- Purpose: Template for all ffmpeg-based processors
- Location: `bot/video_processor.py` (reference implementation)
- Pattern: Class with `__init__(input_path, output_path)` and `process()` method
- Static method `process_video()` for one-shot usage
- Error handling via return boolean + logging

**BotConfig:**
- Purpose: Centralized, validated configuration
- Location: `bot/config.py`
- Pattern: Frozen dataclass with `__post_init__` validation
- Loaded once at startup, immutable thereafter

**Custom Exceptions:**
- Purpose: Domain-specific errors with user-friendly messages
- Location: `bot/error_handler.py`
- Hierarchy: VideoProcessingError -> SpecificError (DownloadError, FFmpegError, etc.)
- Error messages mapped in ERROR_MESSAGES dict for Spanish localization

## Entry Points

**Bot Startup:**
- Location: `bot/main.py`
- Triggers: `python run.py`
- Responsibilities: Configure logging, register handlers, start polling

**Handler Registration:**
- Location: `bot/main.py` lines 71-79
- Pattern: CommandHandler for commands, MessageHandler with filters for videos
- Error handler registered globally

**Signal Handling:**
- Location: `bot/main.py` lines 36-58
- Triggers: SIGINT, SIGTERM
- Responsibilities: Cleanup active temp managers, graceful shutdown

## Error Handling

**Strategy:** Fail-fast with user-friendly messages

**Patterns:**
- Validation before processing (size, integrity, disk space)
- Custom exceptions for each error type
- Centralized error handler maps exceptions to Spanish messages
- Retry logic with exponential backoff for transient network errors
- Correlation IDs for request tracing across logs

## Cross-Cutting Concerns

**Logging:**
- Location: Configured in `bot/main.py`
- Pattern: Standard Python logging with module-level loggers
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Level: Configurable via LOG_LEVEL env var

**Validation:**
- Location: `bot/validators.py`
- Pattern: Functions return (is_valid, error_message) tuple
- Types: File size, video integrity (ffprobe), disk space

**Authentication:**
- Pattern: Telegram bot token via environment variable
- No user authentication beyond Telegram's built-in verification

---

*Architecture analysis: 2026-02-17*
