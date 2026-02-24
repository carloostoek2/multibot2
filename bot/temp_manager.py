"""Temporary file manager for video processing."""
import glob
import os
import shutil
import tempfile
import time
import logging
import uuid
from pathlib import Path
from typing import List, Set, Optional

logger = logging.getLogger(__name__)

# Global set to track active TempManager instances
active_temp_managers: Set['TempManager'] = set()

# Global registry of temp directories by correlation_id
_download_temp_dirs: dict[str, str] = {}


class TempManager:
    """Manages temporary directories and files for video processing.

    Provides automatic cleanup via context manager protocol.
    Supports multi-file session tracking and subdirectory creation.
    Supports correlation_id for download-specific temp directories.
    """

    def __init__(self, correlation_id: Optional[str] = None):
        """Create a unique temporary directory.

        Args:
            correlation_id: Optional ID for download-specific temp directory.
                If provided, the directory name will include this ID.
        """
        self.correlation_id = correlation_id

        if correlation_id:
            # Crear directorio con correlation_id en el nombre
            prefix = f"videonote_{correlation_id}_"
            self.temp_dir = tempfile.mkdtemp(prefix=prefix)
            # Registrar en el mapa global
            _download_temp_dirs[correlation_id] = self.temp_dir
            logger.debug(f"Created temp directory with correlation_id: {self.temp_dir}")
        else:
            # Crear directorio normal
            self.temp_dir = tempfile.mkdtemp(prefix="videonote_")
            logger.debug(f"Created temp directory: {self.temp_dir}")

        self._tracked_files: List[str] = []

        # Register in active managers set
        active_temp_managers.add(self)

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
        # Unregister from active managers
        try:
            active_temp_managers.discard(self)
        except Exception:
            pass

        # Unregister from correlation_id map if applicable
        if self.correlation_id and self.correlation_id in _download_temp_dirs:
            try:
                del _download_temp_dirs[self.correlation_id]
            except Exception:
                pass

        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.debug(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Could not fully clean up temp directory {self.temp_dir}: {e}")
        self._tracked_files.clear()

    @classmethod
    def get_download_temp_dir(cls, correlation_id: str) -> str:
        """Create temp directory specifically for a download.

        Args:
            correlation_id: Unique identifier for the download

        Returns:
            Path to the created directory
        """
        # Check if already exists
        if correlation_id in _download_temp_dirs:
            return _download_temp_dirs[correlation_id]

        # Create new directory
        prefix = f"videonote_dl_{correlation_id}_"
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        _download_temp_dirs[correlation_id] = temp_dir

        logger.debug(f"Created download temp directory: {temp_dir}")
        return temp_dir

    @classmethod
    def cleanup_by_correlation_id(cls, correlation_id: str) -> bool:
        """Find and cleanup temp directory by correlation_id.

        Args:
            correlation_id: ID to search for

        Returns:
            True if found and cleaned, False otherwise
        """
        cleaned = False

        # Check registered directories first
        if correlation_id in _download_temp_dirs:
            dir_path = _download_temp_dirs[correlation_id]
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
                    logger.info(f"Cleaned up temp directory by correlation_id: {dir_path}")
                del _download_temp_dirs[correlation_id]
                cleaned = True
            except Exception as e:
                logger.warning(f"Error cleaning up {dir_path}: {e}")

        # Search for any matching directories in temp
        temp_dir = tempfile.gettempdir()
        pattern = os.path.join(temp_dir, f"videonote_*{correlation_id}*")

        for dir_path in glob.glob(pattern):
            try:
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
                    logger.info(f"Cleaned up matching temp directory: {dir_path}")
                    cleaned = True
            except Exception as e:
                logger.warning(f"Error cleaning up {dir_path}: {e}")

        return cleaned

    @classmethod
    def list_active_downloads(cls) -> List[str]:
        """Return list of correlation_ids for active downloads.

        Scans temp directories for videonote_dl_* pattern
        and extracts correlation_ids from directory names.

        Returns:
            List of correlation_ids
        """
        correlation_ids = []
        temp_dir = tempfile.gettempdir()

        # Buscar directorios de descarga
        pattern = os.path.join(temp_dir, "videonote_dl_*")

        for dir_path in glob.glob(pattern):
            try:
                if os.path.isdir(dir_path):
                    # Extraer correlation_id del nombre
                    # Formato: videonote_dl_{correlation_id}_{random}
                    dir_name = os.path.basename(dir_path)
                    parts = dir_name.split("_")
                    if len(parts) >= 3 and parts[2]:
                        correlation_ids.append(parts[2])
            except Exception as e:
                logger.debug(f"Error parsing directory name {dir_path}: {e}")

        # También incluir los registrados
        for cid in _download_temp_dirs.keys():
            if cid not in correlation_ids:
                correlation_ids.append(cid)

        return correlation_ids

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - always cleanup."""
        self.cleanup()
        return False  # Don't suppress exceptions


def cleanup_old_temp_directories(max_age_hours: int = 24) -> int:
    """Remove old temporary directories on startup.

    Scans for videonote_* directories in the system temp directory
    and removes those older than the specified age.

    Incluye directorios de descarga (videonote_dl_*) en la limpieza.

    Args:
        max_age_hours: Remove directories older than this many hours

    Returns:
        Number of directories removed
    """
    temp_dir = tempfile.gettempdir()

    # Buscar todos los patrones de videonote
    patterns = [
        os.path.join(temp_dir, "videonote_*"),
        os.path.join(temp_dir, "videonote_dl_*"),
    ]

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    removed_count = 0
    checked_dirs: set[str] = set()

    for pattern in patterns:
        for dir_path in glob.glob(pattern):
            # Evitar duplicados
            if dir_path in checked_dirs:
                continue
            checked_dirs.add(dir_path)

            try:
                dir_time = os.path.getctime(dir_path)
                age_seconds = current_time - dir_time

                if age_seconds > max_age_seconds:
                    # Intentar extraer correlation_id para logging
                    dir_name = os.path.basename(dir_path)
                    correlation_info = ""
                    if "videonote_dl_" in dir_name:
                        parts = dir_name.split("_")
                        if len(parts) >= 3:
                            correlation_info = f" (correlation_id: {parts[2]})"

                    shutil.rmtree(dir_path, ignore_errors=True)
                    removed_count += 1
                    logger.info(f"Removed old temp directory: {dir_path} (age: {age_seconds/3600:.1f} hours){correlation_info}")
            except Exception as e:
                logger.warning(f"Failed to check/remove old temp directory {dir_path}: {e}")

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old temporary directories")

    return removed_count


# Clean up old temp directories on module import (startup)
try:
    cleanup_old_temp_directories()
except Exception as e:
    logger.warning(f"Failed to cleanup old temp directories on startup: {e}")
