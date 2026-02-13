# Phase 02: Error Handling & Configuration - Research

**Research Goal:** Determine what is needed to plan robust error handling and configuration management for the Telegram video processing bot.

**Confidence Level:** HIGH - Based on existing codebase analysis and python-telegram-bot v22.6 patterns.

---

## Current State Analysis

### Existing Error Handling Infrastructure

The codebase already has a solid foundation for error handling:

**Custom Exception Hierarchy** (`bot/error_handler.py`):
- `VideoProcessingError` - Base exception with Spanish user message
- `DownloadError` - Video download failures
- `FFmpegError` - Video processing failures
- `ProcessingTimeoutError` - Timeout handling
- `FormatConversionError` - Format conversion failures
- `AudioExtractionError` - Audio extraction failures
- `VideoSplitError` - Video splitting failures
- `VideoJoinError` - Video joining failures

**Error Handler Function**:
- `error_handler(update, context)` - Global error handler registered in main.py
- `handle_processing_error()` - Convenience function for processing errors
- `wrap_with_error_handler()` - Decorator for handler functions
- User-friendly Spanish error messages mapped to exception types
- Full error logging with traceback for debugging

**TempManager Context Manager** (`bot/temp_manager.py`):
- Already implements automatic cleanup via `__exit__()`
- Used consistently across all handlers with `with TempManager() as temp_mgr:`
- Tracks files and subdirectories
- Handles cleanup errors gracefully with `ignore_errors=True`

**Timeout Handling**:
- `PROCESSING_TIMEOUT = 60` seconds constant defined in handlers.py
- Used with `asyncio.wait_for()` in all video processing operations
- Different timeout for join operations (120 seconds per D01.1-03-03)

### Current Configuration Approach

**Existing Configuration** (`bot/config.py`):
```python
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required...")
```

- Uses `python-dotenv` to load `.env` file
- Validates BOT_TOKEN at import time (early fail)
- Simple, focused configuration module

### Current Logging Setup

**Basic Logging** (`bot/main.py`):
```python
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
```

- All modules use `logging.getLogger(__name__)`
- Log levels used appropriately:
  - `logger.info()` - Operations (downloads, processing starts/completions)
  - `logger.debug()` - Detailed debugging (temp directory creation)
  - `logger.warning()` - Non-fatal issues (cleanup failures)
  - `logger.error()` - Errors (download failures, processing errors)
  - `logger.exception()` - Exceptions with traceback

---

## Phase 02 Requirements Analysis

### ERR-01: User Notification on Processing Failure

**Current Status:** PARTIALLY IMPLEMENTED

**What's Working:**
- Custom exceptions with Spanish user messages
- `handle_processing_error()` sends user-friendly messages
- Global error handler catches unhandled exceptions

**What's Missing:**
- No validation of video before processing (size, format, corruption)
- No graceful handling of Telegram API errors (network issues, rate limits)
- No specific handling for disk space issues

**Research Findings:**

1. **Pre-processing Validation**
   - Check video file size before download (Telegram file size limit: 20MB for bots)
   - Validate video format using ffprobe before processing
   - Check available disk space before download

2. **Telegram API Error Handling**
   - Network errors: `telegram.error.NetworkError`
   - Timed out: `telegram.error.TimedOut`
   - Retry logic for transient failures
   - Chat not found/Forbidden: `telegram.error.BadRequest`

3. **Corruption Detection**
   - Use ffprobe to validate video integrity before processing
   - Check video duration (0 duration indicates corruption)
   - Verify video streams exist

### ERR-02: Temporary File Cleanup

**Current Status:** IMPLEMENTED

**What's Working:**
- `TempManager` with context manager protocol
- Automatic cleanup via `__exit__()`
- `ignore_errors=True` in `shutil.rmtree()` prevents cleanup failures from crashing
- Used consistently in all handlers

**What's Missing:**
- No explicit cleanup on bot shutdown
- No tracking of orphaned temp directories from crashes
- No cleanup of old temp directories on startup

**Research Findings:**

1. **Startup Cleanup**
   - Scan for old `videonote_*` directories in temp
   - Remove directories older than 24 hours on startup
   - Prevents disk accumulation from crashes

2. **Signal Handling**
   - Handle SIGINT/SIGTERM for graceful shutdown
   - Ensure cleanup happens on bot stop

