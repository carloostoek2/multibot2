"""yt-dlp based downloader for platform-specific URLs.

This module provides the YtDlpDownloader class for downloading videos from
YouTube, Instagram, TikTok, Twitter/X, Facebook, and 1000+ other sites
supported by yt-dlp.

The implementation uses yt-dlp's Python API with proper async handling
via thread pools to avoid blocking the event loop.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from .base import BaseDownloader, DownloadOptions, TELEGRAM_MAX_FILE_SIZE
from .exceptions import (
    DownloadFailedError,
    FileTooLargeError,
    MetadataExtractionError,
    NetworkError,
    URLValidationError,
)

logger = logging.getLogger(__name__)


class YtDlpDownloader(BaseDownloader):
    """Downloader using yt-dlp for platform video downloads.

    This downloader supports 1000+ video platforms through yt-dlp's
    comprehensive extractor library. It provides:

    - Metadata extraction without downloading
    - Video/audio download with format selection
    - Real-time progress callbacks
    - File size validation before download
    - Audio extraction via FFmpeg postprocessor

    Example:
        downloader = YtDlpDownloader()

        # Check if URL is supported
        if await downloader.can_handle(url):
            # Extract metadata
            metadata = await downloader.extract_metadata(url, options)

            # Download with progress
            result = await downloader.download(url, options)
    """

    def __init__(self):
        """Initialize the YtDlpDownloader.

        Stores a reference to the current event loop for scheduling
        progress callbacks from worker threads.
        """
        self._loop = asyncio.get_event_loop()

    @property
    def name(self) -> str:
        """Human-readable downloader name."""
        return "yt-dlp Downloader"

    @property
    def supported_platforms(self) -> list[str]:
        """List of platform names supported by this downloader."""
        return [
            "YouTube",
            "Instagram",
            "TikTok",
            "Twitter/X",
            "Facebook",
            "1000+ sites",
        ]

    async def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL.

        Uses yt-dlp's extract_info with process=False to quickly check
        if the URL is supported without downloading or full processing.

        Args:
            url: The URL to check

        Returns:
            True if yt-dlp can extract info from this URL, False otherwise.
        """
        if not url or not isinstance(url, str):
            return False

        def _check() -> bool:
            """Synchronous check function to run in thread pool."""
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # process=False for quick check without full extraction
                    ydl.extract_info(url, download=False, process=False)
                    return True
            except ExtractorError:
                # URL is not supported by yt-dlp
                return False
            except Exception as e:
                logger.debug(f"Error checking URL support: {e}")
                return False

        # Run in thread pool to avoid blocking
        return await asyncio.to_thread(_check)

    async def extract_metadata(
        self,
        url: str,
        options: DownloadOptions,
    ) -> dict[str, Any]:
        """Extract metadata from a URL without downloading.

        Per DL-03: Metadata extraction requirement. Fetches information
        about the content (title, duration, uploader, etc.) without
        downloading the actual file.

        Args:
            url: The URL to extract metadata from
            options: Download configuration options

        Returns:
            Dictionary containing metadata fields:
            - title: Content title
            - duration: Duration in seconds (if available)
            - uploader: Content creator/uploader (if available)
            - thumbnail: URL to thumbnail image (if available)
            - filesize: File size in bytes (or filesize_approx)
            - formats: List of available formats
            - description: Video description (truncated)

        Raises:
            URLValidationError: If the URL is invalid
            MetadataExtractionError: If metadata cannot be extracted
        """
        # Validate URL format first
        self.validate_url(url)

        correlation_id = self._generate_correlation_id()
        logger.info(
            f"[{correlation_id}] Extracting metadata from {url}"
        )

        def _extract() -> dict[str, Any]:
            """Synchronous extraction function."""
            from bot.config import config
            import os

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
            }

            # Add cookies file if configured (for YouTube authentication)
            if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
                ydl_opts["cookiefile"] = config.COOKIES_FILE
                logger.debug(f"[{correlation_id}] Using cookies file for metadata: {config.COOKIES_FILE}")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # process=True for full metadata extraction
                    info = ydl.extract_info(url, download=False, process=True)

                    if not info:
                        raise MetadataExtractionError(
                            message="No metadata returned from extractor",
                            url=url,
                            correlation_id=correlation_id,
                        )

                    # Extract relevant fields
                    metadata = {
                        "title": info.get("title", "Unknown"),
                        "duration": info.get("duration"),
                        "uploader": info.get("uploader") or info.get("channel"),
                        "thumbnail": info.get("thumbnail"),
                        "filesize": info.get("filesize") or info.get("filesize_approx"),
                        "formats": info.get("formats", []),
                        "description": self._truncate_description(
                            info.get("description", "")
                        ),
                        "webpage_url": info.get("webpage_url", url),
                        "id": info.get("id"),
                        "extractor": info.get("extractor"),
                    }

                    return metadata

            except ExtractorError as e:
                raise MetadataExtractionError(
                    message=f"Extractor error: {e}",
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            except Exception as e:
                raise MetadataExtractionError(
                    message=f"Unexpected error during extraction: {e}",
                    url=url,
                    correlation_id=correlation_id,
                ) from e

        # Run in thread pool
        try:
            return await asyncio.to_thread(_extract)
        except MetadataExtractionError:
            raise
        except Exception as e:
            raise MetadataExtractionError(
                message=f"Failed to extract metadata: {e}",
                url=url,
                correlation_id=correlation_id,
            ) from e

    async def download(
        self,
        url: str,
        options: DownloadOptions,
    ) -> Any:
        """Download content from the given URL.

        Performs the full download with format selection, file size
        validation, progress callbacks, and optional audio extraction.

        Args:
            url: The URL to download from
            options: Download configuration options

        Returns:
            DownloadResult containing:
            - success: Whether download completed successfully
            - file_path: Path to the downloaded file (if successful)
            - metadata: Additional metadata about the download

        Raises:
            URLValidationError: If the URL is invalid
            FileTooLargeError: If the file exceeds size limits
            DownloadFailedError: If download fails after retries
            NetworkError: For transient network failures
        """
        # Validate URL format
        self.validate_url(url)

        # Generate correlation ID for request tracing (per DM-02)
        correlation_id = self._generate_correlation_id()

        logger.info(
            f"[{correlation_id}] Starting download from {url}"
        )

        # First, extract metadata to check file size before downloading
        metadata = await self.extract_metadata(url, options)

        # Check file size before download (per QF-05)
        filesize = metadata.get("filesize") or metadata.get("filesize_approx", 0)
        if filesize and filesize > options.max_filesize:
            raise FileTooLargeError(
                file_size=filesize,
                max_size=options.max_filesize,
                url=url,
                correlation_id=correlation_id,
            )

        # Build output path
        output_path = self._build_output_path(options, metadata.get("title", "download"))

        # Build yt-dlp options
        ydl_opts = self._build_ydl_options(options, output_path, correlation_id)

        # Run download in thread pool
        try:
            file_path = await asyncio.to_thread(
                self._download_sync, url, ydl_opts, correlation_id
            )

            # Import here to avoid circular imports
            from . import DownloadResult

            return DownloadResult(
                success=True,
                file_path=file_path,
                metadata=metadata,
            )

        except FileTooLargeError:
            raise
        except DownloadFailedError:
            raise
        except NetworkError:
            raise
        except Exception as e:
            raise DownloadFailedError(
                attempts_made=1,
                last_error=e,
                url=url,
                correlation_id=correlation_id,
            ) from e

    def _download_sync(
        self,
        url: str,
        ydl_opts: dict,
        correlation_id: str,
    ) -> str:
        """Synchronous download wrapper.

        This method runs in a worker thread and performs the actual
        download using yt-dlp's synchronous API.

        Args:
            url: The URL to download
            ydl_opts: yt-dlp options dictionary
            correlation_id: Request tracing ID

        Returns:
            Path to the downloaded file

        Raises:
            DownloadFailedError: If download fails
            NetworkError: For network-related failures
        """
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if not info:
                    raise DownloadFailedError(
                        attempts_made=1,
                        message="No info returned from download",
                        correlation_id=correlation_id,
                    )

                # Get the actual file path
                filepath = ydl.prepare_filename(info)

                # Handle audio extraction case where extension changes
                if ydl_opts.get("postprocessors"):
                    for pp in ydl_opts["postprocessors"]:
                        if pp.get("key") == "FFmpegExtractAudio":
                            # Extension changes to audio codec
                            codec = pp.get("preferredcodec", "mp3")
                            filepath = os.path.splitext(filepath)[0] + f".{codec}"

                # Verify file exists
                if not os.path.exists(filepath):
                    # Try to find the file with common extensions
                    base_path = os.path.splitext(filepath)[0]
                    for ext in [".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".ogg"]:
                        alt_path = base_path + ext
                        if os.path.exists(alt_path):
                            filepath = alt_path
                            break

                if not os.path.exists(filepath):
                    raise DownloadFailedError(
                        attempts_made=1,
                        message=f"Downloaded file not found: {filepath}",
                        correlation_id=correlation_id,
                    )

                logger.info(
                    f"[{correlation_id}] Download completed: {filepath}"
                )
                return filepath

        except DownloadError as e:
            # Check for specific error types
            error_msg = str(e).lower()

            if "network" in error_msg or "connection" in error_msg:
                raise NetworkError(
                    message=f"Network error during download: {e}",
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            elif "unavailable" in error_msg or "private" in error_msg:
                raise DownloadFailedError(
                    attempts_made=1,
                    message=f"Content unavailable: {e}",
                    url=url,
                    correlation_id=correlation_id,
                ) from e
            else:
                raise DownloadFailedError(
                    attempts_made=1,
                    message=f"Download error: {e}",
                    url=url,
                    correlation_id=correlation_id,
                ) from e

        except ExtractorError as e:
            raise DownloadFailedError(
                attempts_made=1,
                message=f"Extractor error: {e}",
                url=url,
                correlation_id=correlation_id,
            ) from e

    def _build_ydl_options(
        self,
        options: DownloadOptions,
        output_path: str,
        correlation_id: str,
    ) -> dict:
        """Build yt-dlp options dictionary.

        Args:
            options: Download configuration
            output_path: Output file path template
            correlation_id: Request tracing ID

        Returns:
            Dictionary of yt-dlp options
        """
        # Import config here to avoid circular imports
        from bot.config import config

        # Base options
        ydl_opts = {
            "format": options.video_format,
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,  # Only download single video, not playlists
        }

        # Add cookies file if configured (for YouTube authentication)
        if config.COOKIES_FILE:
            import os
            if os.path.exists(config.COOKIES_FILE):
                ydl_opts["cookiefile"] = config.COOKIES_FILE
                logger.debug(f"[{correlation_id}] Using cookies file: {config.COOKIES_FILE}")
            else:
                logger.warning(f"Cookies file not found: {config.COOKIES_FILE}")

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
            # Update format for audio-only
            ydl_opts["format"] = options.audio_format

        return ydl_opts

    def _create_progress_hook(
        self,
        callback: Callable[[dict], None],
        correlation_id: str,
    ) -> Callable:
        """Create a progress hook function for yt-dlp.

        Args:
            callback: Async callback function to invoke
            correlation_id: Request tracing ID

        Returns:
            Progress hook function for yt-dlp
        """

        def _hook(d: dict) -> None:
            """Progress hook called by yt-dlp during download."""
            if d["status"] == "downloading":
                # Calculate progress
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)

                progress = {
                    "percent": (downloaded / total * 100) if total > 0 else 0,
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "status": "downloading",
                    "correlation_id": correlation_id,
                }

                # Schedule callback in event loop (thread-safe)
                asyncio.run_coroutine_threadsafe(
                    callback(progress),
                    self._loop,
                )

            elif d["status"] == "finished":
                # Download finished
                progress = {
                    "percent": 100.0,
                    "downloaded_bytes": d.get("total_bytes", 0),
                    "total_bytes": d.get("total_bytes", 0),
                    "speed": None,
                    "eta": 0,
                    "status": "finished",
                    "correlation_id": correlation_id,
                }

                asyncio.run_coroutine_threadsafe(
                    callback(progress),
                    self._loop,
                )

        return _hook

    def _build_output_path(self, options: DownloadOptions, title: str) -> str:
        """Build output path template for yt-dlp.

        Args:
            options: Download configuration
            title: Video title for filename

        Returns:
            Output path template string
        """
        # Determine output directory
        if options.output_path:
            output_dir = Path(options.output_path)
        else:
            output_dir = Path("downloads")

        # Ensure directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use custom filename if provided, otherwise use sanitized title
        if options.filename:
            filename = options.filename
        else:
            filename = self._sanitize_filename(title)

        # Build template - yt-dlp will add appropriate extension
        template = str(output_dir / f"{filename}.%(ext)s")

        return template

    @staticmethod
    def _truncate_description(description: Optional[str], max_length: int = 500) -> str:
        """Truncate description to maximum length.

        Args:
            description: Original description
            max_length: Maximum length before truncation

        Returns:
            Truncated description
        """
        if not description:
            return ""

        if len(description) <= max_length:
            return description

        return description[:max_length].rsplit(" ", 1)[0] + "..."

    def _format_size(self, bytes_value: int) -> str:
        """Format file size in bytes to human-readable string.

        Args:
            bytes_value: Size in bytes

        Returns:
            Formatted string like "X MB" or "X GB"
        """
        return self.format_filesize(bytes_value)
