"""Telegram bot handlers for video processing."""
import asyncio
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import NetworkError, TimedOut

from bot.temp_manager import TempManager
from bot.video_processor import VideoProcessor
from bot.format_processor import FormatConverter, AudioExtractor
from bot.split_processor import VideoSplitter
from bot.join_processor import VideoJoiner
from bot.error_handler import (
    DownloadError,
    FFmpegError,
    ProcessingTimeoutError,
    FormatConversionError,
    AudioExtractionError,
    VideoSplitError,
    VideoJoinError,
    handle_processing_error,
)
from bot.config import config

logger = logging.getLogger(__name__)

async def _download_with_retry(file, destination_path: str, max_retries: int = 3) -> bool:
    """Download file with retry logic for transient failures.

    Args:
        file: Telegram file object to download
        destination_path: Path to save the file
        max_retries: Maximum number of retry attempts

    Returns:
        True if download succeeded

    Raises:
        NetworkError, TimedOut: If all retries exhausted
    """
    for attempt in range(max_retries):
        try:
            await file.download_to_drive(destination_path)
            return True
        except (NetworkError, TimedOut) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Download attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"Download failed after {max_retries} attempts: {e}")
                raise
    return False



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
        await _download_with_retry(file, input_path)
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
            timeout=config.PROCESSING_TIMEOUT
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
        "/extract_audio <formato> - Extrae el audio de un video (mp3, aac, wav, ogg)\n"
        "/split [duration|parts] <valor> - Divide un video en segmentos\n"
        "/join - Une múltiples videos en uno solo"
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
                await _download_with_retry(file, input_path)
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
                    timeout=config.PROCESSING_TIMEOUT
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
                await _download_with_retry(file, input_path)
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
                    timeout=config.PROCESSING_TIMEOUT
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


# Default segment duration for split command
DEFAULT_SEGMENT_DURATION = 60


