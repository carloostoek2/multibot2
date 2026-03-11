"""Shared types and data classes for the downloaders package.

This module contains data classes that are shared across multiple modules
to avoid circular import issues.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DownloadResult:
    """Result of a download operation.

    Supports both single file downloads (via file_path) and multiple
    file downloads (via file_paths), such as Instagram carousel posts.

    Attributes:
        success: Whether the download completed successfully
        file_path: Path to the downloaded file (if single file)
        file_paths: List of paths for multi-file downloads (e.g., Instagram carousel)
        error_message: Error description (if failed)
        metadata: Additional metadata about the download (title, duration, etc.)
        is_multi_file: Whether this result contains multiple files
    """
    success: bool
    file_path: Optional[str] = None
    file_paths: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Optional[dict] = None

    @property
    def is_multi_file(self) -> bool:
        """Check if this result contains multiple files."""
        return len(self.file_paths) > 0

    def get_all_files(self) -> list[str]:
        """Get all file paths (works for both single and multi-file)."""
        if self.file_paths:
            return self.file_paths
        elif self.file_path:
            return [self.file_path]
        return []

    def __post_init__(self):
        """Ensure backwards compatibility - sync file_path with file_paths."""
        # If file_path is set but not in file_paths, add it
        if self.file_path and self.file_path not in self.file_paths:
            self.file_paths.insert(0, self.file_path)
        # If only file_paths has items, set file_path to first one
        elif self.file_paths and not self.file_path:
            object.__setattr__(self, 'file_path', self.file_paths[0])
