"""Progress tracking utilities for download operations.

This module provides real-time progress tracking with throttled updates
and visual progress bars for download operations. It integrates with
the downloader system to provide user feedback during downloads.

Features:
- Visual progress bars with Unicode block characters
- Human-readable byte/speed formatting
- Throttled updates (time and percentage based)
- Spanish language messages
- Async callback support for Telegram integration

Example:
    from bot.downloaders.progress_tracker import ProgressTracker, format_progress_message

    # Create tracker with callback
    tracker = ProgressTracker(
        min_update_interval=3.0,
        min_percent_change=5.0,
        on_update=lambda p: print(format_progress_message(p))
    )

    # Update progress
    tracker.update({
        'percent': 45.0,
        'downloaded_bytes': 12582912,
        'total_bytes': 26214400,
        'speed': 2621440,
        'eta': 30,
        'status': 'downloading'
    })
"""
import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_MIN_UPDATE_INTERVAL = 3.0  # seconds (per PT-02: 3-5 seconds)
DEFAULT_MIN_PERCENT_CHANGE = 5.0   # percent (per PT-02: 5-10%)
PROGRESS_BAR_WIDTH = 20

# Unicode block characters for smooth progress bars
BLOCK_FULL = "█"
BLOCK_HALF = "▌"
BLOCK_QUARTER = "▏"
BLOCK_EMPTY = "░"


def format_progress_bar(percent: float, width: int = PROGRESS_BAR_WIDTH) -> str:
    """Create a visual progress bar using Unicode block characters.

    Uses full, half, and quarter block characters for smooth progress
    visualization. The bar shows filled and empty portions with
    percentage at the end.

    Args:
        percent: Progress percentage (0-100)
        width: Width of the progress bar in characters (default: 20)

    Returns:
        Formatted progress bar string like "████████████░░░░░░░░ 60%"

    Example:
        >>> format_progress_bar(45)
        '████████▌░░░░░░░░░░░ 45%'
        >>> format_progress_bar(100)
        '████████████████████ 100%'
    """
    # Clamp percentage to valid range
    percent = max(0.0, min(100.0, percent))

    # Calculate filled portion
    filled_exact = (percent / 100.0) * width
    filled_int = int(filled_exact)
    remainder = filled_exact - filled_int

    # Build the bar
    bar = BLOCK_FULL * filled_int

    # Add partial block for sub-character precision
    if filled_int < width:
        if remainder >= 0.75:
            bar += BLOCK_FULL
        elif remainder >= 0.5:
            bar += BLOCK_HALF
        elif remainder >= 0.25:
            bar += BLOCK_QUARTER
        else:
            bar += BLOCK_EMPTY

    # Fill remaining with empty blocks
    remaining = width - len(bar)
    bar += BLOCK_EMPTY * remaining

    return f"{bar} {int(percent)}%"


def format_bytes(bytes_value: int) -> str:
    """Convert bytes to human-readable format.

    Converts a byte value to the most appropriate unit (B, KB, MB, GB)
    using base 1024. Formats with appropriate precision for readability.

    Args:
        bytes_value: Size in bytes

    Returns:
        Human-readable string like "12.5 MB", "850 KB", "100 B"

    Example:
        >>> format_bytes(13107200)
        '12.5 MB'
        >>> format_bytes(870400)
        '850.0 KB'
    """
    if bytes_value < 0:
        return "0 B"

    if bytes_value == 0:
        return "0 B"

    # Define units
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_value)
    unit_index = 0

    # Convert to appropriate unit
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    # Format with appropriate precision
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def format_speed(speed_bytes_per_sec: Optional[float]) -> str:
    """Format download speed in human-readable form.

    Args:
        speed_bytes_per_sec: Download speed in bytes per second, or None

    Returns:
        Formatted speed string like "2.5 MB/s", "850 KB/s", or "--" if None

    Example:
        >>> format_speed(2621440)
        '2.5 MB/s'
        >>> format_speed(None)
        '--'
    """
    if speed_bytes_per_sec is None or speed_bytes_per_sec < 0:
        return "--"

    return f"{format_bytes(int(speed_bytes_per_sec))}/s"