async def handle_split_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /split command to split video into segments.

    Usage:
        /split duration <segundos> - Divide en segmentos de N segundos
        /split parts <cantidad> - Divide en N partes iguales
        /split (solo) - Divide en segmentos de 60 segundos

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Split command received from user {user_id}")

    # Get video from message or reply
    video, is_reply = await _get_video_from_message(update)

    if not video:
        await update.message.reply_text(
            "Responde a un video con este comando para dividirlo.\n\n"
            "Uso:\n"
            "/split duration 30 - Divide en segmentos de 30 segundos\n"
            "/split parts 5 - Divide en 5 partes iguales\n"
            "/split - Divide en segmentos de 60 segundos (default)"
        )
        return

    # Parse command arguments
    args = context.args if context.args else []

    split_mode = "duration"  # Default mode
    split_value = DEFAULT_SEGMENT_DURATION

    if len(args) >= 1:
        if args[0].lower() in ["duration", "duracion", "tiempo", "time"]:
            split_mode = "duration"
            if len(args) >= 2:
                try:
                    split_value = int(args[1])
                    if split_value < config.MIN_SEGMENT_SECONDS:
                        await update.message.reply_text(
                            f"La duración mínima es {config.MIN_SEGMENT_SECONDS} segundos."
                        )
                        return
                except ValueError:
                    await update.message.reply_text(
                        "Por favor especifica un número válido de segundos.\n"
                        "Ejemplo: /split duration 30"
                    )
                    return
        elif args[0].lower() in ["parts", "partes", "cantidad", "number"]:
            split_mode = "parts"
            if len(args) >= 2:
                try:
                    split_value = int(args[1])
                    if split_value < 1:
                        await update.message.reply_text(
                            "El número de partes debe ser al menos 1."
                        )
                        return
                    if split_value > config.MAX_SEGMENTS:
                        await update.message.reply_text(
                            f"El máximo de partes es {config.MAX_SEGMENTS}."
                        )
                        return
                except ValueError:
                    await update.message.reply_text(
                        "Por favor especifica un número válido de partes.\n"
                        "Ejemplo: /split parts 5"
                    )
                    return
            else:
                await update.message.reply_text(
                    "Por favor especifica cuántas partes quieres.\n"
                    "Ejemplo: /split parts 5"
                )
                return
        else:
            # Try to parse as a number (assume duration mode)
            try:
                split_value = int(args[0])
                if split_value < MIN_SEGMENT_DURATION:
                    await update.message.reply_text(
                        f"La duración mínima es {config.MIN_SEGMENT_SECONDS} segundos."
                    )
                    return
            except ValueError:
                await update.message.reply_text(
                    "Argumento no reconocido. Usa 'duration' o 'parts'.\n"
                    "Ejemplo: /split duration 30 o /split parts 5"
                )
                return

    # Send processing message
    processing_message = None
    try:
        if split_mode == "duration":
            processing_message = await update.message.reply_text(
                f"Dividiendo video en segmentos de {split_value} segundos..."
            )
        else:
            processing_message = await update.message.reply_text(
                f"Dividiendo video en {split_value} partes iguales..."
            )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{video.file_unique_id}.mp4"
            output_dir = temp_mgr.get_temp_path(f"split_{user_id}_{video.file_unique_id}")

            input_path = temp_mgr.get_temp_path(input_filename)

            # Download video
            logger.info(f"Downloading video from user {user_id} for splitting")
            try:
                file = await video.get_file()
                await _download_with_retry(file, input_path)
                logger.info(f"Video downloaded to {input_path}")
            except Exception as e:
                logger.error(f"Failed to download video for user {user_id}: {e}")
                raise DownloadError("No pude descargar el video") from e

            # Create output directory for segments
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Split video with timeout
            logger.info(f"Splitting video for user {user_id} (mode={split_mode}, value={split_value})")
            try:
                loop = asyncio.get_event_loop()
                splitter = VideoSplitter(str(input_path), str(output_dir))

                if split_mode == "duration":
                    # Check how many segments would be created
                    duration = await loop.run_in_executor(None, splitter.get_video_duration)
                    expected_segments = int(duration // split_value) + (1 if duration % split_value > 0 else 0)

                    if expected_segments > MAX_SEGMENTS:
                        await update.message.reply_text(
                            f"El video generaría demasiadas partes ({expected_segments}). "
                            f"Intenta con una duración mayor (máximo {config.MAX_SEGMENTS} partes)."
                        )
                        if processing_message:
                            try:
                                await processing_message.delete()
                            except Exception:
                                pass
                        return

                    segments = await asyncio.wait_for(
                        loop.run_in_executor(None, splitter.split_by_duration, split_value),
                        timeout=config.PROCESSING_TIMEOUT
                    )
                else:  # split_mode == "parts"
                    segments = await asyncio.wait_for(
                        loop.run_in_executor(None, splitter.split_by_parts, split_value),
                        timeout=config.PROCESSING_TIMEOUT
                    )

                    # Check if we got too many segments (shouldn't happen due to validation in split_by_parts)
                    if len(segments) > MAX_SEGMENTS:
                        await update.message.reply_text(
                            f"El video generaría demasiadas partes ({len(segments)}). "
                            f"Intenta con menos partes (máximo {config.MAX_SEGMENTS})."
                        )
                        if processing_message:
                            try:
                                await processing_message.delete()
                            except Exception:
                                pass
                        return

                if not segments:
                    logger.error(f"Video splitting produced no segments for user {user_id}")
                    raise VideoSplitError("No se generaron segmentos del video")

            except asyncio.TimeoutError as e:
                logger.error(f"Video splitting timed out for user {user_id}")
                raise ProcessingTimeoutError("La división del video tardó demasiado") from e

            # Send segments to user
            logger.info(f"Sending {len(segments)} segments to user {user_id}")
            total_segments = len(segments)

            for i, segment_path in enumerate(segments, 1):
                try:
                    # Update progress message
                    if processing_message:
                        try:
                            await processing_message.edit_text(
                                f"Enviando parte {i} de {total_segments}..."
                            )
                        except Exception as e:
                            logger.warning(f"Could not update progress message: {e}")

                    # Send segment
                    with open(segment_path, "rb") as video_file:
                        await update.message.reply_video(
                            video=video_file,
                            caption=f"Parte {i} de {total_segments}"
                        )
                    logger.info(f"Sent segment {i}/{total_segments} to user {user_id}")

                except Exception as e:
                    logger.error(f"Failed to send segment {i} to user {user_id}: {e}")
                    await update.message.reply_text(
                        f"Error enviando la parte {i} de {total_segments}."
                    )

            # Send completion message
            await update.message.reply_text(
                f"¡Listo! El video se dividió en {total_segments} partes."
            )
            logger.info(f"All segments sent successfully to user {user_id}")

            # Delete processing message on success
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except (DownloadError, VideoSplitError, ProcessingTimeoutError) as e:
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error splitting video for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")


# Note: Join command configuration now uses bot.config values


async def handle_join_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join command to start a video join session.

    Usage: /join - Start a session to collect videos for joining

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join command received from user {user_id}")

    # Check if there's already an active session
    if context.user_data.get("join_session"):
        await update.message.reply_text(
            "Ya tienes una sesión de unión activa. "
            f"Tienes {len(context.user_data['join_session']['videos'])} video(s) agregados.\n\n"
            "Envía más videos o usa /done para unir, /cancel para cancelar."
        )
        return

    # Initialize join session
    context.user_data["join_session"] = {
        "videos": [],
        "temp_mgr": TempManager(),
        "last_activity": asyncio.get_event_loop().time(),
    }

    await update.message.reply_text(
        "🎬 *Modo unión de videos activado*\n\n"
        "Envíame los videos que quieres unir (máximo 10).\n"
        "Los videos se unirán en el orden en que los envíes.\n\n"
        "Comandos disponibles:\n"
        "• /done - Unir todos los videos\n"
        "• /cancel - Cancelar la sesión\n\n"
        "Envía el primer video:",
        parse_mode="Markdown"
    )


async def handle_join_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video messages during an active join session.

    Downloads each video and tracks it in the user's join session.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id

    # Check if there's an active join session
    session = context.user_data.get("join_session")
    if not session:
        # No active session, let the default video handler process it
        await handle_video(update, context)
        return

    # Check session timeout
    current_time = asyncio.get_event_loop().time()
    if current_time - session["last_activity"] > config.JOIN_SESSION_TIMEOUT:
        logger.info(f"Join session expired for user {user_id}")
        # Clean up expired session
        session["temp_mgr"].cleanup()
        context.user_data.pop("join_session", None)
        await update.message.reply_text(
            "La sesión expiró. Usa /join para comenzar de nuevo."
        )
        return

    # Update last activity
    session["last_activity"] = current_time

    # Check if we've reached the maximum
    if len(session["videos"]) >= config.JOIN_MAX_VIDEOS:
        await update.message.reply_text(
            f"Máximo {config.JOIN_MAX_VIDEOS} videos permitidos.\n"
            "Usa /done para unir o /cancel para cancelar."
        )
        return

    # Get video from message
    video = update.message.video
    if not video:
        await update.message.reply_text(
            "Por favor envía un video válido."
        )
        return

    # Send processing message
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            f"Descargando video {len(session['videos']) + 1}..."
        )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    try:
        temp_mgr = session["temp_mgr"]

        # Generate safe filename
        video_index = len(session["videos"]) + 1
        input_filename = f"join_{user_id}_video{video_index:02d}_{video.file_unique_id}.mp4"
        input_path = temp_mgr.get_temp_path(input_filename)

        # Download video
        logger.info(f"Downloading video {video_index} for join session, user {user_id}")
        try:
            file = await video.get_file()
            await _download_with_retry(file, input_path)
            logger.info(f"Video downloaded to {input_path}")
        except Exception as e:
            logger.error(f"Failed to download video for user {user_id}: {e}")
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception:
                    pass
            await update.message.reply_text(
                "No pude descargar el video. Intenta con otro archivo."
            )
            return

        # Track the video
        session["videos"].append(str(input_path))
        temp_mgr.track_file(str(input_path))

        video_count = len(session["videos"])

        # Delete processing message
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass

        # Send confirmation
        if video_count == 1:
            await update.message.reply_text(
                f"Video {video_count} agregado. Envía más videos o usa /done para unir."
            )
        elif video_count < config.JOIN_MIN_VIDEOS:
            remaining = config.JOIN_MIN_VIDEOS - video_count
            await update.message.reply_text(
                f"Video {video_count} agregado. Necesitas {remaining} video(s) más para unir."
            )
        else:
            await update.message.reply_text(
                f"Video {video_count} agregado. "
                f"Tienes {video_count} video(s). "
                f"Envía más (máx. {config.JOIN_MAX_VIDEOS}) o usa /done para unir."
            )

    except Exception as e:
        logger.exception(f"Unexpected error handling join video for user {user_id}: {e}")
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass
        await update.message.reply_text(
            "Ocurrió un error procesando el video. Intenta de nuevo."
        )


