"""Downloader package for media URL handling and downloading.

This package provides URL detection, classification, and downloading
capabilities for the Telegram bot. It supports platform-specific
downloads (YouTube, Instagram, TikTok, Twitter/X, Facebook) as well
as generic video URL downloads.
"""
import logging
from dataclasses import dataclass
from typing import Optional

# Set up package logger
logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Base exception for download operations.

    Raised when a download fails due to network issues, invalid URLs,
    platform restrictions, or other download-related errors.
    """
    pass


class URLDetectionError(DownloadError):
    """Exception raised when URL detection or extraction fails."""
    pass


class UnsupportedURLError(DownloadError):
    """Exception raised when a URL type is not supported."""
    pass


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


# Import URL detector components
from .url_detector import (
    URLDetector,
    URLType,
    detect_urls,
    classify_url,
    is_video_url,
)

# Placeholder imports for future modules
# from .base import BaseDownloader
# from .ytdlp_downloader import YtDlpDownloader
# from .generic_downloader import GenericDownloader


# Public API exports
__all__ = [
    # Exceptions
    "DownloadError",
    "URLDetectionError",
    "UnsupportedURLError",
    # Data classes
    "DownloadResult",
    # URL detection
    "URLDetector",
    "URLType",
    "detect_urls",
    "classify_url",
    "is_video_url",
    # Placeholder for future exports
    # "BaseDownloader",
    # "YtDlpDownloader",
    # "GenericDownloader",
]