def format_eta(seconds: Optional[int]) -> str:
    """Format ETA (estimated time of arrival) in human-readable form.

    Args:
        seconds: ETA in seconds, or None

    Returns:
        Formatted ETA string like "2m 30s", "45s", or "--" if None

    Example:
        >>> format_eta(150)
        '2m 30s'
        >>> format_eta(45)
        '45s'
        >>> format_eta(None)
        '--'
    """
    if seconds is None or seconds < 0:
        return "--"

    if seconds == 0:
        return "0s"

    minutes = seconds // 60
    remaining_seconds = seconds % 60

    if minutes > 0:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def format_progress_message(progress: dict) -> str:
    """Format a progress update message in Spanish.

    Creates a formatted progress message suitable for display to users.
    Includes progress bar, percentage, size information, speed, and ETA.
    Uses Spanish messages and emoji indicators.

    Args:
        progress: Dictionary containing progress information:
            - percent: Progress percentage (0-100)
            - downloaded_bytes: Bytes downloaded so far
            - total_bytes: Total bytes to download (may be None for unknown)
            - speed: Download speed in bytes per second (may be None)
            - eta: Estimated time remaining in seconds (may be None)
            - status: One of 'downloading', 'completed', 'error'
            - filename: Filename for completed downloads (optional)

    Returns:
        Formatted progress message in Spanish with emoji indicators

    Example:
        >>> progress = {
        ...     'percent': 45,
        ...     'downloaded_bytes': 12582912,
        ...     'total_bytes': 26214400,
        ...     'speed': 2621440,
        ...     'eta': 30,
        ...     'status': 'downloading'
        ... }
        >>> format_progress_message(progress)
        '⬇️ Descargando: [████████▌░░░░░░░░░░░] 45% (12.5 MB / 25.0 MB) - 2.5 MB/s - ETA: 30s'
    """
    status = progress.get("status", "downloading")

    # Handle completed status
    if status == "completed":
        filename = progress.get("filename", "archivo")
        total_bytes = progress.get("total_bytes", 0)
        size_str = format_bytes(total_bytes) if total_bytes else "tamaño desconocido"
        return f"✅ Descarga completada: {filename} ({size_str})"

    # Handle error status
    if status == "error":
        error_msg = progress.get("error", "Error desconocido")
        return f"❌ Error en la descarga: {error_msg}"

    # Handle downloading status (default)
    percent = progress.get("percent", 0)
    downloaded = progress.get("downloaded_bytes", 0)
    total = progress.get("total_bytes")
    speed = progress.get("speed")
    eta = progress.get("eta")

    # Build progress bar
    bar = format_progress_bar(percent)

    # Build size string
    if total:
        size_str = f"{format_bytes(downloaded)} / {format_bytes(total)}"
    else:
        size_str = format_bytes(downloaded)

    # Build speed and ETA string
    speed_str = format_speed(speed)
    eta_str = format_eta(eta)

    return (
        f"⬇️ Descargando: [{bar}] - {speed_str} - ETA: {eta_str}"
    )


