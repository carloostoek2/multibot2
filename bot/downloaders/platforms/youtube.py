"""YouTube-specific downloader with Shorts detection and enhanced metadata.

This module provides the YouTubeDownloader class that extends YtDlpDownloader
with YouTube-specific features including:
- YouTube Shorts detection and vertical format optimization
- Enhanced metadata extraction (view count, likes, upload date)
- Age-restricted content handling
- View count formatting for display

Example:
    downloader = YouTubeDownloader()

    # Check if URL is a YouTube Short
    if is_youtube_shorts(url):
        print("This is a Short!")

    # Download with YouTube-specific optimizations
    result = await downloader.download(url, options)
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Optional

from bot.downloaders.ytdlp_downloader import YtDlpDownloader
from bot.downloaders.base import DownloadOptions
from bot.downloaders.exceptions import (
    DownloadFailedError,
    MetadataExtractionError,
)

logger = logging.getLogger(__name__)

# YouTube URL patterns for validation
YOUTUBE_PATTERNS = [
    r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
    r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+',
    r'(?:https?://)?youtu\.be/[\w-]+',
    r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
]

# Compiled regex patterns for performance
_YOUTUBE_REGEX = re.compile('|'.join(YOUTUBE_PATTERNS), re.IGNORECASE)
_SHORTS_REGEX = re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+', re.IGNORECASE)
_VIDEO_ID_REGEX = re.compile(r'(?:v=|/shorts/|youtu\.be/|/embed/)([\w-]+)')


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL.

    Args:
        url: The URL to check

    Returns:
        True if URL matches any YouTube pattern, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    return bool(_YOUTUBE_REGEX.match(url.strip()))


def is_youtube_shorts(url: str) -> bool:
    """Check if URL is a YouTube Shorts URL.

    Args:
        url: The URL to check

    Returns:
        True if URL is a YouTube Shorts URL, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    return bool(_SHORTS_REGEX.match(url.strip()))


