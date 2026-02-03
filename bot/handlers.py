"""Telegram bot handlers for video processing."""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.temp_manager import TempManager
from bot.video_processor import VideoProcessor
from bot.error_handler import (
    DownloadError,
    FFmpegError,
    ProcessingTimeoutError,
    handle_processing_error,
)

logger = logging.getLogger(__name__)

# Timeout for video processing (60 seconds)
PROCESSING_TIMEOUT = 60


async def _process_video_with_timeout(
    update: Update,
    temp_mgr: TempManager,
    user_id: int
) -> None:
    """Process video with timeout handling.

    Internal function that handles the actual video processing
    with timeout and proper error handling.

    Args:
        update: Telegram update object
        temp_mgr: TempManager instance for file handling
        user_id: ID of the user sending the video

    Raises:
        DownloadError: If video download fails
        FFmpegError: If video processing fails
        ProcessingTimeoutError: If processing times out
    """
    # Get video from message
    video = update.message.video

    # Generate safe filenames
    input_filename = f"input_{user_id}_{video.file_unique_id}.mp4"
    output_filename = f"output_{user_id}_{video.file_unique_id}.mp4"

    input_path = temp_mgr.get_temp_path(input_filename)
    output_path = temp_mgr.get_temp_path(output_filename)

    # Download video to temp file
    logger.info(f"Downloading video from user {user_id}")
    try:
        file = await video.get_file()
        await file.download_to_drive(input_path)
        logger.info(f"Video downloaded to {input_path}")
    except Exception as e:
        logger.error(f"Failed to download video for user {user_id}: {e}")
        raise DownloadError("No pude descargar el video") from e

    # Process video with timeout
    logger.info(f"Processing video for user {user_id}")
    try:
        # Use asyncio.wait_for to enforce timeout
        loop = asyncio.get_event_loop()
        success = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                VideoProcessor.process_video,
                str(input_path),
                str(output_path)
            ),
            timeout=PROCESSING_TIMEOUT
        )

        if not success:
            logger.error(f"Video processing failed for user {user_id}")
            raise FFmpegError("El procesamiento de video falló")

    except asyncio.TimeoutError as e:
        logger.error(f"Video processing timed out for user {user_id}")
        raise ProcessingTimeoutError("El video tardó demasiado en procesarse") from e

    # Send as video note
    logger.info(f"Sending video note to user {user_id}")
    try:
        with open(output_path, "rb") as video_file:
            await update.message.reply_video_note(video_note=video_file)
        logger.info(f"Video note sent successfully to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send video note to user {user_id}: {e}")
        raise


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video messages by converting them to video notes.

    Downloads the video, processes it to 1:1 square format,
    and sends it back as a circular video note.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Video received from user {user_id}")

    # Send "processing" message to user
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            "Procesando tu video... "
        )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    # Use TempManager as context manager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            await _process_video_with_timeout(update, temp_mgr, user_id)

            # Delete processing message on success
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except (DownloadError, FFmpegError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            await handle_processing_error(update, e, user_id)

            # Delete processing message on error
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"Unexpected error processing video for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Delete processing message on error
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        # TempManager cleanup happens automatically on context exit (finally behavior)
        logger.debug(f"Cleanup completed for user {user_id}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await update.message.reply_text(
        "¡Hola! Envíame un video y lo convertiré en una nota de video circular. "
        "El video debe ser de máximo 60 segundos."
    )
