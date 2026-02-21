"""URL detection, extraction, and classification module.

This module provides functionality to automatically detect URLs in Telegram
messages, extract them from various message entities, and classify URLs by
type (platform-specific vs generic video URLs).
"""
import re
import logging
from enum import Enum, auto
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from bot.downloaders import URLDetectionError, UnsupportedURLError

logger = logging.getLogger(__name__)


class URLType(Enum):
    """Classification of URL types for downloader routing.

    - PLATFORM: URLs from supported platforms (YouTube, Instagram, etc.)
    - GENERIC_VIDEO: Direct video file URLs (.mp4, .webm, .mov)
    - UNKNOWN: URLs that are not recognized as video content
    """
    PLATFORM = auto()
    GENERIC_VIDEO = auto()
    UNKNOWN = auto()


# Platform domain patterns for URL classification
PLATFORM_PATTERNS = {
    "youtube": [
        r"youtube\.com",
        r"youtu\.be",
        r"youtube\.com/shorts",
    ],
    "instagram": [
        r"instagram\.com/p/",
        r"instagram\.com/reel/",
        r"instagram\.com/reels/",
        r"instagram\.com/stories/",
    ],
    "tiktok": [
        r"tiktok\.com/@",
        r"vm\.tiktok\.com",
        r"vt\.tiktok\.com",
    ],
    "twitter": [
        r"twitter\.com",
        r"x\.com",
    ],
    "facebook": [
        r"facebook\.com/watch",
        r"fb\.watch",
        r"facebook\.com/reel/",
        r"facebook\.com/video",
    ],
}

# Generic video file extensions
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".wmv"}

# Regex pattern for URL extraction from plain text
URL_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)


