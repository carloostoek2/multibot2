"""Telegram bot handlers for video processing."""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.temp_manager import TempManager
from bot.video_processor import VideoProcessor
from bot.format_processor import FormatConverter, AudioExtractor
from bot.split_processor import VideoSplitter
from bot.error_handler import (
    DownloadError,
    FFmpegError,
    ProcessingTimeoutError,
    FormatConversionError,
    AudioExtractionError,
    VideoSplitError,
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
        "El video debe ser de máximo 60 segundos.\n\n"
        "Comandos disponibles:\n"
        "/convert <formato> - Convierte un video a otro formato (mp4, avi, mov, mkv, webm)\n"
        "/extract_audio <formato> - Extrae el audio de un video (mp3, aac, wav, ogg)"
    )


async def _get_video_from_message(update: Update) -> tuple:
    """Extract video object and file info from message.

    Args:
        update: Telegram update object

    Returns:
        Tuple of (video_object, is_reply) or (None, False) if no video found
    """
    # Check if the message itself has a video
    if update.message.video:
        return update.message.video, False

    # Check if it's a reply to a video
    if update.message.reply_to_message and update.message.reply_to_message.video:
        return update.message.reply_to_message.video, True

    return None, False


async def handle_convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /convert command to convert video to different format.

    Usage: /convert <formato> (when replying to a video or with video attached)

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Convert command received from user {user_id}")

    # Get video from message or reply
    video, is_reply = await _get_video_from_message(update)

    if not video:
        await update.message.reply_text(
            "Por favor envía un video o responde a un video con /convert <formato>\n"
            "Formatos soportados: mp4, avi, mov, mkv, webm"
        )
        return

    # Parse format from command arguments
    args = context.args
    if not args:
        await update.message.reply_text(
            "Por favor especifica el formato de salida.\n"
            "Ejemplo: /convert mov\n"
            "Formatos soportados: mp4, avi, mov, mkv, webm"
        )
        return

    output_format = args[0].lower().lstrip(".")
    supported_formats = FormatConverter.get_supported_formats()

    if output_format not in supported_formats:
        await update.message.reply_text(
            f"Formato no soportado: {output_format}\n"
            f"Formatos soportados: {', '.join(supported_formats)}"
        )
        return

    # Send processing message
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            f"Convirtiendo video a {output_format.upper()}..."
        )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{video.file_unique_id}.mp4"
            output_filename = f"output_{user_id}_{video.file_unique_id}.{output_format}"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download video
            logger.info(f"Downloading video from user {user_id} for format conversion")
            try:
                file = await video.get_file()
                await file.download_to_drive(input_path)
                logger.info(f"Video downloaded to {input_path}")
            except Exception as e:
                logger.error(f"Failed to download video for user {user_id}: {e}")
                raise DownloadError("No pude descargar el video") from e

            # Convert video with timeout
            logger.info(f"Converting video to {output_format} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = FormatConverter(str(input_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.convert, output_format),
                    timeout=PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"Format conversion failed for user {user_id}")
                    raise FormatConversionError(f"No pude convertir el video a {output_format.upper()}")

            except asyncio.TimeoutError as e:
                logger.error(f"Format conversion timed out for user {user_id}")
                raise ProcessingTimeoutError("La conversión tardó demasiado") from e

            # Send converted video
            logger.info(f"Sending converted video to user {user_id}")
            try:
                with open(output_path, "rb") as video_file:
                    await update.message.reply_video(video=video_file)
                logger.info(f"Converted video sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send converted video to user {user_id}: {e}")
                raise

            # Delete processing message on success
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except (DownloadError, FormatConversionError, ProcessingTimeoutError) as e:
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error converting video for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")


async def handle_extract_audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /extract_audio command to extract audio from video.

    Usage: /extract_audio <formato> (when replying to a video or with video attached)

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Extract audio command received from user {user_id}")

    # Get video from message or reply
    video, is_reply = await _get_video_from_message(update)

    if not video:
        await update.message.reply_text(
            "Por favor envía un video o responde a un video con /extract_audio <formato>\n"
            "Formatos soportados: mp3, aac, wav, ogg"
        )
        return

    # Parse format from command arguments (default to mp3)
    args = context.args
    output_format = args[0].lower().lstrip(".") if args else "mp3"
    supported_formats = AudioExtractor.get_supported_formats()

    if output_format not in supported_formats:
        await update.message.reply_text(
            f"Formato no soportado: {output_format}\n"
            f"Formatos soportados: {', '.join(supported_formats)}"
        )
        return

    # Send processing message
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            f"Extrayendo audio como {output_format.upper()}..."
        )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{video.file_unique_id}.mp4"
            output_filename = f"audio_{user_id}_{video.file_unique_id}.{output_format}"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download video
            logger.info(f"Downloading video from user {user_id} for audio extraction")
            try:
                file = await video.get_file()
                await file.download_to_drive(input_path)
                logger.info(f"Video downloaded to {input_path}")
            except Exception as e:
                logger.error(f"Failed to download video for user {user_id}: {e}")
                raise DownloadError("No pude descargar el video") from e

            # Extract audio with timeout
            logger.info(f"Extracting audio as {output_format} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                extractor = AudioExtractor(str(input_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, extractor.extract, output_format),
                    timeout=PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"Audio extraction failed for user {user_id}")
                    raise AudioExtractionError(f"No pude extraer el audio en formato {output_format.upper()}")

            except asyncio.TimeoutError as e:
                logger.error(f"Audio extraction timed out for user {user_id}")
                raise ProcessingTimeoutError("La extracción de audio tardó demasiado") from e

            # Send extracted audio
            logger.info(f"Sending extracted audio to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await update.message.reply_audio(audio=audio_file)
                logger.info(f"Audio sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send audio to user {user_id}: {e}")
                raise

            # Delete processing message on success
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except (DownloadError, AudioExtractionError, ProcessingTimeoutError) as e:
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error extracting audio for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")
