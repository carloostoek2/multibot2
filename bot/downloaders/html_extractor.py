"""Generic HTML video extractor for parsing video URLs from web pages.

This module provides the HTMLVideoExtractor class that can parse HTML pages
and extract video URLs from various sources including:
- HTML5 <video> tags (src and <source> children)
- Open Graph meta tags (og:video)
- Twitter Card meta tags
- JSON-LD structured data
- Common video player embeds

Example:
    # Extract videos from an HTML page
    async with HTMLVideoExtractor() as extractor:
        videos = await extractor.extract_videos("https://example.com/page")
        for video in videos:
            print(f"Found: {video.url} (source: {video.source})")

    # Or use the convenience function
    videos = await extract_videos_from_html("https://example.com/page")
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp

logger = logging.getLogger(__name__)

# Optional BeautifulSoup import
try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None  # type: ignore


@dataclass
class VideoURL:
    """Represents a video URL found in HTML.

    Attributes:
        url: The video URL
        source: Where the URL was found (e.g., 'video_tag', 'meta_tag')
        quality: Quality label if available (e.g., '720p', '1080p')
        mime_type: MIME type if available
        label: Human-readable label if available
    """

    url: str
    source: str  # 'video_tag', 'meta_tag', 'og_tag', 'json_ld', etc.
    quality: Optional[str] = None
    mime_type: Optional[str] = None
    label: Optional[str] = None


class HTMLVideoExtractor:
    """Extract video URLs from HTML pages.

    Supports extraction from:
    - <video> tags (src and <source> children)
    - Open Graph meta tags (og:video)
    - Twitter Card meta tags
    - JSON-LD structured data
    - Common video player embeds (if detectable)

    Example:
        async with HTMLVideoExtractor() as extractor:
            videos = await extractor.extract_videos("https://example.com/page")
            if videos:
                print(f"Found {len(videos)} videos")
                for v in videos:
                    print(f"  - {v.url} ({v.source})")
    """

    def __init__(self):
        """Initialize the HTMLVideoExtractor."""
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

    async def extract_videos(self, url: str) -> List[VideoURL]:
        """Extract all video URLs from an HTML page.

        Args:
            url: The URL of the HTML page to parse

        Returns:
            List of VideoURL objects found on the page
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                html = await response.text()
                base_url = str(response.url)
        except Exception as e:
            logger.error(f"Failed to fetch HTML: {e}")
            return []

        videos = []

        if HAS_BS4:
            videos.extend(self._extract_from_video_tags(html, base_url))
            videos.extend(self._extract_from_meta_tags(html, base_url))
            videos.extend(self._extract_from_json_ld(html, base_url))
        else:
            # Fallback to regex if BeautifulSoup not available
            logger.debug("BeautifulSoup not available, using regex fallback")
            videos.extend(self._extract_with_regex(html, base_url))

        # Deduplicate by URL
        seen = set()
        unique_videos = []
        for v in videos:
            if v.url not in seen:
                seen.add(v.url)
                unique_videos.append(v)

        return unique_videos

    def _extract_from_video_tags(self, html: str, base_url: str) -> List[VideoURL]:
        """Extract from HTML5 <video> tags.

        Args:
            html: The HTML content
            base_url: The base URL for resolving relative URLs

        Returns:
            List of VideoURL objects from video tags
        """
        videos = []
        if not HAS_BS4 or not BeautifulSoup:
            return videos

        soup = BeautifulSoup(html, "html.parser")

        for video in soup.find_all("video"):
            # Check src attribute
            src = video.get("src")
            if src:
                videos.append(
                    VideoURL(
                        url=urljoin(base_url, src),
                        source="video_tag",
                        mime_type=video.get("type"),
                    )
                )

            # Check <source> children
            for source in video.find_all("source"):
                src = source.get("src")
                if src:
                    videos.append(
                        VideoURL(
                            url=urljoin(base_url, src),
                            source="video_source_tag",
                            mime_type=source.get("type"),
                            quality=source.get("label") or source.get("res"),
                        )
                    )

        return videos

    def _extract_from_meta_tags(self, html: str, base_url: str) -> List[VideoURL]:
        """Extract from Open Graph and Twitter Card meta tags.

        Args:
            html: The HTML content
            base_url: The base URL for resolving relative URLs

        Returns:
            List of VideoURL objects from meta tags
        """
        videos = []
        if not HAS_BS4 or not BeautifulSoup:
            return videos

        soup = BeautifulSoup(html, "html.parser")

        # Open Graph video tags
        og_video_tags = [
            "og:video",
            "og:video:url",
            "og:video:secure_url",
        ]

        for tag in og_video_tags:
            meta = soup.find("meta", property=tag)
            if meta and meta.get("content"):
                videos.append(
                    VideoURL(
                        url=urljoin(base_url, meta["content"]),
                        source="og_meta_tag",
                        mime_type=meta.get("type"),
                    )
                )

        # Twitter Card video
        twitter_video = soup.find("meta", attrs={"name": "twitter:player"})
        if twitter_video and twitter_video.get("content"):
            videos.append(
                VideoURL(
                    url=urljoin(base_url, twitter_video["content"]),
                    source="twitter_card",
                )
            )

        return videos

    def _extract_from_json_ld(self, html: str, base_url: str) -> List[VideoURL]:
        """Extract from JSON-LD structured data.

        Args:
            html: The HTML content
            base_url: The base URL for resolving relative URLs

        Returns:
            List of VideoURL objects from JSON-LD
        """
        videos = []
        if not HAS_BS4 or not BeautifulSoup:
            return videos

        soup = BeautifulSoup(html, "html.parser")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if not script.string:
                    continue

                data = json.loads(script.string)

                # Handle VideoObject
                if isinstance(data, dict) and data.get("@type") == "VideoObject":
                    content_url = data.get("contentUrl")
                    embed_url = data.get("embedUrl")

                    if content_url:
                        videos.append(
                            VideoURL(
                                url=urljoin(base_url, content_url),
                                source="json_ld",
                                mime_type=data.get("encodingFormat"),
                            )
                        )

                    if embed_url:
                        videos.append(
                            VideoURL(
                                url=urljoin(base_url, embed_url),
                                source="json_ld_embed",
                            )
                        )

                # Handle arrays of objects
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "VideoObject":
                            content_url = item.get("contentUrl")
                            if content_url:
                                videos.append(
                                    VideoURL(
                                        url=urljoin(base_url, content_url),
                                        source="json_ld",
                                        mime_type=item.get("encodingFormat"),
                                    )
                                )
            except Exception as e:
                logger.debug(f"Failed to parse JSON-LD: {e}")
                continue

        return videos

    def _extract_with_regex(self, html: str, base_url: str) -> List[VideoURL]:
        """Fallback extraction using regex (no BeautifulSoup).

        Args:
            html: The HTML content
            base_url: The base URL for resolving relative URLs

        Returns:
            List of VideoURL objects from regex extraction
        """
        videos = []

        # Video src patterns
        patterns = [
            r'<video[^>]+src=["\']([^"\']+)["\']',
            r'<source[^>]+src=["\']([^"\']+)["\']',
            r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+property=["\']og:video:url["\'][^>]+content=["\']([^"\']+)["\']',
            r'"contentUrl"\s*:\s*"([^"]+)"',  # JSON-LD
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if match.startswith("http"):
                    videos.append(
                        VideoURL(
                            url=urljoin(base_url, match),
                            source="regex_fallback",
                        )
                    )

        return videos


async def extract_videos_from_html(url: str) -> List[VideoURL]:
    """Convenience function to extract videos from HTML.

    Args:
        url: URL of the HTML page

    Returns:
        List of VideoURL objects

    Example:
        videos = await extract_videos_from_html("https://example.com/page")
        for video in videos:
            print(f"Found: {video.url}")
    """
    async with HTMLVideoExtractor() as extractor:
        return await extractor.extract_videos(url)


async def download_from_html(
    url: str,
    options: "DownloadOptions",
    downloader: Optional["GenericDownloader"] = None,  # type: ignore # noqa: F821
) -> Any:
    """Extract and download first video from HTML page.

    Args:
        url: HTML page URL
        options: Download options
        downloader: GenericDownloader instance (creates if None)

    Returns:
        DownloadResult from the first successfully downloaded video
    """
    from . import DownloadResult
    from .generic_downloader import GenericDownloader

    videos = await extract_videos_from_html(url)

    if not videos:
        return DownloadResult(
            success=False,
            error_message="No videos found on the page",
        )

    if downloader is None:
        downloader = GenericDownloader()

    # Try each video URL until one succeeds
    for video in videos:
        try:
            result = await downloader.download(video.url, options)
            if result.success:
                return result
        except Exception as e:
            logger.debug(f"Failed to download {video.url}: {e}")
            continue

    return DownloadResult(
        success=False,
        error_message="Failed to download any video from the page",
    )


__all__ = [
    "VideoURL",
    "HTMLVideoExtractor",
    "extract_videos_from_html",
    "download_from_html",
]
