"""Twitter/X-specific downloader with quality selection and tweet metadata.

This module provides the TwitterDownloader class that extends YtDlpDownloader
with Twitter/X-specific features including:
- Tweet metadata extraction (text, author, engagement stats)
- Video quality variant selection
- GIF detection
- Support for both twitter.com and x.com domains

Example:
    downloader = TwitterDownloader()

    # Check if URL is a Twitter/X URL
    if is_twitter_url(url):
        print("This is a Twitter/X URL!")

    # Extract metadata with engagement stats
    metadata = await downloader.extract_metadata(url, options)
    print(f"Tweet: {metadata.get('tweet_text')}")
    print(f"Likes: {metadata.get('engagement', {}).get('likes')}")

    # Download with quality selection
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

# Twitter/X URL patterns for validation
TWITTER_PATTERNS = [
    r'twitter\.com/\w+/status/\d+',
    r'x\.com/\w+/status/\d+',
    r'twitter\.com/i/spaces/\d+',  # Spaces (audio only)
]

# Compiled regex patterns for performance
_TWITTER_REGEX = re.compile('|'.join(TWITTER_PATTERNS), re.IGNORECASE)
_TWEET_ID_REGEX = re.compile(r'/status/(\d+)')
_USERNAME_REGEX = re.compile(r'(?:twitter|x)\.com/(\w+)/status/')


def is_twitter_url(url: str) -> bool:
    """Check if URL is a Twitter/X URL.

    Args:
        url: The URL to check

    Returns:
        True if URL matches Twitter/X patterns, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    patterns = [
        r'twitter\.com',
        r'x\.com',
    ]
    return any(re.search(p, url.lower()) for p in patterns)


def extract_tweet_id(url: str) -> Optional[str]:
    """Extract tweet ID from URL.

    Args:
        url: The Twitter/X URL

    Returns:
        Tweet ID string or None if not found
    """
    if not url:
        return None

    match = re.search(r'/status/(\d+)', url)
    if match:
        return match.group(1)
    return None


def extract_username(url: str) -> Optional[str]:
    """Extract username from Twitter URL.

    Args:
        url: The Twitter/X URL

    Returns:
        Username string or None if not found
    """
    if not url:
        return None

    match = re.search(r'(?:twitter|x)\.com/(\w+)/status/', url.lower())
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


def _is_tweet_restricted(info: dict) -> tuple[bool, Optional[str]]:
    """Check if tweet content is restricted.

    Args:
        info: Metadata dictionary from yt-dlp

    Returns:
        Tuple of (is_restricted, reason)
    """
    if not info:
        return False, None

    # Check for age restriction
    age_limit = info.get('age_limit', 0)
    if age_limit and age_limit >= 18:
        return True, "age_restricted"

    # Check availability
    availability = info.get('availability', '').lower()
    if availability == 'needs_auth':
        return True, "private_account"

    # Check title/description for restriction indicators
    title = info.get('title', '').lower()
    if 'suspended' in title:
        return True, "account_suspended"
    if 'not found' in title or 'deleted' in title:
        return True, "tweet_deleted"

    return False, None


