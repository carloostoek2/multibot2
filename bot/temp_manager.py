"""Temporary file manager for video processing."""
import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class TempManager:
    """Manages temporary directories and files for video processing.

    Provides automatic cleanup via context manager protocol.
    Supports multi-file session tracking and subdirectory creation.
    """

    def __init__(self):
        """Create a unique temporary directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="videonote_")
        self._tracked_files: List[str] = []
        logger.debug(f"Created temp directory: {self.temp_dir}")

    def get_temp_path(self, filename: str) -> str:
        """Get absolute path for a file in the temp directory.

        Args:
            filename: Name of the file (without directory components)

        Returns:
            Absolute path to the file in temp directory
        """
        # Ensure filename doesn't contain path separators
        safe_filename = os.path.basename(filename)
        return os.path.join(self.temp_dir, safe_filename)

    def get_subdir(self, subdir_name: str) -> str:
        """Create and return a subdirectory path within the temp directory.

        Useful for organizing multiple files in a session (e.g., join operations).
        The subdirectory will be cleaned up automatically when the temp directory
        is cleaned up.

        Args:
            subdir_name: Name of the subdirectory to create

        Returns:
            Absolute path to the created subdirectory
        """
        # Ensure subdir_name doesn't contain path separators
        safe_name = os.path.basename(subdir_name)
        subdir_path = os.path.join(self.temp_dir, safe_name)
        Path(subdir_path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created subdirectory: {subdir_path}")
        return subdir_path

    def track_file(self, file_path: str) -> None:
        """Track a file for reference during the session.

        Files are tracked for reference only - cleanup still happens via
        rmtree on the temp directory. This is useful for managing multiple
        files in operations like video joining.

        Args:
            file_path: Path to the file to track
        """
        if file_path not in self._tracked_files:
            self._tracked_files.append(file_path)
            logger.debug(f"Tracking file: {file_path}")

    def get_tracked_files(self) -> List[str]:
        """Get all tracked files.

        Returns:
            List of tracked file paths
        """
        return self._tracked_files.copy()

    def clear_tracked_files(self) -> None:
        """Clear the tracking list without deleting files.

        The files themselves are not deleted - only the tracking list is cleared.
        File cleanup happens via cleanup() or context manager exit.
        """
        count = len(self._tracked_files)
        self._tracked_files.clear()
        logger.debug(f"Cleared tracking list ({count} files)")

    def cleanup(self):
        """Remove the temporary directory and all its contents.

        Handles cases where files might be locked or inaccessible.
        Also clears the tracked files list.
        """
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Could not fully clean up temp directory {self.temp_dir}: {e}")
        self._tracked_files.clear()

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - always cleanup."""
        self.cleanup()
        return False  # Don't suppress exceptions