3. **Disk Space Monitoring**
   - Check available space before operations
   - Fail fast if insufficient space

### ERR-03: Timeout Handling

**Current Status:** IMPLEMENTED

**What's Working:**
- `asyncio.wait_for()` with 60-second timeout
- `ProcessingTimeoutError` exception
- User-friendly timeout message in Spanish

**What's Missing:**
- No differentiation between download timeout and processing timeout
- No retry logic for transient timeouts
- No configurable timeout values

**Research Findings:**

1. **Timeout Categories**
   - Download timeout: 30-60 seconds (depends on file size)
   - Processing timeout: 60 seconds (current)
   - Join operation timeout: 120 seconds (D01.1-03-03)

2. **Configurable Timeouts**
   - Environment variables for timeout values
   - Different timeouts for different operations
   - Admin override capability

### CONF-01: Environment Variable Configuration

**Current Status:** PARTIALLY IMPLEMENTED

**What's Working:**
- BOT_TOKEN loaded from environment
- Early validation at import time
- `python-dotenv` for .env file support

**What's Missing:**
- No configuration for timeouts
- No configuration for file size limits
- No configuration for logging level
- No configuration for temp directory location
- No validation of configuration values

**Research Findings:**

Required Configuration Variables:
```bash
# Required
BOT_TOKEN=your_bot_token

# Optional with defaults
PROCESSING_TIMEOUT_SECONDS=60
DOWNLOAD_TIMEOUT_SECONDS=60
JOIN_TIMEOUT_SECONDS=120
MAX_FILE_SIZE_MB=20
LOG_LEVEL=INFO
TEMP_DIR=/tmp
JOIN_SESSION_TIMEOUT_SECONDS=300
MAX_SEGMENTS=10
MIN_SEGMENT_SECONDS=5
```

### CONF-02: Logging Configuration

**Current Status:** BASIC

**What's Working:**
- Basic logging setup in main.py
- Consistent format across modules
- Appropriate log levels used

**What's Missing:**
- No file logging (console only)
- No log rotation
- No structured logging (JSON)
- No correlation IDs for tracking requests
- No configuration of log level via environment

**Research Findings:**

1. **Logging Best Practices for Bots**
   - Structured logging for machine parsing
   - Request correlation IDs (user_id + timestamp)
   - Separate error log for monitoring
   - Log rotation to prevent disk fill

2. **Python Logging Configuration**
   - Use `logging.config.dictConfig()` for complex setups
   - Environment variable for log level: `LOG_LEVEL`
   - Optional file logging: `LOG_FILE_PATH`

---

## Standard Stack & Patterns

### Error Handling Patterns

**Pattern 1: Layered Error Handling**
```python
# Layer 1: Business logic raises specific exceptions
# Layer 2: Handler catches and converts to user messages
# Layer 3: Global error handler catches unexpected errors
```

**Pattern 2: Context Manager for Resources**
```python
with TempManager() as temp_mgr:
    # Process with automatic cleanup
    pass  # Cleanup happens automatically
```

**Pattern 3: Timeout Wrapper**
```python
try:
    result = await asyncio.wait_for(
        operation(),
        timeout=PROCESSING_TIMEOUT
    )
except asyncio.TimeoutError:
    raise ProcessingTimeoutError("Operation timed out")
```

### Configuration Management Pattern

**Pattern: Centralized Config with Validation**
```python
# bot/config.py
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    BOT_TOKEN: str
    PROCESSING_TIMEOUT: int = 60
    # ... etc

def load_config() -> Config:
    # Validation logic
    # Environment loading
    # Type conversion
    pass

config = load_config()
```

### Logging Pattern

**Pattern: Structured Logging with Correlation**
```python
# Add correlation ID to track operations
import uuid
correlation_id = str(uuid.uuid4())[:8]
logger.info(f"[{correlation_id}] Starting processing for user {user_id}")
```

---

## Don't Hand-Roll