class TwitterDownloader(YtDlpDownloader):
    """Twitter/X video downloader with quality selection.

    Extends YtDlpDownloader with Twitter/X-specific features:
    - Tweet metadata extraction (text, author, engagement)
    - Video quality variant selection
    - GIF detection
    - Support for twitter.com and x.com domains

    Example:
        downloader = TwitterDownloader()

        # Check if can handle URL
        if await downloader.can_handle(url):
            # Extract enhanced metadata
            metadata = await downloader.extract_metadata(url, options)
            print(f"Tweet: {metadata.get('tweet_text')}")
            print(f"Engagement: {metadata.get('engagement')}")

            # Download with Twitter optimizations
            result = await downloader.download(url, options)
    """

    @property
    def name(self) -> str:
        """Human-readable downloader name."""
        return "Twitter/X Downloader"

    @property
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader."""
        return ["Twitter", "X"]

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            True if this is a Twitter/X URL with /status/, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        # Quick check for Twitter/X domain
        if not is_twitter_url(url):
            return False

        # Check that URL contains /status/ (tweet URL)
        if '/status/' not in url:
            # Fall back to parent's check for edge cases (Spaces, etc.)
            return await super().can_handle(url)

        return True

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata with Twitter/X-specific fields.

        Extends base metadata extraction with Twitter/X-specific fields:
        - tweet_id: Tweet ID
        - username: Tweet author's username
        - display_name: Author's display name
        - tweet_text: Tweet content text
        - created_at: Tweet timestamp
        - engagement: Replies, retweets, likes, views
        - video_variants: Available quality options
        - has_video: Whether tweet contains video
        - is_gif: Whether content is a GIF

        Args:
            url: The Twitter/X URL
            options: Download configuration options

        Returns:
            Dictionary with base metadata plus Twitter/X-specific fields

        Raises:
            URLValidationError: If URL is invalid
            MetadataExtractionError: If metadata cannot be extracted
        """
        # Get base metadata from parent class
        metadata = await super().extract_metadata(url, options)

        # Add Twitter/X-specific fields
        def _extract_twitter_info() -> dict[str, Any]:
            """Extract full Twitter/X info for additional fields."""
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
                logger.warning(f"Could not extract full Twitter/X info: {e}")
                return {}

        # Run extraction in thread pool
        try:
            info = await asyncio.to_thread(_extract_twitter_info)
        except Exception as e:
            logger.warning(f"Failed to extract Twitter/X-specific metadata: {e}")
            info = {}

        # Check for content restrictions
        is_restricted, restriction_reason = _is_tweet_restricted(info)
        if is_restricted:
            metadata["is_restricted"] = True
            metadata["restriction_reason"] = restriction_reason
        else:
            metadata["is_restricted"] = False

        # Add tweet ID
        tweet_id = extract_tweet_id(url) or info.get('id')
        if tweet_id:
            metadata["tweet_id"] = tweet_id

        # Add username
        username = extract_username(url) or info.get('uploader')
        if username:
            metadata["username"] = username

        # Add display name
        metadata["display_name"] = info.get('uploader')

        # Add tweet text
        metadata["tweet_text"] = info.get('description', '')

        # Add creation timestamp
        metadata["created_at"] = info.get('timestamp')

        # Add engagement stats
        metadata["engagement"] = {
            "replies": info.get('comment_count'),
            "retweets": info.get('repost_count'),
            "likes": info.get('like_count'),
            "views": info.get('view_count'),
        }

        # Format engagement for display
        engagement = metadata["engagement"]
        metadata["engagement_formatted"] = {
            "replies": _format_count(engagement.get("replies")),
            "retweets": _format_count(engagement.get("retweets")),
            "likes": _format_count(engagement.get("likes")),
            "views": _format_count(engagement.get("views")),
        }

        # Extract video variants (quality options)
        formats = info.get('formats', [])
        video_formats = [f for f in formats if f.get('vcodec') != 'none']

        metadata["video_variants"] = [
            {
                "format_id": f.get('format_id'),
                "resolution": f.get('resolution'),
                "filesize": f.get('filesize'),
                "bitrate": f.get('tbr'),
            }
            for f in sorted(
                video_formats,
                key=lambda x: x.get('height', 0) or 0,
                reverse=True
            )
        ]

        # Check if has video
        metadata["has_video"] = len(video_formats) > 0

        # Check if it's a GIF
        metadata["is_gif"] = 'gif' in str(info.get('formats', [])).lower()

        return metadata

    def select_best_variant(
        self,
        variants: list[dict],
        max_size: int,
    ) -> Optional[str]:
        """Select best video variant under size limit.

        Args:
            variants: List of video variant dicts
            max_size: Maximum file size in bytes

        Returns:
            format_id of best variant, or None
        """
        for variant in variants:
            filesize = variant.get('filesize', 0) or 0
            if filesize and filesize <= max_size:
                return variant['format_id']

        # If no size info or all too large, return highest quality
        return variants[0]['format_id'] if variants else None

    def _build_ydl_options(
        self,
        options: DownloadOptions,
        output_path: str,
        correlation_id: str,
    ) -> dict:
        """Build yt-dlp options with Twitter/X optimizations.

        Args:
            options: Download configuration
            output_path: Output file path template
            correlation_id: Request tracing ID

        Returns:
            Dictionary of yt-dlp options
        """
        ydl_opts = super()._build_ydl_options(options, output_path, correlation_id)

        # Twitter-specific: prefer MP4 format
        ydl_opts['format'] = 'best[ext=mp4]/best'

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

    async def download(
        self,
        url: str,
        options: DownloadOptions,
    ) -> Any:
        """Download content with Twitter/X-specific handling.

        Extends base download with:
        - Age-restricted content detection
        - Better error messages for restricted content
        - Private account handling

        Args:
            url: The Twitter/X URL to download
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

        # Check if tweet has video
        if metadata.get("has_video") is False:
            logger.warning(f"Tweet appears to have no video: {url}")

        # Perform the download
        try:
            result = await super().download(url, options)
            return result

        except DownloadFailedError as e:
            # Check for Twitter/X-specific error conditions
            error_msg = str(e).lower()

            if "not found" in error_msg or "deleted" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "Este tweet no existe o ha sido eliminado."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            elif "suspended" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "La cuenta de Twitter/X está suspendida."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            elif "age" in error_msg or "restrict" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "Este contenido tiene restricción de edad y no puede ser "
                        "descargado sin autenticación."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            elif "private" in error_msg or "403" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "Este tweet es de una cuenta privada. "
                        "No puedo acceder a contenido privado."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            elif "rate" in error_msg or "limit" in error_msg:
                raise DownloadFailedError(
                    attempts_made=e.attempts_made,
                    last_error=e.last_error,
                    message=(
                        "Twitter/X está limitando las solicitudes. "
                        "Intenta de nuevo más tarde."
                    ),
                    url=url,
                    correlation_id=getattr(e, "correlation_id", None),
                ) from e
            raise


__all__ = [
    # Main class
    "TwitterDownloader",
    # Helper functions
    "is_twitter_url",
    "extract_tweet_id",
    "extract_username",
    # Patterns
    "TWITTER_PATTERNS",
]
