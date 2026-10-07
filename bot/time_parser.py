"""Parsing and formatting of user-supplied time values.

The bot asks users for cut points (split start/end) and for screenshot
timestamps. Both accept a bare number of seconds or a ``minutes:seconds``
pair, so the logic lives here instead of being duplicated per handler.

This module is intentionally dependency-free (no Telegram, no ``bot.config``)
so importing it never triggers ``load_config()``.
"""
import re
from typing import Optional, Tuple

# "1:24" / "2:34.5" / "0:05" -- minutes may be any length, seconds must be < 60.
_COLON_PATTERN = re.compile(r"^(\d+):(\d+(?:\.\d+)?)$")
# "30" / "30.5" / "-5" -- range checks (negatives, media duration) are the
# callers' job, so negative values are parsed and passed through.
_PLAIN_PATTERN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def parse_time_value(text: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """Parse a single time value entered by the user.

    Accepted formats:
    - Seconds only -> 30, 30.5, 90
    - Minutes and seconds -> 1:24 (84 s), 2:34.5 (154.5 s)

    A bare number is always seconds; only the colon switches to minutes and
    seconds. Hours are not supported: write 90:00 for an hour and a half.

    Args:
        text: Raw user input (may be missing or empty)

    Returns:
        Tuple of (seconds, error message). Exactly one of the two is None.
    """
    if text is None or not text.strip():
        return None, "No recibí ningún tiempo."

    raw = text.strip()

    if ':' in raw:
        if raw.count(':') > 1:
            return None, f"Formato inválido: {raw}. Usa M:SS o MM:SS"

        match = _COLON_PATTERN.match(raw)
        if not match:
            return None, f"No pude entender el tiempo: {raw}"

        minutes, seconds = match.groups()
        seconds_value = float(seconds)
        if seconds_value >= 60:
            return None, f"Los segundos deben ser menores a 60: {raw}"

        return int(minutes) * 60 + seconds_value, None

    if not _PLAIN_PATTERN.match(raw):
        return None, f"No pude entender el número: {raw}"

    return float(raw), None


def format_time(seconds: float) -> str:
    """Format a time value for display in user-facing messages.

    Keeps the unit the user typed: under a minute -> "45s" / "45.5s",
    a minute or more -> "1:24" / "2:34.5" / "90:00".

    Args:
        seconds: Time value in seconds

    Returns:
        Human-readable time string, rounded to tenths of a second
    """
    total = round(float(seconds), 1)

    if total < 60:
        return f"{total:g}s"

    minutes = int(total // 60)
    remainder = round(total - minutes * 60, 1)

    if remainder.is_integer():
        return f"{minutes}:{int(remainder):02d}"

    return f"{minutes}:{remainder:04.1f}"
