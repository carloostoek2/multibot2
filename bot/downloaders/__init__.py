"""Downloader package for media URL handling and downloading.

This package provides URL detection, classification, and downloading
capabilities for the Telegram bot. It supports platform-specific
downloads (YouTube, Instagram, TikTok, Twitter/X, Facebook) as well
as generic video URL downloads.

Quick Start:
    # Route URL to appropriate downloader
    from bot.downloaders import route_url
    result = await route_url('https://youtube.com/watch?v=...')

    # Download with automatic handler selection
    downloader = result.downloader
    result = await downloader.download(url, options)

    # Or use the convenience function
    from bot.downloaders import get_downloader_for_url
    downloader = await get_downloader_for_url(url)
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
    RateLimitError,
    URLDetectionError,  # Backwards compatibility alias
    URLValidationError,
    UnsupportedURLError,
)

# Import URL detector components
from .url_detector import (
    URLDetector,
    URLType,
    classify_url,
    classify_url_enhanced,
    detect_urls,
    is_video_url,
)

# Import downloader implementations
from .generic_downloader import GenericDownloader
from .ytdlp_downloader import YtDlpDownloader

# Import platform handlers
from .platforms import (
    # YouTube
    YouTubeDownloader,
    is_youtube_shorts,
    is_youtube_url,
    # Instagram
    InstagramDownloader,
    InstagramContentType,
    is_instagram_reel,
    is_instagram_story,
    is_instagram_url,
    # TikTok
    TikTokDownloader,
    is_tiktok_url,
    is_tiktok_slideshow,
    # Twitter/X
    TwitterDownloader,
    is_twitter_url,
    # Facebook
    FacebookDownloader,
    is_facebook_url,
    is_facebook_reel,
)

# Import HTML extractor
from .html_extractor import (
    HTMLVideoExtractor,
    VideoURL,
    extract_videos_from_html,
    download_from_html,
)

# Import platform router
from .platform_router import (
    PlatformRouter,
    RouteResult,
    get_downloader_for_url,
    route_url,
)

# Import progress tracker (new)
from .progress_tracker import (
    ProgressTracker,
    create_progress_callback,
    format_bytes,
    format_eta,
    format_progress_bar,
    format_progress_message,
    format_speed,
)

# Import retry handler (new)
from .retry_handler import (
    RetryHandler,
    TimeoutConfig,
    create_timeout_guard,
    is_retryable_error,
)

# Import download lifecycle
from .download_lifecycle import (
    DownloadLifecycle,
    IsolatedDownload,
    cleanup_download,
)

# Import download manager
from .download_manager import (
    DownloadManager,
    DownloadStatus,
    DownloadTask,
)

# Import unified API (facade)
from .download_facade import (
    DownloadFacade,
    DownloadConfig,
    download_url,
)

# DownloadResult for backwards compatibility
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
    "RateLimitError",
    "URLDetectionError",  # Backwards compatibility
    "URLValidationError",
    "UnsupportedURLError",
    # URL detection
    "URLDetector",
    "URLType",
    "classify_url",
    "classify_url_enhanced",
    "detect_urls",
    "is_video_url",
    # Downloader implementations
    "GenericDownloader",
    "YtDlpDownloader",
    # Platform handlers
    "YouTubeDownloader",
    "is_youtube_shorts",
    "is_youtube_url",
    "InstagramDownloader",
    "InstagramContentType",
    "is_instagram_reel",
    "is_instagram_story",
    "is_instagram_url",
    "TikTokDownloader",
    "is_tiktok_url",
    "is_tiktok_slideshow",
    "TwitterDownloader",
    "is_twitter_url",
    "FacebookDownloader",
    "is_facebook_url",
    "is_facebook_reel",
    # HTML extractor
    "HTMLVideoExtractor",
    "VideoURL",
    "extract_videos_from_html",
    "download_from_html",
    # Platform router
    "PlatformRouter",
    "RouteResult",
    "get_downloader_for_url",
    "route_url",
    # Download management
    "DownloadManager",
    "DownloadStatus",
    "DownloadTask",
    # Progress tracking
    "ProgressTracker",
    "create_progress_callback",
    "format_bytes",
    "format_eta",
    "format_progress_bar",
    "format_progress_message",
    "format_speed",
    # Retry handling
    "RetryHandler",
    "TimeoutConfig",
    "create_timeout_guard",
    "is_retryable_error",
    # Lifecycle management
    "DownloadLifecycle",
    "IsolatedDownload",
    "cleanup_download",
    # Unified API (facade)
    "DownloadFacade",
    "DownloadConfig",
    "download_url",
]
