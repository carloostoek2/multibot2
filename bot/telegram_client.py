"""Telegram Application builder with optional Local Bot API support."""
import logging

from telegram.ext import Application, ApplicationBuilder

from bot.config import config

logger = logging.getLogger(__name__)


def derive_file_base_url(api_base_url: str) -> str:
    """Derive the Bot API file URL from the bot API base URL."""
    base = api_base_url.rstrip("/")
    if base.endswith("/bot"):
        return f"{base[:-4]}/file/bot"
    return f"{base}/file/bot"


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
        file_base_url = config.TELEGRAM_API_FILE_BASE_URL or derive_file_base_url(
            config.TELEGRAM_API_BASE_URL
        )
        builder = (
            builder.base_url(config.TELEGRAM_API_BASE_URL)
            .base_file_url(file_base_url)
            .local_mode(True)
            .connect_timeout(config.TELEGRAM_API_TIMEOUT)
            .read_timeout(config.TELEGRAM_API_TIMEOUT)
            .write_timeout(config.TELEGRAM_API_TIMEOUT)
            .pool_timeout(config.TELEGRAM_API_TIMEOUT)
        )
        logger.info(
            "Local Bot API enabled: base_url=%s, file_base_url=%s, max_upload=%dMB, timeout=%ss",
            config.TELEGRAM_API_BASE_URL,
            file_base_url,
            config.TELEGRAM_MAX_UPLOAD_SIZE_MB,
            config.TELEGRAM_API_TIMEOUT,
        )
    else:
        logger.info(
            "Using Telegram cloud API (max upload: %dMB)",
            config.TELEGRAM_MAX_UPLOAD_SIZE_MB,
        )

    return builder.build()


__all__ = ["create_application", "derive_file_base_url"]