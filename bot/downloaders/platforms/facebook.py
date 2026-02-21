"""Facebook-specific downloader for videos and Reels.

This module provides the FacebookDownloader class for downloading content
from Facebook with proper content type detection (videos, Reels) and
enhanced metadata extraction including page name, engagement stats, and
aspect ratio hints.

Example:
    downloader = FacebookDownloader()

    # Check if URL is a Facebook Reel
    if is_facebook_reel(url):
        result = await downloader.download(url, options)

    # Get video metadata
    metadata = await downloader.extract_metadata(url, options)
    print(f"Page: {metadata.get('page_name')}")
    print(f"Reactions: {metadata.get('engagement', {}).get('reactions')}")
"""
import asyncio
import logging
import re
from typing import Any, Optional

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from ..base import DownloadOptions
from ..exceptions import DownloadFailedError, MetadataExtractionError
from ..ytdlp_downloader import YtDlpDownloader

logger = logging.getLogger(__name__)


# Facebook URL patterns for validation
FACEBOOK_PATTERNS = {
    "video": [
        r"facebook\.com/watch\?v=\d+",
        r"facebook\.com/\w+/videos/\d+",
        r"facebook\.com/video\.php\?v=\d+",
        r"fb\.watch/\w+",
    ],
    "reel": [
        r"facebook\.com/reel/\d+",
        r"facebook\.com/\w+/reels/\d+",
    ],
}


def is_facebook_url(url: str) -> bool:
    """Check if URL is a Facebook URL.

    Args:
        url: The URL to check

    Returns:
        True if the URL is from facebook.com or fb.watch
    """
    patterns = [
        r"facebook\.com",
        r"fb\.watch",
    ]
    return any(re.search(p, url.lower()) for p in patterns)


def is_facebook_reel(url: str) -> bool:
    """Check if URL is a Facebook Reel.

    Args:
        url: The URL to check

    Returns:
        True if the URL is a Facebook Reel
    """
    return "/reel/" in url.lower() or "/reels/" in url.lower()


def is_facebook_watch(url: str) -> bool:
    """Check if URL is a Facebook Watch video.

    Args:
        url: The URL to check

    Returns:
        True if the URL is a Facebook Watch video
    """
    return "/watch" in url.lower() or "/videos/" in url.lower()


