"""Download Facade - Unified API for video downloads.

This module provides a simple interface for downloading videos
with automatic concurrency management, progress tracking,
retry logic, and cleanup.

Basic usage:
    from bot.downloaders import download_url

    result = await download_url("https://youtube.com/watch?v=...")
    if result.success:
        print(f"Downloaded: {result.file_path}")

With progress updates:
    from bot.downloaders import DownloadFacade

    facade = DownloadFacade()
    result = await facade.download_with_progress(
        url="https://youtube.com/watch?v=...",
        message_func=lambda text: bot.send_message(chat_id, text)
    )

Advanced configuration:
    config = DownloadConfig(
        max_concurrent=3,
        max_retries=5,
        extract_audio=True
    )
    facade = DownloadFacade(config)

Features:
- Single-call API for downloads with automatic handler selection
- Built-in progress tracking with throttled updates
- Automatic retry with exponential backoff
- Isolated temp directories with automatic cleanup
- Correlation ID tracking for all downloads
- Integration with all platform handlers (YouTube, Instagram, TikTok, etc.)

Example with error handling:
    from bot.downloaders.exceptions import (
        FileTooLargeError,
        URLValidationError,
        UnsupportedURLError,
        DownloadError
    )

    try:
        result = await facade.download_with_progress(url, message_func)
        if result.success:
            await send_file(result.file_path)
    except FileTooLargeError as e:
        await message.edit_text(e.to_user_message())
    except URLValidationError as e:
        await message.edit_text(e.to_user_message())
    except UnsupportedURLError as e:
        await message.edit_text(e.to_user_message())
    except DownloadError as e:
        await message.edit_text(e.to_user_message())
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

# Import download components
from .base import BaseDownloader, DownloadOptions, TELEGRAM_MAX_FILE_SIZE
from .download_manager import DownloadManager, DownloadStatus, DownloadTask
from .download_lifecycle import DownloadLifecycle, DownloadResult as LifecycleResult
from .exceptions import (
    DownloadError,
    FileTooLargeError,
    URLValidationError,
    UnsupportedURLError,
)
from .platform_router import PlatformRouter, RouteResult, route_url
from .progress_tracker import ProgressTracker, format_progress_message
from .retry_handler import RetryHandler, TimeoutConfig
from .url_detector import URLDetector

logger = logging.getLogger(__name__)


@dataclass
class DownloadConfig:
    """Configuration for DownloadFacade operations.

    This dataclass centralizes all configuration options for the download
    facade, including concurrency limits, retry settings, progress tracking,
    and download preferences.

    Attributes:
        max_concurrent: Maximum number of concurrent downloads (default: 5)
        max_retries: Maximum retry attempts for failed downloads (default: 3)
        retry_delay: Base delay between retries in seconds (default: 2.0)
        progress_update_interval: Minimum seconds between progress updates (default: 3.0)
        progress_min_percent: Minimum percentage change for progress update (default: 5.0)
        cleanup_on_success: Clean up temp files after successful download (default: True)
        cleanup_on_failure: Clean up temp files after failed download (default: True)
        extract_audio: Extract audio instead of video (default: False)
        preferred_quality: Preferred video quality (default: "best")

    Example:
        # Default configuration
        config = DownloadConfig()

        # Custom configuration for audio extraction
        config = DownloadConfig(
            max_concurrent=3,
            extract_audio=True,
            preferred_quality="bestaudio"
        )
    """
    max_concurrent: int = 5
    max_retries: int = 3
    retry_delay: float = 2.0
    progress_update_interval: float = 3.0
    progress_min_percent: float = 5.0
    cleanup_on_success: bool = True
    cleanup_on_failure: bool = True
    extract_audio: bool = False
    preferred_quality: str = "best"

    def to_download_options(self, output_path: Optional[str] = None) -> DownloadOptions:
        """Convert DownloadConfig to DownloadOptions.

        Args:
            output_path: Optional output path override

        Returns:
            DownloadOptions instance configured from this config
        """
        return DownloadOptions(
            output_path=output_path or "/tmp",
            extract_audio=self.extract_audio,
            preferred_quality=self.preferred_quality,
            max_filesize=TELEGRAM_MAX_FILE_SIZE,
        )


class DownloadFacade:
    """Unified API for video downloads with integrated management.

    The DownloadFacade provides a simple, single-call interface for downloading
    URLs that handles concurrency, progress tracking, retry logic, and cleanup
    automatically. It integrates all download management components into a
    cohesive API.

    Attributes:
        _config: DownloadConfig instance with configuration
        _manager: DownloadManager for concurrent download handling
        _router: PlatformRouter for URL routing
        _retry_handler: RetryHandler for automatic retries
        _started: Whether the facade has been started

    Example:
        # Basic usage
        facade = DownloadFacade()
        await facade.start()

        result = await facade.download("https://youtube.com/watch?v=...")
        if result.success:
            print(f"Downloaded: {result.file_path}")

        await facade.stop()

        # With progress updates
        result = await facade.download_with_progress(
            url="https://youtube.com/watch?v=...",
            message_func=lambda text: bot.send_message(chat_id, text),
            edit_message_func=lambda text: message.edit_text(text)
        )
    """

    def __init__(self, config: Optional[DownloadConfig] = None) -> None:
        """Initialize the DownloadFacade.

        Args:
            config: Configuration options. If None, uses default config.
        """
        self._config = config or DownloadConfig()
        self._manager = DownloadManager(max_concurrent=self._config.max_concurrent)
        self._router = PlatformRouter()
        self._retry_handler = RetryHandler(
            max_retries=self._config.max_retries,
            base_delay=self._config.retry_delay
        )
        self._started = False

        logger.debug(f"DownloadFacade initialized (max_concurrent={self._config.max_concurrent})")

    async def start(self) -> None:
        """Start the download manager.

        Must be called before submitting downloads.
        """
        if not self._started:
            await self._manager.start()
            self._started = True
            logger.info("DownloadFacade started")

    async def stop(self, wait_for_pending: bool = False) -> None:
        """Stop the download manager.

        Args:
            wait_for_pending: If True, wait for active downloads to complete
        """
        if self._started:
            await self._manager.stop(wait_for_pending=wait_for_pending)
            self._started = False
            logger.info("DownloadFacade stopped")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False

    async def download(
        self,
        url: str,
        chat_id: Optional[int] = None,
        message_func: Optional[Callable[[str], Awaitable[None]]] = None,
        config_overrides: Optional[Dict[str, Any]] = None
    ) -> LifecycleResult:
        """Download a URL with automatic handler selection.

        This method routes the URL to the appropriate downloader, manages
        the download lifecycle, and returns the result. Progress updates
        are sent via message_func if provided.

        Args:
            url: The URL to download
            chat_id: Optional chat ID for tracking
            message_func: Optional async function to send progress messages
            config_overrides: Optional dict to override config values

        Returns:
            LifecycleResult with download result

        Raises:
            RuntimeError: If facade not started
            URLValidationError: If URL is invalid
            UnsupportedURLError: If platform not supported
            DownloadError: If download fails

        Example:
            result = await facade.download(
                url="https://youtube.com/watch?v=...",
                message_func=lambda text: bot.send_message(chat_id, text)
            )
        """
        if not self._started:
            raise RuntimeError("DownloadFacade not started. Use 'await facade.start()' or async context manager.")

        # Apply config overrides if provided
        config = self._config
        if config_overrides:
            config = DownloadConfig(
                max_concurrent=config_overrides.get('max_concurrent', self._config.max_concurrent),
                max_retries=config_overrides.get('max_retries', self._config.max_retries),
                retry_delay=config_overrides.get('retry_delay', self._config.retry_delay),
                progress_update_interval=config_overrides.get('progress_update_interval', self._config.progress_update_interval),
                progress_min_percent=config_overrides.get('progress_min_percent', self._config.progress_min_percent),
                cleanup_on_success=config_overrides.get('cleanup_on_success', self._config.cleanup_on_success),
                cleanup_on_failure=config_overrides.get('cleanup_on_failure', self._config.cleanup_on_failure),
                extract_audio=config_overrides.get('extract_audio', self._config.extract_audio),
                preferred_quality=config_overrides.get('preferred_quality', self._config.preferred_quality),
            )

        # Route URL to appropriate downloader
        route_result = await self._router.route(url)
        downloader = route_result.downloader

        logger.info(f"Downloading {url} via {route_result.platform} ({route_result.confidence} confidence)")

        # Create download options
        options = config.to_download_options()

        # Set up progress callback if message_func provided
        if message_func:
            progress_callback = self._create_progress_callback(
                message_func,
                config.progress_update_interval,
                config.progress_min_percent
            )
            options = options.with_overrides(progress_callback=progress_callback)

        # Execute download with retry logic
        async def download_operation() -> LifecycleResult:
            correlation_id = BaseDownloader._generate_correlation_id()

            logger.debug(f"[{correlation_id}] Creating lifecycle with cleanup_on_success={config.cleanup_on_success}")

            lifecycle = DownloadLifecycle(
                correlation_id=correlation_id,
                options=options,
                cleanup_on_success=config.cleanup_on_success,
                cleanup_on_failure=config.cleanup_on_failure
            )

            async def do_download(temp_dir: str) -> LifecycleResult:
                # Update options with temp directory
                temp_options = options.with_overrides(output_path=temp_dir)

                # Perform the actual download
                result = await downloader.download(url, temp_options)

                # Convert result to LifecycleResult format
                if isinstance(result, LifecycleResult):
                    return result
                elif isinstance(result, dict):
                    return LifecycleResult(
                        success=result.get('success', True),
                        file_path=result.get('file_path') or result.get('path'),
                        metadata=result.get('metadata'),
                        correlation_id=correlation_id,
                        temp_dir=temp_dir
                    )
                else:
                    return LifecycleResult(
                        success=True,
                        file_path=str(result) if result else None,
                        correlation_id=correlation_id,
                        temp_dir=temp_dir
                    )

            return await lifecycle.execute(do_download)

        # Execute with retry
        return await self._retry_handler.execute(
            download_operation,
            operation_name=f"download_{route_result.platform}",
            is_retryable=lambda e: not isinstance(e, (FileTooLargeError, URLValidationError, UnsupportedURLError))
        )

    async def download_with_progress(
        self,
        url: str,
        message_func: Callable[[str], Awaitable[None]],
        edit_message_func: Optional[Callable[[str], Awaitable[None]]] = None,
        chat_id: Optional[int] = None
    ) -> LifecycleResult:
        """Download with enhanced progress updates.

        This method provides a richer progress experience by sending
        initial status messages and updating them with progress bars.

        Args:
            url: The URL to download
            message_func: Async function to send new messages
            edit_message_func: Optional async function to edit existing messages
            chat_id: Optional chat ID for tracking

        Returns:
            LifecycleResult with download result

        Example:
            status_message = await update.message.reply_text("Analizando...")
            result = await facade.download_with_progress(
                url=url,
                message_func=lambda text: context.bot.send_message(chat_id, text),
                edit_message_func=lambda text: status_message.edit_text(text)
            )
        """
        # Send initial message
        await message_func("Analizando enlace...")

        # Create progress callback that edits message
        last_message_text = ["Analizando enlace..."]  # Use list for mutable closure

        async def progress_callback(progress: Dict[str, Any]) -> None:
            message = format_progress_message(progress)

            # Only update if message changed
            if message != last_message_text[0] and edit_message_func:
                try:
                    await edit_message_func(message)
                    last_message_text[0] = message
                except Exception as e:
                    logger.warning(f"Failed to update progress message: {e}")

        # Create tracker with our callback
        tracker = ProgressTracker(
            min_update_interval=self._config.progress_update_interval,
            min_percent_change=self._config.progress_min_percent,
            on_update=lambda p: asyncio.create_task(progress_callback(p))
        )

        # Perform download
        result = await self.download(
            url=url,
            chat_id=chat_id,
            message_func=message_func
        )

        # Send completion message
        if result.success:
            metadata = result.metadata or {}
            title = metadata.get('title', 'Video')
            await message_func(f"Descarga completada: {title}")
        else:
            await message_func("Error en la descarga")

        return result

    def _create_progress_callback(
        self,
        message_func: Callable[[str], Awaitable[None]],
        min_interval: float,
        min_percent: float
    ) -> Callable[[Dict[str, Any]], None]:
        """Create a progress callback for DownloadOptions.

        Args:
            message_func: Async function to send messages
            min_interval: Minimum seconds between updates
            min_percent: Minimum percentage change for update

        Returns:
            Callback function for progress updates
        """
        tracker = ProgressTracker(
            min_update_interval=min_interval,
            min_percent_change=min_percent,
            on_update=lambda p: asyncio.create_task(message_func(format_progress_message(p)))
        )
        return tracker.create_callback()

    def get_download_status(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a download.

        Args:
            correlation_id: The correlation ID of the download

        Returns:
            Dict with status information, or None if not found:
                - correlation_id: Download ID
                - status: Current status (pending, downloading, completed, failed, cancelled)
                - progress: Last progress update
                - temp_dir: Temporary directory path
                - url: Download URL

        Example:
            status = facade.get_download_status("abc12345")
            if status:
                print(f"Status: {status['status']}, Progress: {status['progress']}")
        """
        task = self._manager.get_task(correlation_id)
        if not task:
            return None

        return {
            "correlation_id": task.correlation_id,
            "status": task.status.value,
            "progress": task.progress,
            "temp_dir": task.temp_dir,
            "url": task.url,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    async def cancel_download(self, correlation_id: str) -> bool:
        """Cancel a pending or active download.

        Args:
            correlation_id: The correlation ID of the download to cancel

        Returns:
            True if cancelled, False if not found or already completed

        Example:
            if await facade.cancel_download("abc12345"):
                print("Download cancelled")
            else:
                print("Download not found or already finished")
        """
        result = await self._manager.cancel(correlation_id)
        if result:
            logger.info(f"Download {correlation_id} cancelled")
        return result

    def get_active_downloads(self) -> List[Dict[str, Any]]:
        """Get list of all active downloads.

        Returns:
            List of dicts with download information:
                - correlation_id: Download ID
                - url: Download URL
                - status: Current status
                - progress: Progress percentage if available

        Example:
            active = facade.get_active_downloads()
            print(f"{len(active)} downloads in progress")
            for download in active:
                print(f"  {download['correlation_id']}: {download['progress']}%")
        """
        downloads = []
        for correlation_id, task in self._manager._active_downloads.items():
            progress_pct = task.progress.get('percent', 0) if task.progress else 0
            downloads.append({
                "correlation_id": task.correlation_id,
                "url": task.url,
                "status": task.status.value,
                "progress": progress_pct,
            })
        return downloads

    def get_stats(self) -> Dict[str, Any]:
        """Get facade statistics.

        Returns:
            Dict with current statistics:
                - active: Number of active downloads
                - pending: Number of pending downloads
                - max_concurrent: Maximum concurrent downloads allowed
                - available_slots: Number of available download slots
        """
        return self._manager.get_stats()


async def download_url(url: str, **kwargs) -> LifecycleResult:
    """Convenience function for one-off downloads.

    Creates a DownloadFacade instance, downloads the URL, and cleans up.
    This is the simplest way to download a URL without managing the facade lifecycle.

    Args:
        url: The URL to download
        **kwargs: Additional arguments passed to DownloadFacade.download()
            - chat_id: Chat ID for tracking
            - message_func: Progress message function
            - config_overrides: Configuration overrides

    Returns:
        LifecycleResult with download result

    Raises:
        URLValidationError: If URL is invalid
        UnsupportedURLError: If platform not supported
        DownloadError: If download fails

    Example:
        # Simple download
        result = await download_url("https://youtube.com/watch?v=...")
        if result.success:
            print(f"Downloaded: {result.file_path}")

        # With progress
        result = await download_url(
            url="https://youtube.com/watch?v=...",
            message_func=lambda text: bot.send_message(chat_id, text)
        )
    """
    facade = DownloadFacade()
    async with facade:
        return await facade.download(url, **kwargs)


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    """Run integration tests for DownloadFacade."""
    import tempfile
    from unittest.mock import AsyncMock, MagicMock, patch

    async def test_download_config():
        """Test 1: DownloadConfig creation and defaults."""
        print("\n=== Test 1: DownloadConfig ===")

        # Default config
        config = DownloadConfig()
        assert config.max_concurrent == 5
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
        print("  Default config values correct")

        # Custom config
        custom = DownloadConfig(
            max_concurrent=3,
            max_retries=5,
            extract_audio=True
        )
        assert custom.max_concurrent == 3
        assert custom.max_retries == 5
        assert custom.extract_audio == True
        print("  Custom config values correct")

        # to_download_options
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            options = config.to_download_options(tmpdir)
            assert options.output_path == tmpdir
            assert options.max_filesize == TELEGRAM_MAX_FILE_SIZE
        print("  to_download_options works correctly")

        print("  Test 1 passed")

    async def test_facade_initialization():
        """Test 2: DownloadFacade initialization."""
        print("\n=== Test 2: DownloadFacade Initialization ===")

        # Default initialization
        facade = DownloadFacade()
        assert facade._config.max_concurrent == 5
        assert facade._started == False
        print("  Default facade initialized")

        # Custom config
        config = DownloadConfig(max_concurrent=3)
        facade2 = DownloadFacade(config)
        assert facade2._config.max_concurrent == 3
        print("  Custom facade initialized")

        print("  Test 2 passed")

    async def test_facade_lifecycle():
        """Test 3: Facade start/stop lifecycle."""
        print("\n=== Test 3: Facade Lifecycle ===")

        facade = DownloadFacade()
        assert not facade._started

        # Start
        await facade.start()
        assert facade._started
        print("  Facade started")

        # Stop
        await facade.stop()
        assert not facade._started
        print("  Facade stopped")

        # Context manager
        async with DownloadFacade() as f:
            assert f._started
            print("  Context manager started facade")
        assert not facade._started
        print("  Context manager stopped facade")

        print("  Test 3 passed")

    async def test_download_url_convenience():
        """Test 4: download_url convenience function with mock."""
        print("\n=== Test 4: download_url Convenience Function ===")

        # Mock the router and downloader
        mock_result = LifecycleResult(
            success=True,
            file_path="/tmp/test_video.mp4",
            metadata={"title": "Test Video"},
            correlation_id="test1234",
            temp_dir="/tmp/test"
        )

        with patch.object(PlatformRouter, 'route', new_callable=AsyncMock) as mock_route:
            mock_downloader = AsyncMock()
            mock_downloader.download = AsyncMock(return_value={
                'success': True,
                'file_path': '/tmp/test_video.mp4',
                'metadata': {'title': 'Test Video'}
            })

            mock_route.return_value = RouteResult(
                downloader=mock_downloader,
                platform="youtube",
                confidence="high",
                reason="Test"
            )

            # Test download_url
            result = await download_url("https://youtube.com/watch?v=test")

            assert result.success == True
            assert result.file_path == "/tmp/test_video.mp4"
            print("  download_url returned correct result")

        print("  Test 4 passed")

    async def test_progress_callback_integration():
        """Test 5: Progress callback integration."""
        print("\n=== Test 5: Progress Callback Integration ===")

        facade = DownloadFacade()

        # Mock message function
        messages_sent = []
        async def mock_message_func(text):
            messages_sent.append(text)

        # Create callback
        callback = facade._create_progress_callback(
            mock_message_func,
            min_interval=0.1,
            min_percent=5.0
        )

        # Simulate progress updates
        callback({
            'percent': 0,
            'downloaded_bytes': 0,
            'total_bytes': 1000000,
            'speed': 100000,
            'eta': 10,
            'status': 'downloading'
        })

        # Wait for async callback
        await asyncio.sleep(0.2)

        assert len(messages_sent) > 0
        assert "Descargando" in messages_sent[0]
        print(f"  Progress message sent: {messages_sent[0][:50]}...")

        print("  Test 5 passed")

    async def test_get_download_status():
        """Test 6: get_download_status method."""
        print("\n=== Test 6: get_download_status ===")

        facade = DownloadFacade()

        # Should return None for non-existent download
        status = facade.get_download_status("NONEXISTENT")
        assert status is None
        print("  Returns None for non-existent download")

        print("  Test 6 passed")

    async def test_get_active_downloads():
        """Test 7: get_active_downloads method."""
        print("\n=== Test 7: get_active_downloads ===")

        facade = DownloadFacade()

        # Should return empty list initially
        active = facade.get_active_downloads()
        assert isinstance(active, list)
        assert len(active) == 0
        print("  Returns empty list when no active downloads")

        print("  Test 7 passed")

    async def test_cancel_download():
        """Test 8: cancel_download method."""
        print("\n=== Test 8: cancel_download ===")

        facade = DownloadFacade()
        await facade.start()

        # Should return False for non-existent download
        result = await facade.cancel_download("NONEXISTENT")
        assert result == False
        print("  Returns False for non-existent download")

        await facade.stop()
        print("  Test 8 passed")

    async def test_get_stats():
        """Test 9: get_stats method."""
        print("\n=== Test 9: get_stats ===")

        facade = DownloadFacade()
        await facade.start()

        stats = facade.get_stats()
        assert 'active' in stats
        assert 'pending' in stats
        assert 'max_concurrent' in stats
        assert 'available_slots' in stats
        print(f"  Stats: {stats}")

        await facade.stop()
        print("  Test 9 passed")

    async def test_error_handling():
        """Test 10: Error handling for invalid URLs."""
        print("\n=== Test 10: Error Handling ===")

        facade = DownloadFacade()

        # Test with invalid URL - should raise UnsupportedURLError
        with patch.object(PlatformRouter, 'route', side_effect=UnsupportedURLError("Test")):
            try:
                await facade.start()
                await facade.download("invalid-url")
                assert False, "Should have raised UnsupportedURLError"
            except UnsupportedURLError:
                print("  UnsupportedURLError raised correctly")
            finally:
                await facade.stop()

        print("  Test 10 passed")

    async def run_all_tests():
        """Execute all tests."""
        print("=" * 60)
        print("DownloadFacade Integration Tests")
        print("=" * 60)

        try:
            await test_download_config()
            await test_facade_initialization()
            await test_facade_lifecycle()
            await test_download_url_convenience()
            await test_progress_callback_integration()
            await test_get_download_status()
            await test_get_active_downloads()
            await test_cancel_download()
            await test_get_stats()
            await test_error_handling()

            print("\n" + "=" * 60)
            print("All tests passed!")
            print("=" * 60)

        except AssertionError as e:
            print(f"\nTest failed: {e}")
            raise
        except Exception as e:
            print(f"\nTest error: {e}")
            import traceback
            traceback.print_exc()
            raise

    # Run tests
    asyncio.run(run_all_tests())
