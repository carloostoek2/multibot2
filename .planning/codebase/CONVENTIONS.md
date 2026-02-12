# Coding Conventions

**Analysis Date:** 2026-02-11

## Naming Patterns

**Files:**
- Module files use `snake_case.py`: `video_processor.py`, `temp_manager.py`, `error_handler.py`
- Descriptive names indicate purpose: `handlers.py` for Telegram handlers, `config.py` for configuration

**Functions:**
- Public functions use `snake_case`: `handle_video()`, `start()`, `process_video()`
- Private/helper functions prefixed with underscore: `_process_video_with_timeout()`
- Async functions for I/O operations: `async def handle_video()`, `async def error_handler()`
- Static methods for utility functions: `process_video()` static method in VideoProcessor

**Variables:**
- Constants use `UPPER_SNAKE_CASE`: `PROCESSING_TIMEOUT = 60`, `BOT_TOKEN`
- Instance variables use `snake_case`: `input_path`, `output_path`, `temp_dir`
- Descriptive naming: `processing_message`, `user_id`, `input_filename`

**Classes:**
- PascalCase for class names: `VideoProcessor`, `TempManager`, `VideoProcessingError`
- Exception classes inherit from base exception: `DownloadError(VideoProcessingError)`

**Types:**
- Type hints used consistently for function parameters and returns
- Example: `async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None`
- Example: `def get_temp_path(self, filename: str) -> str`

## Code Style

**Formatting:**
- 4 spaces for indentation
- Max line length: ~100 characters (observed in practice)
- Double quotes for strings
- Trailing commas in multi-line collections

**Docstrings:**
- Google-style docstrings with Args/Returns/Raises sections
- All public functions and classes have docstrings
- Example from `error_handler.py`:
```python
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors gracefully and send user-friendly messages.

    Logs the full error for debugging and sends an appropriate
    message to the user based on the error type.

    Args:
        update: Telegram update object
        context: Telegram context object containing the error
    """
```

**Comments:**
- Inline comments explain complex logic (e.g., ffmpeg command building)
- Comments describe WHY, not WHAT
- Spanish language used for user-facing messages

## Import Organization

**Order:**
1. Standard library imports (grouped)
2. Third-party imports
3. Local module imports

**Example from `handlers.py`:**
```python
import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.temp_manager import TempManager
from bot.video_processor import VideoProcessor
from bot.error_handler import (
    DownloadError,
    FFmpegError,
    ProcessingTimeoutError,
    handle_processing_error,
)
```

**Path Aliases:**
- No path aliases configured
- Absolute imports from package root: `from bot.config import BOT_TOKEN`

## Error Handling

**Patterns:**
- Custom exception hierarchy in `bot/error_handler.py`
- Base exception: `VideoProcessingError`
- Specific exceptions: `DownloadError`, `FFmpegError`, `ProcessingTimeoutError`
- User-friendly error messages in Spanish stored in dictionary mapping
- Graceful degradation with try/except blocks at multiple levels

**Error Handler Decorator:**
```python
def wrap_with_error_handler(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            context.error = e
            await error_handler(update, context)
            raise
    return wrapper
```

**Exception Chaining:**
- Use `raise ... from e` to preserve original exception context
- Example: `raise DownloadError("No pude descargar el video") from e`

## Logging

**Framework:** Python standard `logging` module

**Patterns:**
- Module-level logger: `logger = logging.getLogger(__name__)`
- Log levels used appropriately:
  - `logger.info()`: Operational events (video received, processing started, success)
  - `logger.warning()`: Non-critical issues (cleanup failures, message deletion failures)
  - `logger.error()`: Errors that affect operation (download failures, processing errors)
  - `logger.exception()`: Exceptions with full traceback (in except blocks)
  - `logger.debug()`: Detailed debug info (ffmpeg commands, temp directory creation)

**Log Format:**
```python
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
```

**Log Context:**
- Always include `user_id` in log messages for traceability
- Example: `logger.info(f"Video received from user {user_id}")`

## Function Design

**Size:**
- Functions are focused and single-purpose (20-50 lines typical)
- Large handlers split into helper functions (e.g., `_process_video_with_timeout`)

**Parameters:**
- Explicit parameters with type hints
- Context objects passed through handler chain
- User ID passed explicitly for logging context

**Return Values:**
- Boolean returns for success/failure operations: `process() -> bool`
- None for async handlers
- Explicit return type annotations

## Module Design

**Exports:**
- No `__all__` defined in modules
- Public API implied by lack of underscore prefix

**Barrel Files:**
- Not used; explicit imports from specific modules

**Module Responsibilities:**
- `config.py`: Environment configuration only
- `main.py`: Application entry point and setup
- `handlers.py`: Telegram update handlers
- `error_handler.py`: Exception classes and error handling utilities
- `video_processor.py`: Video processing logic
- `temp_manager.py`: Temporary file management

## Language and Localization

**User-Facing Text:**
- Spanish language for all user messages
- Error messages user-friendly and actionable
- Example: "No pude descargar el video. Intenta con otro archivo."

**Code and Comments:**
- English for code, comments, and docstrings
- Consistent with Python standard library conventions

---

*Convention analysis: 2026-02-11*
