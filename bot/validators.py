"""Video validation module for the Telegram bot.

Provides validation functions to fail fast on invalid or problematic videos
before processing. Validates file size, video integrity, and disk space.
"""
import logging
import os
import shutil
import subprocess
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised when video validation fails."""

    def __init__(self, message: str = "El archivo no es válido"):
        self.message = message
        super().__init__(self.message)


def validate_file_size(file_size_bytes: int, max_size_mb: int) -> Tuple[bool, Optional[str]]:
    """Validate that file size is within acceptable limits.

    Args:
        file_size_bytes: Size of the file in bytes
        max_size_mb: Maximum allowed size in megabytes

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file size is acceptable, False otherwise
        - error_message: None if valid, Spanish error message if invalid
    """
    max_size_bytes = max_size_mb * 1024 * 1024

    logger.debug(f"Validating file size: {file_size_bytes} bytes (max: {max_size_bytes} bytes)")

    if file_size_bytes > max_size_bytes:
        error_msg = f"El archivo es demasiado grande (máximo {max_size_mb}MB)"
        logger.warning(f"File size validation failed: {file_size_bytes} bytes > {max_size_bytes} bytes")
        return False, error_msg

    logger.debug("File size validation passed")
    return True, None


def validate_video_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """Validate video file integrity using ffprobe.

    Checks that the file exists, is not empty, and has valid video streams
    with a positive duration.

    Args:
        file_path: Path to the video file to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if video is valid, False otherwise
        - error_message: None if valid, Spanish error message if invalid
    """
    logger.debug(f"Validating video file: {file_path}")

    # Check file exists
    if not os.path.exists(file_path):
        logger.warning(f"Video file does not exist: {file_path}")
        return False, "El archivo de video no existe"

    # Check file is not empty
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        logger.warning(f"Video file is empty: {file_path}")
        return False, "El archivo de video está vacío"

    # Use ffprobe to validate video integrity
    try:
        # Get video duration and check for video stream
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1",
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.warning(f"ffprobe failed for {file_path}: {result.stderr}")
            return False, "El archivo de video parece estar corrupto"

        # Parse duration from output
        duration = None
        for line in result.stdout.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                if key.strip() == 'duration' and value.strip():
                    try:
                        duration = float(value.strip())
                        break
                    except ValueError:
                        continue

        if duration is None or duration <= 0:
            logger.warning(f"Invalid video duration for {file_path}: {duration}")
            return False, "El archivo de video parece estar corrupto"

        # Check for video stream existence
        stream_result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if stream_result.returncode != 0 or 'video' not in stream_result.stdout.lower():
            logger.warning(f"No video stream found in {file_path}")
            return False, "El archivo de video parece estar corrupto"

        logger.debug(f"Video validation passed for {file_path} (duration: {duration:.2f}s)")
        return True, None

    except FileNotFoundError:
        # ffprobe not available - log warning but don't fail
        logger.warning("ffprobe not found, skipping video integrity validation")
        return True, None
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out for {file_path}")
        return False, "El archivo de video parece estar corrupto"
    except Exception as e:
        logger.warning(f"Error validating video {file_path}: {e}")
        return False, "El archivo de video parece estar corrupto"


def check_disk_space(required_mb: int, path: str = "/") -> Tuple[bool, Optional[str]]:
    """Check if sufficient disk space is available.

    Args:
        required_mb: Required space in megabytes
        path: Path to check disk space for (default: root)

    Returns:
        Tuple of (has_space, error_message)
        - has_space: True if enough space available, False otherwise
        - error_message: None if enough space, Spanish error message if not
    """
    logger.debug(f"Checking disk space: required {required_mb}MB on {path}")

    try:
        # Get disk usage statistics
        stat = os.statvfs(path)

        # Calculate available space in MB
        # f_frsize * f_bavail gives available bytes for non-superuser
        available_bytes = stat.f_frsize * stat.f_bavail
        available_mb = available_bytes / (1024 * 1024)

        logger.debug(f"Available disk space: {available_mb:.2f}MB (required: {required_mb}MB)")

        if available_mb < required_mb:
            logger.warning(f"Insufficient disk space: {available_mb:.2f}MB < {required_mb}MB")
            return False, "Espacio insuficiente en disco"

        return True, None

    except Exception as e:
        # If we can't check disk space, log warning but don't fail
        logger.warning(f"Could not check disk space on {path}: {e}")
        return True, None


def estimate_required_space(video_file_size_mb: int) -> int:
    """Estimate required disk space for video processing.

    Processing typically requires:
    - Original file size (for input)
    - Output file size (similar to input)
    - Temporary files during processing
    - Safety buffer

    Args:
        video_file_size_mb: Size of the video file in megabytes

    Returns:
        Estimated required space in megabytes
    """
    # 2x for input + output + 100MB buffer for temp files
    required = (video_file_size_mb * 2) + 100
    logger.debug(f"Estimated required space: {required}MB for {video_file_size_mb}MB video")
    return required


__all__ = [
    "ValidationError",
    "validate_file_size",
    "validate_video_file",
    "check_disk_space",
    "estimate_required_space",
]
