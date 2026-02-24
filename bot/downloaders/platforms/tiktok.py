"""TikTok-specific downloader with watermark-free option and slideshow support.

This module provides the TikTokDownloader class that extends YtDlpDownloader
with TikTok-specific features including:
- Watermark-free video downloads (when available)
- Slideshow detection and handling
- Enhanced metadata extraction (author, stats, music info)
- TikTok ID extraction from various URL formats

Example:
    downloader = TikTokDownloader()

    # Check if URL is a TikTok URL
    if is_tiktok_url(url):
        print("This is a TikTok URL!")

    # Check if it's a slideshow
    metadata = await downloader.extract_metadata(url, options)
    if metadata.get('is_slideshow'):
        print("This is a slideshow!")

    # Download with watermark-free preference
    result = await downloader.download(url, options)
"""
import asyncio
import logging
import re
from typing import Any, Optional

from bot.downloaders.ytdlp_downloader import YtDlpDownloader
from bot.downloaders.base import DownloadOptions
from bot.downloaders.exceptions import (
    DownloadFailedError,
    MetadataExtractionError,
)

logger = logging.getLogger(__name__)

# TikTok URL patterns for validation
TIKTOK_PATTERNS = [
    r'tiktok\.com/@[\w.]+/video/\d+',
    r'tiktok\.com/t/\w+',
    r'vm\.tiktok\.com/\w+',
    r'vt\.tiktok\.com/\w+',
    r'tiktok\.com/\w+/video/\d+',  # Mobile app share URLs
]

# Compiled regex patterns for performance
_TIKTOK_REGEX = re.compile('|'.join(TIKTOK_PATTERNS), re.IGNORECASE)
_TIKTOK_ID_REGEX = re.compile(r'/video/(\d+)')
_TIKTOK_SHORT_ID_REGEX = re.compile(r'/t/(\w+)')