class ProgressTracker:
    """Track download progress with throttled updates.

    Provides progress tracking with configurable throttling to avoid
    message spam. Updates are sent based on time interval and percentage
    change thresholds. Always sends updates for status changes.

    Attributes:
        min_update_interval: Minimum seconds between updates
        min_percent_change: Minimum percentage change for update
        on_update: Callback function for progress updates

    Example:
        >>> tracker = ProgressTracker(
        ...     min_update_interval=3.0,
        ...     min_percent_change=5.0,
        ...     on_update=lambda p: print(format_progress_message(p))
        ... )
        >>> tracker.update({'percent': 10, 'status': 'downloading'})
        True  # Update sent
        >>> tracker.update({'percent': 11, 'status': 'downloading'})
        False  # Throttled (not enough change)
    """

    def __init__(
        self,
        min_update_interval: float = DEFAULT_MIN_UPDATE_INTERVAL,
        min_percent_change: float = DEFAULT_MIN_PERCENT_CHANGE,
        on_update: Optional[Callable[[dict], None]] = None
    ):
        """Initialize the progress tracker.

        Args:
            min_update_interval: Minimum seconds between updates (default: 3.0)
            min_percent_change: Minimum percentage change for update (default: 5.0)
            on_update: Callback function called when update is sent
        """
        self.min_update_interval = min_update_interval
        self.min_percent_change = min_percent_change
        self._on_update = on_update

        self._last_update_time: Optional[datetime] = None
        self._last_percent: float = 0.0
        self._start_time: datetime = datetime.now()
        self._update_count: int = 0
        self._total_bytes: int = 0

    def should_update(self, percent: float, status: str = "downloading") -> bool:
        """Check if an update should be sent based on throttling rules.

        Updates are sent when:
        - Enough time has passed since last update (min_update_interval)
        - Enough progress has been made (min_percent_change)
        - Status has changed (finished, error)

        Args:
            percent: Current progress percentage (0-100)
            status: Current download status

        Returns:
            True if update should be sent, False otherwise
        """
        # Always update for completed or error status
        if status in ("completed", "error"):
            return True

        # First update always sent
        if self._last_update_time is None:
            return True

        # Check time interval
        now = datetime.now()
        time_since_last = (now - self._last_update_time).total_seconds()
        if time_since_last >= self.min_update_interval:
            return True

        # Check percentage change
        percent_change = abs(percent - self._last_percent)
        if percent_change >= self.min_percent_change:
            return True

        return False

    def update(self, progress: dict) -> bool:
        """Update progress and trigger callback if throttling allows.

        Args:
            progress: Dictionary containing progress information:
                - percent: Progress percentage (0-100)
                - downloaded_bytes: Bytes downloaded so far
                - total_bytes: Total bytes to download
                - speed: Download speed in bytes per second
                - eta: Estimated time remaining in seconds
                - status: One of 'downloading', 'completed', 'error'
                - error: Error message for error status
                - filename: Filename for completed downloads

        Returns:
            True if update was sent, False if throttled
        """
        percent = progress.get("percent", 0.0)
        status = progress.get("status", "downloading")

        # Check if we should send update
        if not self.should_update(percent, status):
            return False

        # Update internal state
        self._last_update_time = datetime.now()
        self._last_percent = percent
        self._update_count += 1

        # Track total bytes
        total = progress.get("total_bytes", 0)
        if total > self._total_bytes:
            self._total_bytes = total

        # Call callback if provided
        if self._on_update:
            try:
                result = self._on_update(progress)
                # Handle async callbacks
                if asyncio.iscoroutine(result):
                    # Schedule in event loop if available
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(result)
                        else:
                            asyncio.run(result)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.warning(f"Error in progress callback: {e}")

        return True

    def create_callback(self) -> Callable[[dict], None]:
        """Create a callback function suitable for DownloadOptions.progress_callback.

        Returns a callback that can be passed to download operations.
        The callback receives progress dict and calls self.update().

        Returns:
            Callback function for progress updates
        """
        def callback(progress: dict) -> None:
            self.update(progress)

        return callback

    def get_summary(self) -> dict:
        """Get a summary of the download progress.

        Returns summary information including total bytes, update count,
        elapsed time, and average speed.

        Returns:
            Dictionary with download summary:
                - total_bytes: Total bytes downloaded
                - update_count: Number of progress updates sent
                - elapsed_seconds: Time elapsed since start
                - average_speed: Average speed in bytes per second
        """
        now = datetime.now()
        elapsed = (now - self._start_time).total_seconds()

        # Calculate average speed
        average_speed = None
        if elapsed > 0 and self._total_bytes > 0:
            average_speed = self._total_bytes / elapsed

        return {
            "total_bytes": self._total_bytes,
            "update_count": self._update_count,
            "elapsed_seconds": int(elapsed),
            "average_speed": average_speed,
        }

    def reset(self) -> None:
        """Reset the tracker to initial state.

        Clears all internal state, useful for reusing the tracker
        for a new download operation.
        """
        self._last_update_time = None
        self._last_percent = 0.0
        self._start_time = datetime.now()
        self._update_count = 0
        self._total_bytes = 0


def create_progress_callback(
    message_func: Callable[[str], Awaitable[None]],
    min_interval: float = DEFAULT_MIN_UPDATE_INTERVAL,
    min_percent: float = DEFAULT_MIN_PERCENT_CHANGE
) -> Callable[[dict], None]:
    """Create a progress callback that sends messages via message_func.

    Creates a callback suitable for integration with Telegram bots.
    Uses ProgressTracker for throttling and formats messages using
    format_progress_message().

    Args:
        message_func: Async function to send messages (e.g., bot.send_message)
        min_interval: Minimum seconds between updates
        min_percent: Minimum percentage change for update

    Returns:
        Callback function for progress updates

    Example:
        >>> async def send_message(text: str) -> None:
        ...     await bot.send_message(chat_id=123, text=text)
        ...
        >>> callback = create_progress_callback(send_message)
        >>> callback({'percent': 50, 'status': 'downloading'})
    """
    async def async_update(progress: dict) -> None:
        message = format_progress_message(progress)
        await message_func(message)

    tracker = ProgressTracker(
        min_update_interval=min_interval,
        min_percent_change=min_percent,
        on_update=lambda p: async_update(p)
    )

    return tracker.create_callback()


# Export public API
__all__ = [
    "ProgressTracker",
    "format_progress_bar",
    "format_bytes",
    "format_speed",
    "format_eta",
    "format_progress_message",
    "create_progress_callback",
    "DEFAULT_MIN_UPDATE_INTERVAL",
    "DEFAULT_MIN_PERCENT_CHANGE",
    "PROGRESS_BAR_WIDTH",
]