**Already Implemented (Don't Rebuild):**

1. **TempManager** - Already has context manager protocol, automatic cleanup
2. **Custom Exceptions** - Already has hierarchy with Spanish messages
3. **Error Handler** - Already has global error handler registration
4. **Basic Logging** - Already has consistent logging setup
5. **Timeout Handling** - Already uses `asyncio.wait_for()`

**Use Existing Solutions:**

1. **python-dotenv** - Already in use for .env loading
2. **logging module** - Don't use third-party logging libraries
3. **tempfile module** - Already used by TempManager
4. **asyncio timeouts** - Don't use signal-based timeouts

---

## Common Pitfalls

### Error Handling Pitfalls

1. **Catching Exception Too Broadly**
   - Current code catches specific exceptions well
   - Avoid `except Exception:` in business logic
   - Use `except Exception:` only in global error handler

2. **Losing Stack Traces**
   - Always use `raise NewError() from original_error`
   - Current code does this correctly

3. **Not Cleaning Up Resources**
   - TempManager handles most cases
   - Ensure cleanup on SIGINT/SIGTERM

4. **Silent Failures**
   - Always log before returning error to user
   - Current code logs with `logger.exception()`

### Configuration Pitfalls

1. **Late Validation**
   - Validate at import time (already done for BOT_TOKEN)
   - Fail fast on missing required config

2. **No Type Conversion**
   - Convert env strings to int/float/bool
   - Validate ranges (timeouts > 0)

3. **Hardcoded Values**
   - Move timeouts to config
   - Move limits to config

### Logging Pitfalls

1. **Logging Sensitive Data**
   - Never log BOT_TOKEN
   - Don't log full file paths with user data
   - Current code is good about this

2. **No Log Rotation**
   - If adding file logging, use RotatingFileHandler
   - Prevent disk space exhaustion

3. **Inconsistent Log Levels**
   - ERROR: Something failed, user impact
   - WARNING: Something odd, no user impact yet
   - INFO: Normal operations
   - DEBUG: Detailed diagnostics

---

## Code Examples

### Example 1: Enhanced Configuration

```python
# bot/config.py
import os
import sys
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class BotConfig:
    """Bot configuration with validation."""

    # Required
    BOT_TOKEN: str

    # Timeouts (seconds)
    PROCESSING_TIMEOUT: int = 60
    DOWNLOAD_TIMEOUT: int = 60
    JOIN_TIMEOUT: int = 120
    JOIN_SESSION_TIMEOUT: int = 300

    # Limits
    MAX_FILE_SIZE_MB: int = 20
    MAX_SEGMENTS: int = 10
    MIN_SEGMENT_SECONDS: int = 5
    JOIN_MAX_VIDEOS: int = 10
    JOIN_MIN_VIDEOS: int = 2

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Paths
    TEMP_DIR: Optional[str] = None

    def __post_init__(self):
        # Validate BOT_TOKEN
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")

        # Validate timeouts are positive
        for field in ['PROCESSING_TIMEOUT', 'DOWNLOAD_TIMEOUT', 'JOIN_TIMEOUT']:
            value = getattr(self, field)
            if value <= 0:
                raise ValueError(f"{field} must be positive, got {value}")

        # Validate LOG_LEVEL
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.LOG_LEVEL.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")


def load_config() -> BotConfig:
    """Load configuration from environment variables."""
    return BotConfig(
        BOT_TOKEN=os.getenv('BOT_TOKEN', ''),
        PROCESSING_TIMEOUT=int(os.getenv('PROCESSING_TIMEOUT_SECONDS', '60')),
        DOWNLOAD_TIMEOUT=int(os.getenv('DOWNLOAD_TIMEOUT_SECONDS', '60')),
        JOIN_TIMEOUT=int(os.getenv('JOIN_TIMEOUT_SECONDS', '120')),
        JOIN_SESSION_TIMEOUT=int(os.getenv('JOIN_SESSION_TIMEOUT_SECONDS', '300')),
        MAX_FILE_SIZE_MB=int(os.getenv('MAX_FILE_SIZE_MB', '20')),
        MAX_SEGMENTS=int(os.getenv('MAX_SEGMENTS', '10')),
        MIN_SEGMENT_SECONDS=int(os.getenv('MIN_SEGMENT_SECONDS', '5')),
        JOIN_MAX_VIDEOS=int(os.getenv('JOIN_MAX_VIDEOS', '10')),
        JOIN_MIN_VIDEOS=int(os.getenv('JOIN_MIN_VIDEOS', '2')),
        LOG_LEVEL=os.getenv('LOG_LEVEL', 'INFO'),
        LOG_FORMAT=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        TEMP_DIR=os.getenv('TEMP_DIR'),
    )


# Global config instance
config = load_config()
```

### Example 2: Startup Cleanup

```python
# bot/temp_manager.py
import atexit
import glob
import os
import tempfile
import time
from pathlib import Path

def cleanup_old_temp_directories(max_age_hours: int = 24):
    """Remove old temporary directories on startup.

    Args:
        max_age_hours: Remove directories older than this many hours
    """
    temp_dir = tempfile.gettempdir()
    pattern = os.path.join(temp_dir, "videonote_*")

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    removed_count = 0
    for dir_path in glob.glob(pattern):
        try:
            dir_time = os.path.getctime(dir_path)
            age_seconds = current_time - dir_time

            if age_seconds > max_age_seconds:
                import shutil
                shutil.rmtree(dir_path, ignore_errors=True)
                removed_count += 1
                logger.info(f"Removed old temp directory: {dir_path} (age: {age_seconds/3600:.1f} hours)")
        except Exception as e:
            logger.warning(f"Failed to check/remove old temp directory {dir_path}: {e}")

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old temporary directories")


# Call on module import
cleanup_old_temp_directories()
```

### Example 3: Signal Handling for Graceful Shutdown

```python
# bot/main.py
import signal
import sys
from bot.temp_manager import active_temp_managers

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")

    # Cleanup any active temp managers
    for temp_mgr in active_temp_managers:
        try:
            temp_mgr.cleanup()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

### Example 4: Enhanced Error Handler with Telegram API Errors

```python
# bot/error_handler.py
from telegram.error import NetworkError, TimedOut, BadRequest, TelegramError

# Add Telegram API errors to error messages
ERROR_MESSAGES.update({
    NetworkError: "Error de conexión. Por favor intenta de nuevo.",
    TimedOut: "La operación tardó demasiado. Intenta con un archivo más pequeño.",
    BadRequest: "Solicitud inválida. Verifica el archivo e intenta de nuevo.",
})

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced error handler with Telegram API error handling."""
    error = context.error
    user_id = update.effective_user.id if update.effective_user else "unknown"

    # Log full error
    logger.exception(f"Error handling update for user {user_id}: {error}")

    # Determine user message
    user_message = DEFAULT_ERROR_MESSAGE

    # Check for specific error types
    for error_type, message in ERROR_MESSAGES.items():
        if isinstance(error, error_type):
            user_message = message
            break

    # Handle specific Telegram errors
    if isinstance(error, TimedOut):
        logger.warning(f"Timeout error for user {user_id}: {error}")
    elif isinstance(error, NetworkError):
        logger.warning(f"Network error for user {user_id}: {error}")

    # Send message to user
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(user_message)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
```

### Example 5: Pre-processing Validation

```python
# bot/validators.py
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
import logging
import subprocess

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_video_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """Validate video file integrity using ffprobe.

    Args:
        file_path: Path to video file

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, "El archivo no existe"

    if os.path.getsize(file_path) == 0:
        return False, "El archivo está vacío"

    # Use ffprobe to check video integrity
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        logger.warning("ffprobe not available, skipping video validation")
        return True, None

    try:
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            file_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Formato de video inválido"
            return False, f"Error validando video: {error_msg}"

        # Check duration
        duration_line = [line for line in result.stdout.split('\n') if line.strip() and not line.startswith('stream')]
        if duration_line:
            try:
                duration = float(duration_line[0])
                if duration <= 0:
                    return False, "El video tiene duración inválida (0 segundos)"
            except ValueError:
                pass

        return True, None

    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timeout validating {file_path}")
        return True, None  # Don't fail on validation timeout
    except Exception as e:
        logger.warning(f"Error running ffprobe: {e}")
        return True, None  # Don't fail on validation error


def check_disk_space(required_mb: int, path: str = "/") -> Tuple[bool, Optional[str]]:
    """Check if sufficient disk space is available.

    Args:
        required_mb: Required space in MB
        path: Path to check

    Returns:
        Tuple of (has_space, error_message)
    """
    try:
        stat = os.statvfs(path)
        available_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)

        if available_mb < required_mb:
            return False, f"Espacio insuficiente: {available_mb:.0f}MB disponible, {required_mb}MB requerido"

        return True, None

    except Exception as e:
        logger.warning(f"Error checking disk space: {e}")
        return True, None  # Don't fail if we can't check
