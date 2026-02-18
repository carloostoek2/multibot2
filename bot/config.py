"""Configuration module for the Telegram bot."""
import os
import sys
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass(frozen=True)
class BotConfig:
    """Bot configuration dataclass with validation.

    All configuration values are loaded from environment variables
    with sensible defaults. Validation occurs at initialization time
    to ensure fail-fast behavior on invalid configuration.
    """

    # Required
    BOT_TOKEN: str

    # Timeouts (seconds)
    PROCESSING_TIMEOUT: int = 60
    DOWNLOAD_TIMEOUT: int = 60
    JOIN_TIMEOUT: int = 120
    JOIN_SESSION_TIMEOUT: int = 300

    # Limits
    MAX_FILE_SIZE_MB: int = 20
    MAX_SEGMENTS: int = 10
    MIN_SEGMENT_SECONDS: int = 5
    JOIN_MAX_VIDEOS: int = 10
    JOIN_MIN_VIDEOS: int = 2

    # Audio configuration
    MAX_VOICE_DURATION_MINUTES: int = 20
    MAX_AUDIO_FILE_SIZE_MB: int = 20
    VOICE_BITRATE: str = "24k"
    MP3_BITRATE: str = "192k"

    # Audio split configuration
    MAX_AUDIO_SEGMENTS: int = 20
    MIN_AUDIO_SEGMENT_SECONDS: int = 5

    # Audio join configuration
    JOIN_MAX_AUDIO_FILES: int = 20
    JOIN_MIN_AUDIO_FILES: int = 2
    JOIN_AUDIO_TIMEOUT: int = 120

    # Logging
    LOG_LEVEL: str = "INFO"

    # Optional Paths
    TEMP_DIR: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        errors = []

        # Validate BOT_TOKEN
        if not self.BOT_TOKEN or not self.BOT_TOKEN.strip():
            errors.append("BOT_TOKEN is required and cannot be empty")

        # Validate timeout fields are positive
        timeout_fields = [
            ("PROCESSING_TIMEOUT", self.PROCESSING_TIMEOUT),
            ("DOWNLOAD_TIMEOUT", self.DOWNLOAD_TIMEOUT),
            ("JOIN_TIMEOUT", self.JOIN_TIMEOUT),
            ("JOIN_SESSION_TIMEOUT", self.JOIN_SESSION_TIMEOUT),
        ]
        for name, value in timeout_fields:
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{name} must be a positive integer (got: {value})")

        # Validate limit fields are positive
        limit_fields = [
            ("MAX_FILE_SIZE_MB", self.MAX_FILE_SIZE_MB),
            ("MAX_SEGMENTS", self.MAX_SEGMENTS),
            ("MIN_SEGMENT_SECONDS", self.MIN_SEGMENT_SECONDS),
            ("JOIN_MAX_VIDEOS", self.JOIN_MAX_VIDEOS),
            ("JOIN_MIN_VIDEOS", self.JOIN_MIN_VIDEOS),
            ("MAX_VOICE_DURATION_MINUTES", self.MAX_VOICE_DURATION_MINUTES),
            ("MAX_AUDIO_FILE_SIZE_MB", self.MAX_AUDIO_FILE_SIZE_MB),
        ]
        for name, value in limit_fields:
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{name} must be a positive integer (got: {value})")

        # Validate audio duration limit (max 20 minutes for Telegram)
        if self.MAX_VOICE_DURATION_MINUTES > 20:
            errors.append(
                f"MAX_VOICE_DURATION_MINUTES must be 20 or less (got: {self.MAX_VOICE_DURATION_MINUTES})"
            )

        # Validate audio split configuration
        audio_split_fields = [
            ("MAX_AUDIO_SEGMENTS", self.MAX_AUDIO_SEGMENTS),
            ("MIN_AUDIO_SEGMENT_SECONDS", self.MIN_AUDIO_SEGMENT_SECONDS),
        ]
        for name, value in audio_split_fields:
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{name} must be a positive integer (got: {value})")

        # Validate audio join configuration
        audio_join_fields = [
            ("JOIN_MAX_AUDIO_FILES", self.JOIN_MAX_AUDIO_FILES),
            ("JOIN_MIN_AUDIO_FILES", self.JOIN_MIN_AUDIO_FILES),
            ("JOIN_AUDIO_TIMEOUT", self.JOIN_AUDIO_TIMEOUT),
        ]
        for name, value in audio_join_fields:
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{name} must be a positive integer (got: {value})")

        # Validate JOIN_MIN_AUDIO_FILES < JOIN_MAX_AUDIO_FILES
        if self.JOIN_MIN_AUDIO_FILES >= self.JOIN_MAX_AUDIO_FILES:
            errors.append(
                f"JOIN_MIN_AUDIO_FILES ({self.JOIN_MIN_AUDIO_FILES}) must be less than "
                f"JOIN_MAX_AUDIO_FILES ({self.JOIN_MAX_AUDIO_FILES})"
            )

        # Validate JOIN_MIN_VIDEOS < JOIN_MAX_VIDEOS
        if self.JOIN_MIN_VIDEOS >= self.JOIN_MAX_VIDEOS:
            errors.append(
                f"JOIN_MIN_VIDEOS ({self.JOIN_MIN_VIDEOS}) must be less than "
                f"JOIN_MAX_VIDEOS ({self.JOIN_MAX_VIDEOS})"
            )

        # Validate LOG_LEVEL
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.LOG_LEVEL not in valid_log_levels:
            errors.append(
                f"LOG_LEVEL must be one of {valid_log_levels} (got: {self.LOG_LEVEL})"
            )

        # Raise if any validation errors
        if errors:
            raise ValueError(
                "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )


def load_config() -> BotConfig:
    """Load configuration from environment variables.

    Reads all configuration values from environment variables with
    sensible defaults. Performs type conversion where needed.

    Returns:
        BotConfig instance with validated configuration values.

    Raises:
        ValueError: If any configuration validation fails.
    """
    # Helper to parse int from env var
    def _int_env(name: str, default: int) -> int:
        value = os.getenv(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ValueError(
                f"{name} must be a valid integer (got: {value!r})"
            )

    return BotConfig(
        BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
        PROCESSING_TIMEOUT=_int_env("PROCESSING_TIMEOUT", 60),
        DOWNLOAD_TIMEOUT=_int_env("DOWNLOAD_TIMEOUT", 60),
        JOIN_TIMEOUT=_int_env("JOIN_TIMEOUT", 120),
        JOIN_SESSION_TIMEOUT=_int_env("JOIN_SESSION_TIMEOUT", 300),
        MAX_FILE_SIZE_MB=_int_env("MAX_FILE_SIZE_MB", 20),
        MAX_SEGMENTS=_int_env("MAX_SEGMENTS", 10),
        MIN_SEGMENT_SECONDS=_int_env("MIN_SEGMENT_SECONDS", 5),
        JOIN_MAX_VIDEOS=_int_env("JOIN_MAX_VIDEOS", 10),
        JOIN_MIN_VIDEOS=_int_env("JOIN_MIN_VIDEOS", 2),
        MAX_VOICE_DURATION_MINUTES=_int_env("MAX_VOICE_DURATION_MINUTES", 20),
        MAX_AUDIO_FILE_SIZE_MB=_int_env("MAX_AUDIO_FILE_SIZE_MB", 20),
        VOICE_BITRATE=os.getenv("VOICE_BITRATE", "24k"),
        MP3_BITRATE=os.getenv("MP3_BITRATE", "192k"),
        MAX_AUDIO_SEGMENTS=_int_env("MAX_AUDIO_SEGMENTS", 20),
        MIN_AUDIO_SEGMENT_SECONDS=_int_env("MIN_AUDIO_SEGMENT_SECONDS", 5),
        JOIN_MAX_AUDIO_FILES=_int_env("JOIN_MAX_AUDIO_FILES", 20),
        JOIN_MIN_AUDIO_FILES=_int_env("JOIN_MIN_AUDIO_FILES", 2),
        JOIN_AUDIO_TIMEOUT=_int_env("JOIN_AUDIO_TIMEOUT", 120),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        TEMP_DIR=os.getenv("TEMP_DIR") or None,
    )


# Global config instance
config = load_config()

__all__ = ["config", "BotConfig", "load_config"]
