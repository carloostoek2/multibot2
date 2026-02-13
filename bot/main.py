"""Main module for the Telegram bot."""
import logging
import signal
import sys

# Import config first (before logging setup to use LOG_LEVEL)
from bot.config import config

# Configure logging based on config
# Validate log level and fallback to INFO if invalid
valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
if config.LOG_LEVEL.upper() not in valid_levels:
    print(f"Warning: Invalid LOG_LEVEL '{config.LOG_LEVEL}'. Using INFO.", file=sys.stderr)
    log_level = logging.INFO
else:
    log_level = getattr(logging, config.LOG_LEVEL.upper())

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=log_level
)
logger = logging.getLogger(__name__)
logger.info(f"Logging configured at level: {config.LOG_LEVEL}")

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import (
    start, handle_video, handle_convert_command, handle_extract_audio_command,
    handle_split_command, handle_join_start, handle_join_done, handle_join_cancel
)
from bot.error_handler import error_handler
from bot.temp_manager import active_temp_managers


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully.

    Cleans up any active temp managers before exiting to prevent
    orphaned temporary directories.
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name} ({signum}), shutting down gracefully...")

    # Cleanup any active temp managers
    cleanup_count = 0
    for temp_mgr in list(active_temp_managers):
        try:
            temp_mgr.cleanup()
            cleanup_count += 1
        except Exception as e:
            logger.warning(f"Error during temp manager cleanup: {e}")

    if cleanup_count > 0:
        logger.info(f"Cleaned up {cleanup_count} active temp managers")

    logger.info("Shutdown complete")
    sys.exit(0)


def main() -> None:
    """Start the bot."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    logger.info("Signal handlers registered for graceful shutdown")

    # Create the Application and pass it your bot's token
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("convert", handle_convert_command))
    application.add_handler(CommandHandler("extract_audio", handle_extract_audio_command))
    application.add_handler(CommandHandler("split", handle_split_command))
    application.add_handler(CommandHandler("join", handle_join_start))
    application.add_handler(CommandHandler("done", handle_join_done))
    application.add_handler(CommandHandler("cancel", handle_join_cancel))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))

    # Add global error handler
    application.add_error_handler(error_handler)
    logger.info("Error handler registered")

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
