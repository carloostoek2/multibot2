"""Downloader package for media URL handling and downloading.

This package provides URL detection, classification, and downloading
capabilities for the Telegram bot. It supports platform-specific
downloads (YouTube, Instagram, TikTok, Twitter/X, Facebook) as well
as generic video URL downloads.
"""
import logging

# Set up package logger
logger = logging.getLogger(__name__)

# Import base classes and types
from .base import (
    BaseDownloader,
    DownloadOptions,
    TELEGRAM_MAX_FILE_SIZE,
)

# Import exception hierarchy
from .exceptions import (
    DownloadError,
    DownloadFailedError,
    FileTooLargeError,
    MetadataExtractionError,
    NetworkError,
    URLDetectionError,  # Backwards compatibility alias
    URLValidationError,
    UnsupportedURLError,
)

# Import URL detector components
from .url_detector import (
    URLDetector,
    URLType,
    detect_urls,
    classify_url,
    is_video_url,
)

# Import downloader implementations
from .generic_downloader import GenericDownloader
from .ytdlp_downloader import YtDlpDownloader

# Import platform handlers
from .platforms import (
    YouTubeDownloader,
    is_youtube_shorts,
    is_youtube_url,
)


# DownloadResult for backwards compatibility
# (New code should use the more specific result types from implementations)
from dataclasses import dataclass
from typing import Optional


async def get_downloader_for_url(url: str) -> Optional[BaseDownloader]:
    """Get appropriate downloader for a URL.

    Returns GenericDownloader for direct video URLs.
    Returns YtDlpDownloader for platform URLs.

    Args:
        url: The URL to find a downloader for

    Returns:
        Appropriate downloader instance, or None if no downloader can handle the URL
    """
    # Try generic first (faster check for direct video URLs)
    generic = GenericDownloader()
    if await generic.can_handle(url):
        return generic

    # Fall back to yt-dlp for platform URLs
    ytdlp = YtDlpDownloader()
    if await ytdlp.can_handle(url):
        return ytdlp

    return None


@dataclass
class DownloadResult:
    """Result of a download operation.

    Attributes:
        success: Whether the download completed successfully
        file_path: Path to the downloaded file (if successful)
        error_message: Error description (if failed)
        metadata: Additional metadata about the download (title, duration, etc.)
    """
    success: bool
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[dict] = None


# Public API exports
__all__ = [
    # Base classes and types
    "BaseDownloader",
    "DownloadOptions",
    "DownloadResult",
    "TELEGRAM_MAX_FILE_SIZE",
    # Exception hierarchy
    "DownloadError",
    "DownloadFailedError",
    "FileTooLargeError",
    "MetadataExtractionError",
    "NetworkError",
    "URLDetectionError",  # Backwards compatibility
    "URLValidationError",
    "UnsupportedURLError",
    # URL detection
    "URLDetector",
    "URLType",
    "detect_urls",
    "classify_url",
    "is_video_url",
    # Downloader implementations
    "GenericDownloader",
    "YtDlpDownloader",
    # Platform handlers
    "YouTubeDownloader",
    "is_youtube_shorts",
    "is_youtube_url",
    # Helper functions
    "get_downloader_for_url",
]