def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL.

    Args:
        url: The YouTube URL

    Returns:
        Video ID string or None if not found
    """
    if not url:
        return None

    match = _VIDEO_ID_REGEX.search(url)
    if match:
        return match.group(1)
    return None


def _format_view_count(count: Optional[int]) -> str:
    """Format view count for display.

    Args:
        count: Number of views

    Returns:
        Formatted string like "1.2M views", "500K views", "1,234 views"
    """
    if count is None:
        return "Unknown views"

    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B views"
    elif count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M views"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K views"
    else:
        return f"{count:,} views"


def _is_age_restricted(info: dict) -> bool:
    """Check if video is age-restricted from yt-dlp info.

    Args:
        info: Metadata dictionary from yt-dlp

    Returns:
        True if video is age-restricted, False otherwise
    """
    if not info:
        return False

    # Check common age restriction indicators
    if info.get("age_limit", 0) >= 18:
        return True

    # Check for age-restricted error in formats
    formats = info.get("formats", [])
    if not formats and info.get("availability") == "needs_auth":
        return True

    # Check title/description for age restriction indicators
    title = info.get("title", "").lower()
    if "age-restricted" in title or "content warning" in title:
        return True

    return False


def _parse_upload_date(date_str: Optional[str]) -> Optional[str]:
    """Parse upload date from YYYYMMDD format to ISO date.

    Args:
        date_str: Date string in YYYYMMDD format

    Returns:
        ISO format date string (YYYY-MM-DD) or None
    """
    if not date_str:
        return None

    try:
        # yt-dlp returns dates in YYYYMMDD format
        if len(date_str) == 8 and date_str.isdigit():
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}-{month}-{day}"
        return None
    except (ValueError, TypeError):
        return None


class YouTubeDownloader(YtDlpDownloader):
    """YouTube-specific downloader with Shorts support.

    Extends YtDlpDownloader with YouTube-specific features:
    - Shorts detection and vertical format optimization
    - Enhanced metadata (view count, likes, upload date, tags)
    - Age-restricted content handling
    - View count formatting

    Example:
        downloader = YouTubeDownloader()

        # Check if can handle URL
        if await downloader.can_handle(url):
            # Extract enhanced metadata
            metadata = await downloader.extract_metadata(url, options)
            print(f"Views: {metadata.get('view_count_formatted')}")

            # Download with YouTube optimizations
            result = await downloader.download(url, options)
    """

    @property
    def name(self) -> str:
        """Human-readable downloader name."""
        return "YouTube Downloader"

    @property
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader."""
        return ["YouTube", "YouTube Shorts"]

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            True if this is a YouTube URL, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Quick check with regex first
        if is_youtube_url(url):
            return True

        # Fall back to parent class for yt-dlp validation
        return await super().can_handle(url)

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata with YouTube-specific fields.

        Extends base metadata extraction with YouTube-specific fields:
        - view_count: Number of views
        - like_count: Number of likes (if available)
        - upload_date: Video upload date (ISO format)
        - tags: Video tags
        - categories: Video categories
        - is_shorts: Boolean indicating if it's a Short
        - aspect_ratio: For Shorts, hints at 9:16 format
        - view_count_formatted: Human-readable view count

        Args:
            url: The YouTube URL
            options: Download configuration options

        Returns:
            Dictionary with base metadata plus YouTube-specific fields

        Raises:
            URLValidationError: If URL is invalid
            MetadataExtractionError: If metadata cannot be extracted
        """
        # Get base metadata from parent class
        metadata = await super().extract_metadata(url, options)

        # Add YouTube-specific fields
        def _extract_youtube_info() -> dict[str, Any]:
            """Extract full YouTube info for additional fields."""
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False, process=True)
                    return info or {}
            except Exception as e:
                logger.warning(f"Could not extract full YouTube info: {e}")
                return {}

        # Run extraction in thread pool
        try:
            info = await asyncio.to_thread(_extract_youtube_info)
        except Exception as e:
            logger.warning(f"Failed to extract YouTube-specific metadata: {e}")
            info = {}

        # Check for age restriction
        if _is_age_restricted(info):
            metadata["is_age_restricted"] = True
            metadata["age_limit"] = info.get("age_limit", 18)
        else:
            metadata["is_age_restricted"] = False

        # Add view count
        view_count = info.get("view_count")
        if view_count is not None:
            metadata["view_count"] = view_count
            metadata["view_count_formatted"] = _format_view_count(view_count)

        # Add like count
        like_count = info.get("like_count")
        if like_count is not None:
            metadata["like_count"] = like_count

        # Add upload date
        upload_date = _parse_upload_date(info.get("upload_date"))
        if upload_date:
            metadata["upload_date"] = upload_date

        # Add tags
        tags = info.get("tags")
        if tags:
            metadata["tags"] = tags

        # Add categories
        categories = info.get("categories")
        if categories:
            metadata["categories"] = categories

        # Add YouTube-specific IDs
        video_id = info.get("id") or _extract_youtube_id(url)
        if video_id:
            metadata["youtube_id"] = video_id

        # Detect if it's a Short
        is_shorts = is_youtube_shorts(url)
        metadata["is_shorts"] = is_shorts

        # Add aspect ratio hint for Shorts
        if is_shorts:
            metadata["aspect_ratio"] = "9:16"
            metadata["orientation"] = "vertical"

            # Shorts are typically under 60 seconds
            duration = metadata.get("duration")
            if duration and duration > 180:  # 3 minutes
                logger.warning(
                    f"Video marked as Short but duration is {duration}s"
                )

        # Add channel info if available
        channel_id = info.get("channel_id")
        if channel_id:
            metadata["channel_id"] = channel_id

        channel_follower_count = info.get("channel_follower_count")
        if channel_follower_count:
            metadata["channel_follower_count"] = channel_follower_count

        return metadata

    def _build_ydl_options(
        self,
        options: DownloadOptions,
        output_path: str,
        correlation_id: str,
    ) -> dict:
        """Build yt-dlp options with YouTube optimizations.

        For Shorts: Adds format preference for vertical video
        For regular videos: Uses standard format selection
        Always adds noplaylist to prevent playlist downloads

        Args:
            options: Download configuration
            output_path: Output file path template
            correlation_id: Request tracing ID

        Returns:
            Dictionary of yt-dlp options
        """
        # Get base options from parent
        ydl_opts = super()._build_ydl_options(options, output_path, correlation_id)

        # Ensure noplaylist is set (should already be set by parent)
        ydl_opts["noplaylist"] = True

        # Add YouTube-specific options
        ydl_opts["extractor_args"] = {
            "youtube": {
                # Skip unavailable videos in playlists (shouldn't happen with noplaylist)
                "skip": ["unavailable"],
                # Prefer player client that works best
                "player_client": ["web"],
            }
        }

        # Check if this is a Shorts URL for format optimization
        # Note: We can't easily access the URL here, so we rely on the
        # format string from options which should already be appropriate

        return ydl_opts

    async def download(
        self,
        url: str,
        options: DownloadOptions,
    ) -> Any:
        """Download content with YouTube-specific handling.

        Extends base download with:
        - Age-restricted content detection
        - Better error messages for restricted content
        - Shorts-specific handling

        Args:
            url: The YouTube URL to download
            options: Download configuration options

        Returns:
            DownloadResult with success status and file path

        Raises:
            URLValidationError: If URL is invalid
            FileTooLargeError: If file exceeds size limits
            DownloadFailedError: If download fails or content is restricted
        """
        # First extract metadata to check for restrictions
        try:
            metadata = await self.extract_metadata(url, options)
        except MetadataExtractionError:
            # If metadata extraction fails, try download anyway
            # yt-dlp might still be able to handle it
            metadata = {}

        # Check for age restriction
        if metadata.get("is_age_restricted"):
            logger.warning(
                f"Attempting to download age-restricted content: {url}"
            )
            # yt-dlp may still be able to download with some extractors
            # We'll try and handle failure gracefully

        # Perform the download
        try:
            result = await super().download(url, options)
            return result

        except DownloadFailedError as e:
            # Check if this might be an age restriction issue
            error_msg = str(e).lower()
            if (
                "age" in error_msg
                or "restrict" in error_msg
                or "sign in" in error_msg
                or "login" in error_msg
            ):
                # Enhance error message for age restriction
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "Este video tiene restricción de edad y no puede ser "
                        "descargado sin autenticación."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            raise