def extract_facebook_video_id(url: str) -> Optional[str]:
    """Extract Facebook video ID from URL.

    Args:
        url: The Facebook URL

    Returns:
        The video ID string or None if not found
    """
    patterns = [
        r"[?&]v=(\d+)",
        r"/videos/(\d+)",
        r"/reel/(\d+)",
        r"/reels/(\d+)",
        r"fb\.watch/(\w+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


class FacebookDownloader(YtDlpDownloader):
    """Facebook video and Reels downloader.

    Extends YtDlpDownloader with Facebook-specific features:
    - Content type detection (video, Reel)
    - Enhanced metadata extraction (page_name, engagement stats)
    - Aspect ratio hints (16:9 for videos, 9:16 for Reels)
    - Spanish error messages for private/unavailable content

    Example:
        downloader = FacebookDownloader()

        # Check if can handle URL
        if await downloader.can_handle(url):
            metadata = await downloader.extract_metadata(url, options)
            print(f"Page: {metadata.get('page_name')}")
            print(f"Reactions: {metadata.get('engagement', {}).get('reactions')}")

            result = await downloader.download(url, options)
    """

    @property
    def name(self) -> str:
        """Human-readable downloader name."""
        return "Facebook Downloader"

    @property
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader."""
        return ["Facebook", "Facebook Reels"]

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            True if this is a Facebook URL
        """
        if not url or not isinstance(url, str):
            return False

        # Quick check for Facebook domain
        if not is_facebook_url(url):
            return False

        # Validate with parent's check for edge cases
        return await super().can_handle(url)

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata from a Facebook URL.

        Extends parent metadata extraction with Facebook-specific fields:
        - video_id: Facebook video identifier
        - is_reel: Boolean indicating if content is a Reel
        - is_watch: Boolean indicating if content is a Watch video
        - page_name: Name of the Facebook page
        - description: Video description
        - engagement: Dict with reactions, comments, shares
        - aspect_ratio: '9:16' for Reels, '16:9' for regular videos

        Args:
            url: The Facebook URL
            options: Download configuration options

        Returns:
            Dictionary containing metadata fields

        Raises:
            URLValidationError: If the URL is invalid
            MetadataExtractionError: If metadata cannot be extracted
        """
        # Get base metadata from parent
        metadata = await super().extract_metadata(url, options)

        # Add Facebook-specific fields
        metadata["video_id"] = extract_facebook_video_id(url)
        metadata["is_reel"] = is_facebook_reel(url)
        metadata["is_watch"] = is_facebook_watch(url)

        # Extract additional fields from yt-dlp info if available
        correlation_id = self._generate_correlation_id()

        def _extract_facebook_info() -> dict[str, Any]:
            """Extract additional Facebook-specific info."""
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False, process=True)

                    if not info:
                        return {}

                    return {
                        "uploader": info.get("uploader"),
                        "page_name": info.get("uploader"),
                        "description": info.get("description", ""),
                        "engagement": {
                            "reactions": info.get("like_count"),
                            "comments": info.get("comment_count"),
                            "shares": info.get("repost_count"),
                        },
                    }
            except Exception as e:
                logger.debug(f"Could not extract extended Facebook info: {e}")
                return {}

        # Run extended extraction in thread pool
        try:
            extended_info = await asyncio.to_thread(_extract_facebook_info)
            metadata.update(extended_info)
        except Exception as e:
            logger.debug(f"Extended metadata extraction failed: {e}")

        # Set aspect ratio based on content type
        if metadata.get("is_reel"):
            metadata["aspect_ratio"] = "9:16"
        else:
            metadata["aspect_ratio"] = "16:9"

        return metadata

    def _build_ydl_options(
        self,
        options: DownloadOptions,
        output_path: str,
        correlation_id: str,
    ) -> dict:
        """Build yt-dlp options with Facebook-specific optimizations.

        Args:
            options: Download configuration
            output_path: Output file path template
            correlation_id: Request tracing ID

        Returns:
            Dictionary of yt-dlp options
        """
        ydl_opts = super()._build_ydl_options(options, output_path, correlation_id)

        # Facebook-specific options
        # Allow unplayable formats (Facebook sometimes marks videos this way)
        ydl_opts["allow_unplayable_formats"] = False

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
        }

        return ydl_opts

    def _download_sync(
        self,
        url: str,
        ydl_opts: dict,
        correlation_id: str,
    ) -> str:
        """Synchronous download wrapper with Facebook error handling.

        Args:
            url: The URL to download
            ydl_opts: yt-dlp options dictionary
            correlation_id: Request tracing ID

        Returns:
            Path to the downloaded file

        Raises:
            DownloadFailedError: If download fails with Facebook-specific messages
        """
        try:
            return super()._download_sync(url, ydl_opts, correlation_id)
        except DownloadFailedError as e:
            # Check for Facebook-specific error conditions
            error_msg = str(e).lower()

            if "private" in error_msg or "403" in error_msg:
                raise DownloadFailedError(
                    attempts_made=1,
                    message=(
                        "Este video de Facebook es privado. "
                        "Solo puedo descargar videos públicos."
                    ),
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            elif (
                "unavailable" in error_msg
                or "not found" in error_msg
                or "404" in error_msg
            ):
                raise DownloadFailedError(
                    attempts_made=1,
                    message="Este video no está disponible o ha sido eliminado.",
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            elif "login" in error_msg or "sign in" in error_msg:
                raise DownloadFailedError(
                    attempts_made=1,
                    message=(
                        "Este video requiere inicio de sesión. "
                        "No puedo acceder a contenido privado."
                    ),
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            else:
                # Re-raise with original message
                raise


__all__ = [
    # Main class
    "FacebookDownloader",
    # Helper functions
    "is_facebook_url",
    "is_facebook_reel",
    "is_facebook_watch",
    "extract_facebook_video_id",
    # Patterns
    "FACEBOOK_PATTERNS",
]