def is_tiktok_url(url: str) -> bool:
    """Check if URL is a TikTok URL.

    Args:
        url: The URL to check

    Returns:
        True if URL matches any TikTok pattern, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    patterns = [
        r'tiktok\.com',
        r'vm\.tiktok\.com',
        r'vt\.tiktok\.com',
    ]
    return any(re.search(p, url.lower()) for p in patterns)


def is_tiktok_slideshow(info: dict) -> bool:
    """Check if TikTok content is a slideshow (multiple images).

    Args:
        info: Metadata dictionary from yt-dlp

    Returns:
        True if content is a slideshow, False otherwise
    """
    if not info:
        return False

    # Slideshows have specific format indicators
    formats = info.get('formats', [])
    # Check for image formats or slideshow indicator
    for fmt in formats:
        if fmt.get('format_id') == 'slideshow':
            return True

    # Alternative: check if video has no video stream but has images
    if info.get('album') is not None:
        return True

    # Check for slideshow in formats string representation
    if 'slideshow' in str(info.get('formats', [])).lower():
        return True

    # Check for image carousel indicator
    if info.get('carousel') or info.get('image_list'):
        return True

    return False


def extract_tiktok_id(url: str) -> Optional[str]:
    """Extract TikTok video ID from URL.

    Args:
        url: The TikTok URL

    Returns:
        Video ID string or None if not found
    """
    if not url:
        return None

    patterns = [
        r'/video/(\d+)',
        r'/t/(\w+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _format_count(count: Optional[int]) -> str:
    """Format count for display.

    Args:
        count: Number to format

    Returns:
        Formatted string like "1.2M", "500K", "1,234"
    """
    if count is None:
        return "Unknown"

    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B"
    elif count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    else:
        return f"{count:,}"


def _is_content_restricted(info: dict) -> tuple[bool, Optional[str]]:
    """Check if TikTok content is restricted.

    Args:
        info: Metadata dictionary from yt-dlp

    Returns:
        Tuple of (is_restricted, reason)
    """
    if not info:
        return False, None

    # Check for region restriction
    availability = info.get('availability', '').lower()
    if 'region' in availability or 'country' in availability:
        return True, "region_restricted"

    # Check for private/removed content
    if availability in ['private', 'subscriber_only']:
        return True, "private_content"

    # Check title for indicators
    title = info.get('title', '').lower()
    if 'not available' in title or 'removed' in title:
        return True, "content_removed"

    return False, None


class TikTokDownloader(YtDlpDownloader):
    """TikTok downloader with watermark-free option and slideshow support.

    Extends YtDlpDownloader with TikTok-specific features:
    - Watermark-free video downloads (best effort)
    - Slideshow detection and handling
    - Enhanced metadata (author, stats, music info)
    - Aspect ratio hint for vertical video (9:16)

    Example:
        downloader = TikTokDownloader()

        # Check if can handle URL
        if await downloader.can_handle(url):
            # Extract enhanced metadata
            metadata = await downloader.extract_metadata(url, options)
            print(f"Author: {metadata.get('author')}")
            print(f"Plays: {metadata.get('stats', {}).get('plays')}")

            # Download with TikTok optimizations
            result = await downloader.download(url, options)
    """

    def __init__(self, prefer_watermark_free: bool = True):
        """Initialize TikTokDownloader.

        Args:
            prefer_watermark_free: Whether to prefer watermark-free versions
        """
        super().__init__()
        self.prefer_watermark_free = prefer_watermark_free

    @property
    def name(self) -> str:
        """Human-readable downloader name."""
        return "TikTok Downloader"

    @property
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader."""
        return ["TikTok"]

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            True if this is a TikTok URL, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Quick check with regex first
        if is_tiktok_url(url):
            return True

        # Fall back to parent class for yt-dlp validation
        return await super().can_handle(url)

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata with TikTok-specific fields.

        Extends base metadata extraction with TikTok-specific fields:
        - tiktok_id: TikTok video ID
        - author: Content creator
        - author_id: Creator's user ID
        - description: Video caption
        - stats: Play count, likes, shares, comments
        - is_slideshow: Whether content is a slideshow
        - music: Music title and author
        - aspect_ratio: Always 9:16 for TikTok

        Args:
            url: The TikTok URL
            options: Download configuration options

        Returns:
            Dictionary with base metadata plus TikTok-specific fields

        Raises:
            URLValidationError: If URL is invalid
            MetadataExtractionError: If metadata cannot be extracted
        """
        # Get base metadata from parent class
        metadata = await super().extract_metadata(url, options)

        # Add TikTok-specific fields
        def _extract_tiktok_info() -> dict[str, Any]:
            """Extract full TikTok info for additional fields."""
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
                logger.warning(f"Could not extract full TikTok info: {e}")
                return {}

        # Run extraction in thread pool
        try:
            info = await asyncio.to_thread(_extract_tiktok_info)
        except Exception as e:
            logger.warning(f"Failed to extract TikTok-specific metadata: {e}")
            info = {}

        # Check for content restrictions
        is_restricted, restriction_reason = _is_content_restricted(info)
        if is_restricted:
            metadata["is_restricted"] = True
            metadata["restriction_reason"] = restriction_reason
        else:
            metadata["is_restricted"] = False

        # Add TikTok ID
        tiktok_id = extract_tiktok_id(url) or info.get('id')
        if tiktok_id:
            metadata["tiktok_id"] = tiktok_id

        # Add author info
        metadata["author"] = info.get('uploader') or info.get('creator')
        metadata["author_id"] = info.get('uploader_id')

        # Add description
        metadata["description"] = info.get('description', '')

        # Add stats
        metadata["stats"] = {
            "plays": info.get('view_count'),
            "likes": info.get('like_count'),
            "shares": info.get('repost_count'),
            "comments": info.get('comment_count'),
        }

        # Format stats for display
        stats = metadata["stats"]
        metadata["stats_formatted"] = {
            "plays": _format_count(stats.get("plays")),
            "likes": _format_count(stats.get("likes")),
            "shares": _format_count(stats.get("shares")),
            "comments": _format_count(stats.get("comments")),
        }

        # Detect slideshow
        metadata["is_slideshow"] = is_tiktok_slideshow(info)

        # Add image count for slideshows
        if metadata["is_slideshow"]:
            metadata["image_count"] = len(info.get('album', [])) or info.get('image_count', 0)

        # Add music info
        metadata["music"] = {
            "title": info.get('track'),
            "author": info.get('artist'),
        }

        # TikTok is always 9:16 vertical format
        metadata["aspect_ratio"] = "9:16"
        metadata["orientation"] = "vertical"

        return metadata

    def _build_ydl_options(
        self,
        options: DownloadOptions,
        output_path: str,
        correlation_id: str,
    ) -> dict:
        """Build yt-dlp options with TikTok optimizations.

        Args:
            options: Download configuration
            output_path: Output file path template
            correlation_id: Request tracing ID

        Returns:
            Dictionary of yt-dlp options
        """
        # Get base options from parent
        ydl_opts = super()._build_ydl_options(options, output_path, correlation_id)

        # TikTok-specific options for watermark-free
        if self.prefer_watermark_free:
            # Use format that prefers watermark-free versions
            # Note: yt-dlp may not always be able to remove watermarks
            # This is a best-effort approach
            ydl_opts['format'] = 'best[format_id!*=watermark]/best'

        # Add extractor args for TikTok
        ydl_opts['extractor_args'] = {
            'tiktok': {
                'api_hostname': 'api16-normal-c-useast1a.tiktokv.com',
                'app_version': '20.9.3',
            }
        }

        return ydl_opts

    async def download_slideshow(
        self,
        url: str,
        options: DownloadOptions,
    ) -> Any:
        """Download TikTok slideshow as video or images.

        For slideshows, we can either:
        1. Download all images and let user choose
        2. Convert to video (requires ffmpeg)

        For now, extract image URLs and return metadata.

        Args:
            url: The TikTok slideshow URL
            options: Download configuration options

        Returns:
            DownloadResult with slideshow information

        Raises:
            ValueError: If URL is not a slideshow
        """
        metadata = await self.extract_metadata(url, options)

        if not metadata.get('is_slideshow'):
            raise ValueError("URL is not a TikTok slideshow")

        # Slideshow handling - return info about images
        # Full implementation would download images or convert to video
        from .. import DownloadResult

        return DownloadResult(
            success=True,
            file_path=None,  # Would be populated with actual path
            metadata={
                'is_slideshow': True,
                'message': 'Slideshow detected. Image download not yet implemented.',
                'image_count': metadata.get('image_count', 0),
            }
        )

    async def download(
        self,
        url: str,
        options: DownloadOptions,
    ) -> Any:
        """Download content with TikTok-specific handling.

        Extends base download with:
        - Region-restricted content detection
        - Better error messages for restricted content
        - Slideshow-specific handling

        Args:
            url: The TikTok URL to download
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

        # Check for content restrictions
        if metadata.get("is_restricted"):
            restriction_reason = metadata.get("restriction_reason")
            logger.warning(
                f"Attempting to download restricted content ({restriction_reason}): {url}"
            )

        # Check if it's a slideshow
        if metadata.get("is_slideshow"):
            logger.info(f"TikTok slideshow detected: {url}")
            # For now, return the slideshow info
            # Full implementation would download images
            return await self.download_slideshow(url, options)

        # Perform the download
        try:
            result = await super().download(url, options)
            return result

        except DownloadFailedError as e:
            # Check for TikTok-specific error conditions
            error_msg = str(e).lower()

            if "not available" in error_msg or "removed" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "Este video de TikTok no está disponible. "
                        "Puede haber sido eliminado o ser privado."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            elif "region" in error_msg or "country" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "Este contenido de TikTok no está disponible en tu región."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            elif "rate" in error_msg or "limit" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "TikTok está limitando las solicitudes. "
                        "Intenta de nuevo más tarde."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            raise


__all__ = [
    # Main class
    "TikTokDownloader",
    # Helper functions
    "is_tiktok_url",
    "is_tiktok_slideshow",
    "extract_tiktok_id",
    # Patterns
    "TIKTOK_PATTERNS",
]
