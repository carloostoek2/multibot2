"""Telegram Application builder with optional Local Bot API support."""
import logging

from telegram.ext import Application, ApplicationBuilder

from bot.config import config

logger = logging.getLogger(__name__)


def create_application() -> Application:
    """Create the Telegram Application, optionally using a local Bot API server.

    When TELEGRAM_LOCAL_MODE is enabled, the bot connects to a self-hosted
    telegram-bot-api instance instead of api.telegram.org. This unlocks:
    - Uploads up to 2000 MB
    - Downloads without size limits
    - Sending files via local filesystem paths
    """
    builder = ApplicationBuilder().token(config.BOT_TOKEN)

    if config.TELEGRAM_LOCAL_MODE:
        builder = (
            builder.base_url(config.TELEGRAM_API_BASE_URL)
            .local_mode(True)
            .connect_timeout(config.TELEGRAM_API_TIMEOUT)
            .read_timeout(config.TELEGRAM_API_TIMEOUT)
            .write_timeout(config.TELEGRAM_API_TIMEOUT)
            .pool_timeout(config.TELEGRAM_API_TIMEOUT)
        )
        logger.info(
            "Local Bot API enabled: base_url=%s, max_upload=%dMB, timeout=%ss",
            config.TELEGRAM_API_BASE_URL,
            config.TELEGRAM_MAX_UPLOAD_SIZE_MB,
            config.TELEGRAM_API_TIMEOUT,
        )
    else:
        logger.info(
            "Using Telegram cloud API (max upload: %dMB)",
            config.TELEGRAM_MAX_UPLOAD_SIZE_MB,
        )

    return builder.build()


__all__ = ["create_application"]