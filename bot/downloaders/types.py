"""Shared types and data classes for the downloaders package.

This module contains data classes that are shared across multiple modules
to avoid circular import issues.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class DownloadResult:
    """Result of a download operation.

    Attributes:
        success: Whether the download completed successfully
        file_path: Path to the downloaded file (if successful)
        error_message: Error description (if failed)
        metadata: Additional metadata about the download (title, duration, etc.)
    """
    success: bool
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[dict] = None
