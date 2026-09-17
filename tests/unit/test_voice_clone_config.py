"""Tests for optional REPLICATE_API_TOKEN configuration."""
import os
from unittest.mock import patch

import pytest

from bot.config import BotConfig, load_config


class TestReplicateConfigOptional:
    def test_botconfig_accepts_missing_replicate_token(self):
        config = BotConfig(BOT_TOKEN="test-token")
        assert config.REPLICATE_API_TOKEN is None
        assert config.VOICE_CLONE_TIMEOUT == 180

    def test_botconfig_accepts_replicate_token(self):
        config = BotConfig(
            BOT_TOKEN="test-token",
            REPLICATE_API_TOKEN="r8_test_token",
            VOICE_CLONE_TIMEOUT=240,
        )
        assert config.REPLICATE_API_TOKEN == "r8_test_token"
        assert config.VOICE_CLONE_TIMEOUT == 240

    def test_load_config_optional_replicate_token(self):
        env = {
            "BOT_TOKEN": "test-token",
            "REPLICATE_API_TOKEN": "r8_from_env",
            "VOICE_CLONE_TIMEOUT": "200",
        }
        # Clear TELEGRAM_LOCAL_MODE etc. that may leak from other tests
        with patch.dict(os.environ, env, clear=False):
            # Ensure local mode from other tests doesn't break
            with patch.dict(
                os.environ,
                {
                    **env,
                    "TELEGRAM_LOCAL_MODE": "false",
                    "TELEGRAM_API_BASE_URL": "",
                },
                clear=False,
            ):
                config = load_config()
        assert config.REPLICATE_API_TOKEN == "r8_from_env"
        assert config.VOICE_CLONE_TIMEOUT == 200

    def test_load_config_without_replicate_token(self):
        with patch.dict(
            os.environ,
            {
                "BOT_TOKEN": "test-token",
                "TELEGRAM_LOCAL_MODE": "false",
            },
            clear=False,
        ):
            os.environ.pop("REPLICATE_API_TOKEN", None)
            config = load_config()
        assert config.REPLICATE_API_TOKEN is None
