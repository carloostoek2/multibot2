"""Instagram-specific downloader for posts, Reels, and Stories.

This module provides the InstagramDownloader class for downloading content
from Instagram with proper content type detection (posts, Reels, Stories)
and enhanced metadata extraction including username, caption, likes count,
and comments count.

Example:
    downloader = InstagramDownloader()

    # Check if URL is an Instagram Reel
    if is_instagram_reel(url):
        result = await downloader.download(url, options)

    # Get content type
    content_type = detect_instagram_content_type(url)
"""
import asyncio
import logging
import re
from enum import Enum, auto
from typing import Any, Optional

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from ..base import DownloadOptions
from ..exceptions import DownloadFailedError, MetadataExtractionError
from ..ytdlp_downloader import YtDlpDownloader

logger = logging.getLogger(__name__)


class InstagramContentType(Enum):
    """Enumeration of Instagram content types."""

    POST = auto()  # Regular post (/p/)
    REEL = auto()  # Reel (/reel/ or /reels/)
    STORY = auto()  # Story (/stories/)
    UNKNOWN = auto()


# Instagram URL patterns for validation
INSTAGRAM_PATTERNS = {
    "post": [
        r"instagram\.com/p/[\w-]+",
        r"instagram\.com/tv/[\w-]+",  # IGTV (legacy)
    ],
    "reel": [
        r"instagram\.com/reel/[\w-]+",
        r"instagram\.com/reels/[\w-]+",
    ],
    "story": [
        r"instagram\.com/stories/[\w.]+/[\d-]+",
    ],
}


def is_instagram_url(url: str) -> bool:
    """Check if URL is an Instagram URL.

    Args:
        url: The URL to check

    Returns:
        True if the URL is from instagram.com
    """
    return "instagram.com" in url.lower()


def detect_instagram_content_type(url: str) -> InstagramContentType:
    """Detect the type of Instagram content from URL.

    Args:
        url: The Instagram URL to analyze

    Returns:
        InstagramContentType enum value indicating the content type
    """
    url_lower = url.lower()

    if "/reel/" in url_lower or "/reels/" in url_lower:
        return InstagramContentType.REEL
    elif "/stories/" in url_lower:
        return InstagramContentType.STORY
    elif "/p/" in url_lower or "/tv/" in url_lower:
        return InstagramContentType.POST
    else:
        return InstagramContentType.UNKNOWN


def is_instagram_reel(url: str) -> bool:
    """Check if URL is an Instagram Reel.

    Args:
        url: The URL to check

    Returns:
        True if the URL is an Instagram Reel
    """
    return detect_instagram_content_type(url) == InstagramContentType.REEL


def is_instagram_story(url: str) -> bool:
    """Check if URL is an Instagram Story.

    Args:
        url: The URL to check

    Returns:
        True if the URL is an Instagram Story
    """
    return detect_instagram_content_type(url) == InstagramContentType.STORY


