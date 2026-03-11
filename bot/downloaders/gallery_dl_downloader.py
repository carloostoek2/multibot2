"""Gallery-dl based downloader for image-focused platforms.

This module provides the GalleryDlDownloader class for downloading images and
galleries from Instagram and other platforms where yt-dlp has limitations with
image-only content.

Gallery-dl is specifically designed for image galleries and handles Instagram
image posts better than yt-dlp in some cases.
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from .base import BaseDownloader, DownloadOptions
from .exceptions import DownloadFailedError, MetadataExtractionError
from .types import DownloadResult

logger = logging.getLogger(__name__)

# Try to import gallery-dl
try:
    from gallery_dl import config, job
    from gallery_dl.extractor import find as find_extractor
    GALLERY_DL_AVAILABLE = True
except ImportError:
    GALLERY_DL_AVAILABLE = False
    logger.warning("gallery-dl not installed. Instagram image posts may not work.")


class GalleryDlDownloader(BaseDownloader):
    """Downloader using gallery-dl for image galleries and Instagram images.

    This downloader complements yt-dlp by handling image-only content
    on platforms like Instagram where yt-dlp's extractor has limitations.

    Example:
        downloader = GalleryDlDownloader()

        if await downloader.can_handle(url):
            result = await downloader.download(url, options)
    """

    def __init__(self):
        """Initialize the GalleryDlDownloader."""
        self._loop = asyncio.get_event_loop()

    @property
    def name(self) -> str:
        """Human-readable downloader name."""
        return "gallery-dl Downloader"

    @property
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader."""
        return ["Instagram Images", "Image Galleries"]

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            True if gallery-dl can handle this URL
        """
        if not GALLERY_DL_AVAILABLE:
            return False

        if not url or not isinstance(url, str):
            return False

        # gallery-dl works best with Instagram images
        if "instagram.com" in url.lower():
            return True

        # Check if gallery-dl has an extractor for this URL
        def _check():
            try:
                extractor = find_extractor(url)
                return extractor is not None
            except Exception:
                return False

        return await asyncio.to_thread(_check)

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata from a URL without downloading.

        Args:
            url: The URL to extract metadata from
            options: Download configuration options

        Returns:
            Dictionary containing metadata fields

        Raises:
            MetadataExtractionError: If metadata cannot be extracted
        """
        if not GALLERY_DL_AVAILABLE:
            raise MetadataExtractionError(
                message="gallery-dl not available",
                url=url,
            )

        correlation_id = self._generate_correlation_id()
        logger.info(f"[{correlation_id}] Extracting metadata with gallery-dl from {url}")

        def _extract():
            try:
                # Use gallery-dl's extractor to get metadata
                extractor_class = find_extractor(url)
                if not extractor_class:
                    raise MetadataExtractionError(
                        message="No gallery-dl extractor found for URL",
                        url=url,
                        correlation_id=correlation_id,
                    )

                # Create extractor instance
                extr = extractor_class.from_url(url)

                # Get items from extractor
                items = list(extr)

                # Try to get caption/description from extractor
                # gallery-dl Instagram extractor puts caption in 'description' field
                caption = getattr(extr, 'description', None)

                # Try to get from the first item's metadata if items exist
                if not caption and items:
                    try:
                        first_item = items[0]
                        if isinstance(first_item, tuple) and len(first_item) > 1:
                            item_metadata = first_item[1]
                            if isinstance(item_metadata, dict):
                                # gallery-dl uses 'description' for post caption
                                caption = item_metadata.get('description') or item_metadata.get('caption', '')
                                # Also try to get username from item metadata
                                if not username and item_metadata.get('username'):
                                    username = item_metadata['username']
                    except Exception:
                        pass

                metadata = {
                    "title": getattr(extr, 'display_name', 'Instagram Post'),
                    "uploader": getattr(extr, 'user', None),
                    "caption": caption,
                    "item_count": len(items),
                    "items": [
                        {
                            "url": item[0] if isinstance(item, tuple) else item,
                            "name": item[1] if isinstance(item, tuple) and len(item) > 1 else None,
                        }
                        for item in items[:10]  # Limit metadata items
                    ],
                    "extractor": getattr(extr, 'category', 'unknown'),
                    "subcategory": getattr(extr, 'subcategory', None),
                }

                return metadata

            except Exception as e:
                logger.error(f"[{correlation_id}] gallery-dl extraction error: {e}")
                raise MetadataExtractionError(
                    message=f"gallery-dl extraction failed: {e}",
                    url=url,
                    correlation_id=correlation_id,
                ) from e

        return await asyncio.to_thread(_extract)

    async def download(
        self,
        url: str,
        options: DownloadOptions,
    ) -> DownloadResult:
        """Download content from the given URL.

        Args:
            url: The URL to download from
            options: Download configuration options

        Returns:
            DownloadResult containing:
            - success: Whether download completed successfully
            - file_path: Path to the first downloaded file
            - file_paths: List of all downloaded files
            - metadata: Additional metadata about the download

        Raises:
            DownloadFailedError: If download fails
        """
        if not GALLERY_DL_AVAILABLE:
            raise DownloadFailedError(
                attempts_made=1,
                message="gallery-dl not installed",
                url=url,
            )

        correlation_id = self._generate_correlation_id()
        logger.info(f"[{correlation_id}] Starting gallery-dl download from {url}")

        # Create temp directory for download
        temp_dir = tempfile.mkdtemp(prefix="gallery_dl_")

        def _download():
            downloaded_files = []

            try:
                # Load config
                config.load()

                # Set output directory - use flat structure to avoid placeholder issues
                config.set(("extractor",), "base-directory", temp_dir)
                config.set(("extractor",), "directory", [""])  # Empty for flat structure

                # Add cookies if available - try to get from environment or default location
                import os
                cookies_file = os.environ.get('COOKIES_FILE', '/data/data/com.termux/files/home/repos/multibot2/cookies.txt')
                if cookies_file and os.path.exists(cookies_file):
                    config.set(("extractor", "instagram"), "cookies", cookies_file)

                # Run download job
                dl_job = job.DownloadJob(url)
                dl_job.run()

                # Find downloaded files
                for root, dirs, files in os.walk(temp_dir):
                    for filename in files:
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp4', '.webm')):
                            filepath = os.path.join(root, filename)
                            downloaded_files.append(filepath)
                            logger.info(f"[{correlation_id}] Downloaded: {filepath}")

                if not downloaded_files:
                    raise DownloadFailedError(
                        attempts_made=1,
                        message="No files were downloaded",
                        url=url,
                        correlation_id=correlation_id,
                    )

                return downloaded_files

            except Exception as e:
                logger.error(f"[{correlation_id}] gallery-dl download error: {e}")
                raise DownloadFailedError(
                    attempts_made=1,
                    message=f"gallery-dl download failed: {e}",
                    url=url,
                    correlation_id=correlation_id,
                ) from e

        try:
            file_paths = await asyncio.to_thread(_download)

            # Extract metadata
            try:
                metadata = await self.extract_metadata(url, options)
            except Exception:
                metadata = {"source": "gallery-dl"}

            return DownloadResult(
                success=True,
                file_path=file_paths[0] if file_paths else None,
                file_paths=file_paths,
                metadata={
                    **metadata,
                    "file_count": len(file_paths),
                    "download_method": "gallery-dl",
                },
            )

        finally:
            # Cleanup temp directory if needed
            # Note: We keep files since they need to be sent
            pass


__all__ = ["GalleryDlDownloader", "GALLERY_DL_AVAILABLE"]
