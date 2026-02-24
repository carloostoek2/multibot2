"""Platform router for automatic downloader selection.

This module provides the PlatformRouter class that routes URLs to the appropriate
downloader based on platform detection. It uses a priority-based routing system:

1. Platform-specific handlers (YouTube, Instagram, TikTok, Twitter/X, Facebook)
2. Generic video URL handler for direct video links
3. yt-dlp fallback for other supported platforms
4. HTML extractor for web pages that might contain videos

Example:
    # Route URL to appropriate downloader
    router = PlatformRouter()
    result = await router.route('https://youtube.com/watch?v=...')

    # Use convenience function
    from bot.downloaders import get_downloader_for_url
    downloader = await get_downloader_for_url(url)
"""
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type
from urllib.parse import urlparse

from .base import BaseDownloader, DownloadOptions
from .exceptions import UnsupportedURLError
from .generic_downloader import GenericDownloader
from .html_extractor import HTMLVideoExtractor, download_from_html
from .url_detector import URLDetector, URLType, classify_url
from .ytdlp_downloader import YtDlpDownloader

# Platform handlers
from .platforms import (
    FacebookDownloader,
    InstagramDownloader,
    TikTokDownloader,
    TwitterDownloader,
    YouTubeDownloader,
    is_facebook_url,
    is_instagram_url,
    is_tiktok_url,
    is_twitter_url,
    is_youtube_url,
)

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Result of routing a URL to a downloader.

    Attributes:
        downloader: The selected downloader instance
        platform: Name of the detected platform
        confidence: Confidence level ('high', 'medium', 'low')
        reason: Explanation of why this downloader was selected
    """

    downloader: BaseDownloader
    platform: str
    confidence: str
    reason: str


class _HTMLExtractorAdapter(BaseDownloader):
    """Adapter to make HTMLVideoExtractor compatible with BaseDownloader."""

    name = "HTML Video Extractor"
    supported_platforms = ["HTML Pages"]

    def __init__(self, generic_downloader: GenericDownloader):
        self._generic = generic_downloader
        self._extractor = HTMLVideoExtractor()

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL."""
        # Can handle if it looks like an HTML page
        return self._looks_like_html_page(url)

    async def extract_metadata(self, url: str, options: DownloadOptions) -> dict:
        """Extract metadata from first video found."""
        videos = await self._extractor.extract_videos(url)
        if videos:
            return {
                "title": "Video from HTML page",
                "videos_found": len(videos),
                "first_video_url": videos[0].url,
                "source": videos[0].source,
            }
        return {"title": "HTML page", "videos_found": 0}

    async def download(self, url: str, options: DownloadOptions) -> Any:
        """Download using the download_from_html function."""
        return await download_from_html(url, options, self._generic)

    def _looks_like_html_page(self, url: str) -> bool:
        """Check if URL looks like an HTML page (not a direct file)."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # No extension suggests HTML page
        if "." not in path.split("/")[-1]:
            return True

        # Common web page extensions
        html_extensions = {".html", ".htm", ".php", ".asp", ".aspx", ".jsp"}
        if any(path.endswith(ext) for ext in html_extensions):
            return True

        return False


class PlatformRouter:
    """Routes URLs to the appropriate downloader.

    Uses a priority-based routing system:
    1. Platform-specific handlers (YouTube, Instagram, etc.)
    2. Generic video URL handler
    3. yt-dlp fallback for other platforms
    4. HTML extractor for web pages

    Example:
        router = PlatformRouter()
        result = await router.route('https://youtube.com/watch?v=...')
        # result.downloader is YouTubeDownloader instance
    """

    def __init__(self):
        self._detector = URLDetector()
        self._downloader_cache: Dict[str, BaseDownloader] = {}

        # Platform checkers in priority order
        self._platform_checks = [
            ("youtube", is_youtube_url, YouTubeDownloader),
            ("instagram", is_instagram_url, InstagramDownloader),
            ("tiktok", is_tiktok_url, TikTokDownloader),
            ("twitter", is_twitter_url, TwitterDownloader),
            ("facebook", is_facebook_url, FacebookDownloader),
        ]

        # Fallback downloaders
        self._generic = GenericDownloader()
        self._ytdlp = YtDlpDownloader()

    async def route(self, url: str) -> RouteResult:
        """Route a URL to the appropriate downloader.

        Args:
            url: The URL to route

        Returns:
            RouteResult with selected downloader

        Raises:
            UnsupportedURLError: If no downloader can handle the URL
        """
        if not url or not isinstance(url, str):
            raise UnsupportedURLError("Invalid URL provided")

        logger.debug(f"Routing URL: {url}")

        # Step 1: Check platform-specific handlers (high confidence)
        for platform_name, check_func, downloader_class in self._platform_checks:
            if check_func(url):
                logger.debug(f"Matched {platform_name} platform")
                downloader = self._get_cached_downloader(platform_name, downloader_class)

                # Verify the downloader can actually handle it
                if await downloader.can_handle(url):
                    return RouteResult(
                        downloader=downloader,
                        platform=platform_name,
                        confidence="high",
                        reason=f"URL matches {platform_name} pattern and downloader confirms support",
                    )
                else:
                    logger.warning(f"{platform_name} matched but can_handle returned False")

        # Step 2: Check for direct video URLs (high confidence)
        url_type = classify_url(url)
        if url_type == URLType.GENERIC_VIDEO:
            if await self._generic.can_handle(url):
                return RouteResult(
                    downloader=self._generic,
                    platform="generic_video",
                    confidence="high",
                    reason="URL is a direct video file link",
                )

        # Step 3: Try yt-dlp for other platforms (medium confidence)
        if await self._ytdlp.can_handle(url):
            # Try to identify the platform from yt-dlp info
            platform = await self._identify_platform(url)
            return RouteResult(
                downloader=self._ytdlp,
                platform=platform or "unknown",
                confidence="medium",
                reason="yt-dlp can handle this URL",
            )

        # Step 4: Check if it's an HTML page that might have videos (low confidence)
        if url_type == URLType.UNKNOWN and self._looks_like_html_page(url):
            return RouteResult(
                downloader=_HTMLExtractorAdapter(self._generic),
                platform="html_page",
                confidence="low",
                reason="URL appears to be an HTML page, will attempt video extraction",
            )

        # No handler found
        raise UnsupportedURLError(
            f"No downloader available for URL: {url}",
            url=url,
        )

    def _get_cached_downloader(
        self,
        platform: str,
        downloader_class: Type[BaseDownloader],
    ) -> BaseDownloader:
        """Get or create a downloader instance (cached)."""
        if platform not in self._downloader_cache:
            self._downloader_cache[platform] = downloader_class()
        return self._downloader_cache[platform]

    async def _identify_platform(self, url: str) -> Optional[str]:
        """Try to identify the platform using yt-dlp metadata."""
        try:
            metadata = await self._ytdlp.extract_metadata(url, DownloadOptions())
            extractor = metadata.get("extractor", "").lower()

            # Map extractor names to platform names
            platform_map = {
                "youtube": "youtube",
                "instagram": "instagram",
                "tiktok": "tiktok",
                "twitter": "twitter",
                "facebook": "facebook",
                "vimeo": "vimeo",
                "dailymotion": "dailymotion",
                "reddit": "reddit",
            }

            for key, value in platform_map.items():
                if key in extractor:
                    return value

            return extractor or "unknown"
        except Exception:
            return None

    def _looks_like_html_page(self, url: str) -> bool:
        """Check if URL looks like an HTML page (not a direct file)."""
        # If URL has no extension or ends with .html/.htm/.php
        parsed = urlparse(url)
        path = parsed.path.lower()

        # No extension suggests HTML page
        if "." not in path.split("/")[-1]:
            return True

        # Common web page extensions
        html_extensions = {".html", ".htm", ".php", ".asp", ".aspx", ".jsp"}
        if any(path.endswith(ext) for ext in html_extensions):
            return True

        return False


async def get_downloader_for_url(url: str) -> Optional[BaseDownloader]:
    """Get the appropriate downloader for a URL.

    Convenience function that creates a router and returns
    just the downloader instance.

    Args:
        url: The URL to get a downloader for

    Returns:
        Downloader instance, or None if no handler available
    """
    router = PlatformRouter()
    try:
        result = await router.route(url)
        return result.downloader
    except UnsupportedURLError:
        return None


async def route_url(url: str) -> RouteResult:
    """Route a URL and return full route result.

    Args:
        url: The URL to route

    Returns:
        RouteResult with downloader and metadata
    """
    router = PlatformRouter()
    return await router.route(url)
