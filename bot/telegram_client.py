"""Telegram Application builder with optional Local Bot API support."""
import asyncio
import logging
import re
from typing import Any, Awaitable, Optional

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, BaseUpdateProcessor

from bot.config import config

logger = logging.getLogger(__name__)

# Max updates processed at once. Waiting handlers are cheap (an IG link queued on
# the download gate just awaits), so the cap must be well above the number of
# links Juan sends in one go or queued downloads would exhaust it and block the
# bot again. Heavy CPU work is separately bounded by the default thread pool
# (min(32, cpu+4) = 6 workers on the 2-vCPU EC2).
DEFAULT_CONCURRENT_UPDATES = 32

_URL_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
# Commands that start downloads (may wait minutes) stay out of the per-user lane.
_CONCURRENT_COMMANDS = frozenset({"download", "downloads"})


def _per_user_lane_key(update: Any) -> Optional[tuple]:
    """Return a (chat_id, user_id) key if this update must keep per-user order.

    Messages (media uploads, session commands like /done, plain-text session
    answers such as screenshot timestamps) are processed in arrival order per
    user, as before. Exempt (fully concurrent): callback queries (buttons, incl.
    screenshots), text containing a URL (download flows) and /download.
    """
    message = getattr(update, "message", None) or getattr(update, "edited_message", None)
    if message is None:
        return None
    text = getattr(message, "text", None) or ""
    if isinstance(text, str) and text:
        if _URL_RE.search(text):
            return None
        if text.startswith("/"):
            command = text[1:].split(maxsplit=1)[0].split("@", 1)[0].lower() if len(text) > 1 else ""
            if command in _CONCURRENT_COMMANDS:
                return None
    chat = getattr(update, "effective_chat", None)
    user = getattr(update, "effective_user", None)
    return (getattr(chat, "id", None), getattr(user, "id", None))


class PerUserOrderedUpdateProcessor(BaseUpdateProcessor):
    """Concurrent update processor that keeps per-user order for messages.

    Long download handlers (URL messages, download buttons) no longer block
    other updates, while uploads/session messages of one user still run one at
    a time in arrival order (join/album/image-group sessions rely on that).
    """

    def __init__(self, max_concurrent_updates: int):
        super().__init__(max_concurrent_updates)
        # key -> [lock, refcount]; entries are dropped when no update uses them.
        self._lanes: dict = {}

    async def do_process_update(self, update: object, coroutine: Awaitable[Any]) -> None:
        key = _per_user_lane_key(update)
        if key is None:
            await coroutine
            return
        lane = self._lanes.setdefault(key, [asyncio.Lock(), 0])
        lane[1] += 1
        try:
            async with lane[0]:
                await coroutine
        finally:
            lane[1] -= 1
            if lane[1] == 0 and self._lanes.get(key) is lane:
                del self._lanes[key]

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


async def _log_connected_bot(application: Application) -> None:
    """Log the bot identity after connecting to Telegram."""
    me = await application.bot.get_me()
    username = f"@{me.username}" if me.username else "(sin username)"
    logger.info("Connected to Telegram bot: %s (%s, id=%s)", me.first_name, username, me.id)


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
    timeout = config.TELEGRAM_API_TIMEOUT
    # PTB defaults media_write_timeout to 20s; large video uploads need more headroom.
    media_timeout = max(timeout, 120.0)

    builder = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .connect_timeout(timeout)
        .read_timeout(timeout)
        .write_timeout(timeout)
        .pool_timeout(timeout)
        .media_write_timeout(media_timeout)
    )

    if config.TELEGRAM_LOCAL_MODE:
        file_base_url = config.TELEGRAM_API_FILE_BASE_URL or derive_file_base_url(
            config.TELEGRAM_API_BASE_URL
        )
        builder = (
            builder.base_url(config.TELEGRAM_API_BASE_URL)
            .base_file_url(file_base_url)
            .local_mode(True)
        )
        logger.info(
            "Local Bot API enabled: base_url=%s, file_base_url=%s, max_upload=%dMB, timeout=%ss, media_timeout=%ss",
            config.TELEGRAM_API_BASE_URL,
            file_base_url,
            config.TELEGRAM_MAX_UPLOAD_SIZE_MB,
            timeout,
            media_timeout,
        )
    else:
        logger.info(
            "Using Telegram cloud API (max upload: %dMB, timeout=%ss, media_timeout=%ss)",
            config.TELEGRAM_MAX_UPLOAD_SIZE_MB,
            timeout,
            media_timeout,
        )

    concurrency = int(getattr(config, "TELEGRAM_CONCURRENT_UPDATES", DEFAULT_CONCURRENT_UPDATES))
    builder = builder.concurrent_updates(PerUserOrderedUpdateProcessor(concurrency))
    logger.info("Concurrent update processing enabled (max %d, per-user ordered messages)", concurrency)

    return builder.post_init(_log_connected_bot).build()


__all__ = ["create_application", "derive_file_base_url"]