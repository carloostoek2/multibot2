"""Tests for Local Bot API configuration."""
import os
from unittest.mock import patch

import pytest

from bot.config import (
    TELEGRAM_CLOUD_MAX_UPLOAD_MB,
    TELEGRAM_LOCAL_MAX_UPLOAD_MB,
    BotConfig,
    load_config,
)


class TestLocalApiConfig:
    """Validate Local Bot API configuration rules."""

    def test_cloud_mode_defaults(self):
        config = BotConfig(BOT_TOKEN="test-token")
        assert config.TELEGRAM_LOCAL_MODE is False
        assert config.TELEGRAM_MAX_UPLOAD_SIZE_MB == TELEGRAM_CLOUD_MAX_UPLOAD_MB
        assert config.telegram_max_upload_bytes == TELEGRAM_CLOUD_MAX_UPLOAD_MB * 1024 * 1024

    def test_local_mode_requires_base_url(self):
        with pytest.raises(ValueError, match="TELEGRAM_API_BASE_URL"):
            BotConfig(
                BOT_TOKEN="test-token",
                TELEGRAM_LOCAL_MODE=True,
            )

    def test_local_mode_accepts_valid_base_url(self):
        config = BotConfig(
            BOT_TOKEN="test-token",
            TELEGRAM_LOCAL_MODE=True,
            TELEGRAM_API_BASE_URL="http://127.0.0.1:8081/bot",
            TELEGRAM_MAX_UPLOAD_SIZE_MB=TELEGRAM_LOCAL_MAX_UPLOAD_MB,
            DOWNLOAD_MAX_SIZE_MB=TELEGRAM_LOCAL_MAX_UPLOAD_MB,
            DOWNLOAD_MAX_SIZE_GENERIC_MB=TELEGRAM_LOCAL_MAX_UPLOAD_MB,
        )
        assert config.TELEGRAM_LOCAL_MODE is True
        assert config.TELEGRAM_MAX_UPLOAD_SIZE_MB == 2000

    def test_cloud_mode_rejects_upload_over_50mb(self):
        with pytest.raises(ValueError, match="TELEGRAM_MAX_UPLOAD_SIZE_MB"):
            BotConfig(
                BOT_TOKEN="test-token",
                TELEGRAM_MAX_UPLOAD_SIZE_MB=100,
            )

    def test_local_mode_rejects_upload_over_2000mb(self):
        with pytest.raises(ValueError, match="TELEGRAM_MAX_UPLOAD_SIZE_MB"):
            BotConfig(
                BOT_TOKEN="test-token",
                TELEGRAM_LOCAL_MODE=True,
                TELEGRAM_API_BASE_URL="http://127.0.0.1:8081/bot",
                TELEGRAM_MAX_UPLOAD_SIZE_MB=3000,
            )

    @patch.dict(
        os.environ,
        {
            "BOT_TOKEN": "test-token",
            "TELEGRAM_LOCAL_MODE": "true",
            "TELEGRAM_API_BASE_URL": "http://127.0.0.1:8081/bot",
        },
        clear=True,
    )
    def test_load_config_local_mode_defaults(self):
        config = load_config()
        assert config.TELEGRAM_LOCAL_MODE is True
        assert config.TELEGRAM_API_BASE_URL == "http://127.0.0.1:8081/bot"
        assert config.TELEGRAM_MAX_UPLOAD_SIZE_MB == TELEGRAM_LOCAL_MAX_UPLOAD_MB
        assert config.DOWNLOAD_MAX_SIZE_MB == TELEGRAM_LOCAL_MAX_UPLOAD_MB