async def handle_join_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /done command to complete video joining.

    Joins all collected videos and sends the result.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join done command received from user {user_id}")

    # Check if there's an active join session
    session = context.user_data.get("join_session")
    if not session:
        await update.message.reply_text(
            "No hay una sesión de unión activa. Usa /join para comenzar."
        )
        return

    # Check session timeout
    current_time = asyncio.get_event_loop().time()
    if current_time - session["last_activity"] > config.JOIN_SESSION_TIMEOUT:
        logger.info(f"Join session expired for user {user_id}")
        session["temp_mgr"].cleanup()
        context.user_data.pop("join_session", None)
        await update.message.reply_text(
            "La sesión expiró. Usa /join para comenzar de nuevo."
        )
        return

    # Check minimum videos
    video_count = len(session["videos"])
    if video_count < config.JOIN_MIN_VIDEOS:
        await update.message.reply_text(
            f"Necesitas al menos {config.JOIN_MIN_VIDEOS} videos para unir. "
            f"Actualmente tienes {video_count}."
        )
        return

    # Send processing message
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            f"Uniendo {video_count} videos... Esto puede tomar un momento."
        )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    temp_mgr = session["temp_mgr"]

    try:
        # Generate output path
        output_filename = f"joined_{user_id}_{int(asyncio.get_event_loop().time())}.mp4"
        output_path = temp_mgr.get_temp_path(output_filename)

        # Create VideoJoiner and add all videos
        logger.info(f"Starting video join for user {user_id} with {video_count} videos")
        joiner = VideoJoiner(str(output_path))

        for video_path in session["videos"]:
            joiner.add_video(video_path)

        # Join videos with timeout
        try:
            loop = asyncio.get_event_loop()
            success = await asyncio.wait_for(
                loop.run_in_executor(None, joiner.join_videos),
                timeout=config.JOIN_TIMEOUT  # Dedicated join timeout (120s default)
            )

            if not success:
                logger.error(f"Video joining failed for user {user_id}")
                raise VideoJoinError("No pude unir los videos")

        except asyncio.TimeoutError as e:
            logger.error(f"Video joining timed out for user {user_id}")
            raise ProcessingTimeoutError("La unión de videos tardó demasiado") from e

        # Send joined video
        logger.info(f"Sending joined video to user {user_id}")
        try:
            with open(output_path, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"Video unido ({video_count} partes)"
                )
            logger.info(f"Joined video sent successfully to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send joined video to user {user_id}: {e}")
            raise

        # Delete processing message on success
        if processing_message:
            try:
                await processing_message.delete()
            except Exception as e:
                logger.warning(f"Could not delete processing message: {e}")

        # Clean up session
        temp_mgr.cleanup()
        context.user_data.pop("join_session", None)

    except (VideoJoinError, ProcessingTimeoutError) as e:
        await handle_processing_error(update, e, user_id)
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass
        # Clean up session on error
        temp_mgr.cleanup()
        context.user_data.pop("join_session", None)

    except Exception as e:
        logger.exception(f"Unexpected error joining videos for user {user_id}: {e}")
        await handle_processing_error(update, e, user_id)
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass
        # Clean up session on error
        temp_mgr.cleanup()
        context.user_data.pop("join_session", None)


async def handle_join_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command to cancel a join session.

    Clears session data and cleans up temporary files.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join cancel command received from user {user_id}")

    # Check if there's an active join session
    session = context.user_data.get("join_session")
    if not session:
        await update.message.reply_text(
            "No hay una sesión de unión activa."
        )
        return

    # Clean up temp files
    video_count = len(session["videos"])
    session["temp_mgr"].cleanup()
    context.user_data.pop("join_session", None)

    await update.message.reply_text(
        f"Sesión cancelada. {video_count} video(s) descartados."
    )
