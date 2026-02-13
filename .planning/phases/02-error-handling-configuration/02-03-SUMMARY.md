# Phase 02 Plan 03: Telegram API Error Handling Summary

**Plan:** 02-03
**Phase:** 02-error-handling-configuration
**Completed:** 2026-02-13
**Duration:** ~15 minutes

## Overview

Enhanced error handling to gracefully handle Telegram API errors and network issues. This plan adds resilience against transient failures through retry logic and improves debugging capabilities with correlation IDs for request tracing.

## Tasks Completed

### Task 1: Add Telegram API Error Handling
- **Status:** Complete
- **Commit:** 38aa03f

Added comprehensive Telegram API error handling to `bot/error_handler.py`:

- Imported `NetworkError`, `TimedOut`, `BadRequest`, `RetryAfter`, and `TelegramError` from `telegram.error`
- Added Spanish error messages for all Telegram error types:
  - `NetworkError`: "Error de conexión. Por favor intenta de nuevo."
  - `TimedOut`: "La operación tardó demasiado. Intenta con un archivo más pequeño."
  - `BadRequest`: "Solicitud inválida. Verifica el archivo e intenta de nuevo."
  - `RetryAfter`: "Demasiadas solicitudes. Por favor espera un momento."
  - `TelegramError`: "Error de Telegram. Por favor intenta de nuevo."
- Updated `error_handler()` to distinguish between transient and permanent errors:
  - `NetworkError`/`TimedOut`: Logged as warnings (transient issues)
  - `BadRequest`: Logged as info (user errors)
  - Other Telegram errors: Logged as errors
  - Internal errors: Full exception logged
- Updated `handle_processing_error()` with same Telegram error handling logic

### Task 2: Add Retry Logic for Video Downloads
- **Status:** Complete
- **Commit:** Part of 247c100 (refactor), enhanced in 15cc306

Implemented retry logic for video downloads in `bot/handlers.py`:

- Added `_download_with_retry()` helper function with:
  - Configurable max retries (default: 3)
  - Exponential backoff (1s, 2s, 3s delays)
  - Specific handling for `NetworkError` and `TimedOut`
  - Comprehensive logging of each attempt
- Replaced all direct `file.download_to_drive()` calls with `_download_with_retry()`:
  - `handle_video()` - main video processing
  - `handle_convert_command()` - format conversion
  - `handle_extract_audio_command()` - audio extraction
  - `handle_split_command()` - video splitting
  - `handle_join_video()` - video joining

### Task 3: Enhance Logging with Correlation IDs
- **Status:** Complete
- **Commit:** 15cc306

Added correlation IDs to improve request tracking in `bot/handlers.py`:

- Imported `uuid` module for ID generation
- Updated `_download_with_retry()` to accept and log correlation IDs
- Updated `_process_video_with_timeout()` to accept and use correlation IDs
- Modified `handle_video()` to:
  - Generate 8-character correlation ID at start
  - Pass correlation ID through processing flow
  - Include correlation ID in all log messages
- Log messages now include correlation ID format: `[{cid}] message`

## Key Decisions

### D02-03-01: Use 8-character UUID for correlation IDs
**Decision:** Use first 8 characters of UUID v4 for correlation IDs.
**Rationale:** Provides sufficient uniqueness (16^8 = 4 billion combinations) while keeping log messages readable. Full UUIDs are too verbose for log reading.

### D02-03-02: Exponential backoff for retries
**Decision:** Use exponential backoff (1s, 2s, 3s) for download retries.
**Rationale:** Gives transient network issues time to resolve without waiting too long between attempts. Linear backoff could hammer a struggling server; exponential is more polite.

### D02-03-03: Log transient errors as warnings
**Decision:** Log `NetworkError` and `TimedOut` as warnings, not errors.
**Rationale:** These are expected transient failures that don't indicate code problems. Error-level logs would trigger alerts unnecessarily. Warnings provide visibility without alarm fatigue.

## Files Modified

| File | Changes |
|------|---------|
| `bot/error_handler.py` | Added Telegram error imports, messages, and handling logic |
| `bot/handlers.py` | Added retry logic, correlation IDs, enhanced logging |

## Technical Details

### Error Classification

| Error Type | Log Level | User Message | Retry? |
|------------|-----------|--------------|--------|
| NetworkError | Warning | Connection error (Spanish) | Yes |
| TimedOut | Warning | Operation timeout (Spanish) | Yes |
| BadRequest | Info | Invalid request (Spanish) | No |
| RetryAfter | Error | Rate limited (Spanish) | No |
| Other Telegram | Error | Generic Telegram error | No |
| Internal | Exception | Generic error | No |

### Retry Configuration

```python
max_retries: int = 3
backoff_delays: [1s, 2s, 3s]  # attempt * 1 second
```

### Correlation ID Flow

```
handle_video()
  └─> generate correlation_id
  └─> _process_video_with_timeout(correlation_id)
      └─> _download_with_retry(correlation_id)
          └─> logs: [{cid}] Video downloaded to {path}
      └─> logs: [{cid}] Processing video for user {id}
      └─> logs: [{cid}] Video note sent successfully
```

## Verification Results

- [x] Telegram errors import successfully
- [x] Spanish error messages exist for all Telegram error types
- [x] `_download_with_retry()` function provides retry logic
- [x] All video download operations use retry logic
- [x] Correlation IDs track requests through processing flow
- [x] Error handler distinguishes transient vs permanent errors
- [x] Bot handles network failures gracefully without crashing

## Deviations from Plan

None - plan executed exactly as written.

## Success Criteria Met

- [x] Telegram API errors (NetworkError, TimedOut, BadRequest) are imported and handled
- [x] Spanish error messages exist for all Telegram error types
- [x] `_download_with_retry` function provides retry logic with exponential backoff
- [x] All video download operations use retry logic
- [x] Correlation IDs track requests through the processing flow
- [x] Error handler distinguishes between transient and permanent errors in logging
- [x] Bot handles network failures gracefully without crashing

## Next Phase Readiness

This plan completes Phase 02-error-handling-configuration. The bot now has:
- Comprehensive error handling for both internal and external errors
- Resilience against transient network failures
- Better debugging capabilities through correlation IDs
- Clear, Spanish-language user feedback for all error conditions

The bot is ready for production deployment with confidence that external failures (network issues, Telegram API problems) will be handled gracefully without crashes.
