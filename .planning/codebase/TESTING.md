# Testing Patterns

**Analysis Date:** 2026-02-11

## Test Framework

**Status:** No testing framework currently configured

**Missing Infrastructure:**
- No test runner (pytest, unittest)
- No test configuration files (pytest.ini, setup.cfg, tox.ini)
- No test directory structure
- No test files in codebase

**Recommended Setup:**
```bash
pip install pytest pytest-asyncio pytest-mock
```

**Recommended Configuration:**
Create `pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

## Test File Organization

**Recommended Structure:**
```
[project-root]/
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_video_processor.py
│   │   ├── test_temp_manager.py
│   │   └── test_error_handler.py
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_handlers.py
│   └── conftest.py
```

**Naming:**
- Test files: `test_<module>.py`
- Test functions: `test_<function_name>_<scenario>()`
- Test classes: `Test<ClassName>`

## Test Structure

**Recommended Patterns:**

Given the async nature of the codebase, use pytest-asyncio:

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
from bot.video_processor import VideoProcessor
from bot.temp_manager import TempManager

@pytest.fixture
def temp_manager():
    return TempManager()

@pytest.mark.asyncio
async def test_handle_video_success():
    """Test successful video processing flow."""
    # Arrange
    mock_update = Mock()
    mock_update.effective_user.id = 12345
    mock_update.message.video.file_unique_id = "abc123"

    # Act
    with patch('bot.handlers.VideoProcessor') as mock_processor:
        mock_processor.process_video.return_value = True
        await handle_video(mock_update, Mock())

    # Assert
    mock_update.message.reply_video_note.assert_called_once()

@pytest.mark.asyncio
async def test_handle_video_download_error():
    """Test handling of download failures."""
    # Arrange
    mock_update = Mock()
    mock_update.effective_user.id = 12345
    mock_update.message.video.get_file.side_effect = Exception("Download failed")

    # Act
    await handle_video(mock_update, Mock())

    # Assert
    mock_update.message.reply_text.assert_called_with(
        "No pude descargar el video. Intenta con otro archivo."
    )
```

## Mocking

**Framework:** unittest.mock (standard library)

**Key Mocking Targets:**
- `telegram.Update` and `telegram.Context` - Mock user interactions
- `telegram.File` - Mock file download operations
- `subprocess.run` - Mock ffmpeg calls
- `tempfile.mkdtemp` - Mock temp directory creation
- `asyncio.get_event_loop` - Mock event loop for timeout testing

**Mocking Patterns:**

```python
# Mock Telegram objects
mock_update = Mock()
mock_update.effective_user.id = 12345
mock_update.message.video.file_unique_id = "unique_id"
mock_update.message.video.file_size = 1024 * 1024  # 1MB

mock_context = Mock()
mock_context.bot = AsyncMock()

# Mock file operations
mock_file = AsyncMock()
mock_file.download_to_drive = AsyncMock()
mock_update.message.video.get_file.return_value = mock_file

# Mock ffmpeg
with patch('subprocess.run') as mock_run:
    mock_run.return_value = Mock(returncode=0, stderr="")
    processor = VideoProcessor("input.mp4", "output.mp4")
    result = processor.process()
    assert result is True
```

**What to Mock:**
- External API calls (Telegram API)
- File system operations (use tmpdir fixtures)
- Subprocess calls (ffmpeg)
- Network operations
- Time-based operations (timeouts)

**What NOT to Mock:**
- Internal utility functions
- Data transformations
- Error classes and simple logic

## Fixtures and Factories

**Recommended Fixtures:**

```python
# conftest.py
import pytest
import tempfile
import os
from unittest.mock import Mock

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

@pytest.fixture
def sample_video_path(temp_dir):
    """Create a sample video file for testing."""
    video_path = os.path.join(temp_dir, "test_video.mp4")
    # Create a minimal valid MP4 or mock the file
    with open(video_path, "wb") as f:
        f.write(b"fake video content")
    return video_path

@pytest.fixture
def mock_telegram_update():
    """Create a mock Telegram update object."""
    update = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.message.message_id = 67890
    update.message.video.file_unique_id = "test_file_123"
    update.message.video.file_size = 5 * 1024 * 1024  # 5MB
    update.message.video.duration = 30  # seconds
    return update

@pytest.fixture
def mock_telegram_context():
    """Create a mock Telegram context."""
    context = Mock()
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    return context
```

## Coverage

**Current Status:** No coverage requirements enforced

**Recommended Targets:**
- Minimum 80% overall coverage
- 100% coverage for error handling paths
- Critical paths (video processing) should have 90%+ coverage

**View Coverage:**
```bash
pytest --cov=bot --cov-report=html --cov-report=term-missing
```

**Coverage Configuration:**
Create `.coveragerc`:
```ini
[run]
source = bot
omit =
    */tests/*
    */__pycache__/*
    bot/__init__.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
```

## Test Types

**Unit Tests:**
- Test individual functions and methods
- Mock all external dependencies
- Fast execution (< 100ms per test)
- Focus on: `video_processor.py`, `temp_manager.py`, `error_handler.py`

**Integration Tests:**
- Test handler chains with mocked Telegram API
- Test actual subprocess calls with test videos
- Test temp file cleanup integration
- Focus on: `handlers.py` with mocked external calls

**E2E Tests:**
- Not currently implemented
- Would require Telegram test bot and server
- Use pytest-asyncio for async testing

## Critical Test Scenarios

**Video Processing (`video_processor.py`):**
- Successful video processing
- Missing ffmpeg binary
- Invalid input file
- ffmpeg processing failure
- Timeout handling

**Error Handling (`error_handler.py`):**
- Exception class instantiation
- Error message mapping
- Error handler decorator functionality
- User message sending on errors

**Temp Manager (`temp_manager.py`):**
- Directory creation
- File path generation
- Context manager cleanup
- Cleanup with locked files

**Handlers (`handlers.py`):**
- Start command response
- Video message handling (success)
- Download errors
- Processing timeout
- Unexpected exceptions
- Message cleanup (processing message deletion)

## Async Testing

**Pattern:**
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_function():
    """Test async function with mocked dependencies."""
    mock_obj = Mock()
    mock_obj.async_method = AsyncMock(return_value="result")

    result = await mock_obj.async_method()
    assert result == "result"
```

**Timeout Testing:**
```python
@pytest.mark.asyncio
async def test_processing_timeout():
    """Test that processing times out after 60 seconds."""
    with patch('asyncio.wait_for') as mock_wait:
        mock_wait.side_effect = asyncio.TimeoutError()

        with pytest.raises(ProcessingTimeoutError):
            await _process_video_with_timeout(mock_update, temp_mgr, 12345)
```

## Testing Commands

**Run All Tests:**
```bash
pytest
```

**Run with Verbosity:**
```bash
pytest -v
```

**Run Specific Test File:**
```bash
pytest tests/unit/test_video_processor.py
```

**Run with Coverage:**
```bash
pytest --cov=bot --cov-report=html
```

**Watch Mode:**
```bash
pytest-watch --runner=pytest
# OR
ptw
```

---

*Testing analysis: 2026-02-11*
