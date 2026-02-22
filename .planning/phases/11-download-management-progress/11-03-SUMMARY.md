---
phase: 11-download-management-progress
plan: 03
subsystem: downloader
status: completed
tags: [retry, error-handling, backoff, rate-limit, timeout]
dependency_graph:
  requires: ["11-01"]
  provides: ["11-04", "11-05"]
  affects: ["09-02", "09-03", "09-04", "10-01", "10-02", "10-03", "10-04", "10-05"]
tech_stack:
  added:
    - RetryHandler: Exponential backoff with jitter
    - RateLimitError: Platform-specific rate limit handling
    - TimeoutConfig: Configurable timeout settings
    - is_retryable_error: Intelligent error classification
  patterns:
    - Circuit breaker pattern via retry exhaustion
    - Backoff with jitter to prevent thundering herd
    - Error classification for retry decisions
key_files:
  created:
    - bot/downloaders/retry_handler.py: 545 lines, RetryHandler + tests
  modified:
    - bot/downloaders/exceptions.py: +55 lines, RateLimitError class
    - bot/downloaders/base.py: +47 lines, download_with_retry method
    - bot/downloaders/__init__.py: +15 lines, new exports
decisions:
  - max_retries=3 default per EH-03 requirement
  - Exponential backoff base_delay=2.0, max_delay=60.0
  - Jitter enabled by default to prevent thundering herd
  - RateLimitError includes retry_after and platform attributes
  - Spanish user messages match bot convention
  - TimeoutConfig dataclass for type-safe timeout configuration
metrics:
  duration_seconds: 299
  completed_date: "2026-02-22"
  tasks_completed: 5
  files_created: 1
  files_modified: 3
  total_commits: 4
---

# Phase 11 Plan 03: Retry Handler Summary

Enhanced error handling with retry logic, rate limit detection, and timeout handling for resilient downloads.

## Overview

This plan implements a comprehensive retry mechanism for the downloader infrastructure, ensuring downloads are resilient to transient failures with intelligent retry decisions and proper backoff strategies.

## What Was Built

### 1. RateLimitError Exception (Task 1)

New exception class extending `DownloadError`:
- Attributes: `retry_after`, `platform`
- Spanish user messages: "Límite de descargas alcanzado. Por favor espera {N} segundos."
- Comprehensive docstring with platform-specific examples (YouTube, Instagram, TikTok, Twitter/X)

### 2. RetryHandler Class (Task 2)

Full-featured retry handler with:
- **Exponential backoff**: base_delay * (exponential_base ^ attempt)
- **Jitter**: Random 0-1s added to prevent thundering herd
- **Max delay cap**: Prevents excessive wait times
- **Rate limit detection**: Extracts retry_after from error messages
- **Configurable**: max_retries, base_delay, max_delay, exponential_base, jitter

Key methods:
- `execute(operation, operation_name, is_retryable)`: Main retry wrapper
- `calculate_delay(attempt, retry_after)`: Delay calculation with backoff
- `execute_with_timeout(operation, timeout)`: Timeout-aware execution

### 3. Error Classification (Task 2)

`is_retryable_error()` function:
- **Retryable**: NetworkError, TimeoutError, ConnectionError, RateLimitError
- **Not retryable**: FileTooLargeError, URLValidationError, UnsupportedURLError
- **Message analysis**: Detects patterns like "timeout", "503", "429"

### 4. BaseDownloader Enhancement (Task 3)

Added `download_with_retry()` method:
- Wraps `download()` with automatic retry logic
- Uses settings from `DownloadOptions` (max_retries, retry_delay)
- Preserves correlation_id across retry attempts

### 5. Package Integration (Task 4)

Updated exports:
- `RetryHandler`, `is_retryable_error`, `RateLimitError`
- `TimeoutConfig`, `create_timeout_guard`

### 6. Comprehensive Tests (Task 5)

Test coverage includes:
- Error classification (retryable vs permanent)
- Exponential backoff calculation
- Jitter variation
- Retry exhaustion
- Rate limit detection
- Retry_after extraction from messages

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| max_retries=3 default | Per EH-03 requirement |
| base_delay=2.0s | Balance between quick recovery and server respect |
| max_delay=60.0s | Prevent excessive wait times |
| Jitter enabled | Prevent thundering herd on recovery |
| Error classification | Avoid retrying permanent failures |
| Spanish messages | Match existing bot convention |

## Files Changed

```
bot/downloaders/
├── retry_handler.py      # NEW: 545 lines
├── exceptions.py         # MOD: +55 lines (RateLimitError)
├── base.py               # MOD: +47 lines (download_with_retry)
└── __init__.py           # MOD: +15 lines (exports)
```

## API Usage

```python
from bot.downloaders import RetryHandler, is_retryable_error, RateLimitError

# Basic retry usage
retry_handler = RetryHandler(max_retries=3, base_delay=2.0)
result = await retry_handler.execute(
    lambda: download_operation(),
    operation_name="download"
)

# With timeout
result = await retry_handler.execute_with_timeout(
    download_operation,
    timeout=300.0,
    operation_name="download"
)

# Error classification
if is_retryable_error(error):
    # Schedule retry
else:
    # Fail immediately
```

## Verification Results

All success criteria met:
- [x] RateLimitError exception class exists
- [x] is_retryable_error correctly identifies retryable errors
- [x] RetryHandler implements exponential backoff with jitter
- [x] RetryHandler respects max_retries=3 per EH-03
- [x] BaseDownloader has download_with_retry method
- [x] Timeout handling guards against stalled downloads per EH-04
- [x] Package exports are updated

## Commits

1. `50fed9a`: feat(11-03): add RateLimitError exception class
2. `b46f07d`: feat(11-03): create RetryHandler with exponential backoff
3. `bb7b5c0`: feat(11-03): add download_with_retry to BaseDownloader
4. `1ea50d4`: feat(11-03): update package exports with retry components

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- [x] All created files exist
- [x] All commits exist in git history
- [x] All imports work correctly
- [x] All tests pass
- [x] No syntax errors
- [x] Spanish messages consistent