def extract_shortcode(url: str) -> Optional[str]:
    """Extract Instagram shortcode from URL.

    Shortcodes are the unique identifiers for posts, reels, and IGTV videos.
    Patterns like /p/ABC123/, /reel/ABC123/

    Args:
        url: The Instagram URL

    Returns:
        The shortcode string or None if not found
    """
    patterns = [
        r"/p/([\w-]+)",
        r"/reel/([\w-]+)",
        r"/reels/([\w-]+)",
        r"/tv/([\w-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_username_from_url(url: str) -> Optional[str]:
    """Extract username from Instagram URL (for stories).

    Args:
        url: The Instagram story URL

    Returns:
        The username or None if not found
    """
    # Pattern: /stories/username/123456/
    match = re.search(r"/stories/([\w.]+)/", url.lower())
    if match:
        return match.group(1)
    return None


class InstagramDownloader(YtDlpDownloader):
    """Instagram-specific downloader for posts, Reels, and Stories.

    Extends YtDlpDownloader with Instagram-specific features:
    - Content type detection (post, Reel, Story)
    - Enhanced metadata extraction (username, caption, likes, comments)
    - Aspect ratio hints for Reels (9:16)
    - Spanish error messages for private/unavailable content

    Example:
        downloader = InstagramDownloader()

        # Check if can handle URL
        if await downloader.can_handle(url):
            metadata = await downloader.extract_metadata(url, options)
            print(f"Username: {metadata.get('username')}")
            print(f"Likes: {metadata.get('likes_count')}")

            result = await downloader.download(url, options)
    """

    @property
    def name(self) -> str:
        """Human-readable downloader name."""
        return "Instagram Downloader"

    @property
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader."""
        return ["Instagram", "Instagram Reels", "Instagram Stories"]

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            True if this is an Instagram URL with known content type
        """
        if not url or not isinstance(url, str):
            return False

        # Quick check for Instagram domain
        if not is_instagram_url(url):
            return False

        # Validate content type is not UNKNOWN
        content_type = detect_instagram_content_type(url)
        if content_type == InstagramContentType.UNKNOWN:
            # Fall back to parent's check for edge cases
            return await super().can_handle(url)

        return True

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata from an Instagram URL.

        Extends parent metadata extraction with Instagram-specific fields:
        - content_type: 'post', 'reel', or 'story'
        - is_reel: Boolean indicating if content is a Reel
        - is_story: Boolean indicating if content is a Story
        - shortcode: Instagram content identifier
        - username: Content creator's username
        - caption: Post caption/description
        - likes_count: Number of likes
        - comments_count: Number of comments
        - aspect_ratio: '9:16' for Reels

        Args:
            url: The Instagram URL
            options: Download configuration options

        Returns:
            Dictionary containing metadata fields

        Raises:
            URLValidationError: If the URL is invalid
            MetadataExtractionError: If metadata cannot be extracted
        """
        # Get base metadata from parent
        metadata = await super().extract_metadata(url, options)

        # Add Instagram-specific fields
        content_type = detect_instagram_content_type(url)
        metadata["content_type"] = content_type.name.lower()
        metadata["is_reel"] = content_type == InstagramContentType.REEL
        metadata["is_story"] = content_type == InstagramContentType.STORY
        metadata["shortcode"] = extract_shortcode(url)

        # Extract additional fields from yt-dlp info if available
        # Note: _raw_info is not stored by parent, so we re-extract
        correlation_id = self._generate_correlation_id()

        def _extract_instagram_info() -> dict[str, Any]:
            """Extract additional Instagram-specific info."""
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False, process=True)
                    return {
                        "username": info.get("uploader") or info.get("channel"),
                        "caption": info.get("description", ""),
                        "likes_count": info.get("like_count"),
                        "comments_count": info.get("comment_count"),
                        "upload_date": info.get("upload_date"),
                        "view_count": info.get("view_count"),
                    }
            except Exception as e:
                logger.debug(f"Could not extract extended Instagram info: {e}")
                return {}

        # Run extended extraction in thread pool
        try:
            extended_info = await asyncio.to_thread(_extract_instagram_info)
            metadata.update(extended_info)
        except Exception as e:
            logger.debug(f"Extended metadata extraction failed: {e}")

        # For Reels, mark aspect ratio
        if metadata.get("is_reel"):
            metadata["aspect_ratio"] = "9:16"

        # Format caption for display
        if metadata.get("caption"):
            metadata["caption_formatted"] = self._format_caption(
                metadata["caption"], max_length=200
            )

        # Format counts for display
        if metadata.get("likes_count") is not None:
            metadata["likes_formatted"] = self._format_count(metadata["likes_count"])
        if metadata.get("comments_count") is not None:
            metadata["comments_formatted"] = self._format_count(
                metadata["comments_count"]
            )

        return metadata

    def _build_ydl_options(
        self,
        options: DownloadOptions,
        output_path: str,
        correlation_id: str,
    ) -> dict:
        """Build yt-dlp options with Instagram-specific optimizations.

        Args:
            options: Download configuration
            output_path: Output file path template
            correlation_id: Request tracing ID

        Returns:
            Dictionary of yt-dlp options
        """
        ydl_opts = super()._build_ydl_options(options, output_path, correlation_id)

        # Instagram-specific options
        ydl_opts["socket_timeout"] = 30  # Instagram can be slow

        # Add headers to avoid blocks
        ydl_opts["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
        }

        return ydl_opts

    def _download_sync(
        self,
        url: str,
        ydl_opts: dict,
        correlation_id: str,
    ) -> str:
        """Synchronous download wrapper with Instagram error handling.

        Args:
            url: The URL to download
            ydl_opts: yt-dlp options dictionary
            correlation_id: Request tracing ID

        Returns:
            Path to the downloaded file

        Raises:
            DownloadFailedError: If download fails with Instagram-specific messages
        """
        try:
            return super()._download_sync(url, ydl_opts, correlation_id)
        except DownloadFailedError as e:
            # Check for Instagram-specific error conditions
            error_msg = str(e).lower()

            if "private" in error_msg or "403" in error_msg:
                raise DownloadFailedError(
                    attempts_made=1,
                    message="Este contenido de Instagram es privado. "
                            "No puedo acceder a posts privados.",
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            elif "story" in error_msg and (
                "expired" in error_msg or "not available" in error_msg
            ):
                raise DownloadFailedError(
                    attempts_made=1,
                    message="Esta historia de Instagram ha expirado o no está disponible.",
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            elif "rate" in error_msg or "limit" in error_msg:
                raise DownloadFailedError(
                    attempts_made=1,
                    message="Instagram está limitando las solicitudes. "
                            "Intenta de nuevo más tarde.",
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            else:
                # Re-raise with original message
                raise

    def _format_caption(self, caption: str, max_length: int = 200) -> str:
        """Format caption for display, truncating if needed.

        Args:
            caption: The original caption
            max_length: Maximum length before truncation

        Returns:
            Formatted caption string
        """
        if not caption:
            return ""

        # Remove excessive newlines and normalize whitespace
        caption = " ".join(caption.split())

        # Truncate if needed
        if len(caption) > max_length:
            caption = caption[:max_length].rsplit(" ", 1)[0] + "..."

        return caption

    def _format_count(self, count: Optional[int]) -> str:
        """Format count as human-readable string.

        Args:
            count: The numeric count

        Returns:
            Formatted string like "15K", "1.5M", or "500"
        """
        if count is None:
            return "Unknown"

        if count >= 1000000:
            return f"{count / 1000000:.1f}M"
        elif count >= 1000:
            return f"{count / 1000:.1f}K"
        else:
            return str(count)


__all__ = [
    # Main class
    "InstagramDownloader",
    # Enums
    "InstagramContentType",
    # Helper functions
    "detect_instagram_content_type",
    "is_instagram_reel",
    "is_instagram_story",
    "is_instagram_url",
    "extract_shortcode",
    "extract_username_from_url",
    # Patterns
    "INSTAGRAM_PATTERNS",
]
