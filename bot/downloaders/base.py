"""Base downloader interface and common types.

This module provides the abstract base class that all downloader implementations
must inherit from, along with the DownloadOptions dataclass for configuration.

The architecture ensures:
- Consistent interface across all downloaders (yt-dlp, generic HTTP, etc.)
- Type-safe configuration with validation
- Async operations with proper cancellation support
- Request tracing via correlation IDs
"""
import abc
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

# Avoid circular imports
if TYPE_CHECKING:
    from bot.config import BotConfig

from .exceptions import (
    DownloadError,
    FileTooLargeError,
    URLValidationError,
)

logger = logging.getLogger(__name__)

# Telegram bot upload limit in bytes (50 MB)
TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024


@dataclass(frozen=True)
class DownloadOptions:
    """Configuration options for download operations.

    This dataclass encapsulates all download configuration parameters
    with sensible defaults aligned with bot.config values. It uses
    frozen=True for immutability to prevent accidental modifications.

    Attributes:
        # Output settings
        output_path: Directory to save downloaded files
        filename: Custom filename (auto-generated if None)

        # Quality settings (yt-dlp format strings)
        video_format: yt-dlp format string for video downloads
        audio_format: yt-dlp format string for audio-only downloads
        preferred_quality: Preferred quality (e.g., "720p", "best")
        max_filesize: Maximum file size in bytes (Telegram limit: 50MB)

        # Format preferences
        output_format: Preferred container format (mp4, webm, etc.)
        audio_codec: Audio codec for extraction (mp3, m4a, etc.)
        audio_bitrate: Audio bitrate (e.g., "320k", "192k")

        # Download mode
        extract_audio: Download audio only (True) or video (False)
        keep_video: Keep video file when extracting audio

        # Retry settings
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds between retry attempts

        # Timeout settings
        metadata_timeout: Seconds to wait for metadata extraction
        download_timeout: Seconds to wait for download completion

        # Progress callback
        progress_callback: Optional callback for progress updates
    """

    # Output settings
    output_path: Optional[str] = None
    filename: Optional[str] = None

    # Quality settings (per QF-01, QF-02, QF-03, QF-05)
    video_format: str = "best[filesize<50M]/best"
    audio_format: str = "bestaudio[filesize<50M]/bestaudio"
    preferred_quality: str = "best"
    max_filesize: int = TELEGRAM_MAX_FILE_SIZE  # 50MB default

    # Format preferences
    output_format: str = "mp4"
    audio_codec: str = "mp3"
    audio_bitrate: str = "320k"

    # Download mode (per DL-04)
    extract_audio: bool = False
    keep_video: bool = True

    # Retry settings (per EH-03)
    max_retries: int = 3
    retry_delay: int = 2

    # Timeout settings
    metadata_timeout: int = 30
    download_timeout: int = 300  # 5 minutes

    # Progress callback
    progress_callback: Optional[Callable[[dict], None]] = None

    def __post_init__(self) -> None:
        """Validate configuration values after initialization.

        Raises:
            ValueError: If any configuration value is invalid.
        """
        # Need to use object.__setattr__ because dataclass is frozen
        errors = []

        # Validate max_filesize doesn't exceed Telegram limits
        if self.max_filesize > TELEGRAM_MAX_FILE_SIZE:
            errors.append(
                f"max_filesize ({self.max_filesize}) exceeds Telegram limit "
                f"({TELEGRAM_MAX_FILE_SIZE} bytes = 50MB)"
            )

        # Validate retry settings are non-negative
        if self.max_retries < 0:
            errors.append(f"max_retries must be non-negative (got: {self.max_retries})")
        if self.retry_delay < 0:
            errors.append(f"retry_delay must be non-negative (got: {self.retry_delay})")

        # Validate timeouts are positive
        if self.metadata_timeout <= 0:
            errors.append(
                f"metadata_timeout must be positive (got: {self.metadata_timeout})"
            )
        if self.download_timeout <= 0:
            errors.append(
                f"download_timeout must be positive (got: {self.download_timeout})"
            )

        # Validate output_path exists if provided
        if self.output_path is not None:
            path = Path(self.output_path)
            if not path.exists():
                errors.append(f"output_path does not exist: {self.output_path}")
            elif not path.is_dir():
                errors.append(f"output_path is not a directory: {self.output_path}")

        # Raise if any validation errors
        if errors:
            raise ValueError(
                "DownloadOptions validation failed:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

    @classmethod
    def from_config(cls, config: Optional[Any] = None) -> "DownloadOptions":
        """Create DownloadOptions from bot configuration.

        Args:
            config: BotConfig instance (uses global config if None)

        Returns:
            DownloadOptions instance with values from config.
        """
        # Import here to avoid circular imports at module level
        from bot.config import config as bot_config

        if config is None:
            config = bot_config

        return cls(
            # Quality settings from config
            video_format=config.DOWNLOAD_VIDEO_FORMAT,
            audio_format=config.DOWNLOAD_AUDIO_FORMAT,
            audio_bitrate=f"{config.DOWNLOAD_AUDIO_QUALITY}k",
            output_format=config.DOWNLOAD_VIDEO_PREFERENCE,
            max_filesize=config.DOWNLOAD_MAX_SIZE_MB * 1024 * 1024,

            # Retry settings from config
            max_retries=config.DOWNLOAD_MAX_RETRIES,
            retry_delay=config.DOWNLOAD_RETRY_DELAY,

            # Timeout settings from config
            metadata_timeout=config.DOWNLOAD_METADATA_TIMEOUT,
            download_timeout=config.DOWNLOAD_TIMEOUT,
        )

    def with_overrides(self, **kwargs) -> "DownloadOptions":
        """Create a new DownloadOptions with overridden values.

        Since the dataclass is frozen, this method creates a new instance
        with the specified values changed.

        Args:
            **kwargs: Field names and new values to override

        Returns:
            New DownloadOptions instance with overrides applied.
        """
        current = {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }
        current.update(kwargs)
        return self.__class__(**current)


class BaseDownloader(abc.ABC):
    """Abstract base class for all downloader implementations.

    This class defines the contract that all downloaders must implement,
    ensuring they can be used interchangeably by higher-level code.

    Implementations must provide:
    - can_handle(): Determine if this downloader can handle a URL
    - extract_metadata(): Extract metadata without downloading
    - download(): Perform the actual download

    The base class provides:
    - URL validation utilities
    - File size checking
    - Formatting utilities (duration, filesize)
    - Correlation ID generation for request tracing
    - Filename sanitization

    Example:
        class MyDownloader(BaseDownloader):
            @property
            def name(self) -> str:
                return "My Downloader"

            async def can_handle(self, url: str) -> bool:
                return url.startswith("https://example.com")

            async def extract_metadata(self, url, options):
                # Implementation
                pass

            async def download(self, url, options):
                # Implementation
                pass
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable downloader name.

        Returns:
            String name of this downloader implementation.
        """
        pass

    @property
    @abc.abstractmethod
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader.

        Returns:
            List of human-readable platform names.
        """
        pass

    @abc.abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            True if this downloader can handle the URL, False otherwise.
        """
        pass

    @abc.abstractmethod
    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions
    ) -> dict[str, Any]:
        """Extract metadata from a URL without downloading.

        Per DL-03: Metadata extraction requirement. This method should
        fetch information about the content (title, duration, format, etc.)
        without downloading the actual file.

        Args:
            url: The URL to extract metadata from
            options: Download configuration options

        Returns:
            Dictionary containing metadata fields:
            - title: Content title
            - duration: Duration in seconds (if available)
            - uploader: Content creator/uploader (if available)
            - thumbnail: URL to thumbnail image (if available)
            - formats: List of available formats (if applicable)

        Raises:
            URLValidationError: If the URL is invalid
            MetadataExtractionError: If metadata cannot be extracted
            UnsupportedURLError: If the URL is from an unsupported platform
        """
        pass

    @abc.abstractmethod
    async def download(
        self,
        url: str,
        options: DownloadOptions
    ) -> Any:
        """Download content from the given URL.

        Args:
            url: The URL to download from
            options: Download configuration options

        Returns:
            DownloadResult containing:
            - success: Whether download completed successfully
            - file_path: Path to the downloaded file (if successful)
            - metadata: Additional metadata about the download

        Raises:
            URLValidationError: If the URL is invalid
            FileTooLargeError: If the file exceeds size limits
            DownloadFailedError: If download fails after retries
            NetworkError: For transient network failures
        """
        pass

    # Utility methods (concrete implementations)

    def validate_url(self, url: str) -> bool:
        """Validate URL format.

        Performs basic URL validation (scheme and netloc presence).

        Args:
            url: The URL to validate

        Returns:
            True if URL format is valid

        Raises:
            URLValidationError: If URL format is invalid
        """
        if not url or not isinstance(url, str):
            raise URLValidationError("URL is empty or not a string")

        if not self._is_valid_url(url):
            raise URLValidationError(f"Invalid URL format: {url}")

        return True

    def check_filesize(self, size: int, max_size: int) -> None:
        """Check if file size is within limits.

        Args:
            size: File size in bytes
            max_size: Maximum allowed size in bytes

        Raises:
            FileTooLargeError: If size exceeds max_size
        """
        if size > max_size:
            raise FileTooLargeError(
                file_size=size,
                max_size=max_size,
                message=f"File size {size} bytes exceeds limit {max_size} bytes"
            )

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format duration in seconds to human-readable string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string like "MM:SS" or "HH:MM:SS"
        """
        if seconds < 0:
            return "00:00"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def format_filesize(bytes_value: int) -> str:
        """Format file size in bytes to human-readable string.

        Args:
            bytes_value: Size in bytes

        Returns:
            Formatted string like "X MB" or "X GB"
        """
        if bytes_value < 0:
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

    @staticmethod
    def _generate_correlation_id() -> str:
        """Generate unique correlation ID for request tracing.

        Per DM-02: Request tracing for debugging and monitoring.

        Returns:
            Unique 8-character identifier string.
        """
        return str(uuid.uuid4())[:8]

    @staticmethod
    def _sanitize_filename(title: str) -> str:
        """Sanitize a string for use as a filename.

        Removes or replaces characters that are invalid in filenames.

        Args:
            title: The original title/string

        Returns:
            Sanitized string safe for use as filename
        """
        if not title:
            return "download"

        # Replace spaces with underscores
        sanitized = title.replace(" ", "_")

        # Remove invalid characters
        # Keep: alphanumeric, underscore, hyphen, period
        sanitized = re.sub(r'[^\w\-\.]', '', sanitized)

        # Limit length
        max_length = 100
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        # Ensure not empty after sanitization
        if not sanitized:
            sanitized = "download"

        return sanitized

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if URL has valid format.

        Validates that URL has a scheme (http/https) and netloc.

        Args:
            url: The URL to validate

        Returns:
            True if URL format is valid, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Simple regex for URL validation
        pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )

        return bool(pattern.match(url.strip()))


__all__ = [
    "BaseDownloader",
    "DownloadOptions",
    "TELEGRAM_MAX_FILE_SIZE",
]