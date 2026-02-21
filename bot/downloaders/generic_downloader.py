"""Generic HTTP downloader for direct video file URLs.

This module provides the GenericDownloader class which implements the
BaseDownloader interface for downloading videos from direct URLs using
aiohttp for async streaming downloads.

Features:
- Streaming downloads to avoid memory issues
- Content-Type validation (DL-05)
- File size checking from Content-Length header (QF-05)
- Progress callbacks for real-time feedback
- Automatic redirect following (GV-03)
- File integrity validation after download
"""
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import aiofiles
import aiohttp
from aiohttp import ClientConnectorError, ClientResponseError

from .base import BaseDownloader, DownloadOptions
from .exceptions import (
    DownloadFailedError,
    FileTooLargeError,
    NetworkError,
    UnsupportedURLError,
    URLValidationError,
)

logger = logging.getLogger(__name__)


class GenericDownloader(BaseDownloader):
    """Downloader for direct video file URLs using aiohttp.

    This downloader handles direct video file URLs (ending in .mp4, .webm, etc.)
    by streaming the content using aiohttp. It validates content types,
    checks file sizes, and provides progress callbacks during download.

    Attributes:
        name: Human-readable downloader name
        supported_platforms: List of supported platform names
        VIDEO_EXTENSIONS: Set of recognized video file extensions
        VIDEO_MIME_TYPES: Set of recognized video MIME types
    """

    name = "Generic HTTP Downloader"
    supported_platforms = ["Direct Video URLs"]

    VIDEO_EXTENSIONS = {
        '.mp4', '.webm', '.mov', '.mkv', '.avi', '.flv', '.wmv',
        '.m4v', '.3gp', '.ogv', '.mpeg', '.mpg'
    }

    VIDEO_MIME_TYPES = {
        'video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo',
        'video/x-flv', 'video/x-ms-wmv', 'video/x-matroska', 'video/3gpp',
        'video/ogg', 'video/mpeg', 'application/mp4', 'video/x-m4v'
    }

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        This is a quick check that looks for video file extensions or
        valid HTTP/HTTPS URLs. Full validation happens in extract_metadata.

        Args:
            url: The URL to check

        Returns:
            True if this downloader might be able to handle the URL
        """
        if not url or not isinstance(url, str):
            return False

        url = url.strip()

        # Check if it's a valid HTTP/HTTPS URL
        if not self._is_valid_url(url):
            return False

        # Check if URL ends with a video extension
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Remove query parameters and fragments for extension check
        path = path.split('?')[0].split('#')[0]

        for ext in self.VIDEO_EXTENSIONS:
            if path.endswith(ext):
                return True

        # Also accept any HTTP(S) URL that might be a video
        # (full validation in extract_metadata)
        return True

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions
    ) -> dict[str, Any]:
        """Extract metadata from a URL without downloading.

        Makes a HEAD request to get headers and validate the content
        is a video file before downloading.

        Args:
            url: The URL to extract metadata from
            options: Download configuration options

        Returns:
            Dictionary containing metadata fields:
            - title: Filename extracted from URL
            - duration: None (can't determine from headers)
            - uploader: None
            - thumbnail: None
            - filesize: File size in bytes (from Content-Length)
            - content_type: MIME type from headers
            - url: Final URL after redirects

        Raises:
            URLValidationError: If the URL is invalid
            UnsupportedURLError: If the URL doesn't point to a video
            MetadataExtractionError: If metadata cannot be extracted
            NetworkError: For transient network failures
        """
        self.validate_url(url)

        correlation_id = self._generate_correlation_id()
        logger.info(
            f"[{correlation_id}] Extracting metadata from {url}"
        )

        try:
            timeout = aiohttp.ClientTimeout(total=options.metadata_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(url, allow_redirects=True) as response:
                    response.raise_for_status()

                    content_type = response.headers.get('content-type', '').lower()
                    content_length = response.headers.get('content-length')

                    # Validate it's a video
                    if not self._is_video_content(content_type, str(response.url)):
                        raise UnsupportedURLError(
                            message="URL does not point to a video file",
                            url=url,
                            correlation_id=correlation_id
                        )

                    metadata = {
                        'title': self._extract_filename_from_url(str(response.url)),
                        'duration': None,  # Can't determine from headers
                        'uploader': None,
                        'thumbnail': None,
                        'filesize': int(content_length) if content_length else None,
                        'content_type': content_type,
                        'url': str(response.url),  # Final URL after redirects
                    }

                    logger.info(
                        f"[{correlation_id}] Metadata extracted: "
                        f"title={metadata['title']}, "
                        f"filesize={metadata['filesize']}"
                    )

                    return metadata

        except ClientResponseError as e:
            if e.status == 404:
                raise UnsupportedURLError(
                    message="Video not found (404)",
                    url=url,
                    correlation_id=correlation_id
                ) from e
            elif e.status == 403:
                raise UnsupportedURLError(
                    message="Access denied (403) - video may be private",
                    url=url,
                    correlation_id=correlation_id
                ) from e
            else:
                raise DownloadFailedError(
                    attempts_made=1,
                    last_error=e,
                    message=f"HTTP error {e.status}: {e.message}",
                    url=url,
                    correlation_id=correlation_id
                ) from e

        except ClientConnectorError as e:
            raise NetworkError(
                message=f"Failed to connect to server: {e}",
                url=url,
                correlation_id=correlation_id,
                retry_suggested=True
            ) from e

        except asyncio.TimeoutError as e:
            raise DownloadFailedError(
                attempts_made=1,
                last_error=e,
                message="Metadata extraction timed out",
                url=url,
                correlation_id=correlation_id
            ) from e

    async def download(
        self,
        url: str,
        options: DownloadOptions
    ) -> Any:
        """Download content from the given URL.

        Performs a streaming download using aiohttp with progress callbacks,
        file size validation, and integrity checking.

        Args:
            url: The URL to download from
            options: Download configuration options

        Returns:
            DownloadResult with success status and file path

        Raises:
            URLValidationError: If the URL is invalid
            FileTooLargeError: If the file exceeds size limits
            DownloadFailedError: If download fails after retries
            NetworkError: For transient network failures
        """
        from . import DownloadResult

        self.validate_url(url)

        correlation_id = self._generate_correlation_id()
        logger.info(
            f"[{correlation_id}] Starting download from {url}"
        )

        output_path = None

        try:
            timeout = aiohttp.ClientTimeout(total=options.download_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, allow_redirects=True) as response:
                    response.raise_for_status()

                    # Check content type (per DL-05)
                    content_type = response.headers.get('content-type', '').lower()
                    if not self._is_video_content(content_type, str(response.url)):
                        raise UnsupportedURLError(
                            message="URL does not point to a video file",
                            url=url,
                            correlation_id=correlation_id
                        )

                    # Check file size from Content-Length header (per QF-05)
                    total_size = int(response.headers.get('content-length', 0))
                    if total_size > options.max_filesize:
                        raise FileTooLargeError(
                            file_size=total_size,
                            max_size=options.max_filesize,
                            url=url,
                            correlation_id=correlation_id
                        )

                    # Determine output path
                    output_path = self._build_output_path(
                        str(response.url), options, content_type
                    )

                    # Ensure output directory exists
                    output_dir = os.path.dirname(output_path)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)

                    # Stream download with progress (per research Pattern 4)
                    downloaded = 0
                    async with aiofiles.open(output_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                            downloaded += len(chunk)

                            # Call progress callback
                            if options.progress_callback and total_size:
                                progress = {
                                    'percent': (downloaded / total_size) * 100,
                                    'downloaded_bytes': downloaded,
                                    'total_bytes': total_size,
                                    'correlation_id': correlation_id,
                                }
                                await options.progress_callback(progress)

                    # Validate downloaded file
                    self._validate_downloaded_file(
                        output_path, total_size, url, correlation_id
                    )

                    logger.info(
                        f"[{correlation_id}] Download complete: {output_path} "
                        f"({downloaded} bytes)"
                    )

                    return DownloadResult(
                        success=True,
                        file_path=output_path,
                        metadata={
                            'content_type': content_type,
                            'filesize': downloaded,
                            'correlation_id': correlation_id,
                        }
                    )

        except (ClientResponseError, ClientConnectorError, asyncio.TimeoutError,
                UnsupportedURLError, FileTooLargeError):
            # Clean up partial file on error
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(
                        f"[{correlation_id}] Cleaned up partial file: {output_path}"
                    )
                except OSError as cleanup_error:
                    logger.warning(
                        f"[{correlation_id}] Failed to clean up partial file: "
                        f"{cleanup_error}"
                    )
            raise

        except Exception as e:
            # Clean up partial file on unexpected error
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(
                        f"[{correlation_id}] Cleaned up partial file: {output_path}"
                    )
                except OSError as cleanup_error:
                    logger.warning(
                        f"[{correlation_id}] Failed to clean up partial file: "
                        f"{cleanup_error}"
                    )
            raise DownloadFailedError(
                attempts_made=1,
                last_error=e,
                message=f"Unexpected error during download: {e}",
                url=url,
                correlation_id=correlation_id
            ) from e

    def _is_video_content(self, content_type: str, url: str) -> bool:
        """Check if content is a video based on MIME type or URL extension.

        Args:
            content_type: The Content-Type header value
            url: The URL being checked

        Returns:
            True if the content appears to be a video
        """
        # Check MIME type
        if content_type:
            # Remove charset suffix if present
            mime = content_type.split(';')[0].strip()
            if mime in self.VIDEO_MIME_TYPES:
                return True
            # Also accept generic application/octet-stream if URL has video extension
            if mime == 'application/octet-stream' or mime == 'binary/octet-stream':
                parsed = urlparse(url.lower())
                path = parsed.path.split('?')[0].split('#')[0]
                for ext in self.VIDEO_EXTENSIONS:
                    if path.endswith(ext):
                        return True

        # Check URL extension as fallback
        parsed = urlparse(url.lower())
        path = parsed.path.split('?')[0].split('#')[0]
        for ext in self.VIDEO_EXTENSIONS:
            if path.endswith(ext):
                return True

        return False

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL path.

        Args:
            url: The URL to extract filename from

        Returns:
            Filename string (sanitized)
        """
        parsed = urlparse(url)
        path = parsed.path

        # Get the last path component
        filename = os.path.basename(path)

        # If no filename, generate one
        if not filename:
            return "video"

        # Sanitize the filename
        return self._sanitize_filename(filename)

    def _build_output_path(
        self,
        url: str,
        options: DownloadOptions,
        content_type: str
    ) -> str:
        """Build output file path for download.

        Args:
            url: The URL being downloaded
            options: Download configuration options
            content_type: The content MIME type

        Returns:
            Absolute path for the output file
        """
        # Use custom filename if provided
        if options.filename:
            filename = self._sanitize_filename(options.filename)
        else:
            filename = self._extract_filename_from_url(url)

        # Ensure proper extension
        if not any(filename.lower().endswith(ext) for ext in self.VIDEO_EXTENSIONS):
            ext = self._get_extension_from_content_type(content_type)
            filename = f"{filename}{ext}"

        # Determine output directory
        if options.output_path:
            output_dir = options.output_path
        else:
            output_dir = os.getcwd()

        return os.path.abspath(os.path.join(output_dir, filename))

    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Map MIME type to file extension.

        Args:
            content_type: The MIME type from headers

        Returns:
            File extension (including the dot)
        """
        if not content_type:
            return '.mp4'

        mime = content_type.split(';')[0].strip().lower()

        mapping = {
            'video/mp4': '.mp4',
            'video/webm': '.webm',
            'video/quicktime': '.mov',
            'video/x-msvideo': '.avi',
            'video/x-flv': '.flv',
            'video/x-ms-wmv': '.wmv',
            'video/x-matroska': '.mkv',
            'video/3gpp': '.3gp',
            'video/ogg': '.ogv',
            'video/mpeg': '.mpeg',
            'video/x-m4v': '.m4v',
        }

        return mapping.get(mime, '.mp4')

    def _validate_downloaded_file(
        self,
        output_path: str,
        expected_size: int,
        url: str,
        correlation_id: str
    ) -> None:
        """Validate the downloaded file for integrity.

        Args:
            output_path: Path to the downloaded file
            expected_size: Expected file size from Content-Length header
            url: The original URL
            correlation_id: Request tracing ID

        Raises:
            DownloadFailedError: If validation fails
        """
        # Check file exists
        if not os.path.exists(output_path):
            raise DownloadFailedError(
                attempts_made=1,
                message="Downloaded file not found",
                url=url,
                correlation_id=correlation_id
            )

        actual_size = os.path.getsize(output_path)

        # Non-empty file check
        if actual_size == 0:
            raise DownloadFailedError(
                attempts_made=1,
                message="Downloaded file is empty",
                url=url,
                correlation_id=correlation_id
            )

        # Size validation
        if expected_size and actual_size != expected_size:
            raise DownloadFailedError(
                attempts_made=1,
                message=(
                    f"Download incomplete: expected {expected_size} bytes, "
                    f"got {actual_size}"
                ),
                url=url,
                correlation_id=correlation_id
            )

        # File type validation (optional, if python-magic available)
        try:
            import magic
            mime = magic.from_file(output_path, mime=True)
            if mime and not mime.startswith('video/'):
                # Some valid video formats might not start with video/
                # Check for common exceptions
                if mime not in ('application/mp4', 'application/octet-stream'):
                    raise DownloadFailedError(
                        attempts_made=1,
                        message=f"Downloaded file is not a video (detected: {mime})",
                        url=url,
                        correlation_id=correlation_id
                    )
        except ImportError:
            pass  # Skip if python-magic not installed

        logger.debug(
            f"[{correlation_id}] File validation passed: {actual_size} bytes"
        )