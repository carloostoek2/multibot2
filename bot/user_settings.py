"""Per-user settings persisted on disk (survives bot restarts).

Mirrors the voice_refs pattern: files under data/ with an optional env override
for Railway Volumes.

Layout:
  data/user_settings/{user_id}.json
  or $USER_SETTINGS_DIR/{user_id}.json

Example file:
  {"album_auto_pipeline": true, "image_candid_preset": "medium",
   "image_candid_delivery": "document"}
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from bot.candid_engine import DEFAULT_PRESET as DEFAULT_CANDID_PRESET
from bot.candid_engine import PRESET_NAMES as CANDID_PRESET_NAMES

logger = logging.getLogger(__name__)

_DEFAULT_USER_SETTINGS_DIR = Path("data") / "user_settings"
ALBUM_AUTO_PIPELINE_KEY = "album_auto_pipeline"
IMAGE_CANDID_PRESET_KEY = "image_candid_preset"
IMAGE_CANDID_DELIVERY_KEY = "image_candid_delivery"

# document = PNG file (no Telegram recompression); photo = regular image.
CANDID_DELIVERY_MODES = ("document", "photo")
DEFAULT_CANDID_DELIVERY = "document"


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


def get_image_candid_preset(user_id: int) -> str:
    """Return the user's last «Fotográfico» preset (default: medium)."""
    data = _read_user_settings(user_id)
    value = data.get(IMAGE_CANDID_PRESET_KEY)
    return value if value in CANDID_PRESET_NAMES else DEFAULT_CANDID_PRESET


def set_image_candid_preset(user_id: int, preset: str) -> str:
    """Persist the «Fotográfico» preset for *user_id*. Returns the stored value."""
    if preset not in CANDID_PRESET_NAMES:
        raise ValueError(f"Preset fotográfico no soportado: {preset}")
    data = _read_user_settings(user_id)
    data[IMAGE_CANDID_PRESET_KEY] = preset
    try:
        _write_user_settings(user_id, data)
    except OSError as exc:
        logger.error("Failed to persist image_candid_preset for %s: %s", user_id, exc)
        raise
    logger.info(
        "Persisted image_candid_preset=%s for user %s at %s",
        preset,
        user_id,
        get_user_settings_path(user_id),
    )
    return preset


def get_image_candid_delivery(user_id: int) -> str:
    """Return how «Fotográfico» results are delivered: document or photo."""
    data = _read_user_settings(user_id)
    value = data.get(IMAGE_CANDID_DELIVERY_KEY)
    return value if value in CANDID_DELIVERY_MODES else DEFAULT_CANDID_DELIVERY


def set_image_candid_delivery(user_id: int, mode: str) -> str:
    """Persist the «Fotográfico» delivery mode for *user_id*."""
    if mode not in CANDID_DELIVERY_MODES:
        raise ValueError(f"Modo de entrega no soportado: {mode}")
    data = _read_user_settings(user_id)
    data[IMAGE_CANDID_DELIVERY_KEY] = mode
    try:
        _write_user_settings(user_id, data)
    except OSError as exc:
        logger.error("Failed to persist image_candid_delivery for %s: %s", user_id, exc)
        raise
    logger.info(
        "Persisted image_candid_delivery=%s for user %s at %s",
        mode,
        user_id,
        get_user_settings_path(user_id),
    )
    return mode


__all__ = [
    "ALBUM_AUTO_PIPELINE_KEY",
    "IMAGE_CANDID_PRESET_KEY",
    "IMAGE_CANDID_DELIVERY_KEY",
    "CANDID_DELIVERY_MODES",
    "DEFAULT_CANDID_DELIVERY",
    "get_user_settings_root",
    "get_user_settings_path",
    "get_album_auto_pipeline",
    "set_album_auto_pipeline",
    "get_image_candid_preset",
    "set_image_candid_preset",
    "get_image_candid_delivery",
    "set_image_candid_delivery",
]
