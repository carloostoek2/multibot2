"""Ephemeral download session tracking for user sessions.

This module provides session-based download tracking that is NOT persisted
to storage. Downloads are tracked only for the current session and are
lost when the session ends or the bot restarts.

Privacy-focused: No download history is stored permanently (INT-04 requirement).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class DownloadEntry:
    """Entry representing a single download in a session.

    Attributes:
        correlation_id: Unique identifier for the download
        url: Source URL that was downloaded
        file_path: Path to the downloaded file
        metadata: Additional metadata (title, platform, etc.)
        timestamp: When the download completed
        status: Download status (completed, failed, cancelled)
    """
    correlation_id: str
    url: str
    file_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "completed"  # completed, failed, cancelled

    def get_title(self) -> str:
        """Get display title from metadata."""
        return self.metadata.get('title', 'Unknown')

    def get_platform(self) -> str:
        """Get platform name from metadata."""
        return self.metadata.get('platform', 'Unknown')

    def time_ago(self) -> str:
        """Get human-readable time since download."""
        delta = datetime.now() - self.timestamp
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        else:
            return f"{seconds // 86400}d"


class DownloadSession:
    """Session-based ephemeral download tracking.

    Tracks downloads for a single user session. Downloads are stored in memory
    only and are not persisted. Maximum 5 recent downloads are kept (UI-06).

    Attributes:
        MAX_RECENT: Maximum number of downloads to track (5)
    """
    MAX_RECENT = 5

    def __init__(self):
        """Initialize empty download session."""
        self._downloads: Dict[str, DownloadEntry] = {}
        self._order: List[str] = []  # correlation_ids in FIFO order

    def add(self, entry: DownloadEntry) -> None:
        """Add a download entry to the session.

        If the maximum number of entries is exceeded, the oldest entry
        is removed (FIFO eviction).

        Args:
            entry: DownloadEntry to add
        """
        # Remove existing entry with same correlation_id (shouldn't happen)
        if entry.correlation_id in self._downloads:
            self._order.remove(entry.correlation_id)

        # Add new entry
        self._downloads[entry.correlation_id] = entry
        self._order.append(entry.correlation_id)

        # FIFO eviction if exceeding max
        while len(self._order) > self.MAX_RECENT:
            oldest_id = self._order.pop(0)
            removed = self._downloads.pop(oldest_id, None)
            if removed:
                logger.debug(f"Evicted oldest download from session: {oldest_id}")

        logger.debug(f"Added download to session: {entry.correlation_id}")

    def get_recent(self, n: int = 5) -> List[DownloadEntry]:
        """Get the n most recent downloads.

        Args:
            n: Number of entries to return (default 5, max 5)

        Returns:
            List of DownloadEntry objects, most recent first
        """
        n = min(n, self.MAX_RECENT)
        # Return in reverse order (most recent first)
        recent_ids = reversed(self._order[-n:])
        return [self._downloads[cid] for cid in recent_ids if cid in self._downloads]

    def get(self, correlation_id: str) -> Optional[DownloadEntry]:
        """Get a specific download entry by correlation ID.

        Args:
            correlation_id: The correlation ID to look up

        Returns:
            DownloadEntry if found, None otherwise
        """
        return self._downloads.get(correlation_id)

    def clear(self) -> None:
        """Clear all downloads from the session.

        This removes all tracked downloads. Files are NOT deleted;
        cleanup is handled by the download lifecycle.
        """
        count = len(self._downloads)
        self._downloads.clear()
        self._order.clear()
        logger.debug(f"Cleared {count} downloads from session")

    def remove(self, correlation_id: str) -> bool:
        """Remove a specific download entry.

        Args:
            correlation_id: The correlation ID to remove

        Returns:
            True if removed, False if not found
        """
        if correlation_id in self._downloads:
            del self._downloads[correlation_id]
            self._order.remove(correlation_id)
            logger.debug(f"Removed download from session: {correlation_id}")
            return True
        return False

    def __len__(self) -> int:
        """Return number of tracked downloads."""
        return len(self._downloads)

    def __contains__(self, correlation_id: str) -> bool:
        """Check if a correlation_id is tracked."""
        return correlation_id in self._downloads


def get_user_download_session(context) -> DownloadSession:
    """Get or create the download session for a user.

    Retrieves the DownloadSession from context.user_data, creating
    a new one if it doesn't exist.

    Args:
        context: Telegram context object with user_data

    Returns:
        DownloadSession instance for the user
    """
    if "download_session" not in context.user_data:
        context.user_data["download_session"] = DownloadSession()
        logger.debug("Created new download session for user")
    return context.user_data["download_session"]
