"""Platform-specific downloader implementations.

This package provides specialized downloaders for popular video platforms
with enhanced metadata extraction and platform-specific optimizations.

Available platforms:
- YouTube (via YouTubeDownloader)
- Instagram (via InstagramDownloader)
- TikTok (planned)
- Twitter/X (planned)
- Facebook (planned)

Example:
    from bot.downloaders.platforms import InstagramDownloader

    downloader = InstagramDownloader()
    if await downloader.can_handle(url):
        result = await downloader.download(url, options)
"""
import logging

logger = logging.getLogger(__name__)

# Import platform handlers
from .youtube import (
    YouTubeDownloader,
    is_youtube_shorts,
    is_youtube_url,
)

# Import Instagram handlers (from 10-02)
from .instagram import (
    INSTAGRAM_PATTERNS,
    InstagramContentType,
    InstagramDownloader,
    detect_instagram_content_type,
    extract_shortcode,
    extract_username_from_url,
    is_instagram_reel,
    is_instagram_story,
    is_instagram_url,
)

__all__ = [
    # YouTube platform handler
    'YouTubeDownloader',
    'is_youtube_shorts',
    'is_youtube_url',
    # Instagram platform handler (from 10-02)
    'InstagramDownloader',
    'InstagramContentType',
    'detect_instagram_content_type',
    'is_instagram_reel',
    'is_instagram_story',
    'is_instagram_url',
    'extract_shortcode',
    'extract_username_from_url',
    'INSTAGRAM_PATTERNS',
]