if __name__ == "__main__":
    """Run tests for progress tracking utilities."""
    import asyncio

    async def run_tests():
        """Test all progress tracking functionality."""
        print("=" * 60)
        print("Testing Progress Tracker")
        print("=" * 60)

        # Test format_progress_bar
        print("\n1. Testing format_progress_bar:")
        print("-" * 40)
        test_percentages = [0, 25, 50, 75, 100]
        for pct in test_percentages:
            bar = format_progress_bar(pct)
            print(f"  {pct:3d}%: {bar}")

        # Test format_bytes
        print("\n2. Testing format_bytes:")
        print("-" * 40)
        test_sizes = [
            0,
            512,
            1024,
            870400,      # 850 KB
            13107200,    # 12.5 MB
            1073741824,  # 1 GB
        ]
        for size in test_sizes:
            formatted = format_bytes(size)
            print(f"  {size:>12} bytes = {formatted}")

        # Test format_speed
        print("\n3. Testing format_speed:")
        print("-" * 40)
        test_speeds = [None, 0, 1024, 2621440, 10485760]
        for speed in test_speeds:
            formatted = format_speed(speed)
            print(f"  {speed}: {formatted}")

        # Test format_eta
        print("\n4. Testing format_eta:")
        print("-" * 40)
        test_etas = [None, 0, 30, 60, 150, 3600]
        for eta in test_etas:
            formatted = format_eta(eta)
            print(f"  {eta}: {formatted}")

        # Test format_progress_message
        print("\n5. Testing format_progress_message:")
        print("-" * 40)
        test_progresses = [
            {
                "percent": 0,
                "downloaded_bytes": 0,
                "total_bytes": 26214400,
                "speed": 0,
                "eta": 120,
                "status": "downloading",
            },
            {
                "percent": 45,
                "downloaded_bytes": 12582912,
                "total_bytes": 26214400,
                "speed": 2621440,
                "eta": 30,
                "status": "downloading",
            },
            {
                "percent": 100,
                "downloaded_bytes": 26214400,
                "total_bytes": 26214400,
                "speed": 0,
                "eta": 0,
                "status": "completed",
                "filename": "video.mp4",
            },
            {
                "percent": 50,
                "downloaded_bytes": 13107200,
                "total_bytes": 26214400,
                "speed": 0,
                "eta": None,
                "status": "error",
                "error": "Conexión perdida",
            },
        ]
        for progress in test_progresses:
            message = format_progress_message(progress)
            print(f"  Status: {progress['status']}")
            print(f"    {message}\n")

        # Test ProgressTracker throttling
        print("6. Testing ProgressTracker throttling:")
        print("-" * 40)
        updates_sent = []

        def on_update(progress: dict) -> None:
            updates_sent.append(progress["percent"])
            print(f"  Update sent: {progress['percent']}%")

        tracker = ProgressTracker(
            min_update_interval=0.5,  # 0.5 seconds for testing
            min_percent_change=10.0,  # 10% change required
            on_update=on_update
        )

        # Rapid updates - only first should be sent
        print("  Sending rapid updates (0%, 5%, 8%)...")
        tracker.update({"percent": 0, "status": "downloading"})
        tracker.update({"percent": 5, "status": "downloading"})
        tracker.update({"percent": 8, "status": "downloading"})

        # Wait for interval
        print("  Waiting 0.6 seconds...")
        await asyncio.sleep(0.6)

        # This should trigger (time passed)
        print("  Sending update at 15%...")
        tracker.update({"percent": 15, "status": "downloading"})

        # Large percent jump - should trigger
        print("  Sending update at 30% (big jump)...")
        tracker.update({"percent": 30, "status": "downloading"})

        # Small jump - should be throttled
        print("  Sending update at 33% (small jump)...")
        tracker.update({"percent": 33, "status": "downloading"})

        # Completed - always sent
        print("  Sending completed status...")
        tracker.update({"percent": 100, "status": "completed", "total_bytes": 26214400})

        print(f"\n  Total updates sent: {len(updates_sent)}")
        print(f"  Update percentages: {updates_sent}")

        # Test get_summary
        print("\n7. Testing get_summary:")
        print("-" * 40)
        summary = tracker.get_summary()
        print(f"  Total bytes: {summary['total_bytes']}")
        print(f"  Update count: {summary['update_count']}")
        print(f"  Elapsed seconds: {summary['elapsed_seconds']}")
        print(f"  Average speed: {format_speed(summary['average_speed'])}")

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    # Run tests
    asyncio.run(run_tests())
