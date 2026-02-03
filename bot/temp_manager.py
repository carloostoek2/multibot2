"""Temporary file manager for video processing."""
import os
import shutil
import tempfile
import logging

logger = logging.getLogger(__name__)


class TempManager:
    """Manages temporary directories and files for video processing.

    Provides automatic cleanup via context manager protocol.
    """

    def __init__(self):
        """Create a unique temporary directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="videonote_")
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

    def cleanup(self):
        """Remove the temporary directory and all its contents.

        Handles cases where files might be locked or inaccessible.
        """
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Could not fully clean up temp directory {self.temp_dir}: {e}")

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - always cleanup."""
        self.cleanup()
        return False  # Don't suppress exceptions