```

---

## Implementation Recommendations

### Priority 1: Configuration Enhancement (CONF-01)

**Why First:** Enables other improvements, low risk, foundation for testing.

**Implementation:**
1. Create `BotConfig` dataclass with all settings
2. Add environment variable loading with type conversion
3. Validate at startup with clear error messages
4. Replace hardcoded constants in handlers.py

**Files to Modify:**
- `bot/config.py` - Complete rewrite with dataclass
- `bot/handlers.py` - Import config instead of hardcoded constants
- `.env.example` - Document all configuration options

### Priority 2: Pre-processing Validation (ERR-01)

**Why Second:** Prevents wasted processing time, improves user experience.

**Implementation:**
1. Create `bot/validators.py` with video validation functions
2. Add file size check before download
3. Add video integrity check with ffprobe
4. Add disk space check before operations

**Files to Create:**
- `bot/validators.py`

**Files to Modify:**
- `bot/handlers.py` - Add validation calls before processing

### Priority 3: Enhanced Error Handling (ERR-01, ERR-03)

**Why Third:** Builds on validation, handles edge cases.

**Implementation:**
1. Add Telegram API error handling to error_handler.py
2. Implement retry logic for transient errors
3. Add specific handling for network timeouts
4. Enhance error messages with context

**Files to Modify:**
- `bot/error_handler.py` - Add Telegram error types
- `bot/handlers.py` - Add retry logic for downloads

### Priority 4: Startup Cleanup (ERR-02)

**Why Fourth:** Safety net for resource cleanup.

**Implementation:**
1. Add `cleanup_old_temp_directories()` to temp_manager.py
2. Call on module import
3. Add signal handlers for graceful shutdown

**Files to Modify:**
- `bot/temp_manager.py` - Add cleanup function
- `bot/main.py` - Add signal handlers

### Priority 5: Logging Enhancement (CONF-02)

**Why Fifth:** Nice to have, but existing logging is sufficient.

**Implementation:**
1. Add structured logging option (JSON)
2. Add correlation IDs for request tracking
3. Add file logging with rotation (optional)
4. Make log level configurable

**Files to Modify:**
- `bot/main.py` - Enhanced logging setup
- All handlers - Add correlation IDs

---

## Testing Considerations

### Error Handling Tests

1. **Simulate Network Errors**
   - Disconnect network during download
   - Verify user gets appropriate message

2. **Simulate Corrupt Videos**
   - Send invalid file renamed as .mp4
   - Verify validation catches it

3. **Simulate Disk Full**
   - Fill temp directory
   - Verify graceful failure

4. **Simulate Timeouts**
   - Use very short timeout
   - Verify timeout handling

### Configuration Tests

1. **Missing Required Config**
   - Remove BOT_TOKEN
   - Verify clear error message

2. **Invalid Config Values**
   - Set negative timeout
   - Verify validation catches it

3. **Environment Loading**
   - Set all values via env vars
   - Verify correct loading

---

## Open Questions

1. **Log Retention:** How long to keep logs? (Recommendation: 7 days)
2. **Metrics:** Do we need metrics/monitoring? (Out of scope for this phase)
3. **Health Checks:** Do we need a health check endpoint? (Not for Telegram bot)
4. **Rate Limiting:** Should we implement user rate limiting? (Consider for future)

---

## Summary

**Current State:** The codebase has a solid foundation with custom exceptions, TempManager cleanup, and basic error handling.

**Key Gaps:**
1. Configuration is minimal (only BOT_TOKEN)
2. No pre-processing validation
3. No Telegram API error handling
4. No startup cleanup of orphaned temp files
5. Basic logging (no file output, no structured logging)

**Implementation Ready:** Yes. The research shows clear patterns and examples for implementing all Phase 02 requirements.

**Estimated Effort:**
- Configuration enhancement: 2-3 hours
- Validation: 3-4 hours
- Error handling: 2-3 hours
- Cleanup: 1-2 hours
- Testing: 2-3 hours
- **Total: 10-15 hours**

**Risk Level:** LOW - All changes are additive, existing functionality preserved.
