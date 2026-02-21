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

# Placeholder imports for future modules
# from .ytdlp_downloader import YtDlpDownloader
# from .generic_downloader import GenericDownloader


# DownloadResult for backwards compatibility
# (New code should use the more specific result types from implementations)
from dataclasses import dataclass
from typing import Optional


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
    # Placeholder for future exports
    # "YtDlpDownloader",
    # "GenericDownloader",
]
