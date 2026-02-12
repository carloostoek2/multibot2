# Architecture

**Analysis Date:** 2026-02-11

## Pattern Overview

**Overall:** Layered Architecture with Handler-Based Message Processing

**Key Characteristics:**
- Asynchronous message-driven architecture using python-telegram-bot v20+
- Separation of concerns with distinct layers for configuration, processing, and error handling
- Context manager pattern for resource cleanup (temporary files)
- Static method pattern for stateless video processing operations
- Decorator pattern for error handling wrapper

## Layers

**Configuration Layer:**
- Purpose: Environment setup and secrets management
- Location: `bot/config.py`
- Contains: Environment variable loading, BOT_TOKEN validation
- Depends on: python-dotenv, os
- Used by: Main application layer

**Application Layer:**
- Purpose: Bot initialization and handler registration
- Location: `bot/main.py`
- Contains: Application setup, handler routing, error handler registration
- Depends on: Configuration layer, Handler layer, Error handling layer
- Used by: Entry point script

**Handler Layer:**
- Purpose: Telegram message processing and user interaction
- Location: `bot/handlers.py`
- Contains: Command handlers (/start), message handlers (video processing), timeout management
- Depends on: TempManager, VideoProcessor, ErrorHandler
- Used by: Application layer

**Processing Layer:**
- Purpose: Video transformation using ffmpeg
- Location: `bot/video_processor.py`
- Contains: VideoProcessor class with ffmpeg command construction and execution
- Depends on: shutil, subprocess, pathlib
- Used by: Handler layer

**Resource Management Layer:**
- Purpose: Temporary file lifecycle management
- Location: `bot/temp_manager.py`
- Contains: TempManager context manager for automatic cleanup
- Depends on: tempfile, shutil, os
- Used by: Handler layer

**Error Handling Layer:**
- Purpose: Centralized exception management and user-friendly error messages
- Location: `bot/error_handler.py`
- Contains: Custom exception hierarchy, error handler function, error message mapping
- Depends on: telegram.Update, telegram.ext.ContextTypes
- Used by: All layers

## Data Flow

**Video Processing Flow:**

1. **Receive:** Telegram webhook/polling receives video message (`bot/main.py`)
2. **Route:** Application routes to `handle_video` handler (`bot/handlers.py`)
3. **Initialize:** TempManager creates temporary directory (`bot/temp_manager.py`)
4. **Download:** Video file downloaded from Telegram to temp location (`bot/handlers.py`)
5. **Process:** VideoProcessor executes ffmpeg transformation (`bot/video_processor.py`)
   - Validates ffmpeg availability
   - Constructs ffmpeg command with filters
   - Executes subprocess with timeout
6. **Respond:** Processed video sent as video note (`bot/handlers.py`)
7. **Cleanup:** TempManager removes temporary files (context manager exit)

**Error Handling Flow:**

1. Exception occurs in any layer
2. Exception propagates to handler layer
3. Known exceptions (DownloadError, FFmpegError, ProcessingTimeoutError) mapped to user-friendly Spanish messages
4. Unknown exceptions logged with full stack trace
5. User receives error message via Telegram
6. Cleanup still executes via context manager

**State Management:**
- No persistent state - purely request/response processing
- Temporary state managed via TempManager context manager
- Configuration loaded once at startup from environment variables

## Key Abstractions

**VideoProcessor:**
- Purpose: Encapsulate ffmpeg video transformation logic
- Examples: `bot/video_processor.py`
- Pattern: Class with static factory method (process_video)

**TempManager:**
- Purpose: Ensure temporary file cleanup via context manager protocol
- Examples: `bot/temp_manager.py`
- Pattern: Context manager (`__enter__`/`__exit__`)

**VideoProcessingError (Exception Hierarchy):**
- Purpose: Structured error handling with domain-specific exceptions
- Examples: `bot/error_handler.py` - DownloadError, FFmpegError, ProcessingTimeoutError
- Pattern: Exception inheritance hierarchy

**Error Handler Decorator:**
- Purpose: Wrap handlers with standardized error handling
- Examples: `bot/error_handler.py` - wrap_with_error_handler
- Pattern: Decorator with functools.wraps

## Entry Points

**Primary Entry Point:**
- Location: `run.py`
- Triggers: Direct execution or deployment platform
- Responsibilities: Async runtime setup, graceful shutdown on KeyboardInterrupt

**Bot Application Entry Point:**
- Location: `bot/main.py` - main()
- Triggers: Called by run.py
- Responsibilities: Application builder pattern, handler registration, polling initialization

**Error Handler Entry Point:**
- Location: `bot/error_handler.py` - error_handler()
- Triggers: Registered as global error handler in Application
- Responsibilities: Exception logging, user message mapping, error response sending

## Error Handling

**Strategy:** Layer-specific exceptions with centralized mapping to user-friendly messages

**Patterns:**
- Custom exception hierarchy inheriting from VideoProcessingError
- Error type to message mapping dictionary (ERROR_MESSAGES)
- Graceful degradation with try/except blocks at handler level
- Automatic cleanup via context managers (finally behavior)

## Cross-Cutting Concerns

**Logging:** Standard Python logging with module-level loggers, structured format including timestamp, name, level, message

**Validation:** Input validation via python-telegram-bot filters (filters.VIDEO), environment variable validation at startup

**Authentication:** Token-based authentication via BOT_TOKEN environment variable, handled by python-telegram-bot library

---

*Architecture analysis: 2026-02-11*
