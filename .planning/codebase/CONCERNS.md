# Codebase Concerns

**Analysis Date:** 2026-02-11

## Tech Debt

**Synchronous Video Processing:**
- Issue: Video processing uses `asyncio.wait_for()` with `run_in_executor()` but still blocks on single-file processing
- Files: `bot/handlers.py` (lines 66-75)
- Impact: Only one video can be processed at a time per bot instance; high concurrency will create a queue
- Fix approach: Implement queue-based processing with worker pool or offload to dedicated processing service

**Hardcoded Configuration Values:**
- Issue: Timeout duration (60s), video dimensions (640x640), and max duration (60s) are hardcoded
- Files: `bot/handlers.py` (line 19), `bot/video_processor.py` (lines 70-79)
- Impact: Cannot adjust limits without code changes; no environment-based configuration for tuning
- Fix approach: Move configuration to environment variables or config module with sensible defaults

**No Input Validation:**
- Issue: Video file size and format validation missing before download
- Files: `bot/handlers.py` (lines 42-60)
- Impact: Users can upload extremely large files causing memory/disk issues; no pre-download checks
- Fix approach: Check `video.file_size` before downloading; reject files > configurable limit (e.g., 100MB)

## Known Bugs

**None Identified:**
- Current codebase appears to handle known error cases appropriately
- Error handling covers download failures, processing failures, and timeouts

## Security Considerations

**No File Type Validation:**
- Risk: Users could potentially upload non-video files disguised as videos
- Files: `bot/handlers.py` (lines 54-60)
- Current mitigation: Telegram API validates MIME type, but bot doesn't verify
- Recommendations: Validate file extensions and magic bytes before processing

**Temporary File Security:**
- Risk: Predictable temp directory names could allow temp file attacks in shared environments
- Files: `bot/temp_manager.py` (line 18)
- Current mitigation: Uses `tempfile.mkdtemp()` which creates directories with 0o700 permissions
- Recommendations: Current implementation is acceptable; verify permissions are restrictive

**Token Exposure Risk:**
- Risk: BOT_TOKEN in `.env` file could be committed accidentally
- Files: `.env`, `bot/config.py` (lines 9-12)
- Current mitigation: `.env` in .gitignore (assumed), runtime validation raises error if missing
- Recommendations: Add `.env` to `.gitignore` explicitly if not present; document token security practices

**No Rate Limiting:**
- Risk: Users can flood bot with videos causing DoS
- Files: `bot/handlers.py` (lines 96-154)
- Current mitigation: Processing timeout prevents indefinite hangs but doesn't limit request rate
- Recommendations: Implement per-user rate limiting (e.g., max 1 video per 30 seconds)

## Performance Bottlenecks

**Single-Threaded Processing:**
- Problem: All video processing happens in a single executor thread
- Files: `bot/handlers.py` (lines 67-70)
- Cause: `run_in_executor()` with default executor (single thread)
- Improvement path: Use `concurrent.futures.ThreadPoolExecutor` with configurable max_workers

**No Streaming/Download Optimization:**
- Problem: Videos download completely before processing starts
- Files: `bot/handlers.py` (line 56)
- Cause: `download_to_drive()` waits for full download
- Improvement path: Could start processing partial downloads for large files (advanced)

**FFmpeg Process Overhead:**
- Problem: New ffmpeg process spawned for each video
- Files: `bot/video_processor.py` (lines 66-99)
- Cause: Subprocess execution per video
- Improvement path: Consider ffmpeg-python bindings or persistent process pool (complex)

## Fragile Areas

**FFmpeg Dependency:**
- Files: `bot/video_processor.py` (lines 31-37, 82-99)
- Why fragile: Requires external binary installed on system; version differences can affect behavior
- Safe modification: Check ffmpeg version on startup; document required version range
- Test coverage: No automated tests for ffmpeg integration

**Telegram API Reliability:**
- Files: `bot/handlers.py` (lines 54-60, 87-93)
- Why fragile: Network issues can cause download/upload failures at any time
- Safe modification: Implement retry logic with exponential backoff for API calls
- Test coverage: No tests for network failure scenarios

**Temp File Cleanup Edge Cases:**
- Files: `bot/temp_manager.py` (lines 34-44)
- Why fragile: Uses `ignore_errors=True` which can leave files behind if locked
- Safe modification: Implement retry logic for cleanup; log uncleaned files for manual intervention
- Test coverage: No tests for cleanup failure scenarios

## Scaling Limits

**Current Capacity:**
- Single video processing at a time (blocking)
- 60-second timeout per video
- Temp storage limited by disk space

**Limits:**
- Bot will queue requests under load (no queue visibility)
- No horizontal scaling strategy (single instance)
- File system temp storage is local only

**Scaling Path:**
- Implement Redis/RabbitMQ queue for video processing jobs
- Separate processing workers from bot frontend
- Use cloud storage (S3) for temp files to allow multi-instance deployment

## Dependencies at Risk

**python-telegram-bot:**
- Risk: v20+ has breaking changes from v13; future updates may require code changes
- Impact: Bot framework is core dependency
- Migration plan: Pin to v20.x in requirements.txt; test thoroughly before upgrading

**ffmpeg System Dependency:**
- Risk: Not a Python package; deployment environment must have compatible version
- Impact: Processing fails entirely without ffmpeg
- Migration plan: Containerize with ffmpeg included; or use static ffmpeg binary

## Missing Critical Features

**No Database/Persistence:**
- Problem: Cannot track usage stats, user preferences, or processing history
- Blocks: Analytics, rate limiting per user, abuse prevention
- Priority: Medium

**No Admin/Monitoring:**
- Problem: No health check endpoint or admin commands
- Blocks: Production monitoring, alerting, maintenance operations
- Priority: High

**No Input Pre-validation:**
- Problem: No file size checks before downloading large videos
- Blocks: Preventing abuse, managing resource usage
- Priority: High

## Test Coverage Gaps

**No Unit Tests:**
- What's not tested: All video processing logic, error handlers, temp manager
- Files: Entire `bot/` package
- Risk: Refactoring can break functionality silently
- Priority: High

**No Integration Tests:**
- What's not tested: Telegram API integration, ffmpeg processing pipeline
- Files: `bot/handlers.py`, `bot/video_processor.py`
- Risk: Changes to dependencies break bot
- Priority: High

**No Error Scenario Tests:**
- What's not tested: Timeout handling, cleanup on failure, network errors
- Files: `bot/error_handler.py`, `bot/handlers.py`
- Risk: Error handling may not work as expected under real failure conditions
- Priority: Medium

## Documentation Gaps

**Deployment Documentation:**
- Missing: Production deployment guide, environment setup beyond basic
- Impact: Difficult to deploy to cloud platforms (Heroku, AWS, etc.)

**Configuration Reference:**
- Missing: Complete list of environment variables and their effects
- Impact: Trial and error required for tuning

**Architecture Overview:**
- Missing: System architecture diagram, data flow documentation
- Impact: New developers need to read code to understand design

---

*Concerns audit: 2026-02-11*
