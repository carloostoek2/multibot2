"""Telegram bot handlers for video processing."""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.temp_manager import TempManager
from bot.video_processor import VideoProcessor

logger = logging.getLogger(__name__)


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

    # Use TempManager as context manager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Get video from message
            video = update.message.video

            # Generate safe filenames
            input_filename = f"input_{user_id}_{video.file_unique_id}.mp4"
            output_filename = f"output_{user_id}_{video.file_unique_id}.mp4"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download video to temp file
            logger.info(f"Downloading video from user {user_id}")
            file = await video.get_file()
            await file.download_to_drive(input_path)
            logger.info(f"Video downloaded to {input_path}")

            # Process video
            logger.info(f"Processing video for user {user_id}")
            success = VideoProcessor.process_video(str(input_path), str(output_path))

            if not success:
                logger.error(f"Video processing failed for user {user_id}")
                await update.message.reply_text(
                    "Lo siento, no pude procesar el video. "
                    "Asegúrate de que sea un video válido."
                )
                return

            # Send as video note
            logger.info(f"Sending video note to user {user_id}")
            with open(output_path, "rb") as video_file:
                await update.message.reply_video_note(video=video_file)

            logger.info(f"Video note sent successfully to user {user_id}")

        except Exception as e:
            logger.exception(f"Error processing video for user {user_id}: {e}")
            await update.message.reply_text(
                "Ocurrió un error al procesar el video. "
                "Por favor intenta con otro video."
            )
        # TempManager cleanup happens automatically on context exit


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