class URLDetector:
    """Detects, extracts, and classifies URLs from Telegram messages.

    This class handles URL extraction from both message entities (url, text_link)
    and plain text fallback. It also classifies URLs by type to determine
    which downloader should handle them.
    """

    @staticmethod
    def extract_urls(message_text: Optional[str], entities: Optional[List] = None) -> List[str]:
        """Extract URLs from message text and entities.

        Extracts URLs from:
        1. Message entities (url type and text_link type)
        2. Plain text regex fallback for any missed URLs

        Args:
            message_text: The text content of the message
            entities: List of MessageEntity objects from Telegram

        Returns:
            List of extracted URL strings (deduplicated, in order of appearance)

        Raises:
            URLDetectionError: If URL extraction fails critically
        """
        if not message_text:
            return []

        urls = []
        seen_urls = set()

        # Extract from entities first (handles text_link properly)
        if entities:
            for entity in entities:
                try:
                    if entity.type == "url":
                        # Extract URL from the entity offset/length in message text
                        url = message_text[entity.offset:entity.offset + entity.length]
                        if url and url not in seen_urls:
                            urls.append(url)
                            seen_urls.add(url)
                    elif entity.type == "text_link":
                        # Hidden URL behind clickable text
                        url = entity.url
                        if url and url not in seen_urls:
                            urls.append(url)
                            seen_urls.add(url)
                except (AttributeError, IndexError) as e:
                    logger.warning(f"Failed to extract URL from entity: {e}")
                    continue

        # Fallback to regex for any URLs not caught by entities
        regex_urls = URL_REGEX.findall(message_text)
        for url in regex_urls:
            # Clean up trailing punctuation that might be captured
            url = url.rstrip(".,;:!?)]}")
            if url and url not in seen_urls:
                urls.append(url)
                seen_urls.add(url)

        logger.debug(f"Extracted {len(urls)} URLs from message: {urls}")
        return urls

    @staticmethod
    def classify_url(url: str) -> URLType:
        """Classify a URL by type to determine handling strategy.

        Args:
            url: The URL string to classify

        Returns:
            URLType enum value indicating the URL classification

        Raises:
            URLDetectionError: If the URL is malformed
        """
        if not url or not isinstance(url, str):
            raise URLDetectionError("URL must be a non-empty string")

        # Validate URL has basic structure
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise URLDetectionError(f"Invalid URL format: {url}")
        except Exception as e:
            raise URLDetectionError(f"URL parsing failed: {e}")

        # Check for platform patterns
        url_lower = url.lower()
        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower, re.IGNORECASE):
                    logger.debug(f"Classified URL as PLATFORM ({platform}): {url}")
                    return URLType.PLATFORM

        # Check for generic video file extensions
        path = parsed.path.lower()
        for ext in VIDEO_EXTENSIONS:
            if path.endswith(ext):
                logger.debug(f"Classified URL as GENERIC_VIDEO: {url}")
                return URLType.GENERIC_VIDEO

        logger.debug(f"Classified URL as UNKNOWN: {url}")
        return URLType.UNKNOWN

    @staticmethod
    def is_supported(url: str) -> bool:
        """Check if a URL can be handled by any downloader.

        Args:
            url: The URL string to check

        Returns:
            True if the URL is supported (PLATFORM or GENERIC_VIDEO), False otherwise
        """
        try:
            url_type = URLDetector.classify_url(url)
            return url_type in (URLType.PLATFORM, URLType.GENERIC_VIDEO)
        except URLDetectionError:
            return False

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate that a URL is well-formed and accessible.

        Performs basic validation of URL structure. Does not check
        if the URL is actually reachable (that requires network access).

        Args:
            url: The URL string to validate

        Returns:
            True if the URL is valid, False otherwise
        """
        if not url or not isinstance(url, str):
            return False

        try:
            parsed = urlparse(url)
            # Must have scheme (http/https) and netloc (domain)
            if not parsed.scheme or not parsed.netloc:
                return False
            # Scheme must be http or https
            if parsed.scheme not in ("http", "https"):
                return False
            # Netloc must contain at least one dot (domain.tld)
            if "." not in parsed.netloc:
                return False
            return True
        except Exception:
            return False


# Convenience functions for direct use
def detect_urls(message_text: Optional[str], entities: Optional[List] = None) -> List[str]:
    """Extract URLs from a message.

    Convenience function that wraps URLDetector.extract_urls().

    Args:
        message_text: The text content of the message
        entities: List of MessageEntity objects from Telegram

    Returns:
        List of extracted URL strings
    """
    return URLDetector.extract_urls(message_text, entities)


def classify_url(url: str) -> URLType:
    """Classify a URL by type.

    Convenience function that wraps URLDetector.classify_url().

    Args:
        url: The URL string to classify

    Returns:
        URLType enum value
    """
    return URLDetector.classify_url(url)


def is_video_url(url: str) -> bool:
    """Check if a URL is a video URL (platform or generic).

    Args:
        url: The URL string to check

    Returns:
        True if the URL is a supported video URL
    """
    return URLDetector.is_supported(url)


def classify_url_enhanced(url: str) -> Tuple[URLType, Optional[str]]:
    """Classify URL with platform identification.

    Returns:
        Tuple of (URLType, platform_name)
    """
    basic_type = URLDetector.classify_url(url)

    if basic_type == URLType.PLATFORM:
        # Try to identify specific platform
        checkers = _get_platform_checkers()
        for platform, checker in checkers.items():
            if checker(url):
                return URLType.PLATFORM, platform
        return URLType.PLATFORM, "unknown"

    return basic_type, None


# Import platform checkers for enhanced detection
# Use lazy import to avoid circular dependencies
def _get_platform_checkers():
    try:
        from .platforms import (
            is_youtube_url,
            is_instagram_url,
            is_tiktok_url,
            is_twitter_url,
            is_facebook_url,
        )
        return {
            "youtube": is_youtube_url,
            "instagram": is_instagram_url,
            "tiktok": is_tiktok_url,
            "twitter": is_twitter_url,
            "facebook": is_facebook_url,
        }
    except ImportError:
        return {}


# Export public API
__all__ = [
    "URLType",
    "URLDetector",
    "detect_urls",
    "classify_url",
    "classify_url_enhanced",
    "is_video_url",
    "PLATFORM_PATTERNS",
    "VIDEO_EXTENSIONS",
]
