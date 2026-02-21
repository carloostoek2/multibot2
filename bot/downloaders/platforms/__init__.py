"""Platform-specific downloader implementations.

This package provides specialized downloaders for specific platforms
that extend the base yt-dlp functionality with platform-specific
features and metadata extraction.
"""
import logging

logger = logging.getLogger(__name__)

# Import platform handlers
from .youtube import (
    YouTubeDownloader,
    is_youtube_shorts,
    is_youtube_url,
)

__all__ = [
    # YouTube platform handler
    'YouTubeDownloader',
    'is_youtube_shorts',
    'is_youtube_url',
]
