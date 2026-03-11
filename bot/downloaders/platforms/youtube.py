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

import yt_dlp

from bot.downloaders.ytdlp_downloader import YtDlpDownloader
from bot.downloaders.base import DownloadOptions
from bot.downloaders.exceptions import (
    DownloadFailedError,
    MetadataExtractionError,
)

# TYPE_CHECKING import to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bot.downloaders.types import DownloadResult

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
    """YouTube-specific downloader with Shorts support and client fallback.

    Extends YtDlpDownloader with YouTube-specific features:
    - Shorts detection and vertical format optimization
    - Enhanced metadata (view count, likes, upload date, tags)
    - Age-restricted content handling
    - Multi-strategy client fallback for reliability
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

    # Multi-strategy fallback for YouTube downloads
    # Each strategy tries different player clients, user agents, and configurations
    # to work around YouTube's anti-bot protection
    # Docs: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#using-client-identity
    _CLIENT_STRATEGIES = [
        {
            "name": "ios_no_auth",
            "player_client": ["ios", "mweb"],
            "use_cookies": False,
            "format": "best[height<=1080]/best",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            "referer": "https://m.youtube.com/",
        },
        {
            "name": "ios_with_auth",
            "player_client": ["ios", "mweb"],
            "use_cookies": True,
            "format": "best[height<=1080]/best",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
            "referer": "https://m.youtube.com/",
        },
        {
            "name": "android",
            "player_client": ["android", "web"],
            "use_cookies": False,
            "format": "best[height<=720]/best",
            "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "referer": "https://m.youtube.com/",
        },
        {
            "name": "android_with_auth",
            "player_client": ["android", "web"],
            "use_cookies": True,
            "format": "best[height<=720]/best",
            "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "referer": "https://m.youtube.com/",
        },
        {
            "name": "tv_embedded",
            "player_client": ["tv_embedded"],
            "use_cookies": False,
            "format": "best[height<=1080]/best",
            "user_agent": "Mozilla/5.0 (SmartHub; SMART-TV; U; Linux/SmartTV; Android 11.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 TV Safari/537.36",
            "referer": "https://www.youtube.com/tv",
        },
    ]

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

    async def _extract_with_strategy(
        self,
        url: str,
        options: DownloadOptions,
        strategy: dict,
    ) -> dict[str, Any]:
        """Extract metadata using a specific client strategy.

        Args:
            url: The YouTube URL
            options: Download configuration options
            strategy: Client strategy configuration

        Returns:
            Metadata dictionary

        Raises:
            MetadataExtractionError: If extraction fails
        """
        from bot.config import config
        import os

        correlation_id = self._generate_correlation_id()
        logger.info(f"[{correlation_id}] Trying strategy: {strategy['name']}")

        def _extract() -> dict[str, Any]:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": strategy["format"],
                # Anti-bot: Headers de navegador real
                "http_headers": {
                    "User-Agent": strategy.get("user_agent", "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36"),
                    "Referer": strategy.get("referer", "https://www.youtube.com/"),
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                "extractor_args": {
                    "youtube": {
                        "player_client": strategy["player_client"],
                        "skip": ["unavailable"],
                    }
                },
                # Retries para mayor resiliencia
                "retries": 5,
                "fragment_retries": 5,
                "file_access_retries": 3,
            }

            # Add cookies if strategy requires them
            if strategy.get("use_cookies") and config.COOKIES_FILE:
                if os.path.exists(config.COOKIES_FILE):
                    file_size = os.path.getsize(config.COOKIES_FILE)
                    if file_size > 0:
                        ydl_opts["cookiefile"] = config.COOKIES_FILE
                        logger.info(f"[{correlation_id}] Using cookies with strategy {strategy['name']}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False, process=True)
                    if not info:
                        raise MetadataExtractionError(
                            message="No metadata returned",
                            url=url,
                            correlation_id=correlation_id,
                        )
                    return info
            except Exception as e:
                logger.warning(f"[{correlation_id}] Strategy {strategy['name']} failed: {e}")
                raise

        return await asyncio.to_thread(_extract)

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata with YouTube-specific fields and client fallback.

        Extends base metadata extraction with YouTube-specific fields:
        - view_count: Number of views
        - like_count: Number of likes (if available)
        - upload_date: Video upload date (ISO format)
        - tags: Video tags
        - categories: Video categories
        - is_shorts: Boolean indicating if it's a Short
        - aspect_ratio: For Shorts, hints at 9:16 format
        - view_count_formatted: Human-readable view count

        Implements multi-strategy fallback to handle YouTube's anti-bot protection.

        Args:
            url: The YouTube URL
            options: Download configuration options

        Returns:
            Dictionary with base metadata plus YouTube-specific fields

        Raises:
            URLValidationError: If URL is invalid
            MetadataExtractionError: If metadata cannot be extracted with any strategy
        """
        # Try each client strategy in order
        last_error = None
        for strategy in self._CLIENT_STRATEGIES:
            try:
                info = await self._extract_with_strategy(url, options, strategy)
                logger.info(f"Strategy {strategy['name']} succeeded for {url}")

                # Build metadata from successful extraction
                metadata = self._build_metadata_from_info(info, url)
                metadata["_strategy_used"] = strategy["name"]  # Track which strategy worked
                return metadata

            except Exception as e:
                last_error = e
                logger.warning(f"Strategy {strategy['name']} failed: {e}")
                continue

        # All strategies failed
        raise MetadataExtractionError(
            message=f"All client strategies failed. Last error: {last_error}",
            url=url,
            correlation_id=self._generate_correlation_id(),
        )

    def _build_metadata_from_info(self, info: dict, url: str) -> dict[str, Any]:
        """Build metadata dictionary from yt-dlp info.

        Args:
            info: yt-dlp info dictionary
            url: Original URL

        Returns:
            Metadata dictionary
        """
        metadata = {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader") or info.get("channel"),
            "thumbnail": info.get("thumbnail"),
            "filesize": info.get("filesize") or info.get("filesize_approx"),
            "formats": info.get("formats", []),
            "description": self._truncate_description(info.get("description", "")),
            "webpage_url": info.get("webpage_url", url),
            "id": info.get("id"),
            "extractor": info.get("extractor"),
        }

        # Add YouTube-specific fields directly from info (no second extraction)
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
                # Use 'android' player client - works with cookies and doesn't require
                # JavaScript runtime (Node.js) for signature deciphering
                # Other clients like 'web' or 'ios' may require JS which causes
                # "Requested format is not available" errors in environments without Node.js
                "player_client": ["android"],
            }
        }

        # Anti-bot: Headers de navegador móvil Android (consistente con estrategia android)
        ydl_opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": "https://www.youtube.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
        """Download content with YouTube-specific handling and client fallback.

        Extends base download with:
        - Age-restricted content detection
        - Better error messages for restricted content
        - Shorts-specific handling
        - Multi-strategy client fallback for reliability

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
        from bot.config import config
        from bot.downloaders import DownloadResult
        import os

        # First extract metadata to check for restrictions
        try:
            metadata = await self.extract_metadata(url, options)
        except MetadataExtractionError:
            metadata = {}

        # Check for age restriction
        if metadata.get("is_age_restricted"):
            logger.warning(
                f"Attempting to download age-restricted content: {url}"
            )

        # Try each client strategy
        last_error = None
        correlation_id = self._generate_correlation_id()

        for strategy in self._CLIENT_STRATEGIES:
            try:
                logger.info(
                    f"[{correlation_id}] Download attempt with strategy: {strategy['name']}"
                )

                result = await self._download_with_strategy(
                    url, options, strategy, correlation_id
                )

                logger.info(
                    f"[{correlation_id}] Download succeeded with strategy: {strategy['name']}"
                )
                return result

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Check for specific error types
                if "age" in error_msg or "restrict" in error_msg:
                    logger.warning(f"Age restriction with strategy {strategy['name']}")
                    # Continue to next strategy - some may handle age restrictions
                elif "format" in error_msg and "not available" in error_msg:
                    logger.warning(f"Format not available with strategy {strategy['name']}")
                    # This is expected with some clients, continue
                else:
                    logger.warning(f"Strategy {strategy['name']} failed: {e}")

                continue

        # All strategies failed
        error_msg = str(last_error).lower() if last_error else ""
        if "age" in error_msg or "restrict" in error_msg or "sign in" in error_msg:
            raise DownloadFailedError(
                attempts_made=len(self._CLIENT_STRATEGIES),
                last_error=last_error,
                message=(
                    "Este video tiene restricción de edad y no puede ser "
                    "descargado sin autenticación."
                ),
                url=url,
                correlation_id=correlation_id,
            )

        raise DownloadFailedError(
            attempts_made=len(self._CLIENT_STRATEGIES),
            last_error=last_error,
            message=f"All download strategies failed. Last error: {last_error}",
            url=url,
            correlation_id=correlation_id,
        )

    async def _download_with_strategy(
        self,
        url: str,
        options: DownloadOptions,
        strategy: dict,
        correlation_id: str,
    ) -> "DownloadResult":
        """Download using a specific client strategy.

        Args:
            url: The YouTube URL
            options: Download configuration
            strategy: Client strategy configuration
            correlation_id: Request tracing ID

        Returns:
            DownloadResult

        Raises:
            Exception: If download fails
        """
        from bot.config import config
        import os

        output_path = self._build_output_path(options, "download")

        # Build yt-dlp options with strategy
        ydl_opts = {
            "format": strategy["format"],
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            # Anti-bot: Headers de navegador real
            "http_headers": {
                "User-Agent": strategy.get("user_agent", "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36"),
                "Referer": strategy.get("referer", "https://www.youtube.com/"),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": strategy["player_client"],
                    "skip": ["unavailable"],
                }
            },
        }

        # Add progress hook if callback provided
        if options.progress_callback:
            ydl_opts["progress_hooks"] = [
                self._create_progress_hook(options.progress_callback, correlation_id)
            ]

        # Add audio extraction postprocessor if requested
        if options.extract_audio:
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": options.audio_codec,
                    "preferredquality": options.audio_bitrate.replace("k", ""),
                }
            ]
            ydl_opts["format"] = options.audio_format

        # Add cookies if strategy requires them
        if strategy.get("use_cookies") and config.COOKIES_FILE:
            if os.path.exists(config.COOKIES_FILE):
                file_size = os.path.getsize(config.COOKIES_FILE)
                if file_size > 0:
                    ydl_opts["cookiefile"] = config.COOKIES_FILE
                    logger.info(f"[{correlation_id}] Using cookies with strategy {strategy['name']}")

        # Run download in thread pool
        def _download_sync():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise Exception("No info returned from download")

                filepath = ydl.prepare_filename(info)

                # Handle audio extraction extension change
                if ydl_opts.get("postprocessors"):
                    for pp in ydl_opts["postprocessors"]:
                        if pp.get("key") == "FFmpegExtractAudio":
                            codec = pp.get("preferredcodec", "mp3")
                            filepath = os.path.splitext(filepath)[0] + f".{codec}"

                # Verify file exists
                if not os.path.exists(filepath):
                    base_path = os.path.splitext(filepath)[0]
                    for ext in [".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".ogg"]:
                        alt_path = base_path + ext
                        if os.path.exists(alt_path):
                            filepath = alt_path
                            break

                if not os.path.exists(filepath):
                    raise Exception(f"Downloaded file not found: {filepath}")

                return filepath, info

        filepath, info = await asyncio.to_thread(_download_sync)

        # Import here to avoid circular imports
        from bot.downloaders import DownloadResult

        return DownloadResult(
            success=True,
            file_path=filepath,
            metadata={
                "title": info.get("title"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "strategy_used": strategy["name"],
            },
        )
