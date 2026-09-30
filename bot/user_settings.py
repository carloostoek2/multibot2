"""Per-user settings persisted on disk (survives bot restarts).

Mirrors the voice_refs pattern: files under data/ with an optional env override
for Railway Volumes.

Layout:
  data/user_settings/{user_id}.json
  or $USER_SETTINGS_DIR/{user_id}.json

Example file:
  {"album_auto_pipeline": true}
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_USER_SETTINGS_DIR = Path("data") / "user_settings"
ALBUM_AUTO_PIPELINE_KEY = "album_auto_pipeline"


def get_user_settings_root() -> Path:
    """Return the root directory for per-user settings JSON files.

    Honours USER_SETTINGS_DIR when set (e.g. /data/user_settings on a Railway
    Volume); otherwise uses data/user_settings relative to the process CWD.
    """
    raw = (os.getenv("USER_SETTINGS_DIR") or "").strip()
    return Path(raw) if raw else _DEFAULT_USER_SETTINGS_DIR


def get_user_settings_path(user_id: int) -> Path:
    """Return the JSON path for a Telegram user id."""
    return get_user_settings_root() / f"{int(user_id)}.json"


def _read_user_settings(user_id: int) -> dict[str, Any]:
    path = get_user_settings_path(user_id)
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        logger.warning("User settings for %s is not a JSON object; ignoring", user_id)
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read user settings for %s: %s", user_id, exc)
        return {}


def _write_user_settings(user_id: int, data: dict[str, Any]) -> None:
    root = get_user_settings_root()
    root.mkdir(parents=True, exist_ok=True)
    path = get_user_settings_path(user_id)
    # Atomic replace to avoid truncated files on crash mid-write
    fd, tmp_name = tempfile.mkstemp(prefix=f".{user_id}.", suffix=".json", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def get_album_auto_pipeline(user_id: int) -> bool:
    """Return whether album auto-pipeline is enabled for *user_id* (default OFF)."""
    data = _read_user_settings(user_id)
    return bool(data.get(ALBUM_AUTO_PIPELINE_KEY, False))


def set_album_auto_pipeline(user_id: int, enabled: bool) -> bool:
    """Persist album auto-pipeline preference for *user_id*. Returns new value."""
    enabled = bool(enabled)
    data = _read_user_settings(user_id)
    data[ALBUM_AUTO_PIPELINE_KEY] = enabled
    try:
        _write_user_settings(user_id, data)
    except OSError as exc:
        logger.error("Failed to persist album_auto_pipeline for %s: %s", user_id, exc)
        raise
    logger.info(
        "Persisted album_auto_pipeline=%s for user %s at %s",
        enabled,
        user_id,
        get_user_settings_path(user_id),
    )
    return enabled


__all__ = [
    "ALBUM_AUTO_PIPELINE_KEY",
    "get_user_settings_root",
    "get_user_settings_path",
    "get_album_auto_pipeline",
    "set_album_auto_pipeline",
]
