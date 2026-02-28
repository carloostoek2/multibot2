"""Telegram bot handlers for video processing."""
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.error import NetworkError, TimedOut

from bot.temp_manager import TempManager
from bot.video_processor import VideoProcessor
from bot.video_merger import VideoAudioMerger
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
    VoiceConversionError,
    VoiceToMp3Error,
    AudioSplitError,
    AudioJoinError,
    AudioFormatConversionError,
    AudioEnhancementError,
    AudioEffectsError,
    VideoMergeError,
    handle_processing_error,
)
from bot.config import config
from bot.validators import (
    validate_file_size,
    validate_video_file,
    validate_audio_file,
    check_disk_space,
    estimate_required_space,
    ValidationError,
)
from bot.audio_processor import VoiceNoteConverter, VoiceToMp3Converter, get_audio_duration
from bot.audio_splitter import AudioSplitter
from bot.audio_joiner import AudioJoiner
from bot.audio_format_converter import AudioFormatConverter, detect_audio_format, get_supported_audio_formats
from bot.audio_enhancer import AudioEnhancer
from bot.audio_effects import AudioEffects

# Import downloaders for URL handling
from bot.downloaders import (
    DownloadFacade,
    download_url,
    URLDetector,
)
from bot.downloaders.exceptions import (
    DownloadError,
    FileTooLargeError,
    URLValidationError,
    UnsupportedURLError,
)

logger = logging.getLogger(__name__)

# URL detector instance for detecting URLs in messages
url_detector = URLDetector()

async def _download_with_retry(file, destination_path: str, max_retries: int = 3, correlation_id: str = None) -> bool:
    """Download file with retry logic for transient failures.

    Args:
        file: Telegram file object to download
        destination_path: Path to save the file
        max_retries: Maximum number of retry attempts
        correlation_id: Optional correlation ID for request tracing

    Returns:
        True if download succeeded

    Raises:
        NetworkError, TimedOut: If all retries exhausted
    """
    cid = correlation_id or "no-cid"
    for attempt in range(max_retries):
        try:
            await file.download_to_drive(destination_path)
            logger.info(f"[{cid}] Video downloaded to {destination_path}")
            return True
        except (NetworkError, TimedOut) as e:
            if attempt < max_retries - 1:
                logger.warning(f"[{cid}] Download attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"[{cid}] Download failed after {max_retries} attempts: {e}")
                raise
    return False



async def _process_video_with_timeout(
    update: Update,
    temp_mgr: TempManager,
    user_id: int,
    correlation_id: str = None
) -> None:
    """Process video with timeout handling.

    Internal function that handles the actual video processing
    with timeout and proper error handling.

    Args:
        update: Telegram update object
        temp_mgr: TempManager instance for file handling
        user_id: ID of the user sending the video
        correlation_id: Optional correlation ID for request tracing

    Raises:
        DownloadError: If video download fails
        FFmpegError: If video processing fails
        ProcessingTimeoutError: If processing times out
    """
    cid = correlation_id or "no-cid"
    # Get video from message
    video = update.message.video

    # Generate safe filenames
    input_filename = f"input_{user_id}_{video.file_unique_id}.mp4"
    output_filename = f"output_{user_id}_{video.file_unique_id}.mp4"

    input_path = temp_mgr.get_temp_path(input_filename)
    output_path = temp_mgr.get_temp_path(output_filename)

    # Download video to temp file
    logger.info(f"[{cid}] Downloading video from user {user_id}")
    try:
        file = await video.get_file()
        await _download_with_retry(file, input_path, correlation_id=cid)
    except Exception as e:
        logger.error(f"[{cid}] Failed to download video for user {user_id}: {e}")
        raise DownloadError("No pude descargar el video") from e

    # Validate video integrity after download
    is_valid, error_msg = validate_video_file(str(input_path))
    if not is_valid:
        logger.warning(f"[{cid}] Video validation failed for user {user_id}: {error_msg}")
        raise ValidationError(error_msg)

    # Check disk space before processing
    video_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
    required_space = estimate_required_space(int(video_size_mb))
    has_space, space_error = check_disk_space(required_space)
    if not has_space:
        logger.warning(f"[{cid}] Disk space check failed for user {user_id}: {space_error}")
        raise ValidationError(space_error)

    # Process video with timeout
    logger.info(f"[{cid}] Processing video for user {user_id}")
    logger.debug(f"[{cid}] Processing with timeout: {config.PROCESSING_TIMEOUT}s")
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
            logger.error(f"[{cid}] Video processing failed for user {user_id}")
            raise FFmpegError("El procesamiento de video falló")

    except asyncio.TimeoutError as e:
        logger.error(f"[{cid}] Video processing timed out for user {user_id}")
        raise ProcessingTimeoutError("El video tardó demasiado en procesarse") from e

    # Send as video note
    logger.info(f"[{cid}] Sending video note to user {user_id}")
    try:
        with open(output_path, "rb") as video_file:
            await update.message.reply_video_note(video_note=video_file)
        logger.info(f"[{cid}] Video note sent successfully to user {user_id}")
    except Exception as e:
        logger.error(f"[{cid}] Failed to send video note to user {user_id}: {e}")
        raise


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video messages by showing an inline menu with available actions.

    When a user sends a video, displays an inline keyboard with options:
    - Nota de Video: Convert to circular video note
    - Extraer Audio: Extract audio from video
    - Convertir Formato: Convert video to different format
    - Dividir Video: Split video into segments

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Video received from user {user_id}")

    # Validate file size before showing menu
    video = update.message.video
    if video.file_size:
        logger.debug(f"[{correlation_id}] Video file size: {video.file_size} bytes")
        is_valid, error_msg = validate_file_size(video.file_size, config.MAX_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file info for callback handler
    context.user_data["video_menu_file_id"] = video.file_id
    context.user_data["video_menu_correlation_id"] = correlation_id

    # Show inline menu
    reply_markup = _get_video_menu_keyboard()
    await update.message.reply_text(
        "Video recibido. Selecciona una acción:",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Video menu displayed to user {user_id}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    await update.message.reply_text(
        "¡Hola! Envíame un video, audio, o enlace de video y te mostraré opciones de procesamiento.\n\n"
        "📥 Descargas desde plataformas:\n"
        "/download <url> - Descargar video/audio de YouTube, Instagram, TikTok, Twitter/X, Facebook\n"
        "/downloads - Ver descargas activas y recientes\n"
        "También puedes enviarme directamente un enlace de video\n\n"
        "🎬 Procesamiento de video:\n"
        "/convert <formato> - Convierte un video a otro formato (mp4, avi, mov, mkv, webm)\n"
        "/extract_audio <formato> - Extrae el audio de un video (mp3, aac, wav, ogg)\n"
        "/split [duration|parts] <valor> - Divide un video en segmentos\n"
        "/join - Une múltiples videos en uno solo\n\n"
        "🎵 Procesamiento de audio:\n"
        "/split_audio [duration|parts] <valor> - Divide un audio en segmentos\n"
        "/join_audio - Une múltiples archivos de audio\n"
        "/convert_audio - Convierte un audio a otro formato (MP3, WAV, OGG, AAC, FLAC)\n"
        "/bass_boost - Aumenta los bajos del audio (intensidad ajustable)\n"
        "/treble_boost - Aumenta los agudos del audio (intensidad ajustable)\n"
        "/equalize - Ecualizador de 3 bandas (bass, mid, treble)\n"
        "/denoise - Reduce el ruido de fondo del audio (intensidad ajustable)\n"
        "/compress - Comprime el rango dinámico del audio (nivel ajustable)\n"
        "/normalize - Normaliza el volumen del audio (EBU R128)\n"
        "/effects - Aplica múltiples efectos en cadena (pipeline)\n\n"
        "💡 También puedes usar los menús inline:\n"
        "- Envía un video → Menú con opciones (Nota de Video, Extraer Audio, Merge con Audio, etc.)\n"
        "- Envía un audio → Menú con opciones (Nota de Voz, Dividir Audio, Unir Audios, etc.)\n"
        "- Envía un enlace de video → Menú de descarga con opciones combinadas"
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


async def _get_audio_from_message(update: Update) -> tuple:
    """Extract audio object and file info from message.

    Args:
        update: Telegram update object

    Returns:
        Tuple of (audio_object, is_reply) or (None, False) if no audio found
    """
    # Check if the message itself has audio
    if update.message.audio:
        return update.message.audio, False

    # Check if it's a reply to an audio message
    if update.message.reply_to_message and update.message.reply_to_message.audio:
        return update.message.reply_to_message.audio, True

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

    # Validate file size before downloading
    if video.file_size:
        is_valid, error_msg = validate_file_size(video.file_size, config.MAX_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
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

            # Validate video integrity after download
            is_valid, error_msg = validate_video_file(str(input_path))
            if not is_valid:
                logger.warning(f"Video validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            video_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(video_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

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

        except (DownloadError, FormatConversionError, ProcessingTimeoutError, ValidationError) as e:
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

    # Validate file size before downloading
    if video.file_size:
        is_valid, error_msg = validate_file_size(video.file_size, config.MAX_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
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

            # Validate video integrity after download
            is_valid, error_msg = validate_video_file(str(input_path))
            if not is_valid:
                logger.warning(f"Video validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            video_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(video_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

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

        except (DownloadError, AudioExtractionError, ProcessingTimeoutError, ValidationError) as e:
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
DEFAULT_AUDIO_SEGMENT_DURATION = 60

# Split session states
SPLIT_WAITING_START_TIME = "waiting_start_time"
SPLIT_WAITING_END_TIME = "waiting_end_time"
SPLIT_CONFIRMING = "confirming"


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

    # Validate file size before downloading
    if video.file_size:
        is_valid, error_msg = validate_file_size(video.file_size, config.MAX_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
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
                if split_value < config.MIN_SEGMENT_SECONDS:
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

            # Validate video integrity after download
            is_valid, error_msg = validate_video_file(str(input_path))
            if not is_valid:
                logger.warning(f"Video validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            video_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(video_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

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

                    if expected_segments > config.MAX_SEGMENTS:
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
                    if len(segments) > config.MAX_SEGMENTS:
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

        except (DownloadError, VideoSplitError, ProcessingTimeoutError, ValidationError) as e:
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


# Default audio segment duration for split_audio command
DEFAULT_AUDIO_SEGMENT_DURATION = 60


async def handle_split_audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /split_audio command to split audio files into segments.

    Usage:
        /split_audio duration <segundos> - Divide en segmentos de N segundos
        /split_audio parts <cantidad> - Divide en N partes iguales
        /split_audio (solo) - Divide en segmentos de 60 segundos

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Split audio command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Responde a un audio con este comando para dividirlo.\n\n"
            "Uso:\n"
            "/split_audio duration 30 - Divide en segmentos de 30 segundos\n"
            "/split_audio parts 5 - Divide en 5 partes iguales\n"
            "/split_audio - Divide en segmentos de 60 segundos (default)"
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Parse command arguments
    args = context.args if context.args else []

    split_mode = "duration"  # Default mode
    split_value = DEFAULT_AUDIO_SEGMENT_DURATION

    if len(args) >= 1:
        if args[0].lower() in ["duration", "duracion", "tiempo", "time"]:
            split_mode = "duration"
            if len(args) >= 2:
                try:
                    split_value = int(args[1])
                    if split_value < config.MIN_AUDIO_SEGMENT_SECONDS:
                        await update.message.reply_text(
                            f"La duración mínima es {config.MIN_AUDIO_SEGMENT_SECONDS} segundos."
                        )
                        return
                except ValueError:
                    await update.message.reply_text(
                        "Por favor especifica un número válido de segundos.\n"
                        "Ejemplo: /split_audio duration 30"
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
                    if split_value > config.MAX_AUDIO_SEGMENTS:
                        await update.message.reply_text(
                            f"El máximo de partes es {config.MAX_AUDIO_SEGMENTS}."
                        )
                        return
                except ValueError:
                    await update.message.reply_text(
                        "Por favor especifica un número válido de partes.\n"
                        "Ejemplo: /split_audio parts 5"
                    )
                    return
            else:
                await update.message.reply_text(
                    "Por favor especifica cuántas partes quieres.\n"
                    "Ejemplo: /split_audio parts 5"
                )
                return
        else:
            # Try to parse as a number (assume duration mode)
            try:
                split_value = int(args[0])
                if split_value < config.MIN_AUDIO_SEGMENT_SECONDS:
                    await update.message.reply_text(
                        f"La duración mínima es {config.MIN_AUDIO_SEGMENT_SECONDS} segundos."
                    )
                    return
            except ValueError:
                await update.message.reply_text(
                    "Argumento no reconocido. Usa 'duration' o 'parts'.\n"
                    "Ejemplo: /split_audio duration 30 o /split_audio parts 5"
                )
                return

    # Send processing message
    processing_message = None
    try:
        if split_mode == "duration":
            processing_message = await update.message.reply_text(
                f"Dividiendo audio en segmentos de {split_value} segundos..."
            )
        else:
            processing_message = await update.message.reply_text(
                f"Dividiendo audio en {split_value} partes iguales..."
            )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_audio_{user_id}_{audio.file_unique_id}.mp3"
            output_dir = temp_mgr.get_temp_path(f"split_audio_{user_id}_{audio.file_unique_id}")

            input_path = temp_mgr.get_temp_path(input_filename)

            # Download audio
            logger.info(f"Downloading audio from user {user_id} for splitting")
            try:
                file = await audio.get_file()
                await _download_with_retry(file, input_path)
                logger.info(f"Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Create output directory for segments
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # Split audio with timeout
            logger.info(f"Splitting audio for user {user_id} (mode={split_mode}, value={split_value})")
            try:
                loop = asyncio.get_event_loop()
                splitter = AudioSplitter(str(input_path), str(output_dir))

                if split_mode == "duration":
                    # Check how many segments would be created
                    duration = await loop.run_in_executor(None, splitter.get_audio_duration)
                    expected_segments = int(duration // split_value) + (1 if duration % split_value > 0 else 0)

                    if expected_segments > config.MAX_AUDIO_SEGMENTS:
                        await update.message.reply_text(
                            f"El audio generaría demasiadas partes ({expected_segments}). "
                            f"Intenta con una duración mayor (máximo {config.MAX_AUDIO_SEGMENTS} partes)."
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

                    # Check if we got too many segments
                    if len(segments) > config.MAX_AUDIO_SEGMENTS:
                        await update.message.reply_text(
                            f"El audio generaría demasiadas partes ({len(segments)}). "
                            f"Intenta con menos partes (máximo {config.MAX_AUDIO_SEGMENTS})."
                        )
                        if processing_message:
                            try:
                                await processing_message.delete()
                            except Exception:
                                pass
                        return

                if not segments:
                    logger.error(f"Audio splitting produced no segments for user {user_id}")
                    raise AudioSplitError("No se generaron segmentos del audio")

            except asyncio.TimeoutError as e:
                logger.error(f"Audio splitting timed out for user {user_id}")
                raise ProcessingTimeoutError("La división del audio tardó demasiado") from e

            # Send segments to user
            logger.info(f"Sending {len(segments)} audio segments to user {user_id}")
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
                    with open(segment_path, "rb") as audio_file:
                        await update.message.reply_audio(
                            audio=audio_file,
                            caption=f"Parte {i} de {total_segments}"
                        )
                    logger.info(f"Sent audio segment {i}/{total_segments} to user {user_id}")

                except Exception as e:
                    logger.error(f"Failed to send audio segment {i} to user {user_id}: {e}")
                    await update.message.reply_text(
                        f"Error enviando la parte {i} de {total_segments}."
                    )

            # Send completion message
            await update.message.reply_text(
                f"¡Listo! El audio se dividió en {total_segments} partes."
            )
            logger.info(f"All audio segments sent successfully to user {user_id}")

            # Delete processing message on success
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except (DownloadError, AudioSplitError, ProcessingTimeoutError, ValidationError) as e:
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"Could not delete processing message: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error splitting audio for user {user_id}: {e}")
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

    # Validate file size before downloading
    if video.file_size:
        is_valid, error_msg = validate_file_size(video.file_size, config.MAX_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
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

        # Validate video integrity after download
        is_valid, error_msg = validate_video_file(str(input_path))
        if not is_valid:
            logger.warning(f"Video validation failed for user {user_id}: {error_msg}")
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception:
                    pass
            await update.message.reply_text(error_msg)
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
    """Handle /done command to complete video or audio joining.

    Joins all collected videos or audios and sends the result.
    Checks for video join session first, then audio join session.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join done command received from user {user_id}")

    # Check if there's an active video join session
    session = context.user_data.get("join_session")
    if not session:
        # No video session - check for audio join session
        if context.user_data.get("join_audio_session"):
            # Delegate to audio join handler
            await handle_join_audio_done(update, context)
            return
        await update.message.reply_text(
            "No hay una sesión de unión activa. Usa /join o /join_audio para comenzar."
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

    # Check disk space before joining
    total_size_mb = 0
    for video_path in session["videos"]:
        total_size_mb += Path(video_path).stat().st_size / (1024 * 1024)
    required_space = estimate_required_space(int(total_size_mb))
    has_space, space_error = check_disk_space(required_space)
    if not has_space:
        logger.warning(f"Disk space check failed for user {user_id}: {space_error}")
        await update.message.reply_text(space_error)
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
    Checks for video join session first, then audio join session.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join cancel command received from user {user_id}")

    # Check if there's an active video join session
    session = context.user_data.get("join_session")
    if not session:
        # No video session - check for audio join session
        if context.user_data.get("join_audio_session"):
            # Delegate to audio join handler
            await handle_join_audio_cancel(update, context)
            return
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


# =============================================================================
# Audio Join Handlers
# =============================================================================

async def handle_join_audio_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join_audio command to start an audio join session.

    Usage: /join_audio - Start a session to collect audio files for joining

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join audio command received from user {user_id}")

    # Check if there's already an active audio join session
    if context.user_data.get("join_audio_session"):
        await update.message.reply_text(
            "Ya tienes una sesión de unión de audio activa. "
            f"Tienes {len(context.user_data['join_audio_session']['audios'])} audio(s) agregados.\n\n"
            "Envía más audios o usa /done para unir, /cancel para cancelar."
        )
        return

    # Check if there's an active video join session (can't have both)
    if context.user_data.get("join_session"):
        await update.message.reply_text(
            "Ya tienes una sesión de unión de videos activa. "
            "Usa /cancel para cancelarla primero, luego usa /join_audio."
        )
        return

    # Initialize audio join session
    context.user_data["join_audio_session"] = {
        "audios": [],
        "temp_mgr": TempManager(),
        "last_activity": asyncio.get_event_loop().time(),
    }

    await update.message.reply_text(
        "🎵 *Modo unión de audio activado*\n\n"
        "Envíame los archivos de audio que quieres unir (máximo 20).\n"
        "Los audios se unirán en el orden en que los envíes.\n\n"
        "Comandos disponibles:\n"
        "• /done - Unir todos los audios\n"
        "• /cancel - Cancelar la sesión\n\n"
        "Envía el primer archivo de audio:",
        parse_mode="Markdown"
    )


async def handle_join_audio_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle audio file messages during an active audio join session.

    Downloads each audio file and tracks it in the user's join session.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id

    # Check if there's an active audio join session
    session = context.user_data.get("join_audio_session")
    if not session:
        # No active audio join session, let the default audio handler process it
        await handle_audio_file(update, context)
        return

    # Check session timeout
    current_time = asyncio.get_event_loop().time()
    if current_time - session["last_activity"] > config.JOIN_SESSION_TIMEOUT:
        logger.info(f"Join audio session expired for user {user_id}")
        # Clean up expired session
        session["temp_mgr"].cleanup()
        context.user_data.pop("join_audio_session", None)
        await update.message.reply_text(
            "La sesión expiró. Usa /join_audio para comenzar de nuevo."
        )
        return

    # Update last activity
    session["last_activity"] = current_time

    # Check if we've reached the maximum
    if len(session["audios"]) >= config.JOIN_MAX_AUDIO_FILES:
        await update.message.reply_text(
            f"Máximo {config.JOIN_MAX_AUDIO_FILES} archivos de audio permitidos.\n"
            "Usa /done para unir o /cancel para cancelar."
        )
        return

    # Get audio from message
    audio = update.message.audio
    if not audio:
        await update.message.reply_text(
            "Por favor envía un archivo de audio válido."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Send processing message
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            f"Descargando audio {len(session['audios']) + 1}..."
        )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    try:
        temp_mgr = session["temp_mgr"]

        # Generate safe filename
        audio_index = len(session["audios"]) + 1
        input_filename = f"join_audio_{user_id}_{audio_index:02d}_{audio.file_unique_id}.mp3"
        input_path = temp_mgr.get_temp_path(input_filename)

        # Download audio
        logger.info(f"Downloading audio {audio_index} for join session, user {user_id}")
        try:
            file = await audio.get_file()
            await _download_with_retry(file, input_path)
            logger.info(f"Audio downloaded to {input_path}")
        except Exception as e:
            logger.error(f"Failed to download audio for user {user_id}: {e}")
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception:
                    pass
            await update.message.reply_text(
                "No pude descargar el audio. Intenta con otro archivo."
            )
            return

        # Validate audio integrity after download
        is_valid, error_msg = validate_audio_file(str(input_path))
        if not is_valid:
            logger.warning(f"Audio validation failed for user {user_id}: {error_msg}")
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception:
                    pass
            await update.message.reply_text(error_msg)
            return

        # Track the audio
        session["audios"].append(str(input_path))
        temp_mgr.track_file(str(input_path))

        audio_count = len(session["audios"])

        # Delete processing message
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass

        # Send confirmation
        if audio_count == 1:
            await update.message.reply_text(
                f"Audio {audio_count} agregado. Envía más audios o usa /done para unir."
            )
        elif audio_count < config.JOIN_MIN_AUDIO_FILES:
            remaining = config.JOIN_MIN_AUDIO_FILES - audio_count
            await update.message.reply_text(
                f"Audio {audio_count} agregado. Necesitas {remaining} audio(s) más para unir."
            )
        else:
            await update.message.reply_text(
                f"Audio {audio_count} agregado. "
                f"Tienes {audio_count} audio(s). "
                f"Envía más (máx. {config.JOIN_MAX_AUDIO_FILES}) o usa /done para unir."
            )

    except Exception as e:
        logger.exception(f"Unexpected error handling join audio for user {user_id}: {e}")
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass
        await update.message.reply_text(
            "Ocurrió un error procesando el audio. Intenta de nuevo."
        )


async def handle_join_audio_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /done command to complete audio joining.

    Joins all collected audio files and sends the result.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join audio done command received from user {user_id}")

    # Check if there's an active audio join session
    session = context.user_data.get("join_audio_session")
    if not session:
        # No active audio join session - let video join handler check
        # This will be handled by the router in main.py or the video handler
        await update.message.reply_text(
            "No hay una sesión de unión de audio activa. Usa /join_audio para comenzar."
        )
        return

    # Check session timeout
    current_time = asyncio.get_event_loop().time()
    if current_time - session["last_activity"] > config.JOIN_SESSION_TIMEOUT:
        logger.info(f"Join audio session expired for user {user_id}")
        session["temp_mgr"].cleanup()
        context.user_data.pop("join_audio_session", None)
        await update.message.reply_text(
            "La sesión expiró. Usa /join_audio para comenzar de nuevo."
        )
        return

    # Check minimum audios
    audio_count = len(session["audios"])
    if audio_count < config.JOIN_MIN_AUDIO_FILES:
        await update.message.reply_text(
            f"Necesitas al menos {config.JOIN_MIN_AUDIO_FILES} audios para unir. "
            f"Actualmente tienes {audio_count}."
        )
        return

    # Check disk space before joining
    total_size_mb = 0
    for audio_path in session["audios"]:
        total_size_mb += Path(audio_path).stat().st_size / (1024 * 1024)
    required_space = estimate_required_space(int(total_size_mb))
    has_space, space_error = check_disk_space(required_space)
    if not has_space:
        logger.warning(f"Disk space check failed for user {user_id}: {space_error}")
        await update.message.reply_text(space_error)
        return

    # Send processing message
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            f"Uniendo {audio_count} audios... Esto puede tomar un momento."
        )
    except Exception as e:
        logger.warning(f"Could not send processing message to user {user_id}: {e}")

    temp_mgr = session["temp_mgr"]

    try:
        # Generate output path
        output_filename = f"joined_audio_{user_id}_{int(asyncio.get_event_loop().time())}.mp3"
        output_path = temp_mgr.get_temp_path(output_filename)

        # Create AudioJoiner and add all audios
        logger.info(f"Starting audio join for user {user_id} with {audio_count} audios")
        joiner = AudioJoiner(str(output_path))

        for audio_path in session["audios"]:
            joiner.add_audio(audio_path)

        # Join audios with timeout
        try:
            loop = asyncio.get_event_loop()
            success = await asyncio.wait_for(
                loop.run_in_executor(None, joiner.join_audios),
                timeout=config.JOIN_AUDIO_TIMEOUT
            )

            if not success:
                logger.error(f"Audio joining failed for user {user_id}")
                raise AudioJoinError("No pude unir los archivos de audio")

        except asyncio.TimeoutError as e:
            logger.error(f"Audio joining timed out for user {user_id}")
            raise ProcessingTimeoutError("La unión de audios tardó demasiado") from e

        # Send joined audio
        logger.info(f"Sending joined audio to user {user_id}")
        try:
            with open(output_path, "rb") as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    caption=f"Audio unido ({audio_count} partes)"
                )
            logger.info(f"Joined audio sent successfully to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send joined audio to user {user_id}: {e}")
            raise

        # Delete processing message on success
        if processing_message:
            try:
                await processing_message.delete()
            except Exception as e:
                logger.warning(f"Could not delete processing message: {e}")

        # Clean up session
        temp_mgr.cleanup()
        context.user_data.pop("join_audio_session", None)

    except (AudioJoinError, ProcessingTimeoutError) as e:
        await handle_processing_error(update, e, user_id)
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass
        # Clean up session on error
        temp_mgr.cleanup()
        context.user_data.pop("join_audio_session", None)

    except Exception as e:
        logger.exception(f"Unexpected error joining audios for user {user_id}: {e}")
        await handle_processing_error(update, e, user_id)
        if processing_message:
            try:
                await processing_message.delete()
            except Exception:
                pass
        # Clean up session on error
        temp_mgr.cleanup()
        context.user_data.pop("join_audio_session", None)


async def handle_join_audio_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command to cancel an audio join session.

    Clears session data and cleans up temporary files.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    logger.info(f"Join audio cancel command received from user {user_id}")

    # Check if there's an active audio join session
    session = context.user_data.get("join_audio_session")
    if not session:
        # No active audio join session
        await update.message.reply_text(
            "No hay una sesión de unión de audio activa."
        )
        return

    # Clean up temp files
    audio_count = len(session["audios"])
    session["temp_mgr"].cleanup()
    context.user_data.pop("join_audio_session", None)

    await update.message.reply_text(
        f"Sesión cancelada. {audio_count} audio(s) descartados."
    )


async def handle_audio_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle audio file messages by converting them to voice notes.

    Downloads the audio file, validates it, converts it to OGG Opus format,
    and sends it back as a Telegram voice note.

    If there's an active audio join session, routes to handle_join_audio_file instead.
    If there's an active video-audio merge session, routes to handle_merge_audio_received.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id

    # Check if there's an active audio join session
    if context.user_data.get("join_audio_session"):
        # Route to join audio handler
        await handle_join_audio_file(update, context)
        return

    # Check if there's an active video-audio merge session
    if context.user_data.get("merge_video_file_id"):
        # Route to merge audio handler
        await handle_merge_audio_received(update, context)
        return

    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Audio file received from user {user_id}")

    # Get audio from message
    audio = update.message.audio
    if not audio:
        logger.warning(f"[{correlation_id}] No audio found in message from user {user_id}")
        await update.message.reply_text("No encontré un archivo de audio en tu mensaje.")
        return

    # Validate file size before downloading
    if audio.file_size:
        logger.debug(f"[{correlation_id}] Audio file size: {audio.file_size} bytes")
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file info for callback handler
    context.user_data["audio_menu_file_id"] = audio.file_id
    context.user_data["audio_menu_correlation_id"] = correlation_id

    # Show inline menu
    reply_markup = _get_audio_menu_keyboard()
    await update.message.reply_text(
        "Audio recibido. Selecciona una acción:",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Audio menu displayed to user {user_id}")


async def handle_merge_audio_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle audio file received during video-audio merge process.

    Downloads the video and audio files, merges them, and sends the result.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = context.user_data.get("merge_video_correlation_id", str(uuid.uuid4())[:8])
    logger.info(f"[{correlation_id}] Audio received for merge from user {user_id}")

    # Get audio from message
    audio = update.message.audio
    if not audio:
        logger.warning(f"[{correlation_id}] No audio found in message from user {user_id}")
        await update.message.reply_text("No encontré un archivo de audio en tu mensaje.")
        # Clean up merge context
        context.user_data.pop("merge_video_file_id", None)
        context.user_data.pop("merge_video_correlation_id", None)
        return

    # Validate file size
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] Audio file size validation failed: {error_msg}")
            await update.message.reply_text(error_msg)
            context.user_data.pop("merge_video_file_id", None)
            context.user_data.pop("merge_video_correlation_id", None)
            return

    # Send processing message
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            "Uniendo video con audio..."
        )
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not send processing message: {e}")

    # Process with TempManager
    with TempManager() as temp_mgr:
        try:
            # Retrieve video file_id from context
            video_file_id = context.user_data.get("merge_video_file_id")
            if not video_file_id:
                logger.error(f"[{correlation_id}] No video file_id in context")
                raise DownloadError("No encontré el video original. Intenta de nuevo.")

            # Generate safe filenames
            video_filename = f"merge_video_{user_id}_{correlation_id}.mp4"
            audio_filename = f"merge_audio_{user_id}_{correlation_id}.audio"
            output_filename = f"merged_{user_id}_{correlation_id}.mp4"

            video_path = temp_mgr.get_temp_path(video_filename)
            audio_path = temp_mgr.get_temp_path(audio_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download video
            logger.info(f"[{correlation_id}] Downloading video for merge")
            try:
                file = await context.bot.get_file(video_file_id)
                await _download_with_retry(file, video_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Video downloaded to {video_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download video: {e}")
                raise DownloadError("No pude descargar el video") from e

            # Download audio
            logger.info(f"[{correlation_id}] Downloading audio for merge")
            try:
                file = await audio.get_file()
                await _download_with_retry(file, audio_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {audio_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate files
            is_valid, error_msg = validate_video_file(str(video_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Video validation failed: {error_msg}")
                raise ValidationError(error_msg)

            is_valid, error_msg = validate_audio_file(str(audio_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space
            video_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
            audio_size_mb = Path(audio_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(video_size_mb + audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed: {space_error}")
                raise ValidationError(space_error)

            # Merge video and audio
            logger.info(f"[{correlation_id}] Merging video and audio")
            try:
                loop = asyncio.get_event_loop()
                merger = VideoAudioMerger(str(video_path), str(audio_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, merger.merge),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"[{correlation_id}] Video-audio merge failed")
                    raise VideoMergeError("No pude unir el video con el audio")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Merge timed out")
                raise ProcessingTimeoutError("La unión tardó demasiado") from e

            # Send merged video
            logger.info(f"[{correlation_id}] Sending merged video")
            try:
                with open(output_path, "rb") as video_file:
                    await update.message.reply_video(video=video_file)
                logger.info(f"[{correlation_id}] Merged video sent successfully")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send merged video: {e}")
                raise

            # Delete processing message
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"[{correlation_id}] Could not delete processing message: {e}")

            # Clean up context
            context.user_data.pop("merge_video_file_id", None)
            context.user_data.pop("merge_video_correlation_id", None)

        except (DownloadError, VideoMergeError, ProcessingTimeoutError, ValidationError) as e:
            logger.error(f"[{correlation_id}] Merge processing error: {e}")
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"[{correlation_id}] Could not delete processing message: {e}")
            # Clean up context
            context.user_data.pop("merge_video_file_id", None)
            context.user_data.pop("merge_video_correlation_id", None)

        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error in merge: {e}")
            await handle_processing_error(update, e, user_id)
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"[{correlation_id}] Could not delete processing message: {e}")
            # Clean up context
            context.user_data.pop("merge_video_file_id", None)
            context.user_data.pop("merge_video_correlation_id", None)


# Video Split Interactive Handlers

async def handle_video_split_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start interactive video split process.

    Downloads the video, gets its duration, and asks user for start time.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    query = update.callback_query
    callback_data = query.data
    correlation_id = str(uuid.uuid4())[:8]

    # Parse video file_id from callback (format: video_split:<file_id>)
    if not callback_data.startswith("video_split:"):
        logger.warning(f"[{correlation_id}] Invalid callback data for video split")
        return

    file_id = callback_data.split(":", 1)[1]
    if not file_id:
        logger.error(f"[{correlation_id}] No file_id in callback data")
        await query.edit_message_text("Error: no se encontró el video.")
        return

    logger.info(f"[{correlation_id}] Video split started by user {user_id}")

    # Store file info in context
    context.user_data["split_video_session"] = {
        "file_id": file_id,
        "correlation_id": correlation_id,
        "state": SPLIT_WAITING_START_TIME,
    }

    await query.edit_message_text(
        "✂️ *Dividir Video*\n\n"
        "Primero necesito saber la duración del video para ayudarte.\n\n"
        "⏳ Procesando...",
        parse_mode="Markdown"
    )

    # Download video and get duration
    with TempManager() as temp_mgr:
        try:
            input_filename = f"split_video_{user_id}_{correlation_id}.mp4"
            input_path = temp_mgr.get_temp_path(input_filename)

            # Download video
            file = await context.bot.get_file(file_id)
            await _download_with_retry(file, input_path, correlation_id=correlation_id)

            # Get duration
            splitter = VideoSplitter(str(input_path), str(temp_mgr.get_temp_path("output")))
            duration = splitter.get_video_duration()

            context.user_data["split_video_session"]["duration"] = duration
            context.user_data["split_video_session"]["input_path"] = input_path

            minutes = int(duration // 60)
            seconds = int(duration % 60)

            await query.edit_message_text(
                f"✂️ *Dividir Video*\n\n"
                f"📊 Duración del video: *{minutes}m {seconds}s*\n\n"
                f"Envía el tiempo de *inicio* en segundos (ej: 30 para 30 segundos).\n\n"
                f"Puede ser un número decimal (ej: 30.5)",
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"[{correlation_id}] Error preparing video split: {e}")
            await query.edit_message_text(
                "Error al preparar el video. Intenta de nuevo."
            )
            context.user_data.pop("split_video_session", None)


async def handle_video_split_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle start time input for video split.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    session = context.user_data.get("split_video_session")

    if not session or session.get("type") != "video":
        # Not a video split session, ignore
        return

    correlation_id = session.get("correlation_id", "unknown")
    logger.info(f"[{correlation_id}] Start time input received from user {user_id}")

    try:
        start_time = float(update.message.text.strip())
    except (ValueError, AttributeError):
        await update.message.reply_text(
            "Por favor envía un número válido (ej: 30 o 30.5)"
        )
        return

    duration = session.get("duration", 0)
    if start_time < 0:
        await update.message.reply_text(
            "El tiempo de inicio no puede ser negativo."
        )
        return

    if start_time >= duration:
        await update.message.reply_text(
            f"El tiempo de inicio debe ser menor a la duración del video ({duration}s)."
        )
        return

    # Store start time
    session["start_time"] = start_time
    session["state"] = SPLIT_WAITING_END_TIME

    remaining = duration - start_time
    await update.message.reply_text(
        f"✅ Tiempo de inicio: *{start_time}s*\n\n"
        f"Ahora envía el tiempo *final* en segundos.\n"
        f"Debe ser mayor a {start_time}s y menor a {duration}s.\n\n"
        f"Tiempo máximo disponible: *{remaining:.1f}s*",
        parse_mode="Markdown"
    )


async def handle_video_split_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle end time input for video split and process the cut.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    session = context.user_data.get("split_video_session")

    if not session or session.get("type") != "video":
        return

    correlation_id = session.get("correlation_id", "unknown")
    logger.info(f"[{correlation_id}] End time input received from user {user_id}")

    try:
        end_time = float(update.message.text.strip())
    except (ValueError, AttributeError):
        await update.message.reply_text(
            "Por favor envía un número válido (ej: 60 o 90.5)"
        )
        return

    start_time = session.get("start_time", 0)
    duration = session.get("duration", 0)

    if end_time <= start_time:
        await update.message.reply_text(
            f"El tiempo final debe ser mayor al tiempo de inicio ({start_time}s)."
        )
        return

    if end_time > duration:
        await update.message.reply_text(
            f"El tiempo final no puede exceder la duración del video ({duration}s)."
        )
        return

    segment_duration = end_time - start_time
    if segment_duration < 1:
        await update.message.reply_text(
            "La duración mínima del segmento es 1 segundo."
        )
        return

    # Store end time and proceed to cut
    session["end_time"] = end_time
    session["state"] = SPLIT_CONFIRMING

    # Send processing message
    processing_message = await update.message.reply_text(
        f"✂️ Extrayendo segmento de {start_time}s a {end_time}s...\n"
        f"Duración: {segment_duration:.1f}s"
    )

    with TempManager() as temp_mgr:
        try:
            input_path = session["input_path"]
            output_dir = temp_mgr.get_temp_path(f"split_output_{correlation_id}")
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            splitter = VideoSplitter(str(input_path), str(output_dir))
            output_path = splitter.split_by_time_range(start_time, end_time)

            # Send video segment
            await update.message.reply_video(
                video=open(output_path, "rb"),
                caption=f"Segmento extraído ({start_time}s - {end_time}s)"
            )

            await processing_message.delete()
            logger.info(f"[{correlation_id}] Video segment sent successfully")

        except Exception as e:
            logger.error(f"[{correlation_id}] Error splitting video: {e}")
            await processing_message.delete()
            await update.message.reply_text(
                "Error al extraer el segmento. Intenta de nuevo."
            )
        finally:
            context.user_data.pop("split_video_session", None)


async def handle_audio_split_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start interactive audio split process.

    Downloads the audio, gets its duration, and asks user for start time.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    query = update.callback_query
    callback_data = query.data
    correlation_id = str(uuid.uuid4())[:8]

    # Parse audio file_id from callback (format: audio_split:<file_id>)
    if not callback_data.startswith("audio_split:"):
        logger.warning(f"[{correlation_id}] Invalid callback data for audio split")
        return

    file_id = callback_data.split(":", 1)[1]
    if not file_id:
        logger.error(f"[{correlation_id}] No file_id in callback data")
        await query.edit_message_text("Error: no se encontró el audio.")
        return

    logger.info(f"[{correlation_id}] Audio split started by user {user_id}")

    # Store file info in context
    context.user_data["split_audio_session"] = {
        "file_id": file_id,
        "correlation_id": correlation_id,
        "state": SPLIT_WAITING_START_TIME,
        "type": "audio",
    }

    await query.edit_message_text(
        "✂️ *Dividir Audio*\n\n"
        "Primero necesito saber la duración del audio para ayudarte.\n\n"
        "⏳ Procesando...",
        parse_mode="Markdown"
    )

    # Download audio and get duration
    with TempManager() as temp_mgr:
        try:
            input_filename = f"split_audio_{user_id}_{correlation_id}.audio"
            input_path = temp_mgr.get_temp_path(input_filename)

            # Download audio
            file = await context.bot.get_file(file_id)
            await _download_with_retry(file, input_path, correlation_id=correlation_id)

            # Get duration
            splitter = AudioSplitter(str(input_path), str(temp_mgr.get_temp_path("output")))
            duration = splitter.get_audio_duration()

            context.user_data["split_audio_session"]["duration"] = duration
            context.user_data["split_audio_session"]["input_path"] = input_path

            minutes = int(duration // 60)
            seconds = int(duration % 60)

            await query.edit_message_text(
                f"✂️ *Dividir Audio*\n\n"
                f"📊 Duración del audio: *{minutes}m {seconds}s*\n\n"
                f"Envía el tiempo de *inicio* en segundos (ej: 30 para 30 segundos).\n\n"
                f"Puede ser un número decimal (ej: 30.5)",
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"[{correlation_id}] Error preparing audio split: {e}")
            await query.edit_message_text(
                "Error al preparar el audio. Intenta de nuevo."
            )
            context.user_data.pop("split_audio_session", None)


async def handle_audio_split_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle start time input for audio split.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    session = context.user_data.get("split_audio_session")

    if not session:
        return

    correlation_id = session.get("correlation_id", "unknown")
    logger.info(f"[{correlation_id}] Audio start time input received from user {user_id}")

    try:
        start_time = float(update.message.text.strip())
    except (ValueError, AttributeError):
        await update.message.reply_text(
            "Por favor envía un número válido (ej: 30 o 30.5)"
        )
        return

    duration = session.get("duration", 0)
    if start_time < 0:
        await update.message.reply_text(
            "El tiempo de inicio no puede ser negativo."
        )
        return

    if start_time >= duration:
        await update.message.reply_text(
            f"El tiempo de inicio debe ser menor a la duración del audio ({duration}s)."
        )
        return

    # Store start time
    session["start_time"] = start_time
    session["state"] = SPLIT_WAITING_END_TIME

    remaining = duration - start_time
    await update.message.reply_text(
        f"✅ Tiempo de inicio: *{start_time}s*\n\n"
        f"Ahora envía el tiempo *final* en segundos.\n"
        f"Debe ser mayor a {start_time}s y menor a {duration}s.\n\n"
        f"Tiempo máximo disponible: *{remaining:.1f}s*",
        parse_mode="Markdown"
    )


async def handle_audio_split_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle end time input for audio split and process the cut.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    session = context.user_data.get("split_audio_session")

    if not session:
        return

    correlation_id = session.get("correlation_id", "unknown")
    logger.info(f"[{correlation_id}] Audio end time input received from user {user_id}")

    try:
        end_time = float(update.message.text.strip())
    except (ValueError, AttributeError):
        await update.message.reply_text(
            "Por favor envía un número válido (ej: 60 o 90.5)"
        )
        return

    start_time = session.get("start_time", 0)
    duration = session.get("duration", 0)

    if end_time <= start_time:
        await update.message.reply_text(
            f"El tiempo final debe ser mayor al tiempo de inicio ({start_time}s)."
        )
        return

    if end_time > duration:
        await update.message.reply_text(
            f"El tiempo final no puede exceder la duración del audio ({duration}s)."
        )
        return

    segment_duration = end_time - start_time
    if segment_duration < 1:
        await update.message.reply_text(
            "La duración mínima del segmento es 1 segundo."
        )
        return

    # Store end time and proceed to cut
    session["end_time"] = end_time
    session["state"] = SPLIT_CONFIRMING

    # Send processing message
    processing_message = await update.message.reply_text(
        f"✂️ Extrayendo segmento de {start_time}s a {end_time}s...\n"
        f"Duración: {segment_duration:.1f}s"
    )

    with TempManager() as temp_mgr:
        try:
            input_path = session["input_path"]
            output_dir = temp_mgr.get_temp_path(f"split_output_{correlation_id}")
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            splitter = AudioSplitter(str(input_path), str(output_dir))
            output_path = splitter.split_by_time_range(start_time, end_time)

            # Send audio segment
            await update.message.reply_audio(
                audio=open(output_path, "rb"),
                caption=f"Segmento extraído ({start_time}s - {end_time}s)"
            )

            await processing_message.delete()
            logger.info(f"[{correlation_id}] Audio segment sent successfully")

        except Exception as e:
            logger.error(f"[{correlation_id}] Error splitting audio: {e}")
            await processing_message.delete()
            await update.message.reply_text(
                "Error al extraer el segmento. Intenta de nuevo."
            )
        finally:
            context.user_data.pop("split_audio_session", None)


async def handle_split_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages during active split sessions.

    Routes to appropriate handler based on active session type.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    # Check for video split session
    if context.user_data.get("split_video_session"):
        session = context.user_data["split_video_session"]
        if session.get("state") == SPLIT_WAITING_START_TIME:
            await handle_video_split_start_time(update, context)
        elif session.get("state") == SPLIT_WAITING_END_TIME:
            await handle_video_split_end_time(update, context)
        return

    # Check for audio split session
    if context.user_data.get("split_audio_session"):
        session = context.user_data["split_audio_session"]
        if session.get("state") == SPLIT_WAITING_START_TIME:
            await handle_audio_split_start_time(update, context)
        elif session.get("state") == SPLIT_WAITING_END_TIME:
            await handle_audio_split_end_time(update, context)
        return


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages by converting them to MP3 format.

    Downloads the voice note (OGG Opus), converts it to MP3 format,
    and sends it back as a downloadable audio file.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Voice message received from user {user_id}")

    # Get voice from message
    voice = update.message.voice
    if not voice:
        logger.warning(f"[{correlation_id}] No voice found in message from user {user_id}")
        await update.message.reply_text("No encontré una nota de voz en tu mensaje.")
        return

    # Validate file size before downloading
    if voice.file_size:
        logger.debug(f"[{correlation_id}] Voice file size: {voice.file_size} bytes")
        is_valid, error_msg = validate_file_size(voice.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Send "processing" message to user
    processing_message = None
    try:
        processing_message = await update.message.reply_text(
            "Convirtiendo nota de voz a MP3..."
        )
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not send processing message to user {user_id}: {e}")

    # Use TempManager as context manager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            # Telegram voice messages are OGG Opus format with .oga extension
            input_filename = f"voice_{user_id}_{voice.file_unique_id}.oga"
            output_filename = f"voice_{user_id}_{voice.file_unique_id}.mp3"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download voice file
            logger.info(f"[{correlation_id}] Downloading voice from user {user_id}")
            try:
                file = await voice.get_file()
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download voice for user {user_id}: {e}")
                raise DownloadError("No pude descargar la nota de voz") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            voice_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(voice_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Convert to MP3 with timeout
            logger.info(f"[{correlation_id}] Converting voice to MP3 for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = VoiceToMp3Converter(str(input_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.process),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"[{correlation_id}] Voice to MP3 conversion failed for user {user_id}")
                    raise VoiceToMp3Error("No pude convertir la nota de voz a MP3")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Voice to MP3 conversion timed out for user {user_id}")
                raise ProcessingTimeoutError("La conversión tardó demasiado") from e

            # Send as audio file with metadata
            logger.info(f"[{correlation_id}] Sending MP3 to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title="Nota de voz",
                        performer="Telegram Voice",
                        filename=f"voice_{user_id}.mp3"
                    )
                logger.info(f"[{correlation_id}] MP3 sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send MP3 to user {user_id}: {e}")
                raise

            # Delete processing message on success
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"[{correlation_id}] Could not delete processing message: {e}")

        except (DownloadError, ValidationError, VoiceToMp3Error, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Delete processing message on error
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"[{correlation_id}] Could not delete processing message: {e}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error processing voice for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Delete processing message on error
            if processing_message:
                try:
                    await processing_message.delete()
                except Exception as e:
                    logger.warning(f"[{correlation_id}] Could not delete processing message: {e}")

        # TempManager cleanup happens automatically on context exit
        logger.debug(f"[{correlation_id}] Cleanup completed for user {user_id}")


async def handle_convert_audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /convert_audio command to convert audio to different format.

    Usage: /convert_audio (when replying to an audio or with audio attached)
    Shows inline keyboard with format options for user to select.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Convert audio command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /convert_audio respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file_id in context for later retrieval
    context.user_data["convert_audio_file_id"] = audio.file_id
    context.user_data["convert_audio_correlation_id"] = correlation_id

    # Create inline keyboard with format options (3 + 2 layout)
    keyboard = [
        [
            InlineKeyboardButton("MP3", callback_data="format:mp3"),
            InlineKeyboardButton("WAV", callback_data="format:wav"),
            InlineKeyboardButton("OGG", callback_data="format:ogg"),
        ],
        [
            InlineKeyboardButton("AAC", callback_data="format:aac"),
            InlineKeyboardButton("FLAC", callback_data="format:flac"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Selecciona el formato de salida:",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Format selection keyboard sent to user {user_id}")


async def handle_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle format selection callback from inline keyboard.

    Downloads the audio, converts it to selected format, and sends back.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Extract format from callback data (e.g., "format:mp3" -> "mp3")
    callback_data = query.data
    if not callback_data.startswith("format:"):
        logger.warning(f"Invalid callback data received: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    output_format = callback_data.split(":")[1]

    # Retrieve file_id from context
    file_id = context.user_data.get("convert_audio_file_id")
    correlation_id = context.user_data.get("convert_audio_correlation_id", str(uuid.uuid4())[:8])

    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    logger.info(f"[{correlation_id}] Format {output_format} selected by user {user_id}")

    # Update message to show processing
    try:
        await query.edit_message_text(f"Convirtiendo a {output_format.upper()}...")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{correlation_id}.audio"
            output_filename = f"converted_{user_id}_{correlation_id}.{output_format}"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Detect input format
            input_format = detect_audio_format(str(input_path))
            if input_format:
                logger.info(f"[{correlation_id}] Detected input format: {input_format}")
                # Check if input format equals output format
                if input_format == output_format:
                    await query.edit_message_text(
                        f"El archivo ya está en formato {output_format.upper()}. No es necesario convertir."
                    )
                    return
            else:
                logger.warning(f"[{correlation_id}] Could not detect input format for user {user_id}")

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Convert audio with timeout
            logger.info(f"[{correlation_id}] Converting audio to {output_format} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = AudioFormatConverter(str(input_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.convert, output_format),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"[{correlation_id}] Audio format conversion failed for user {user_id}")
                    raise AudioFormatConversionError(f"No pude convertir el audio a {output_format.upper()}")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Audio conversion timed out for user {user_id}")
                raise ProcessingTimeoutError("La conversión tardó demasiado") from e

            # Send converted audio
            logger.info(f"[{correlation_id}] Sending converted audio to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        filename=f"converted.{output_format}",
                        title=f"Audio convertido a {output_format.upper()}"
                    )
                logger.info(f"[{correlation_id}] Converted audio sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send converted audio to user {user_id}: {e}")
                raise

            # Update message on success
            try:
                await query.edit_message_text(f"Audio convertido a {output_format.upper()} exitosamente.")
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("convert_audio_file_id", None)
            context.user_data.pop("convert_audio_correlation_id", None)

        except (DownloadError, ValidationError, AudioFormatConversionError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text(f"Error: {str(e)}")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error converting audio for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        # TempManager cleanup happens automatically on context exit
        logger.debug(f"[{correlation_id}] Cleanup completed for user {user_id}")


async def handle_bass_boost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /bass_boost command to apply bass boost enhancement.

    Usage: /bass_boost (when replying to an audio or with audio attached)
    Shows inline keyboard with intensity options (1-10) for user to select.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Bass boost command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /bass_boost respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file_id in context for later retrieval
    context.user_data["enhance_audio_file_id"] = audio.file_id
    context.user_data["enhance_audio_correlation_id"] = correlation_id
    context.user_data["enhance_type"] = "bass"

    # Create inline keyboard with intensity options (5 + 5 layout)
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="bass:1"),
            InlineKeyboardButton("2", callback_data="bass:2"),
            InlineKeyboardButton("3", callback_data="bass:3"),
            InlineKeyboardButton("4", callback_data="bass:4"),
            InlineKeyboardButton("5", callback_data="bass:5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="bass:6"),
            InlineKeyboardButton("7", callback_data="bass:7"),
            InlineKeyboardButton("8", callback_data="bass:8"),
            InlineKeyboardButton("9", callback_data="bass:9"),
            InlineKeyboardButton("10", callback_data="bass:10"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Selecciona la intensidad del bass boost (1-10):",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Intensity selection keyboard sent to user {user_id}")


async def handle_treble_boost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /treble_boost command to apply treble boost enhancement.

    Usage: /treble_boost (when replying to an audio or with audio attached)
    Shows inline keyboard with intensity options (1-10) for user to select.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Treble boost command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /treble_boost respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file_id in context for later retrieval
    context.user_data["enhance_audio_file_id"] = audio.file_id
    context.user_data["enhance_audio_correlation_id"] = correlation_id
    context.user_data["enhance_type"] = "treble"

    # Create inline keyboard with intensity options (5 + 5 layout)
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="treble:1"),
            InlineKeyboardButton("2", callback_data="treble:2"),
            InlineKeyboardButton("3", callback_data="treble:3"),
            InlineKeyboardButton("4", callback_data="treble:4"),
            InlineKeyboardButton("5", callback_data="treble:5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="treble:6"),
            InlineKeyboardButton("7", callback_data="treble:7"),
            InlineKeyboardButton("8", callback_data="treble:8"),
            InlineKeyboardButton("9", callback_data="treble:9"),
            InlineKeyboardButton("10", callback_data="treble:10"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Selecciona la intensidad del treble boost (1-10):",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Intensity selection keyboard sent to user {user_id}")


async def handle_intensity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle intensity selection callback from inline keyboard.

    Downloads the audio, applies the selected enhancement (bass or treble),
    and sends back the enhanced audio.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Parse callback data (e.g., "bass:5" or "treble:8")
    callback_data = query.data
    if not callback_data or ":" not in callback_data:
        logger.warning(f"Invalid callback data received: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    parts = callback_data.split(":")
    if len(parts) != 2:
        logger.warning(f"Invalid callback data format: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    enhance_type = parts[0]
    try:
        intensity = int(parts[1])
    except ValueError:
        logger.warning(f"Invalid intensity value: {parts[1]}")
        await query.edit_message_text("Error: intensidad inválida.")
        return

    if enhance_type not in ("bass", "treble"):
        logger.warning(f"Invalid enhancement type: {enhance_type}")
        await query.edit_message_text("Error: tipo de mejora inválido.")
        return

    if intensity < 1 or intensity > 10:
        logger.warning(f"Invalid intensity range: {intensity}")
        await query.edit_message_text("Error: intensidad debe estar entre 1 y 10.")
        return

    # Retrieve file_id from context
    file_id = context.user_data.get("enhance_audio_file_id")
    correlation_id = context.user_data.get("enhance_audio_correlation_id", str(uuid.uuid4())[:8])
    stored_enhance_type = context.user_data.get("enhance_type")

    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    # Verify enhance_type matches stored type
    if stored_enhance_type and stored_enhance_type != enhance_type:
        logger.warning(f"[{correlation_id}] Mismatch: stored={stored_enhance_type}, callback={enhance_type}")

    effect_name = "bass" if enhance_type == "bass" else "treble"
    logger.info(f"[{correlation_id}] {effect_name.capitalize()} boost intensity {intensity} selected by user {user_id}")

    # Update message to show processing
    try:
        await query.edit_message_text(f"Aplicando {effect_name} boost (intensidad {intensity})...")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{correlation_id}.audio"
            output_filename = f"enhanced_{user_id}_{correlation_id}.mp3"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Apply enhancement with timeout
            logger.info(f"[{correlation_id}] Applying {effect_name} boost (intensity {intensity}) for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                enhancer = AudioEnhancer(str(input_path), str(output_path))

                if enhance_type == "bass":
                    success = await asyncio.wait_for(
                        loop.run_in_executor(None, enhancer.bass_boost, intensity),
                        timeout=config.PROCESSING_TIMEOUT
                    )
                else:  # treble
                    success = await asyncio.wait_for(
                        loop.run_in_executor(None, enhancer.treble_boost, intensity),
                        timeout=config.PROCESSING_TIMEOUT
                    )

                if not success:
                    logger.error(f"[{correlation_id}] Audio enhancement failed for user {user_id}")
                    raise AudioEnhancementError(f"No pude aplicar el {effect_name} boost")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Audio enhancement timed out for user {user_id}")
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            # Send enhanced audio
            logger.info(f"[{correlation_id}] Sending enhanced audio to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        filename=f"enhanced_{effect_name}.mp3",
                        title=f"Audio mejorado ({effect_name.capitalize()} Boost)"
                    )
                logger.info(f"[{correlation_id}] Enhanced audio sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send enhanced audio to user {user_id}: {e}")
                raise

            # Update message on success
            try:
                await query.edit_message_text(
                    f"¡Listo! Audio mejorado con {effect_name} boost (intensidad {intensity}/10)."
                )
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("enhance_audio_file_id", None)
            context.user_data.pop("enhance_audio_correlation_id", None)
            context.user_data.pop("enhance_type", None)

        except (DownloadError, ValidationError, AudioEnhancementError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text(f"Error: {str(e)}")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error enhancing audio for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        # TempManager cleanup happens automatically on context exit
        logger.debug(f"[{correlation_id}] Cleanup completed for user {user_id}")


# =============================================================================
# Equalizer Handlers
# =============================================================================


def _get_video_menu_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for video menu options."""
    keyboard = [
        [
            InlineKeyboardButton("Nota de Video", callback_data="video_action:videonote"),
            InlineKeyboardButton("Extraer Audio", callback_data="video_action:extract_audio"),
        ],
        [
            InlineKeyboardButton("Convertir Formato", callback_data="video_action:convert"),
            InlineKeyboardButton("Dividir Video", callback_data="video_action:split"),
        ],
        [
            InlineKeyboardButton("Merge con Audio", callback_data="video_action:merge_audio"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_video_format_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for video format selection."""
    keyboard = [
        [
            InlineKeyboardButton("MP4", callback_data="video_format:mp4"),
            InlineKeyboardButton("AVI", callback_data="video_format:avi"),
            InlineKeyboardButton("MOV", callback_data="video_format:mov"),
        ],
        [
            InlineKeyboardButton("MKV", callback_data="video_format:mkv"),
            InlineKeyboardButton("WEBM", callback_data="video_format:webm"),
        ],
        [
            InlineKeyboardButton("← Volver", callback_data="back:video"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_video_audio_format_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for audio extraction format selection."""
    keyboard = [
        [
            InlineKeyboardButton("MP3", callback_data="video_audio_format:mp3"),
            InlineKeyboardButton("AAC", callback_data="video_audio_format:aac"),
        ],
        [
            InlineKeyboardButton("WAV", callback_data="video_audio_format:wav"),
            InlineKeyboardButton("OGG", callback_data="video_audio_format:ogg"),
        ],
        [
            InlineKeyboardButton("← Volver", callback_data="back:video"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_equalizer_keyboard(bass: int, mid: int, treble: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for 3-band equalizer.

    Args:
        bass: Current bass value (-10 to +10)
        mid: Current mid value (-10 to +10)
        treble: Current treble value (-10 to +10)

    Returns:
        InlineKeyboardMarkup with equalizer controls
    """
    # Format values with sign for positive numbers
    bass_str = f"{bass:+d}" if bass != 0 else "0"
    mid_str = f"{mid:+d}" if mid != 0 else "0"
    treble_str = f"{treble:+d}" if treble != 0 else "0"

    keyboard = [
        # Bass row
        [
            InlineKeyboardButton("Bass", callback_data="eq_noop"),
            InlineKeyboardButton("-", callback_data="eq_bass_down"),
            InlineKeyboardButton(bass_str, callback_data="eq_noop"),
            InlineKeyboardButton("+", callback_data="eq_bass_up"),
        ],
        # Mid row
        [
            InlineKeyboardButton("Mid", callback_data="eq_noop"),
            InlineKeyboardButton("-", callback_data="eq_mid_down"),
            InlineKeyboardButton(mid_str, callback_data="eq_noop"),
            InlineKeyboardButton("+", callback_data="eq_mid_up"),
        ],
        # Treble row
        [
            InlineKeyboardButton("Treble", callback_data="eq_noop"),
            InlineKeyboardButton("-", callback_data="eq_treble_down"),
            InlineKeyboardButton(treble_str, callback_data="eq_noop"),
            InlineKeyboardButton("+", callback_data="eq_treble_up"),
        ],
        # Reset and Apply row
        [
            InlineKeyboardButton("Reset", callback_data="eq_reset_all"),
            InlineKeyboardButton("Aplicar", callback_data="eq_apply"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_equalize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /equalize command to show 3-band equalizer interface.

    Usage: /equalize (when replying to an audio or with audio attached)

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Equalize command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /equalize respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Initialize equalizer state in context.user_data
    context.user_data["eq_file_id"] = audio.file_id
    context.user_data["eq_correlation_id"] = correlation_id
    context.user_data["eq_bass"] = 0
    context.user_data["eq_mid"] = 0
    context.user_data["eq_treble"] = 0

    # Create inline keyboard
    reply_markup = _get_equalizer_keyboard(0, 0, 0)

    await update.message.reply_text(
        "Ecualizador de 3 bandas:\n"
        "🎵 Bass: 0\n"
        "🎵 Mid: 0\n"
        "🎵 Treble: 0\n\n"
        "Ajusta cada banda y presiona Aplicar.",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Equalizer interface sent to user {user_id}")


async def handle_equalizer_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle equalizer adjustment callbacks from inline keyboard.

    Handles up/down adjustments for bass/mid/treble, reset, and apply.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Handle noop callbacks (display buttons)
    if callback_data == "eq_noop":
        return

    # Get current values from context
    bass = context.user_data.get("eq_bass", 0)
    mid = context.user_data.get("eq_mid", 0)
    treble = context.user_data.get("eq_treble", 0)
    correlation_id = context.user_data.get("eq_correlation_id", str(uuid.uuid4())[:8])

    # Process callback
    if callback_data == "eq_apply":
        await _handle_equalizer_apply(update, context, bass, mid, treble)
        return

    # Step size for adjustments
    STEP = 2
    MIN_VAL = -10
    MAX_VAL = 10

    if callback_data == "eq_bass_up":
        bass = min(MAX_VAL, bass + STEP)
    elif callback_data == "eq_bass_down":
        bass = max(MIN_VAL, bass - STEP)
    elif callback_data == "eq_mid_up":
        mid = min(MAX_VAL, mid + STEP)
    elif callback_data == "eq_mid_down":
        mid = max(MIN_VAL, mid - STEP)
    elif callback_data == "eq_treble_up":
        treble = min(MAX_VAL, treble + STEP)
    elif callback_data == "eq_treble_down":
        treble = max(MIN_VAL, treble - STEP)
    elif callback_data == "eq_reset_all":
        bass = 0
        mid = 0
        treble = 0
    else:
        logger.warning(f"[{correlation_id}] Unknown equalizer callback: {callback_data}")
        return

    # Store updated values
    context.user_data["eq_bass"] = bass
    context.user_data["eq_mid"] = mid
    context.user_data["eq_treble"] = treble

    # Format values for display
    bass_display = f"{bass:+d}" if bass != 0 else "0"
    mid_display = f"{mid:+d}" if mid != 0 else "0"
    treble_display = f"{treble:+d}" if treble != 0 else "0"

    # Update message with new values
    reply_markup = _get_equalizer_keyboard(bass, mid, treble)

    try:
        await query.edit_message_text(
            f"Ecualizador de 3 bandas:\n"
            f"🎵 Bass: {bass_display}\n"
            f"🎵 Mid: {mid_display}\n"
            f"🎵 Treble: {treble_display}\n\n"
            f"Ajusta cada banda y presiona Aplicar.",
            reply_markup=reply_markup
        )
        logger.info(f"[{correlation_id}] Equalizer updated: bass={bass}, mid={mid}, treble={treble}")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update equalizer message: {e}")


async def _handle_equalizer_apply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    bass: int,
    mid: int,
    treble: int
) -> None:
    """Apply equalizer settings and process audio.

    Args:
        update: Telegram update object
        context: Telegram context object
        bass: Bass gain value (-10 to +10)
        mid: Mid gain value (-10 to +10)
        treble: Treble gain value (-10 to +10)
    """
    query = update.callback_query
    user_id = update.effective_user.id
    correlation_id = context.user_data.get("eq_correlation_id", str(uuid.uuid4())[:8])

    # Check if any adjustments were made
    if bass == 0 and mid == 0 and treble == 0:
        await query.edit_message_text(
            "No has hecho ajustes. Modifica al menos una banda antes de aplicar."
        )
        return

    # Retrieve file_id from context
    file_id = context.user_data.get("eq_file_id")
    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    # Format values for display
    bass_display = f"{bass:+d}" if bass != 0 else "0"
    mid_display = f"{mid:+d}" if mid != 0 else "0"
    treble_display = f"{treble:+d}" if treble != 0 else "0"

    # Update message to show processing
    try:
        await query.edit_message_text(
            f"Aplicando ecualización (Bass: {bass_display}, Mid: {mid_display}, Treble: {treble_display})..."
        )
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    logger.info(f"[{correlation_id}] Applying equalizer: bass={bass}, mid={mid}, treble={treble}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_eq_{user_id}_{correlation_id}.audio"
            output_filename = f"equalized_{user_id}_{correlation_id}.mp3"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Apply equalization with timeout
            logger.info(f"[{correlation_id}] Applying equalization for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                enhancer = AudioEnhancer(str(input_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, enhancer.equalize, bass, mid, treble),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"[{correlation_id}] Equalization failed for user {user_id}")
                    raise AudioEnhancementError("No pude aplicar la ecualización")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Equalization timed out for user {user_id}")
                raise ProcessingTimeoutError("La ecualización tardó demasiado") from e

            # Send equalized audio
            logger.info(f"[{correlation_id}] Sending equalized audio to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        filename=f"equalized.mp3",
                        title=f"Audio ecualizado"
                    )
                logger.info(f"[{correlation_id}] Equalized audio sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send equalized audio to user {user_id}: {e}")
                raise

            # Update message on success
            try:
                await query.edit_message_text(
                    f"¡Listo! Ecualización aplicada:\n"
                    f"🎵 Bass: {bass_display}\n"
                    f"🎵 Mid: {mid_display}\n"
                    f"🎵 Treble: {treble_display}"
                )
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("eq_file_id", None)
            context.user_data.pop("eq_correlation_id", None)
            context.user_data.pop("eq_bass", None)
            context.user_data.pop("eq_mid", None)
            context.user_data.pop("eq_treble", None)

        except (DownloadError, ValidationError, AudioEnhancementError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text(f"Error: {str(e)}")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error applying equalizer for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        # TempManager cleanup happens automatically on context exit


async def handle_denoise_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /denoise command to apply noise reduction.

    Usage: /denoise (when replying to an audio or with audio attached)
    Shows inline keyboard with strength options (1-10) for user to select.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Denoise command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /denoise respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file_id in context for later retrieval
    context.user_data["effect_audio_file_id"] = audio.file_id
    context.user_data["effect_audio_correlation_id"] = correlation_id
    context.user_data["effect_type"] = "denoise"

    # Create inline keyboard with strength options (5 + 5 layout)
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="denoise:1"),
            InlineKeyboardButton("2", callback_data="denoise:2"),
            InlineKeyboardButton("3", callback_data="denoise:3"),
            InlineKeyboardButton("4", callback_data="denoise:4"),
            InlineKeyboardButton("5", callback_data="denoise:5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="denoise:6"),
            InlineKeyboardButton("7", callback_data="denoise:7"),
            InlineKeyboardButton("8", callback_data="denoise:8"),
            InlineKeyboardButton("9", callback_data="denoise:9"),
            InlineKeyboardButton("10", callback_data="denoise:10"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Selecciona la intensidad de reducción de ruido (1-10):\n\n"
        "1 = Reducción ligera\n"
        "10 = Reducción máxima",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Denoise strength selection keyboard sent to user {user_id}")


async def handle_compress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /compress command to apply dynamic range compression.

    Usage: /compress (when replying to an audio or with audio attached)
    Shows inline keyboard with compression ratio presets for user to select.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Compress command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /compress respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file_id in context for later retrieval
    context.user_data["effect_audio_file_id"] = audio.file_id
    context.user_data["effect_audio_correlation_id"] = correlation_id
    context.user_data["effect_type"] = "compress"

    # Create inline keyboard with compression ratio presets (2 + 2 layout)
    keyboard = [
        [
            InlineKeyboardButton("Compresión ligera", callback_data="compress:light"),
            InlineKeyboardButton("Compresión media", callback_data="compress:medium"),
        ],
        [
            InlineKeyboardButton("Compresión fuerte", callback_data="compress:heavy"),
            InlineKeyboardButton("Compresión extrema", callback_data="compress:extreme"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Selecciona el nivel de compresión:\n\n"
        "La compresión reduce la diferencia entre sonidos fuertes y débiles.",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Compression ratio selection keyboard sent to user {user_id}")


async def handle_effect_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle effect selection callback from inline keyboard.

    Downloads the audio, applies the selected effect (denoise or compress),
    and sends back the processed audio.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Parse callback data (e.g., "denoise:5" or "compress:medium")
    callback_data = query.data
    if not callback_data or ":" not in callback_data:
        logger.warning(f"Invalid callback data received: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    parts = callback_data.split(":")
    if len(parts) != 2:
        logger.warning(f"Invalid callback data format: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    effect_type = parts[0]
    parameter = parts[1]

    if effect_type not in ("denoise", "compress"):
        logger.warning(f"Invalid effect type: {effect_type}")
        await query.edit_message_text("Error: tipo de efecto inválido.")
        return

    # Validate and convert parameter
    if effect_type == "denoise":
        try:
            strength = int(parameter)
            if strength < 1 or strength > 10:
                logger.warning(f"Invalid denoise strength: {strength}")
                await query.edit_message_text("Error: intensidad debe estar entre 1 y 10.")
                return
        except ValueError:
            logger.warning(f"Invalid denoise strength value: {parameter}")
            await query.edit_message_text("Error: intensidad inválida.")
            return
    else:  # compress
        preset_map = {
            "light": (2.0, "ligera"),
            "medium": (4.0, "media"),
            "heavy": (8.0, "fuerte"),
            "extreme": (12.0, "extrema"),
        }
        if parameter not in preset_map:
            logger.warning(f"Invalid compress preset: {parameter}")
            await query.edit_message_text("Error: nivel de compresión inválido.")
            return
        ratio, preset_name = preset_map[parameter]

    # Retrieve file_id from context
    file_id = context.user_data.get("effect_audio_file_id")
    correlation_id = context.user_data.get("effect_audio_correlation_id", str(uuid.uuid4())[:8])
    stored_effect_type = context.user_data.get("effect_type")

    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    # Verify effect_type matches stored type
    if stored_effect_type and stored_effect_type != effect_type:
        logger.warning(f"[{correlation_id}] Mismatch: stored={stored_effect_type}, callback={effect_type}")

    # Update message to show processing
    if effect_type == "denoise":
        processing_text = f"Aplicando reducción de ruido (intensidad {strength})..."
        effect_name = "reducción de ruido"
        success_text = f"¡Listo! Reducción de ruido aplicada (intensidad {strength}/10)."
    else:
        processing_text = f"Aplicando compresión ({preset_name})..."
        effect_name = "compresión"
        success_text = f"¡Listo! Compresión aplicada (nivel: {preset_name})."

    logger.info(f"[{correlation_id}] {effect_name.capitalize()} selected by user {user_id}")

    try:
        await query.edit_message_text(processing_text)
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{correlation_id}.audio"
            output_filename = f"effect_{user_id}_{correlation_id}.mp3"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Apply effect with timeout
            logger.info(f"[{correlation_id}] Applying {effect_name} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                effects = AudioEffects(str(input_path), str(output_path))

                if effect_type == "denoise":
                    await asyncio.wait_for(
                        loop.run_in_executor(None, effects.denoise, float(strength)),
                        timeout=config.PROCESSING_TIMEOUT
                    )
                else:  # compress
                    await asyncio.wait_for(
                        loop.run_in_executor(None, effects.compress, ratio, -20.0),
                        timeout=config.PROCESSING_TIMEOUT
                    )

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Audio effect timed out for user {user_id}")
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            # Send processed audio
            logger.info(f"[{correlation_id}] Sending processed audio to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        filename=f"{effect_type}_audio.mp3",
                        title=f"Audio con {effect_name.capitalize()}"
                    )
                logger.info(f"[{correlation_id}] Processed audio sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send processed audio to user {user_id}: {e}")
                raise

            # Update message on success
            try:
                await query.edit_message_text(success_text)
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("effect_audio_file_id", None)
            context.user_data.pop("effect_audio_correlation_id", None)
            context.user_data.pop("effect_type", None)

        except (DownloadError, ValidationError, AudioEffectsError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text(f"Error: {str(e)}")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error applying effect for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        # TempManager cleanup happens automatically on context exit
        logger.debug(f"[{correlation_id}] Cleanup completed for user {user_id}")


# =============================================================================
# Normalize Handler
# =============================================================================


async def handle_normalize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /normalize command to apply loudness normalization.

    Usage: /normalize (when replying to an audio or with audio attached)
    Shows inline keyboard with normalization preset options for user to select.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Normalize command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /normalize respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Store file_id in context for later retrieval
    context.user_data["effect_audio_file_id"] = audio.file_id
    context.user_data["effect_audio_correlation_id"] = correlation_id
    context.user_data["effect_type"] = "normalize"

    # Create inline keyboard with normalization presets (1 per row for clarity)
    keyboard = [
        [
            InlineKeyboardButton("Música/General (-14 LUFS)", callback_data="normalize:music"),
        ],
        [
            InlineKeyboardButton("Podcast/Voz (-16 LUFS)", callback_data="normalize:podcast"),
        ],
        [
            InlineKeyboardButton("Streaming/Broadcast (-23 LUFS)", callback_data="normalize:streaming"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Selecciona el perfil de normalización:\n\n"
        "La normalización ajusta el volumen al estándar EBU R128.",
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Normalization preset keyboard sent to user {user_id}")


async def handle_normalize_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle normalization preset selection callback from inline keyboard.

    Downloads the audio, applies loudness normalization with the selected preset,
    and sends back the normalized audio.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Parse callback data (e.g., "normalize:music", "normalize:podcast", "normalize:streaming")
    callback_data = query.data
    if not callback_data or not callback_data.startswith("normalize:"):
        logger.warning(f"Invalid callback data received: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    parts = callback_data.split(":")
    if len(parts) != 2:
        logger.warning(f"Invalid callback data format: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    preset = parts[1]

    # Map preset to target LUFS value
    preset_map = {
        "music": (-14.0, "Música/General", "reproducción general"),
        "podcast": (-16.0, "Podcast/Voz", "contenido de voz"),
        "streaming": (-23.0, "Streaming/Broadcast", "plataformas de streaming"),
    }

    if preset not in preset_map:
        logger.warning(f"Invalid normalization preset: {preset}")
        await query.edit_message_text("Error: perfil de normalización inválido.")
        return

    target_lufs, preset_name, use_case = preset_map[preset]

    # Retrieve file_id from context
    file_id = context.user_data.get("effect_audio_file_id")
    correlation_id = context.user_data.get("effect_audio_correlation_id", str(uuid.uuid4())[:8])
    stored_effect_type = context.user_data.get("effect_type")

    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    # Verify effect_type matches stored type
    if stored_effect_type and stored_effect_type != "normalize":
        logger.warning(f"[{correlation_id}] Mismatch: stored={stored_effect_type}, callback=normalize")

    logger.info(f"[{correlation_id}] Normalization preset '{preset}' ({target_lufs} LUFS) selected by user {user_id}")

    # Update message to show processing
    try:
        await query.edit_message_text(f"Normalizando audio a {preset_name} ({target_lufs} LUFS)...")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{correlation_id}.audio"
            output_filename = f"normalized_{user_id}_{correlation_id}.mp3"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Apply normalization with timeout
            logger.info(f"[{correlation_id}] Applying normalization ({target_lufs} LUFS) for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                effects = AudioEffects(str(input_path), str(output_path))

                success = await asyncio.wait_for(
                    loop.run_in_executor(None, effects.normalize, target_lufs),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"[{correlation_id}] Normalization failed for user {user_id}")
                    raise AudioEffectsError("No pude normalizar el audio")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Normalization timed out for user {user_id}")
                raise ProcessingTimeoutError("La normalización tardó demasiado") from e

            # Send normalized audio
            logger.info(f"[{correlation_id}] Sending normalized audio to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        filename=f"normalized.mp3",
                        title=f"Audio normalizado ({preset_name})"
                    )
                logger.info(f"[{correlation_id}] Normalized audio sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send normalized audio to user {user_id}: {e}")
                raise

            # Update message on success
            try:
                await query.edit_message_text(
                    f"¡Listo! Audio normalizado a {preset_name} ({target_lufs} LUFS).\n\n"
                    f"El volumen ahora está optimizado para {use_case}."
                )
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("effect_audio_file_id", None)
            context.user_data.pop("effect_audio_correlation_id", None)
            context.user_data.pop("effect_type", None)

        except (DownloadError, ValidationError, AudioEffectsError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text(f"Error: {str(e)}")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error normalizing audio for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        # TempManager cleanup happens automatically on context exit
        logger.debug(f"[{correlation_id}] Cleanup completed for user {user_id}")


# =============================================================================
# Audio Inline Menu Handler
# =============================================================================


def _get_audio_menu_keyboard() -> InlineKeyboardMarkup:
    """Generate inline keyboard for audio menu options.

    Returns:
        InlineKeyboardMarkup with audio action buttons
    """
    keyboard = [
        [
            InlineKeyboardButton("Nota de Voz", callback_data="audio_action:voicenote"),
            InlineKeyboardButton("Convertir Formato", callback_data="audio_action:convert"),
        ],
        [
            InlineKeyboardButton("Bass Boost", callback_data="audio_action:bass_boost"),
            InlineKeyboardButton("Treble Boost", callback_data="audio_action:treble_boost"),
            InlineKeyboardButton("Ecualizar", callback_data="audio_action:equalize"),
        ],
        [
            InlineKeyboardButton("Reducir Ruido", callback_data="audio_action:denoise"),
            InlineKeyboardButton("Comprimir", callback_data="audio_action:compress"),
            InlineKeyboardButton("Normalizar", callback_data="audio_action:normalize"),
        ],
        [
            InlineKeyboardButton("Dividir Audio", callback_data="audio_action:split"),
            InlineKeyboardButton("Unir Audios", callback_data="audio_action:join"),
        ],
        [
            InlineKeyboardButton("Pipeline de Efectos", callback_data="audio_action:effects"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_audio_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle audio menu selection callbacks from inline keyboard.

    Routes to appropriate action based on user selection:
    - voicenote: Convert to voice note
    - convert: Show format selection
    - bass_boost/treble_boost/equalize: Show enhancement options
    - denoise/compress/normalize: Show effect options
    - effects: Show pipeline builder

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Parse callback data (format: "audio_action:<action>")
    callback_data = query.data
    if not callback_data or not callback_data.startswith("audio_action:"):
        logger.warning(f"Invalid callback data received: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    action = callback_data.split(":")[1]

    # Retrieve file_id from context
    file_id = context.user_data.get("audio_menu_file_id")
    correlation_id = context.user_data.get("audio_menu_correlation_id", str(uuid.uuid4())[:8])

    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    logger.info(f"[{correlation_id}] Audio menu action '{action}' selected by user {user_id}")

    # Route to appropriate action
    if action == "voicenote":
        await _handle_audio_menu_voicenote(update, context, file_id, correlation_id)

    elif action == "convert":
        # Store action and show format selection
        context.user_data["audio_menu_action"] = "convert"
        keyboard = [
            [
                InlineKeyboardButton("MP3", callback_data="audio_menu_format:mp3"),
                InlineKeyboardButton("WAV", callback_data="audio_menu_format:wav"),
                InlineKeyboardButton("OGG", callback_data="audio_menu_format:ogg"),
            ],
            [
                InlineKeyboardButton("AAC", callback_data="audio_menu_format:aac"),
                InlineKeyboardButton("FLAC", callback_data="audio_menu_format:flac"),
            ],
            [
                InlineKeyboardButton("← Volver", callback_data="back:audio"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Selecciona el formato de conversión:",
            reply_markup=reply_markup
        )

    elif action == "bass_boost":
        # Store file info for enhancement handler
        context.user_data["enhance_audio_file_id"] = file_id
        context.user_data["enhance_audio_correlation_id"] = correlation_id
        context.user_data["enhance_type"] = "bass"
        # Show intensity selection keyboard
        keyboard = [
            [
                InlineKeyboardButton("1", callback_data="bass:1"),
                InlineKeyboardButton("2", callback_data="bass:2"),
                InlineKeyboardButton("3", callback_data="bass:3"),
                InlineKeyboardButton("4", callback_data="bass:4"),
                InlineKeyboardButton("5", callback_data="bass:5"),
            ],
            [
                InlineKeyboardButton("6", callback_data="bass:6"),
                InlineKeyboardButton("7", callback_data="bass:7"),
                InlineKeyboardButton("8", callback_data="bass:8"),
                InlineKeyboardButton("9", callback_data="bass:9"),
                InlineKeyboardButton("10", callback_data="bass:10"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Selecciona la intensidad del Bass Boost (1-10):",
            reply_markup=reply_markup
        )

    elif action == "treble_boost":
        # Store file info for enhancement handler
        context.user_data["enhance_audio_file_id"] = file_id
        context.user_data["enhance_audio_correlation_id"] = correlation_id
        context.user_data["enhance_type"] = "treble"
        # Show intensity selection keyboard
        keyboard = [
            [
                InlineKeyboardButton("1", callback_data="treble:1"),
                InlineKeyboardButton("2", callback_data="treble:2"),
                InlineKeyboardButton("3", callback_data="treble:3"),
                InlineKeyboardButton("4", callback_data="treble:4"),
                InlineKeyboardButton("5", callback_data="treble:5"),
            ],
            [
                InlineKeyboardButton("6", callback_data="treble:6"),
                InlineKeyboardButton("7", callback_data="treble:7"),
                InlineKeyboardButton("8", callback_data="treble:8"),
                InlineKeyboardButton("9", callback_data="treble:9"),
                InlineKeyboardButton("10", callback_data="treble:10"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Selecciona la intensidad del Treble Boost (1-10):",
            reply_markup=reply_markup
        )

    elif action == "equalize":
        # Store file info for equalizer
        context.user_data["eq_file_id"] = file_id
        context.user_data["eq_correlation_id"] = correlation_id
        context.user_data["eq_bass"] = 0
        context.user_data["eq_mid"] = 0
        context.user_data["eq_treble"] = 0
        # Show equalizer keyboard
        reply_markup = _get_equalizer_keyboard(0, 0, 0)
        await query.edit_message_text(
            "Ecualizador de 3 bandas:\n"
            "🎵 Bass: 0\n"
            "🎵 Mid: 0\n"
            "🎵 Treble: 0\n\n"
            "Ajusta cada banda y presiona Aplicar.",
            reply_markup=reply_markup
        )

    elif action == "denoise":
        # Store file info for effect handler
        context.user_data["effect_audio_file_id"] = file_id
        context.user_data["effect_audio_correlation_id"] = correlation_id
        context.user_data["effect_type"] = "denoise"
        # Show strength selection keyboard
        keyboard = [
            [
                InlineKeyboardButton("1", callback_data="denoise:1"),
                InlineKeyboardButton("2", callback_data="denoise:2"),
                InlineKeyboardButton("3", callback_data="denoise:3"),
                InlineKeyboardButton("4", callback_data="denoise:4"),
                InlineKeyboardButton("5", callback_data="denoise:5"),
            ],
            [
                InlineKeyboardButton("6", callback_data="denoise:6"),
                InlineKeyboardButton("7", callback_data="denoise:7"),
                InlineKeyboardButton("8", callback_data="denoise:8"),
                InlineKeyboardButton("9", callback_data="denoise:9"),
                InlineKeyboardButton("10", callback_data="denoise:10"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Selecciona la intensidad de reducción de ruido (1-10):\n\n"
            "1 = Reducción ligera\n"
            "10 = Reducción máxima",
            reply_markup=reply_markup
        )

    elif action == "compress":
        # Store file info for effect handler
        context.user_data["effect_audio_file_id"] = file_id
        context.user_data["effect_audio_correlation_id"] = correlation_id
        context.user_data["effect_type"] = "compress"
        # Show compression preset keyboard
        keyboard = [
            [
                InlineKeyboardButton("Ligera", callback_data="compress:light"),
                InlineKeyboardButton("Media", callback_data="compress:medium"),
            ],
            [
                InlineKeyboardButton("Fuerte", callback_data="compress:heavy"),
                InlineKeyboardButton("Extrema", callback_data="compress:extreme"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Selecciona el nivel de compresión:",
            reply_markup=reply_markup
        )

    elif action == "normalize":
        # Store file info for effect handler
        context.user_data["effect_audio_file_id"] = file_id
        context.user_data["effect_audio_correlation_id"] = correlation_id
        context.user_data["effect_type"] = "normalize"
        # Show normalization preset keyboard
        keyboard = [
            [
                InlineKeyboardButton("Música", callback_data="normalize:music"),
            ],
            [
                InlineKeyboardButton("Podcast", callback_data="normalize:podcast"),
            ],
            [
                InlineKeyboardButton("Streaming", callback_data="normalize:streaming"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Selecciona el perfil de normalización:",
            reply_markup=reply_markup
        )

    elif action == "effects":
        # Store file info for pipeline builder
        context.user_data["pipeline_file_id"] = file_id
        context.user_data["pipeline_correlation_id"] = correlation_id
        context.user_data["pipeline_effects"] = []
        # Show pipeline builder keyboard
        reply_markup = _get_pipeline_keyboard([])
        await query.edit_message_text(
            _format_pipeline_message([]),
            reply_markup=reply_markup
        )

    elif action == "split":
        # Start interactive audio split process
        await handle_audio_split_start(update, context)

    elif action == "join":
        # Start audio join session
        context.user_data["join_audio_session"] = True
        context.user_data["join_audio_files"] = []
        context.user_data["join_audio_correlation_id"] = correlation_id
        await query.edit_message_text(
            "¡Perfecto! Ahora envíame los archivos de audio que quieres unir (uno por uno).\n\n"
            "Cuando termines, envía /done para procesar.\n"
            "Envía /cancel para cancelar."
        )
        logger.info(f"[{correlation_id}] Started audio join session for user {user_id}")

    else:
        logger.warning(f"[{correlation_id}] Unknown audio action: {action}")
        await query.edit_message_text("Error: acción no reconocida.")


async def _handle_audio_menu_voicenote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id: str,
    correlation_id: str
) -> None:
    """Handle voice note conversion from audio menu.

    Args:
        update: Telegram update object
        context: Telegram context object
        file_id: Telegram file ID of the audio
        correlation_id: Correlation ID for tracing
    """
    query = update.callback_query
    user_id = update.effective_user.id

    # Update message to show processing
    try:
        await query.edit_message_text("Convirtiendo a nota de voz...")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{correlation_id}.audio"
            output_filename = f"voice_{user_id}_{correlation_id}.ogg"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Convert to voice note with timeout
            logger.info(f"[{correlation_id}] Converting audio to voice note for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = VoiceNoteConverter(str(input_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.process),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"[{correlation_id}] Voice note conversion failed for user {user_id}")
                    raise VoiceConversionError("No pude convertir el audio a nota de voz")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Voice note conversion timed out for user {user_id}")
                raise ProcessingTimeoutError("El audio tardó demasiado en procesarse") from e

            # Send as voice note
            logger.info(f"[{correlation_id}] Sending voice note to user {user_id}")
            try:
                with open(output_path, "rb") as voice_file:
                    await context.bot.send_voice(
                        chat_id=update.effective_chat.id,
                        voice=voice_file
                    )
                logger.info(f"[{correlation_id}] Voice note sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send voice note to user {user_id}: {e}")
                raise

            # Update message on success
            try:
                await query.edit_message_text("¡Listo! Audio convertido a nota de voz.")
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("audio_menu_file_id", None)
            context.user_data.pop("audio_menu_correlation_id", None)

        except (DownloadError, ValidationError, VoiceConversionError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text(f"Error: {str(e)}")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error converting audio for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")


async def handle_audio_menu_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle audio format selection callback from inline menu.

    Downloads the audio, converts it to selected format, and sends back.
    This is specifically for the menu flow (audio_menu_format:* pattern).

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Extract format from callback data (e.g., "audio_menu_format:mp3" -> "mp3")
    callback_data = query.data
    if not callback_data.startswith("audio_menu_format:"):
        logger.warning(f"Invalid callback data received: {callback_data}")
        await query.edit_message_text("Error: selección inválida.")
        return

    output_format = callback_data.split(":")[1]

    # Retrieve file_id from context
    file_id = context.user_data.get("audio_menu_file_id")
    correlation_id = context.user_data.get("audio_menu_correlation_id", str(uuid.uuid4())[:8])

    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    logger.info(f"[{correlation_id}] Format {output_format} selected by user {user_id} (from menu)")

    # Update message to show processing
    try:
        await query.edit_message_text(f"Convirtiendo audio a {output_format.upper()}...")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{user_id}_{correlation_id}.audio"
            output_filename = f"converted_{user_id}_{correlation_id}.{output_format}"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Detect input format
            input_format = detect_audio_format(str(input_path))
            if input_format:
                logger.info(f"[{correlation_id}] Detected input format: {input_format}")
                # Check if input format equals output format
                if input_format == output_format:
                    await query.edit_message_text(
                        f"El archivo ya está en formato {output_format.upper()}. No es necesario convertir."
                    )
                    return
            else:
                logger.warning(f"[{correlation_id}] Could not detect input format for user {user_id}")

            # Check disk space before processing
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Convert audio with timeout
            logger.info(f"[{correlation_id}] Converting audio to {output_format} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = AudioFormatConverter(str(input_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.convert, output_format),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not success:
                    logger.error(f"[{correlation_id}] Audio format conversion failed for user {user_id}")
                    raise AudioFormatConversionError(f"No pude convertir el audio a {output_format.upper()}")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Audio conversion timed out for user {user_id}")
                raise ProcessingTimeoutError("La conversión tardó demasiado") from e

            # Send converted audio
            logger.info(f"[{correlation_id}] Sending converted audio to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        filename=f"converted.{output_format}",
                        title=f"Audio convertido a {output_format.upper()}"
                    )
                logger.info(f"[{correlation_id}] Converted audio sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send converted audio to user {user_id}: {e}")
                raise

            # Update message on success
            try:
                await query.edit_message_text(f"Audio convertido a {output_format.upper()} exitosamente.")
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("audio_menu_file_id", None)
            context.user_data.pop("audio_menu_correlation_id", None)
            context.user_data.pop("audio_menu_action", None)

        except (DownloadError, ValidationError, AudioFormatConversionError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text(f"Error: {str(e)}")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error converting audio for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")


# Effects Pipeline Handler
# =============================================================================


def _get_pipeline_keyboard(pipeline_effects: list) -> InlineKeyboardMarkup:
    """Generate inline keyboard for pipeline builder.

    Args:
        pipeline_effects: List of effect configs in the pipeline

    Returns:
        InlineKeyboardMarkup with add/preview/apply/cancel buttons
    """
    # Add effect buttons row
    add_buttons = [
        InlineKeyboardButton("+ Denoise", callback_data="pipeline_add:denoise"),
        InlineKeyboardButton("+ Compress", callback_data="pipeline_add:compress"),
        InlineKeyboardButton("+ Normalize", callback_data="pipeline_add:normalize"),
    ]

    # Preview button row
    preview_button = [InlineKeyboardButton("Ver Pipeline", callback_data="pipeline_preview")]

    # Action buttons row
    action_buttons = [
        InlineKeyboardButton("Aplicar", callback_data="pipeline_apply"),
        InlineKeyboardButton("Cancelar", callback_data="pipeline_cancel"),
    ]

    keyboard = [add_buttons, preview_button, action_buttons]
    return InlineKeyboardMarkup(keyboard)


def _format_pipeline_message(pipeline_effects: list) -> str:
    """Format pipeline display message.

    Args:
        pipeline_effects: List of effect configs in the pipeline

    Returns:
        Formatted message string showing current pipeline
    """
    if not pipeline_effects:
        return (
            "Constructor de efectos de audio:\n\n"
            "Efectos en pipeline: (ninguno)\n\n"
            "Agrega efectos en el orden que deseas aplicarlos.\n"
            "Orden recomendado: Denoise → Compress → Normalize"
        )

    effect_lines = []
    for i, effect in enumerate(pipeline_effects, 1):
        effect_type = effect.get("type", "unknown")
        params = effect.get("params", {})

        if effect_type == "denoise":
            strength = params.get("strength", 5)
            effect_lines.append(f"{i}. Denoise (intensidad: {strength})")
        elif effect_type == "compress":
            ratio = params.get("ratio", 4.0)
            preset_name = params.get("preset_name", "media")
            effect_lines.append(f"{i}. Compress (ratio: {preset_name})")
        elif effect_type == "normalize":
            target_lufs = params.get("target_lufs", -14.0)
            preset_name = params.get("preset_name", "música")
            effect_lines.append(f"{i}. Normalize (perfil: {preset_name})")
        else:
            effect_lines.append(f"{i}. {effect_type}")

    pipeline_text = "\n".join(effect_lines)
    return (
        f"Constructor de efectos de audio:\n\n"
        f"Pipeline ({len(pipeline_effects)} efectos):\n"
        f"{pipeline_text}\n\n"
        f"Agrega más efectos o aplica el pipeline."
    )


async def handle_effects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /effects command to show pipeline builder interface.

    Usage: /effects (when replying to an audio or with audio attached)

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] Effects command received from user {user_id}")

    # Get audio from message or reply
    audio, is_reply = await _get_audio_from_message(update)

    if not audio:
        await update.message.reply_text(
            "Envía /effects respondiendo a un archivo de audio o adjunta el audio al mensaje."
        )
        return

    # Validate file size before downloading
    if audio.file_size:
        is_valid, error_msg = validate_file_size(audio.file_size, config.MAX_AUDIO_FILE_SIZE_MB)
        if not is_valid:
            logger.warning(f"[{correlation_id}] File size validation failed for user {user_id}: {error_msg}")
            await update.message.reply_text(error_msg)
            return

    # Initialize pipeline state in context.user_data
    context.user_data["pipeline_file_id"] = audio.file_id
    context.user_data["pipeline_correlation_id"] = correlation_id
    context.user_data["pipeline_effects"] = []

    # Create inline keyboard
    reply_markup = _get_pipeline_keyboard([])

    await update.message.reply_text(
        _format_pipeline_message([]),
        reply_markup=reply_markup
    )
    logger.info(f"[{correlation_id}] Pipeline builder interface sent to user {user_id}")


async def handle_pipeline_builder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pipeline builder callbacks from inline keyboard.

    Handles add effect, preview, apply, and cancel actions.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data
    correlation_id = context.user_data.get("pipeline_correlation_id", str(uuid.uuid4())[:8])

    # Get current pipeline state
    pipeline_effects = context.user_data.get("pipeline_effects", [])

    # Handle cancel
    if callback_data == "pipeline_cancel":
        # Clear all pipeline state
        context.user_data.pop("pipeline_file_id", None)
        context.user_data.pop("pipeline_correlation_id", None)
        context.user_data.pop("pipeline_effects", None)
        context.user_data.pop("pipeline_selecting_effect", None)

        await query.edit_message_text("Pipeline cancelado.")
        logger.info(f"[{correlation_id}] Pipeline cancelled by user {user_id}")
        return

    # Handle preview
    if callback_data == "pipeline_preview":
        if not pipeline_effects:
            await query.answer("No hay efectos en el pipeline", show_alert=True)
        else:
            preview_text = "Pipeline actual:\n\n"
            for i, effect in enumerate(pipeline_effects, 1):
                effect_type = effect.get("type", "unknown")
                params = effect.get("params", {})

                if effect_type == "denoise":
                    strength = params.get("strength", 5)
                    preview_text += f"{i}. Denoise (intensidad: {strength})\n"
                elif effect_type == "compress":
                    preset_name = params.get("preset_name", "media")
                    preview_text += f"{i}. Compress (ratio: {preset_name})\n"
                elif effect_type == "normalize":
                    preset_name = params.get("preset_name", "música")
                    preview_text += f"{i}. Normalize (perfil: {preset_name})\n"

            await query.answer(preview_text, show_alert=True)
        return

    # Handle add effect selection
    if callback_data.startswith("pipeline_add:"):
        effect_type = callback_data.split(":")[1]

        if effect_type == "denoise":
            # Show denoise strength selection keyboard
            keyboard = [
                [
                    InlineKeyboardButton("1", callback_data="pipeline_denoise:1"),
                    InlineKeyboardButton("2", callback_data="pipeline_denoise:2"),
                    InlineKeyboardButton("3", callback_data="pipeline_denoise:3"),
                    InlineKeyboardButton("4", callback_data="pipeline_denoise:4"),
                    InlineKeyboardButton("5", callback_data="pipeline_denoise:5"),
                ],
                [
                    InlineKeyboardButton("6", callback_data="pipeline_denoise:6"),
                    InlineKeyboardButton("7", callback_data="pipeline_denoise:7"),
                    InlineKeyboardButton("8", callback_data="pipeline_denoise:8"),
                    InlineKeyboardButton("9", callback_data="pipeline_denoise:9"),
                    InlineKeyboardButton("10", callback_data="pipeline_denoise:10"),
                ],
                [InlineKeyboardButton("Volver", callback_data="pipeline_back")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Selecciona la intensidad de reducción de ruido (1-10):\n\n"
                "1 = Reducción ligera\n"
                "10 = Reducción máxima",
                reply_markup=reply_markup
            )

        elif effect_type == "compress":
            # Show compress ratio selection keyboard
            keyboard = [
                [
                    InlineKeyboardButton("Ligera", callback_data="pipeline_compress:light"),
                    InlineKeyboardButton("Media", callback_data="pipeline_compress:medium"),
                ],
                [
                    InlineKeyboardButton("Fuerte", callback_data="pipeline_compress:heavy"),
                    InlineKeyboardButton("Extrema", callback_data="pipeline_compress:extreme"),
                ],
                [InlineKeyboardButton("Volver", callback_data="pipeline_back")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Selecciona el nivel de compresión:",
                reply_markup=reply_markup
            )

        elif effect_type == "normalize":
            # Show normalize preset selection keyboard
            keyboard = [
                [
                    InlineKeyboardButton("Música (-14 LUFS)", callback_data="pipeline_normalize:music"),
                ],
                [
                    InlineKeyboardButton("Podcast (-16 LUFS)", callback_data="pipeline_normalize:podcast"),
                ],
                [
                    InlineKeyboardButton("Streaming (-23 LUFS)", callback_data="pipeline_normalize:streaming"),
                ],
                [InlineKeyboardButton("Volver", callback_data="pipeline_back")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Selecciona el perfil de normalización:",
                reply_markup=reply_markup
            )

        return

    # Handle back button
    if callback_data == "pipeline_back":
        reply_markup = _get_pipeline_keyboard(pipeline_effects)
        await query.edit_message_text(
            _format_pipeline_message(pipeline_effects),
            reply_markup=reply_markup
        )
        return

    # Handle denoise parameter selection
    if callback_data.startswith("pipeline_denoise:"):
        strength = int(callback_data.split(":")[1])
        effect_config = {
            "type": "denoise",
            "params": {"strength": strength}
        }
        pipeline_effects.append(effect_config)
        context.user_data["pipeline_effects"] = pipeline_effects

        reply_markup = _get_pipeline_keyboard(pipeline_effects)
        await query.edit_message_text(
            _format_pipeline_message(pipeline_effects),
            reply_markup=reply_markup
        )
        logger.info(f"[{correlation_id}] Denoise (strength={strength}) added to pipeline by user {user_id}")
        return

    # Handle compress parameter selection
    if callback_data.startswith("pipeline_compress:"):
        preset = callback_data.split(":")[1]
        preset_map = {
            "light": (2.0, "ligera"),
            "medium": (4.0, "media"),
            "heavy": (8.0, "fuerte"),
            "extreme": (12.0, "extrema"),
        }
        ratio, preset_name = preset_map.get(preset, (4.0, "media"))
        effect_config = {
            "type": "compress",
            "params": {"ratio": ratio, "preset_name": preset_name}
        }
        pipeline_effects.append(effect_config)
        context.user_data["pipeline_effects"] = pipeline_effects

        reply_markup = _get_pipeline_keyboard(pipeline_effects)
        await query.edit_message_text(
            _format_pipeline_message(pipeline_effects),
            reply_markup=reply_markup
        )
        logger.info(f"[{correlation_id}] Compress (ratio={preset_name}) added to pipeline by user {user_id}")
        return

    # Handle normalize parameter selection
    if callback_data.startswith("pipeline_normalize:"):
        preset = callback_data.split(":")[1]
        preset_map = {
            "music": (-14.0, "música", "streaming y música"),
            "podcast": (-16.0, "podcast", "podcasts y voz"),
            "streaming": (-23.0, "streaming", "broadcast profesional"),
        }
        target_lufs, preset_name, use_case = preset_map.get(preset, (-14.0, "música", "streaming y música"))
        effect_config = {
            "type": "normalize",
            "params": {"target_lufs": target_lufs, "preset_name": preset_name, "use_case": use_case}
        }
        pipeline_effects.append(effect_config)
        context.user_data["pipeline_effects"] = pipeline_effects

        reply_markup = _get_pipeline_keyboard(pipeline_effects)
        await query.edit_message_text(
            _format_pipeline_message(pipeline_effects),
            reply_markup=reply_markup
        )
        logger.info(f"[{correlation_id}] Normalize (profile={preset_name}) added to pipeline by user {user_id}")
        return

    # Handle apply pipeline
    if callback_data == "pipeline_apply":
        await _handle_pipeline_apply(update, context, pipeline_effects)
        return

    logger.warning(f"[{correlation_id}] Unknown pipeline callback: {callback_data}")


async def _handle_pipeline_apply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pipeline_effects: list
) -> None:
    """Apply the effect pipeline and process audio.

    Args:
        update: Telegram update object
        context: Telegram context object
        pipeline_effects: List of effect configs to apply
    """
    query = update.callback_query
    user_id = update.effective_user.id
    correlation_id = context.user_data.get("pipeline_correlation_id", str(uuid.uuid4())[:8])

    # Validate pipeline
    if not pipeline_effects:
        await query.answer("No has agregado efectos. Agrega al menos uno antes de aplicar.", show_alert=True)
        return

    # Retrieve file_id from context
    file_id = context.user_data.get("pipeline_file_id")
    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el archivo de audio. Intenta de nuevo.")
        return

    # Update message to show processing
    try:
        await query.edit_message_text(f"Aplicando pipeline ({len(pipeline_effects)} efectos)...")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not update message: {e}")

    logger.info(f"[{correlation_id}] Applying pipeline with {len(pipeline_effects)} effects for user {user_id}")

    # Process with TempManager for automatic cleanup
    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_pipeline_{user_id}_{correlation_id}.audio"
            output_filename = f"pipeline_{user_id}_{correlation_id}.mp3"

            input_path = temp_mgr.get_temp_path(input_filename)
            output_path = temp_mgr.get_temp_path(output_filename)

            # Download audio file
            logger.info(f"[{correlation_id}] Downloading audio from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Audio downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download audio for user {user_id}: {e}")
                raise DownloadError("No pude descargar el audio") from e

            # Validate audio integrity after download
            is_valid, error_msg = validate_audio_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Audio validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space before processing (estimate based on number of effects)
            audio_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(audio_size_mb * (1 + len(pipeline_effects) * 0.5)))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            # Apply effects in chain using AudioEffects
            logger.info(f"[{correlation_id}] Processing pipeline with {len(pipeline_effects)} effects for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                effects = AudioEffects(str(input_path), str(output_path))

                # Build method chain based on pipeline_effects order
                for effect in pipeline_effects:
                    effect_type = effect.get("type")
                    params = effect.get("params", {})

                    if effect_type == "denoise":
                        strength = params.get("strength", 5)
                        await asyncio.wait_for(
                            loop.run_in_executor(None, effects.denoise, float(strength)),
                            timeout=config.PROCESSING_TIMEOUT
                        )
                    elif effect_type == "compress":
                        ratio = params.get("ratio", 4.0)
                        await asyncio.wait_for(
                            loop.run_in_executor(None, effects.compress, ratio, -20.0),
                            timeout=config.PROCESSING_TIMEOUT
                        )
                    elif effect_type == "normalize":
                        target_lufs = params.get("target_lufs", -14.0)
                        await asyncio.wait_for(
                            loop.run_in_executor(None, effects.normalize, target_lufs),
                            timeout=config.PROCESSING_TIMEOUT
                        )

                # Finalize the effect chain
                final_output = await asyncio.wait_for(
                    loop.run_in_executor(None, effects.finalize),
                    timeout=config.PROCESSING_TIMEOUT
                )

                if not final_output or not Path(final_output).exists():
                    logger.error(f"[{correlation_id}] Pipeline processing failed for user {user_id}")
                    raise AudioEffectsError("No pude procesar el pipeline de efectos")

            except asyncio.TimeoutError as e:
                logger.error(f"[{correlation_id}] Pipeline processing timed out for user {user_id}")
                raise ProcessingTimeoutError("El procesamiento del pipeline tardó demasiado") from e

            # Send processed audio
            logger.info(f"[{correlation_id}] Sending pipeline result to user {user_id}")
            try:
                with open(output_path, "rb") as audio_file:
                    await context.bot.send_audio(
                        chat_id=update.effective_chat.id,
                        audio=audio_file,
                        filename=f"pipeline_audio.mp3",
                        title=f"Audio con pipeline ({len(pipeline_effects)} efectos)"
                    )
                logger.info(f"[{correlation_id}] Pipeline result sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to send pipeline result to user {user_id}: {e}")
                raise

            # Build effect list for success message
            effect_list = []
            for effect in pipeline_effects:
                effect_type = effect.get("type", "unknown")
                params = effect.get("params", {})
                if effect_type == "denoise":
                    effect_list.append(f"Denoise ({params.get('strength', 5)})")
                elif effect_type == "compress":
                    effect_list.append(f"Compress ({params.get('preset_name', 'media')})")
                elif effect_type == "normalize":
                    effect_list.append(f"Normalize ({params.get('preset_name', 'música')})")

            # Update message on success
            try:
                await query.edit_message_text(
                    f"¡Listo! Pipeline aplicado ({len(pipeline_effects)} efectos):\n"
                    + "\n".join(f"  {i+1}. {name}" for i, name in enumerate(effect_list))
                )
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not update final message: {e}")

            # Clean up user_data
            context.user_data.pop("pipeline_file_id", None)
            context.user_data.pop("pipeline_correlation_id", None)
            context.user_data.pop("pipeline_effects", None)

        except (DownloadError, ValidationError, AudioEffectsError, ProcessingTimeoutError) as e:
            # Handle known processing errors
            logger.error(f"[{correlation_id}] Pipeline processing error: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error (keep state so user can retry)
            try:
                await query.edit_message_text(f"Error: {str(e)}\n\nPuedes intentar aplicar el pipeline de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        except Exception as e:
            # Handle unexpected errors
            logger.exception(f"[{correlation_id}] Unexpected error applying pipeline for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)

            # Update message on error
            try:
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
            except Exception as edit_error:
                logger.warning(f"[{correlation_id}] Could not update error message: {edit_error}")

        # TempManager cleanup happens automatically on context exit


async def handle_video_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video menu selections from inline keyboard.

    Routes to appropriate action based on user selection:
    - videonote: Convert video to circular video note
    - extract_audio: Show format selection for audio extraction
    - convert: Show format selection for video conversion
    - split: Show split options or prompt for parameters

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data
    correlation_id = context.user_data.get("video_menu_correlation_id", str(uuid.uuid4())[:8])

    # Parse action from callback data (format: video_action:<action>)
    if not callback_data.startswith("video_action:"):
        logger.warning(f"[{correlation_id}] Unexpected callback data: {callback_data}")
        return

    action = callback_data.split(":")[1]
    logger.info(f"[{correlation_id}] Video menu action selected: {action} by user {user_id}")

    # Retrieve file_id from context
    file_id = context.user_data.get("video_menu_file_id")
    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el video. Intenta de nuevo.")
        return

    if action == "videonote":
        # Process video to video note
        await query.edit_message_text("Procesando video a nota de video...")

        with TempManager() as temp_mgr:
            try:
                # Generate safe filenames
                input_filename = f"input_videonote_{user_id}_{correlation_id}.mp4"
                output_filename = f"videonote_{user_id}_{correlation_id}.mp4"

                input_path = temp_mgr.get_temp_path(input_filename)
                output_path = temp_mgr.get_temp_path(output_filename)

                # Download video
                logger.info(f"[{correlation_id}] Downloading video for videonote from user {user_id}")
                try:
                    file = await context.bot.get_file(file_id)
                    await _download_with_retry(file, input_path, correlation_id=correlation_id)
                    logger.info(f"[{correlation_id}] Video downloaded to {input_path}")
                except Exception as e:
                    logger.error(f"[{correlation_id}] Failed to download video for user {user_id}: {e}")
                    raise DownloadError("No pude descargar el video") from e

                # Validate video integrity
                is_valid, error_msg = validate_video_file(str(input_path))
                if not is_valid:
                    logger.warning(f"[{correlation_id}] Video validation failed for user {user_id}: {error_msg}")
                    raise ValidationError(error_msg)

                # Check disk space
                video_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
                required_space = estimate_required_space(int(video_size_mb))
                has_space, space_error = check_disk_space(required_space)
                if not has_space:
                    logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                    raise ValidationError(space_error)

                # Process video with timeout
                logger.info(f"[{correlation_id}] Processing video to video note for user {user_id}")
                try:
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
                        logger.error(f"[{correlation_id}] Video processing failed for user {user_id}")
                        raise FFmpegError("El procesamiento de video falló")

                except asyncio.TimeoutError as e:
                    logger.error(f"[{correlation_id}] Video processing timed out for user {user_id}")
                    raise ProcessingTimeoutError("El video tardó demasiado en procesarse") from e

                # Send as video note
                logger.info(f"[{correlation_id}] Sending video note to user {user_id}")
                try:
                    with open(output_path, "rb") as video_file:
                        await query.message.reply_video_note(video_note=video_file)
                    logger.info(f"[{correlation_id}] Video note sent successfully to user {user_id}")
                except Exception as e:
                    logger.error(f"[{correlation_id}] Failed to send video note to user {user_id}: {e}")
                    raise

                # Update message to confirm completion
                await query.edit_message_text("¡Listo! Nota de video enviada.")

                # Clean up context
                context.user_data.pop("video_menu_file_id", None)
                context.user_data.pop("video_menu_correlation_id", None)

            except (DownloadError, FFmpegError, ProcessingTimeoutError, ValidationError) as e:
                logger.error(f"[{correlation_id}] Video note processing error: {e}")
                await handle_processing_error(update, e, user_id)
                await query.edit_message_text(f"Error: {str(e)}")

                # Clean up context on error
                context.user_data.pop("video_menu_file_id", None)
                context.user_data.pop("video_menu_correlation_id", None)

            except Exception as e:
                logger.exception(f"[{correlation_id}] Unexpected error processing video note for user {user_id}: {e}")
                await handle_processing_error(update, e, user_id)
                await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")

                # Clean up context on error
                context.user_data.pop("video_menu_file_id", None)
                context.user_data.pop("video_menu_correlation_id", None)

    elif action == "extract_audio":
        # Store action type and show format selection
        context.user_data["video_menu_action"] = "extract_audio"

        reply_markup = _get_video_audio_format_keyboard()
        await query.edit_message_text(
            "Selecciona el formato de audio:",
            reply_markup=reply_markup
        )
        logger.info(f"[{correlation_id}] Showing audio format selection to user {user_id}")

    elif action == "convert":
        # Store action type and show format selection
        context.user_data["video_menu_action"] = "convert"

        reply_markup = _get_video_format_keyboard()
        await query.edit_message_text(
            "Selecciona el formato de video:",
            reply_markup=reply_markup
        )
        logger.info(f"[{correlation_id}] Showing video format selection to user {user_id}")

    elif action == "split":
        # Start interactive video split process
        # Send callback data with file_id to the split handler
        await query.edit_message_text(
            "✂️ Iniciando proceso para dividir video..."
        )
        
        # Create callback data with file_id
        split_callback_data = f"video_split:{file_id}"
        
        # Store original context for later
        context.user_data["video_menu_file_id"] = file_id
        context.user_data["video_menu_correlation_id"] = correlation_id
        
        # Call the split start handler
        # Create a fake update with the callback data
        await handle_video_split_start(update, context)

    elif action == "merge_audio":
        # Store video info and prompt user to send audio
        context.user_data["merge_video_file_id"] = file_id
        context.user_data["merge_video_correlation_id"] = correlation_id
        await query.edit_message_text(
            "¡Perfecto! Ahora envíame el archivo de audio que quieres agregar al video.\n\n"
            "Puede ser MP3, WAV, OGG, AAC, etc.\n\n"
            "Envía /cancel para cancelar."
        )
        logger.info(f"[{correlation_id}] Waiting for audio file from user {user_id} for merge")

    else:
        logger.warning(f"[{correlation_id}] Unknown video menu action: {action}")
        await query.edit_message_text("Acción no reconocida. Por favor intenta de nuevo.")

        # Clean up context
        context.user_data.pop("video_menu_file_id", None)
        context.user_data.pop("video_menu_correlation_id", None)


async def handle_video_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video format selection callbacks.

    Processes video conversion or audio extraction based on the
    previously stored action type and selected format.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data
    correlation_id = context.user_data.get("video_menu_correlation_id", str(uuid.uuid4())[:8])

    # Retrieve file_id and action from context
    file_id = context.user_data.get("video_menu_file_id")
    action = context.user_data.get("video_menu_action")

    if not file_id:
        logger.error(f"[{correlation_id}] No file_id found in context for user {user_id}")
        await query.edit_message_text("Error: no se encontró el video. Intenta de nuevo.")
        return

    if not action:
        logger.error(f"[{correlation_id}] No action found in context for user {user_id}")
        await query.edit_message_text("Error: acción no encontrada. Intenta de nuevo.")
        return

    # Parse format from callback data
    if callback_data.startswith("video_format:"):
        output_format = callback_data.split(":")[1]
    elif callback_data.startswith("video_audio_format:"):
        output_format = callback_data.split(":")[1]
    else:
        logger.warning(f"[{correlation_id}] Unexpected callback data: {callback_data}")
        return

    logger.info(f"[{correlation_id}] Format selected: {output_format} for action: {action} by user {user_id}")

    with TempManager() as temp_mgr:
        try:
            # Generate safe filenames
            input_filename = f"input_{action}_{user_id}_{correlation_id}.mp4"
            input_path = temp_mgr.get_temp_path(input_filename)

            # Download video
            logger.info(f"[{correlation_id}] Downloading video for {action} from user {user_id}")
            try:
                file = await context.bot.get_file(file_id)
                await _download_with_retry(file, input_path, correlation_id=correlation_id)
                logger.info(f"[{correlation_id}] Video downloaded to {input_path}")
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to download video for user {user_id}: {e}")
                raise DownloadError("No pude descargar el video") from e

            # Validate video integrity
            is_valid, error_msg = validate_video_file(str(input_path))
            if not is_valid:
                logger.warning(f"[{correlation_id}] Video validation failed for user {user_id}: {error_msg}")
                raise ValidationError(error_msg)

            # Check disk space
            video_size_mb = Path(input_path).stat().st_size / (1024 * 1024)
            required_space = estimate_required_space(int(video_size_mb))
            has_space, space_error = check_disk_space(required_space)
            if not has_space:
                logger.warning(f"[{correlation_id}] Disk space check failed for user {user_id}: {space_error}")
                raise ValidationError(space_error)

            if action == "convert":
                # Process video conversion
                await query.edit_message_text(f"Convirtiendo video a {output_format.upper()}...")

                output_filename = f"converted_{user_id}_{correlation_id}.{output_format}"
                output_path = temp_mgr.get_temp_path(output_filename)

                logger.info(f"[{correlation_id}] Converting video to {output_format} for user {user_id}")
                try:
                    loop = asyncio.get_event_loop()
                    converter = FormatConverter(str(input_path), str(output_path))
                    success = await asyncio.wait_for(
                        loop.run_in_executor(None, converter.convert, output_format),
                        timeout=config.PROCESSING_TIMEOUT
                    )

                    if not success:
                        logger.error(f"[{correlation_id}] Format conversion failed for user {user_id}")
                        raise FormatConversionError(f"No pude convertir el video a {output_format.upper()}")

                except asyncio.TimeoutError as e:
                    logger.error(f"[{correlation_id}] Format conversion timed out for user {user_id}")
                    raise ProcessingTimeoutError("La conversión tardó demasiado") from e

                # Send converted video
                logger.info(f"[{correlation_id}] Sending converted video to user {user_id}")
                try:
                    with open(output_path, "rb") as video_file:
                        await query.message.reply_video(video=video_file)
                    logger.info(f"[{correlation_id}] Converted video sent successfully to user {user_id}")
                except Exception as e:
                    logger.error(f"[{correlation_id}] Failed to send converted video to user {user_id}: {e}")
                    raise

                # Update message to confirm completion
                await query.edit_message_text(f"¡Listo! Video convertido a {output_format.upper()}.")

            elif action == "extract_audio":
                # Process audio extraction
                await query.edit_message_text(f"Extrayendo audio como {output_format.upper()}...")

                output_filename = f"audio_{user_id}_{correlation_id}.{output_format}"
                output_path = temp_mgr.get_temp_path(output_filename)

                logger.info(f"[{correlation_id}] Extracting audio as {output_format} for user {user_id}")
                try:
                    loop = asyncio.get_event_loop()
                    extractor = AudioExtractor(str(input_path), str(output_path))
                    success = await asyncio.wait_for(
                        loop.run_in_executor(None, extractor.extract, output_format),
                        timeout=config.PROCESSING_TIMEOUT
                    )

                    if not success:
                        logger.error(f"[{correlation_id}] Audio extraction failed for user {user_id}")
                        raise AudioExtractionError(f"No pude extraer el audio en formato {output_format.upper()}")

                except asyncio.TimeoutError as e:
                    logger.error(f"[{correlation_id}] Audio extraction timed out for user {user_id}")
                    raise ProcessingTimeoutError("La extracción de audio tardó demasiado") from e

                # Send extracted audio
                logger.info(f"[{correlation_id}] Sending extracted audio to user {user_id}")
                try:
                    with open(output_path, "rb") as audio_file:
                        await query.message.reply_audio(audio=audio_file)
                    logger.info(f"[{correlation_id}] Audio sent successfully to user {user_id}")
                except Exception as e:
                    logger.error(f"[{correlation_id}] Failed to send audio to user {user_id}: {e}")
                    raise

                # Update message to confirm completion
                await query.edit_message_text(f"¡Listo! Audio extraído como {output_format.upper()}.")

            # Clean up context
            context.user_data.pop("video_menu_file_id", None)
            context.user_data.pop("video_menu_correlation_id", None)
            context.user_data.pop("video_menu_action", None)

        except (DownloadError, FormatConversionError, AudioExtractionError, ProcessingTimeoutError, ValidationError) as e:
            logger.error(f"[{correlation_id}] Format selection processing error: {e}")
            await handle_processing_error(update, e, user_id)
            await query.edit_message_text(f"Error: {str(e)}")

            # Clean up context on error
            context.user_data.pop("video_menu_file_id", None)
            context.user_data.pop("video_menu_correlation_id", None)
            context.user_data.pop("video_menu_action", None)

        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error in format selection for user {user_id}: {e}")
            await handle_processing_error(update, e, user_id)
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")

            # Clean up context on error
            context.user_data.pop("video_menu_file_id", None)
            context.user_data.pop("video_menu_correlation_id", None)
            context.user_data.pop("video_menu_action", None)


async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel callback from inline keyboard.

    Cleans up all user context data related to ongoing operations
    and shows a cancellation confirmation message.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]

    # Clear video menu keys
    context.user_data.pop("video_menu_file_id", None)
    context.user_data.pop("video_menu_correlation_id", None)
    context.user_data.pop("video_menu_action", None)

    # Clear audio menu keys
    context.user_data.pop("audio_menu_file_id", None)
    context.user_data.pop("audio_menu_correlation_id", None)
    context.user_data.pop("audio_menu_action", None)

    # Clear convert keys
    context.user_data.pop("convert_audio_file_id", None)
    context.user_data.pop("convert_audio_correlation_id", None)

    # Clear enhance keys
    context.user_data.pop("enhance_audio_file_id", None)
    context.user_data.pop("enhance_audio_correlation_id", None)
    context.user_data.pop("enhance_type", None)

    # Clear EQ keys
    context.user_data.pop("eq_file_id", None)
    context.user_data.pop("eq_correlation_id", None)
    context.user_data.pop("eq_bass", None)
    context.user_data.pop("eq_mid", None)
    context.user_data.pop("eq_treble", None)

    # Clear effect keys
    context.user_data.pop("effect_audio_file_id", None)
    context.user_data.pop("effect_audio_correlation_id", None)
    context.user_data.pop("effect_type", None)

    # Clear pipeline keys
    context.user_data.pop("pipeline_file_id", None)
    context.user_data.pop("pipeline_correlation_id", None)
    context.user_data.pop("pipeline_effects", None)
    context.user_data.pop("pipeline_selecting_effect", None)

    # Clear merge keys
    context.user_data.pop("merge_video_file_id", None)
    context.user_data.pop("merge_video_correlation_id", None)

    await query.edit_message_text("Operación cancelada.")
    logger.info(f"[{correlation_id}] Operation cancelled by user {user_id}")


async def handle_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle back navigation callback from inline keyboard.

    Returns the user to the appropriate parent menu based on context.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Parse callback data: back:video or back:audio
    if not callback_data.startswith("back:"):
        logger.warning(f"Invalid back callback data: {callback_data}")
        return

    menu_type = callback_data.split(":")[1]

    if menu_type == "video":
        # Re-show video menu with stored file_id
        file_id = context.user_data.get("video_menu_file_id")
        if not file_id:
            await query.edit_message_text(
                "Error: no se encontró el archivo de video. Por favor envía el video de nuevo."
            )
            logger.warning(f"Back to video menu failed: no file_id for user {user_id}")
            return

        reply_markup = _get_video_menu_keyboard()
        await query.edit_message_text(
            "¿Qué quieres hacer con este video?",
            reply_markup=reply_markup
        )
        logger.info(f"User {user_id} navigated back to video menu")

    elif menu_type == "audio":
        # Re-show audio menu with stored file_id
        file_id = context.user_data.get("audio_menu_file_id")
        if not file_id:
            await query.edit_message_text(
                "Error: no se encontró el archivo de audio. Por favor envía el audio de nuevo."
            )
            logger.warning(f"Back to audio menu failed: no file_id for user {user_id}")
            return

        reply_markup = _get_audio_menu_keyboard()
        await query.edit_message_text(
            "¿Qué quieres hacer con este audio?",
            reply_markup=reply_markup
        )
        logger.info(f"User {user_id} navigated back to audio menu")

    else:
        logger.warning(f"Unknown back menu type: {menu_type}")


# =============================================================================
# URL Download Handlers
# =============================================================================

# Import PlatformRouter for metadata extraction
from bot.downloaders.platform_router import PlatformRouter

# Constants
TELEGRAM_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _detect_platform_for_display(url: str) -> str:
    """Detect platform name from URL for display purposes.

    Args:
        url: The URL to analyze

    Returns:
        Platform name for display, or empty string if unknown
    """
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'YouTube'
    elif 'instagram.com' in url_lower:
        return 'Instagram'
    elif 'tiktok.com' in url_lower:
        return 'TikTok'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'Twitter/X'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'Facebook'
    else:
        return ''


def _get_error_message_for_exception(e: Exception, url: str, correlation_id: str) -> str:
    """Get user-friendly error message for download exceptions.

    Handles network errors, platform-specific errors, file system errors,
    and Telegram errors with appropriate Spanish messages.

    Args:
        e: The exception that occurred
        url: The URL being downloaded
        correlation_id: Unique download ID for logging

    Returns:
        User-friendly error message in Spanish
    """
    import errno
    from telegram.error import NetworkError as TelegramNetworkError, RetryAfter, TimedOut as TelegramTimedOut

    error_msg = str(e).lower()
    platform = _detect_platform_for_display(url)

    # Network errors
    if isinstance(e, (ConnectionResetError, BrokenPipeError)):
        logger.warning(f"[{correlation_id}] Connection reset during download: {e}")
        return "La conexión se interrumpió. Intenta de nuevo."

    if isinstance(e, TimeoutError) or "timeout" in error_msg:
        logger.warning(f"[{correlation_id}] Download timeout: {e}")
        return "La descarga tardó demasiado, intenta de nuevo."

    if "dns" in error_msg or "name resolution" in error_msg or "getaddrinfo" in error_msg:
        logger.warning(f"[{correlation_id}] DNS failure: {e}")
        return "No se pudo conectar al servidor. Verifica la URL."

    # Platform-specific errors
    if platform == "YouTube":
        if "age" in error_msg or "restricted" in error_msg:
            return "Este video tiene restricción de edad."
        if "unavailable" in error_msg or "not available" in error_msg:
            return "Este video no está disponible."
        if "private" in error_msg:
            return "Este video es privado."

    if platform == "Instagram":
        if "private" in error_msg:
            return "Este contenido de Instagram es privado."
        if "story" in error_msg and ("expired" in error_msg or "unavailable" in error_msg):
            return "Esta historia de Instagram ha expirado."
        if "login" in error_msg or "authent" in error_msg:
            return "Este contenido requiere inicio de sesión en Instagram."

    if platform == "TikTok":
        if "slideshow" in error_msg or "carousel" in error_msg:
            return "Los slideshows de TikTok no son soportados."
        if "watermark" in error_msg:
            return "No se pudo descargar el video sin marca de agua."

    if platform == "Twitter/X":
        if "restricted" in error_msg or "sensitive" in error_msg:
            return "Este contenido está restringido."
        if "deleted" in error_msg or "not found" in error_msg:
            return "Este tweet no existe o fue eliminado."

    if platform == "Facebook":
        if "login" in error_msg or "authent" in error_msg:
            return "Este video requiere inicio de sesión en Facebook."
        if "private" in error_msg:
            return "Este video de Facebook es privado."

    # File system errors
    if isinstance(e, OSError):
        if e.errno == errno.ENOSPC:
            logger.error(f"[{correlation_id}] Disk full: {e}")
            return "No hay espacio suficiente en el servidor."
        if e.errno == errno.EACCES or e.errno == errno.EPERM:
            logger.error(f"[{correlation_id}] Permission denied: {e}")
            return "Error de permisos al guardar archivo."
        if e.errno == errno.ENOSPC or "no space" in error_msg:
            logger.error(f"[{correlation_id}] Disk full: {e}")
            return "No hay espacio suficiente en el servidor."

    # Telegram errors
    if isinstance(e, TelegramNetworkError):
        logger.warning(f"[{correlation_id}] Telegram network error: {e}")
        return "Error de red al enviar el archivo, intenta de nuevo."

    if isinstance(e, TelegramTimedOut):
        logger.warning(f"[{correlation_id}] Telegram timeout: {e}")
        return "El envío tardó demasiado, intenta de nuevo."

    if isinstance(e, RetryAfter):
        retry_after = getattr(e, 'retry_after', 30)
        logger.warning(f"[{correlation_id}] Rate limited: retry after {retry_after}s")
        return f"Demasiadas solicitudes, espera {retry_after} segundos."

    # File too large for Telegram
    if "file is too big" in error_msg or "too large" in error_msg or "entity too large" in error_msg:
        logger.warning(f"[{correlation_id}] File too large for Telegram: {e}")
        return "El archivo excede el límite de Telegram (50MB)."

    # Generic download errors
    if "404" in error_msg or "not found" in error_msg:
        return "No se encontró el contenido en la URL proporcionada."

    if "403" in error_msg or "forbidden" in error_msg:
        return "Acceso denegado al contenido."

    # Default error
    logger.error(f"[{correlation_id}] Unhandled error: {type(e).__name__}: {e}")
    return "Ocurrió un error inesperado. Por favor intenta de nuevo."


def _get_download_format_keyboard(correlation_id: str, url_metadata: dict = None) -> InlineKeyboardMarkup:
    """Generate inline keyboard for download format selection.

    Args:
        correlation_id: Unique ID for this download request
        url_metadata: Optional metadata about the URL (platform, content type, etc.)

    Returns:
        InlineKeyboardMarkup with video/audio options and combined actions
    """
    # Determine available options based on content type
    is_video_content = True  # Default to showing video options
    is_audio_content = False

    if url_metadata:
        # Check if content is audio-only (e.g., YouTube audio, SoundCloud)
        content_type = url_metadata.get('content_type', 'video')
        is_audio_content = content_type == 'audio' or url_metadata.get('is_audio_only', False)
        is_video_content = not is_audio_content or url_metadata.get('has_video', True)

    keyboard = []

    # Basic download options
    basic_row = []
    if is_video_content:
        basic_row.append(InlineKeyboardButton("Video", callback_data=f"download:video:{correlation_id}"))
    if is_audio_content or is_video_content:
        basic_row.append(InlineKeyboardButton("Audio", callback_data=f"download:audio:{correlation_id}"))
    if basic_row:
        keyboard.append(basic_row)

    # Combined action options (video content only)
    if is_video_content:
        keyboard.append([
            InlineKeyboardButton("Video + Nota de Video", callback_data=f"download:video:videonote:{correlation_id}"),
            InlineKeyboardButton("Video + Extraer Audio", callback_data=f"download:video:extract:{correlation_id}"),
        ])

    # Combined action options for audio
    if is_audio_content or is_video_content:
        keyboard.append([
            InlineKeyboardButton("Audio + Nota de Voz", callback_data=f"download:audio:voicenote:{correlation_id}"),
        ])

    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])

    return InlineKeyboardMarkup(keyboard)


def _get_large_download_confirmation_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for large download confirmation.

    Args:
        correlation_id: Unique ID for this download request

    Returns:
        InlineKeyboardMarkup with confirm/cancel options
    """
    keyboard = [
        [
            InlineKeyboardButton("Confirmar Descarga", callback_data=f"download:confirm:{correlation_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_download_cancel_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard with cancel button for active download.

    Args:
        correlation_id: Unique ID for this download request

    Returns:
        InlineKeyboardMarkup with cancel button
    """
    keyboard = [
        [
            InlineKeyboardButton("❌ Cancelar Descarga", callback_data=f"download:cancel:{correlation_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_download_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /download command to download a URL.

    Usage: /download <url>

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id
    correlation_id = str(uuid.uuid4())[:8]

    # Parse URL from command arguments
    args = context.args
    if not args:
        await update.message.reply_text(
            "Por favor proporciona una URL para descargar.\n"
            "Ejemplo: /download https://youtube.com/watch?v=..."
        )
        return

    url = args[0]

    # Validate URL
    if not url_detector.validate_url(url):
        await update.message.reply_text(
            "La URL proporcionada no parece válida.\n"
            "Asegúrate de incluir http:// o https://"
        )
        return

    # Check if URL is supported
    if not url_detector.is_supported(url):
        await update.message.reply_text(
            "Esta URL no parece ser un video soportado.\n"
            "Soporto YouTube, Instagram, TikTok, Twitter/X, Facebook y URLs directas de video."
        )
        return

    logger.info(f"[{correlation_id}] Download command from user {user_id}: {url}")

    # Store URL and correlation_id in context
    context.user_data[f"download_url_{correlation_id}"] = url
    context.user_data[f"download_correlation_id_{user_id}"] = correlation_id

    # Show format selection menu
    reply_markup = _get_download_format_keyboard(correlation_id)
    await update.message.reply_text(
        "Selecciona formato:\n"
        "- Video: Solo descargar video\n"
        "- Audio: Solo extraer audio\n"
        "- Video + Nota de Video: Descargar y convertir a nota circular\n"
        "- Video + Extraer Audio: Descargar y extraer audio\n"
        "- Audio + Nota de Voz: Descargar y convertir a nota de voz",
        reply_markup=reply_markup
    )


async def handle_url_detection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle URL detection in regular text messages.

    Detects URLs and shows inline menu for format selection.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    message_text = update.message.text
    user_id = update.effective_user.id

    # Detect URLs in message
    urls = url_detector.extract_urls(message_text, update.message.entities)
    if not urls:
        # No URLs, delegate to split text input handler
        await handle_split_text_input(update, context)
        return

    # Process first URL
    url = urls[0]

    # Validate URL
    if not url_detector.validate_url(url):
        # Not a valid URL, delegate to split text input handler
        await handle_split_text_input(update, context)
        return

    # Check if URL is supported
    if not url_detector.is_supported(url):
        # Not a supported video URL, delegate to split text input handler
        await handle_split_text_input(update, context)
        return

    correlation_id = str(uuid.uuid4())[:8]
    logger.info(f"[{correlation_id}] URL detected in message from user {user_id}: {url}")

    # Store URL and correlation_id in context
    context.user_data[f"download_url_{correlation_id}"] = url
    context.user_data[f"download_correlation_id_{user_id}"] = correlation_id

    # Show format selection menu
    reply_markup = _get_download_format_keyboard(correlation_id)
    await update.message.reply_text(
        "Enlace de video detectado. Selecciona el formato:\n"
        "- Video: Solo descargar video\n"
        "- Audio: Solo extraer audio\n"
        "- Video + Nota de Video: Descargar y convertir a nota circular\n"
        "- Video + Extraer Audio: Descargar y extraer audio\n"
        "- Audio + Nota de Voz: Descargar y convertir a nota de voz",
        reply_markup=reply_markup
    )


async def handle_download_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle format selection callback for downloads.

    Parses callback data, retrieves URL, checks file size,
    and either shows confirmation or starts download.
    Supports both simple format selection and combined download+process actions.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Parse callback data:
    # - download:format:correlation_id (simple)
    # - download:format:action:correlation_id (combined)
    if not callback_data.startswith("download:video:") and not callback_data.startswith("download:audio:"):
        logger.warning(f"Unexpected callback data: {callback_data}")
        return

    parts = callback_data.split(":")
    if len(parts) not in (3, 4):
        logger.warning(f"Invalid callback data format: {callback_data}")
        return

    format_type = parts[1]  # video or audio
    correlation_id = parts[-1]  # Last part is always correlation_id
    post_action = parts[2] if len(parts) == 4 else None  # videonote, extract, voicenote

    # Retrieve URL from context
    url = context.user_data.get(f"download_url_{correlation_id}")
    if not url:
        await query.edit_message_text(
            "Error: No se encontró la URL. Intenta de nuevo."
        )
        return

    if post_action:
        logger.info(f"[{correlation_id}] Combined action selected: {format_type} + {post_action} by user {user_id}")
    else:
        logger.info(f"[{correlation_id}] Format selected: {format_type} by user {user_id}")

    # Store format preference and post-action
    context.user_data[f"download_format_{correlation_id}"] = format_type
    if post_action:
        context.user_data[f"download_post_action_{correlation_id}"] = post_action

    # Check file size before downloading
    await query.edit_message_text("Analizando tamaño del archivo...")

    try:
        # Extract metadata using PlatformRouter
        from bot.downloaders import DownloadOptions
        router = PlatformRouter()
        route_result = await router.route(url)
        options = DownloadOptions(output_path="/tmp")
        metadata = await route_result.downloader.extract_metadata(url, options)

        # Get file size
        size = metadata.get('filesize') or metadata.get('filesize_approx', 0)

        # Store metadata for later use
        context.user_data[f"download_meta_{correlation_id}"] = metadata

        if size and size > TELEGRAM_MAX_FILE_SIZE:
            # Large file - show confirmation
            size_mb = size / (1024 * 1024)
            logger.info(f"[{correlation_id}] Large file detected: {size_mb:.1f} MB")

            # For combined actions, note that processing may change size
            action_note = ""
            if post_action:
                action_note = "\nNota: El procesamiento posterior puede cambiar el tamaño."

            reply_markup = _get_large_download_confirmation_keyboard(correlation_id)
            await query.edit_message_text(
                f"El archivo es grande (~{size_mb:.1f} MB).{action_note}\n\n"
                f"Esto puede tomar tiempo y consumir datos.\n"
                f"¿Deseas continuar?",
                reply_markup=reply_markup
            )
        else:
            # Small file or unknown size - proceed directly
            if size:
                size_mb = size / (1024 * 1024)
                logger.info(f"[{correlation_id}] File size: {size_mb:.1f} MB - proceeding")
            else:
                logger.info(f"[{correlation_id}] Unknown file size - proceeding")

            # Start download (combined flow if post_action specified)
            if post_action:
                await _start_combined_download(update, context, correlation_id, url, format_type, post_action)
            else:
                await _start_download(update, context, correlation_id, url, format_type)

    except Exception as e:
        logger.warning(f"[{correlation_id}] Could not get metadata: {e}")
        # If we can't get metadata, proceed anyway (will fail during download if too large)
        if post_action:
            await _start_combined_download(update, context, correlation_id, url, format_type, post_action)
        else:
            await _start_download(update, context, correlation_id, url, format_type)


async def handle_download_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation callback for large downloads.

    Starts the download after user confirms.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Parse callback data: download:confirm:correlation_id
    if not callback_data.startswith("download:confirm:"):
        return

    correlation_id = callback_data.split(":")[2]

    # Retrieve URL and format from context
    url = context.user_data.get(f"download_url_{correlation_id}")
    format_type = context.user_data.get(f"download_format_{correlation_id}", "video")

    if not url:
        await query.edit_message_text(
            "Error: No se encontró la información de descarga. Intenta de nuevo."
        )
        return

    logger.info(f"[{correlation_id}] Large download confirmed by user {user_id}")

    # Check for combined action
    post_action = context.user_data.get(f"download_post_action_{correlation_id}")

    # Start download (combined flow if post_action specified)
    if post_action:
        await _start_combined_download(update, context, correlation_id, url, format_type, post_action)
    else:
        await _start_download(update, context, correlation_id, url, format_type)


async def _start_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    correlation_id: str,
    url: str,
    format_type: str
) -> None:
    """Start the download process with progress updates.

    Args:
        update: Telegram update object
        context: Telegram context object
        correlation_id: Unique download ID
        url: URL to download
        format_type: 'video' or 'audio'
    """
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Detect platform for display
    platform = _detect_platform_for_display(url)

    # Create facade
    facade = DownloadFacade()

    try:
        await facade.start()

        # Store facade instance for cancellation support
        context.user_data[f"download_facade_{correlation_id}"] = facade
        context.user_data[f"download_url_{correlation_id}"] = url
        context.user_data[f"download_format_{correlation_id}"] = format_type
        context.user_data[f"download_status_{correlation_id}"] = "downloading"

        # Initial message with cancel button
        reply_markup = _get_download_cancel_keyboard(correlation_id)
        await query.edit_message_text(
            f"Analizando enlace de {platform}...",
            reply_markup=reply_markup
        )

        # Progress tracking with enhanced state management
        last_message_text = [f"Analizando enlace de {platform}..."]
        last_update_time = [0.0]  # Track last update time for rate limiting

        async def progress_callback(progress: dict) -> None:
            """Update download progress message with cancel button."""
            import time
            from bot.downloaders.progress_tracker import format_progress_message

            status = progress.get('status', 'downloading')
            percent = progress.get('percent', 0)

            # Rate limiting: only update every 1 second minimum
            current_time = time.time()
            if current_time - last_update_time[0] < 1.0 and status == 'downloading':
                return

            # Format message based on status
            if status == 'downloading':
                message = format_progress_message(progress)
                # Add platform info to message
                if platform:
                    message = f"Descargando de {platform}...\n{message}"

                if message != last_message_text[0]:
                    try:
                        await query.edit_message_text(
                            message,
                            reply_markup=reply_markup
                        )
                        last_message_text[0] = message
                        last_update_time[0] = current_time
                    except Exception as e:
                        logger.debug(f"Failed to update progress message: {e}")

            elif status == 'completed':
                # Remove cancel button, show completed
                try:
                    await query.edit_message_text("Descarga completada")
                    context.user_data[f"download_status_{correlation_id}"] = "completed"
                except Exception:
                    pass

            elif status == 'error':
                error_msg = progress.get('error', 'Error desconocido')
                try:
                    await query.edit_message_text(f"Error: {error_msg}")
                    context.user_data[f"download_status_{correlation_id}"] = "error"
                except Exception:
                    pass

        # Create progress tracker with callback
        from bot.downloaders.progress_tracker import ProgressTracker
        tracker = ProgressTracker(
            min_update_interval=3.0,
            min_percent_change=5.0,
            on_update=lambda p: asyncio.create_task(progress_callback(p))
        )

        # Download with progress callback integration
        config_overrides = {
            'extract_audio': (format_type == 'audio'),
        }

        result = await facade.download(
            url=url,
            chat_id=chat_id,
            config_overrides=config_overrides
        )

        if result.success:
            context.user_data[f"download_status_{correlation_id}"] = "completed"

            # Send downloaded file
            await _send_downloaded_file_with_menu(update, context, result, format_type, correlation_id)

            # Clean up status message
            try:
                await query.delete_message()
            except Exception:
                pass
        else:
            context.user_data[f"download_status_{correlation_id}"] = "error"
            await query.edit_message_text(
                f"Error en la descarga: {getattr(result, 'error_message', 'Error desconocido')}"
            )

    except FileTooLargeError as e:
        logger.warning(f"[{correlation_id}] File too large: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        await query.edit_message_text(e.to_user_message())
    except URLValidationError as e:
        logger.warning(f"[{correlation_id}] URL validation error: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        await query.edit_message_text(e.to_user_message())
    except UnsupportedURLError as e:
        logger.warning(f"[{correlation_id}] Unsupported URL: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        await query.edit_message_text(e.to_user_message())
    except DownloadError as e:
        logger.error(f"[{correlation_id}] Download error: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        error_msg = _get_error_message_for_exception(e, url, correlation_id)
        await query.edit_message_text(error_msg)
    except Exception as e:
        logger.error(f"[{correlation_id}] Unexpected error: {type(e).__name__}: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        error_msg = _get_error_message_for_exception(e, url, correlation_id)
        await query.edit_message_text(error_msg)
    finally:
        # Clean up facade reference but keep status for /downloads command
        context.user_data.pop(f"download_facade_{correlation_id}", None)
        try:
            await facade.stop()
        except Exception:
            pass


async def _send_downloaded_file_with_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: Any,
    format_type: str,
    correlation_id: str
) -> None:
    """Send downloaded file and show post-download menu.

    Args:
        update: Telegram update object
        context: Telegram context object
        result: Download result
        format_type: 'video' or 'audio'
        correlation_id: Unique download ID
    """
    from bot.downloaders.download_lifecycle import DownloadResult as LifecycleResult

    if isinstance(result, LifecycleResult):
        file_path = result.file_path
        metadata = result.metadata or {}
    elif isinstance(result, dict):
        file_path = result.get('file_path') or result.get('path')
        metadata = result.get('metadata', {})
    else:
        file_path = str(result)
        metadata = {}

    if not file_path or not os.path.exists(file_path):
        await update.callback_query.message.reply_text(
            "Error: No se encontró el archivo descargado."
        )
        return

    # Determine file type
    file_ext = os.path.splitext(file_path)[1].lower()
    audio_extensions = {'.mp3', '.aac', '.wav', '.ogg', '.flac', '.m4a', '.opus'}

    title = metadata.get('title', 'Video')

    try:
        if format_type == 'audio' or file_ext in audio_extensions:
            # Send as audio
            with open(file_path, 'rb') as audio_file:
                await update.callback_query.message.reply_audio(
                    audio=audio_file,
                    caption=f"Descarga completada: {title}",
                    title=title,
                    performer=metadata.get('artist') or metadata.get('uploader')
                )
        else:
            # Send as video with post-download menu
            with open(file_path, 'rb') as video_file:
                sent_message = await update.callback_query.message.reply_video(
                    video=video_file,
                    caption=f"Descarga completada: {title}",
                    supports_streaming=True
                )

            # Show post-download menu for video
            # Store file info for post-download actions
            context.user_data["video_menu_file_id"] = sent_message.video.file_id
            context.user_data["video_menu_correlation_id"] = correlation_id

            reply_markup = _get_video_menu_keyboard()
            await update.callback_query.message.reply_text(
                "¿Qué quieres hacer con este video?",
                reply_markup=reply_markup
            )

        logger.info(f"Downloaded file sent to user {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Failed to send downloaded file: {e}")
        await update.callback_query.message.reply_text(
            "Error al enviar el archivo descargado."
        )


async def _start_combined_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    correlation_id: str,
    url: str,
    format_type: str,
    post_action: str
) -> None:
    """Start combined download and process flow.

    Downloads the file and immediately processes it based on post_action.

    Args:
        update: Telegram update object
        context: Telegram context object
        correlation_id: Unique download ID
        url: URL to download
        format_type: 'video' or 'audio'
        post_action: 'videonote', 'extract', or 'voicenote'
    """
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Detect platform for display
    platform = _detect_platform_for_display(url)

    # Create facade
    facade = DownloadFacade()

    try:
        await facade.start()

        # Store facade instance for cancellation support
        context.user_data[f"download_facade_{correlation_id}"] = facade
        context.user_data[f"download_url_{correlation_id}"] = url
        context.user_data[f"download_format_{correlation_id}"] = format_type
        context.user_data[f"download_post_action_{correlation_id}"] = post_action
        context.user_data[f"download_status_{correlation_id}"] = "downloading"

        # Initial message with cancel button
        reply_markup = _get_download_cancel_keyboard(correlation_id)

        # Map action to display name
        action_names = {
            "videonote": "Nota de Video",
            "extract": "Extraer Audio",
            "voicenote": "Nota de Voz"
        }
        action_name = action_names.get(post_action, post_action)

        await query.edit_message_text(
            f"Descargando de {platform} para convertir a {action_name}...",
            reply_markup=reply_markup
        )

        # Progress tracking with enhanced state management
        last_message_text = [f"Descargando de {platform}..."]
        last_update_time = [0.0]

        async def progress_callback(progress: dict) -> None:
            """Update download progress message."""
            import time
            from bot.downloaders.progress_tracker import format_progress_message

            status = progress.get('status', 'downloading')
            percent = progress.get('percent', 0)

            # Rate limiting: only update every 1 second minimum
            current_time = time.time()
            if current_time - last_update_time[0] < 1.0 and status == 'downloading':
                return

            # Format message based on status
            if status == 'downloading':
                message = format_progress_message(progress)
                message = f"Descargando de {platform}...\n{message}\nLuego: convertir a {action_name}"

                if message != last_message_text[0]:
                    try:
                        await query.edit_message_text(
                            message,
                            reply_markup=reply_markup
                        )
                        last_message_text[0] = message
                        last_update_time[0] = current_time
                    except Exception as e:
                        logger.debug(f"Failed to update progress message: {e}")

            elif status == 'completed':
                try:
                    await query.edit_message_text(f"Descarga completada. Convirtiendo a {action_name}...")
                    context.user_data[f"download_status_{correlation_id}"] = "completed"
                except Exception:
                    pass

            elif status == 'error':
                error_msg = progress.get('error', 'Error desconocido')
                try:
                    await query.edit_message_text(f"Error en la descarga: {error_msg}")
                    context.user_data[f"download_status_{correlation_id}"] = "error"
                except Exception:
                    pass

        # Create progress tracker with callback
        from bot.downloaders.progress_tracker import ProgressTracker
        tracker = ProgressTracker(
            min_update_interval=3.0,
            min_percent_change=5.0,
            on_update=lambda p: asyncio.create_task(progress_callback(p))
        )

        # Download with progress callback integration
        config_overrides = {
            'extract_audio': (format_type == 'audio'),
        }

        result = await facade.download(
            url=url,
            chat_id=chat_id,
            config_overrides=config_overrides
        )

        if result.success:
            context.user_data[f"download_status_{correlation_id}"] = "completed"

            # Immediately process based on post_action
            await query.edit_message_text(f"Descarga completada. Convirtiendo a {action_name}...")

            try:
                if post_action == "videonote":
                    await _process_to_videonote(update, context, result, correlation_id)
                elif post_action == "extract":
                    await _process_extract_audio(update, context, result, correlation_id)
                elif post_action == "voicenote":
                    await _process_to_voicenote(update, context, result, correlation_id)
                else:
                    logger.warning(f"Unknown post_action: {post_action}")
                    await _send_downloaded_file_with_menu(update, context, result, format_type, correlation_id)
            except Exception as e:
                logger.error(f"[{correlation_id}] Post-download processing failed: {e}")
                await query.edit_message_text(
                    f"Descarga completada pero el procesamiento falló: {e}\n"
                    f"El archivo descargado se enviará sin procesar."
                )
                # Send original file as fallback
                await _send_downloaded_file_with_menu(update, context, result, format_type, correlation_id)
        else:
            context.user_data[f"download_status_{correlation_id}"] = "error"
            await query.edit_message_text(
                f"Error en la descarga: {getattr(result, 'error_message', 'Error desconocido')}"
            )

    except FileTooLargeError as e:
        logger.warning(f"[{correlation_id}] File too large: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        await query.edit_message_text(e.to_user_message())
    except URLValidationError as e:
        logger.warning(f"[{correlation_id}] URL validation error: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        await query.edit_message_text(e.to_user_message())
    except UnsupportedURLError as e:
        logger.warning(f"[{correlation_id}] Unsupported URL: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        await query.edit_message_text(e.to_user_message())
    except DownloadError as e:
        logger.error(f"[{correlation_id}] Download error: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        error_msg = _get_error_message_for_exception(e, url, correlation_id)
        await query.edit_message_text(error_msg)
    except Exception as e:
        logger.error(f"[{correlation_id}] Unexpected error: {type(e).__name__}: {e}")
        context.user_data[f"download_status_{correlation_id}"] = "error"
        error_msg = _get_error_message_for_exception(e, url, correlation_id)
        await query.edit_message_text(error_msg)
    finally:
        # Clean up facade reference but keep status for /downloads command
        context.user_data.pop(f"download_facade_{correlation_id}", None)
        context.user_data.pop(f"download_post_action_{correlation_id}", None)
        try:
            await facade.stop()
        except Exception:
            pass


async def _process_to_videonote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: Any,
    correlation_id: str
) -> None:
    """Process downloaded video to video note.

    Args:
        update: Telegram update object
        context: Telegram context object
        result: Download result with file_path
        correlation_id: Unique download ID
    """
    from bot.downloaders.download_lifecycle import DownloadResult as LifecycleResult

    if isinstance(result, LifecycleResult):
        file_path = result.file_path
        metadata = result.metadata or {}
    elif isinstance(result, dict):
        file_path = result.get('file_path') or result.get('path')
        metadata = result.get('metadata', {})
    else:
        file_path = str(result)
        metadata = {}

    if not file_path or not os.path.exists(file_path):
        await update.callback_query.message.reply_text(
            "Error: No se encontró el archivo descargado."
        )
        return

    temp_mgr = TempManager()
    output_filename = f"videonote_{correlation_id}.mp4"
    output_path = temp_mgr.get_temp_path(output_filename)

    try:
        # Process video to video note format
        success = await asyncio.get_event_loop().run_in_executor(
            None,
            VideoProcessor.process_video,
            str(file_path),
            str(output_path)
        )

        if success and os.path.exists(output_path):
            with open(output_path, 'rb') as video_file:
                await update.callback_query.message.reply_video_note(video_note=video_file)
            logger.info(f"[{correlation_id}] Video note sent successfully")
        else:
            raise FFmpegError("El procesamiento de video falló")

    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to convert to video note: {e}")
        await update.callback_query.message.reply_text(
            f"Error al convertir a nota de video: {e}"
        )
        # Send original as fallback
        await _send_downloaded_file_with_menu(update, context, result, "video", correlation_id)
    finally:
        temp_mgr.cleanup()


async def _process_extract_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: Any,
    correlation_id: str
) -> None:
    """Extract audio from downloaded video.

    Args:
        update: Telegram update object
        context: Telegram context object
        result: Download result with file_path
        correlation_id: Unique download ID
    """
    from bot.downloaders.download_lifecycle import DownloadResult as LifecycleResult

    if isinstance(result, LifecycleResult):
        file_path = result.file_path
        metadata = result.metadata or {}
    elif isinstance(result, dict):
        file_path = result.get('file_path') or result.get('path')
        metadata = result.get('metadata', {})
    else:
        file_path = str(result)
        metadata = {}

    if not file_path or not os.path.exists(file_path):
        await update.callback_query.message.reply_text(
            "Error: No se encontró el archivo descargado."
        )
        return

    temp_mgr = TempManager()
    output_filename = f"audio_{correlation_id}.mp3"
    output_path = temp_mgr.get_temp_path(output_filename)

    try:
        # Extract audio using AudioExtractor
        extractor = AudioExtractor(str(file_path), str(output_path))
        success = await asyncio.get_event_loop().run_in_executor(
            None,
            extractor.extract
        )

        if success and os.path.exists(output_path):
            title = metadata.get('title', 'Video')
            with open(output_path, 'rb') as audio_file:
                await update.callback_query.message.reply_audio(
                    audio=audio_file,
                    caption=f"Audio extraído: {title}",
                    title=title,
                    performer=metadata.get('artist') or metadata.get('uploader')
                )
            logger.info(f"[{correlation_id}] Audio extracted and sent successfully")
        else:
            raise AudioExtractionError("La extracción de audio falló")

    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to extract audio: {e}")
        await update.callback_query.message.reply_text(
            f"Error al extraer audio: {e}"
        )
        # Send original as fallback
        await _send_downloaded_file_with_menu(update, context, result, "video", correlation_id)
    finally:
        temp_mgr.cleanup()


async def _process_to_voicenote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: Any,
    correlation_id: str
) -> None:
    """Process downloaded audio to voice note.

    Args:
        update: Telegram update object
        context: Telegram context object
        result: Download result with file_path
        correlation_id: Unique download ID
    """
    from bot.downloaders.download_lifecycle import DownloadResult as LifecycleResult

    if isinstance(result, LifecycleResult):
        file_path = result.file_path
        metadata = result.metadata or {}
    elif isinstance(result, dict):
        file_path = result.get('file_path') or result.get('path')
        metadata = result.get('metadata', {})
    else:
        file_path = str(result)
        metadata = {}

    if not file_path or not os.path.exists(file_path):
        await update.callback_query.message.reply_text(
            "Error: No se encontró el archivo descargado."
        )
        return

    temp_mgr = TempManager()
    output_filename = f"voicenote_{correlation_id}.ogg"
    output_path = temp_mgr.get_temp_path(output_filename)

    try:
        # Convert to voice note format (OGG Opus)
        converter = VoiceNoteConverter(str(file_path), str(output_path))
        success = await asyncio.get_event_loop().run_in_executor(
            None,
            converter.convert
        )

        if success and os.path.exists(output_path):
            with open(output_path, 'rb') as voice_file:
                await update.callback_query.message.reply_voice(voice=voice_file)
            logger.info(f"[{correlation_id}] Voice note sent successfully")
        else:
            raise VoiceConversionError("La conversión a nota de voz falló")

    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to convert to voice note: {e}")
        await update.callback_query.message.reply_text(
            f"Error al convertir a nota de voz: {e}"
        )
        # Send original as fallback
        await _send_downloaded_file_with_menu(update, context, result, "audio", correlation_id)
    finally:
        temp_mgr.cleanup()


async def handle_download_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle download cancellation callback.

    Handles race conditions gracefully:
    - If download completes before cancel is processed, show "already completed"
    - If cancel fails due to already-finished state, show appropriate message
    - Always clean up user_data to prevent stale references

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Parse callback data: download:cancel:correlation_id
    if not callback_data.startswith("download:cancel:"):
        logger.warning(f"Invalid cancel callback data: {callback_data}")
        await query.edit_message_text("Error: callback inválido")
        return

    parts = callback_data.split(":")
    if len(parts) != 3:
        logger.warning(f"Invalid callback data format: {callback_data}")
        await query.edit_message_text("Error: formato de callback inválido")
        return

    correlation_id = parts[2]

    logger.info(f"[{correlation_id}] Download cancel requested by user {user_id}")

    # Get current status to check race conditions
    current_status = context.user_data.get(f"download_status_{correlation_id}", "unknown")

    # Get facade instance
    facade = context.user_data.get(f"download_facade_{correlation_id}")

    cancelled = False
    if facade:
        try:
            # Cancel the download
            cancelled = await facade.cancel_download(correlation_id)
            if cancelled:
                logger.info(f"[{correlation_id}] Download cancelled successfully")
                await query.edit_message_text("Descarga cancelada")
                context.user_data[f"download_status_{correlation_id}"] = "cancelled"
            else:
                # Check if already completed (race condition)
                if current_status == "completed":
                    logger.info(f"[{correlation_id}] Cancel failed - download already completed")
                    await query.edit_message_text("La descarga ya se había completado")
                else:
                    logger.info(f"[{correlation_id}] Cancel failed - download not found or already finished")
                    await query.edit_message_text("No se pudo cancelar (¿ya completada?)")
        except Exception as e:
            logger.error(f"[{correlation_id}] Error during cancel: {e}")
            await query.edit_message_text("Error al cancelar la descarga")
    else:
        # No facade found - download may have already finished
        if current_status == "completed":
            logger.info(f"[{correlation_id}] No facade found - download already completed")
            await query.edit_message_text("La descarga ya se había completado")
        elif current_status == "error":
            logger.info(f"[{correlation_id}] No facade found - download already failed")
            await query.edit_message_text("La descarga ya había fallado")
        else:
            logger.info(f"[{correlation_id}] No facade found - marking as cancelled")
            await query.edit_message_text("Descarga cancelada")
            context.user_data[f"download_status_{correlation_id}"] = "cancelled"

    # Clean up user_data
    context.user_data.pop(f"download_url_{correlation_id}", None)
    context.user_data.pop(f"download_format_{correlation_id}", None)
    context.user_data.pop(f"download_meta_{correlation_id}", None)
    context.user_data.pop(f"download_facade_{correlation_id}", None)
    # Keep download_status for /downloads command history


async def handle_downloads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /downloads command to show active and recent downloads.

    Displays a list of active downloads with progress and recent downloads
    with their completion status. Provides cancel buttons for active downloads.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id

    # Collect active downloads from user_data
    active_downloads = []
    recent_downloads = []

    # Scan user_data for download entries
    for key in list(context.user_data.keys()):
        if key.startswith("download_status_"):
            correlation_id = key.replace("download_status_", "")
            status = context.user_data.get(key, "unknown")
            url = context.user_data.get(f"download_url_{correlation_id}", "")
            format_type = context.user_data.get(f"download_format_{correlation_id}", "video")

            # Get platform for display
            platform = _detect_platform_for_display(url) or "Desconocido"

            download_info = {
                "correlation_id": correlation_id,
                "status": status,
                "platform": platform,
                "format": format_type,
                "url": url[:50] + "..." if len(url) > 50 else url
            }

            if status == "downloading":
                active_downloads.append(download_info)
            elif status in ["completed", "error", "cancelled"]:
                recent_downloads.append(download_info)

    # Sort recent downloads by correlation_id (which includes timestamp info)
    recent_downloads = sorted(recent_downloads, key=lambda x: x["correlation_id"], reverse=True)[:5]

    # Build message
    lines = ["Descargas activas:"]

    if active_downloads:
        for d in active_downloads:
            lines.append(f"  {d['correlation_id']}: {d['platform']} ({d['format']})")
    else:
        lines.append("  Ninguna")

    lines.append("\nDescargas recientes:")

    if recent_downloads:
        for d in recent_downloads:
            status_icon = "✅" if d['status'] == "completed" else "❌" if d['status'] == "error" else "🚫"
            lines.append(f"  {status_icon} {d['correlation_id']}: {d['platform']}")
    else:
        lines.append("  Ninguna")

    # Add cancel buttons for active downloads
    keyboard = []
    for d in active_downloads:
        keyboard.append([
            InlineKeyboardButton(
                f"Cancelar {d['correlation_id']}",
                callback_data=f"download:cancel:{d['correlation_id']}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=reply_markup
    )


async def send_downloaded_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: Any
) -> None:
    """Send downloaded file to user (legacy helper).

    Args:
        update: Telegram update object
        context: Telegram context object
        result: Download result with file_path and metadata
    """
    from bot.downloaders.download_lifecycle import DownloadResult as LifecycleResult

    if isinstance(result, LifecycleResult):
        file_path = result.file_path
        metadata = result.metadata or {}
    elif isinstance(result, dict):
        file_path = result.get('file_path') or result.get('path')
        metadata = result.get('metadata', {})
    else:
        file_path = str(result)
        metadata = {}

    if not file_path or not os.path.exists(file_path):
        await update.message.reply_text(
            "Error: No se encontró el archivo descargado."
        )
        return

    # Determine file type
    file_ext = os.path.splitext(file_path)[1].lower()
    audio_extensions = {'.mp3', '.aac', '.wav', '.ogg', '.flac', '.m4a', '.opus'}

    title = metadata.get('title', 'Video')
    caption = f"Descarga completada: {title}"

    try:
        if file_ext in audio_extensions:
            with open(file_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    caption=caption,
                    title=title,
                    performer=metadata.get('artist') or metadata.get('uploader')
                )
        else:
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=caption,
                    supports_streaming=True
                )
        logger.info(f"Downloaded file sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Failed to send downloaded file: {e}")
        await update.message.reply_text(
            "Error al enviar el archivo descargado."
        )


async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages containing URLs for download (legacy direct download).

    This handler is kept for backward compatibility.
    New behavior uses handle_url_detection with inline menu.

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    # Delegate to the new URL detection handler with menu
    await handle_url_detection(update, context)


# =============================================================================
# Post-Download Integration Handlers
# =============================================================================


def _get_postdownload_video_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for post-download video menu options."""
    keyboard = [
        [
            InlineKeyboardButton("Convertir a Nota de Video", callback_data=f"postdownload:videonote:{correlation_id}"),
            InlineKeyboardButton("Extraer Audio", callback_data=f"postdownload:extract_audio:{correlation_id}"),
        ],
        [
            InlineKeyboardButton("Convertir Formato", callback_data=f"postdownload:convert_video:{correlation_id}"),
            InlineKeyboardButton("Descargas Recientes", callback_data=f"postdownload:recent:{correlation_id}"),
        ],
        [
            InlineKeyboardButton("Cerrar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_postdownload_audio_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for post-download audio menu options."""
    keyboard = [
        [
            InlineKeyboardButton("Convertir a Nota de Voz", callback_data=f"postdownload:voicenote:{correlation_id}"),
            InlineKeyboardButton("Convertir Formato", callback_data=f"postdownload:convert_audio:{correlation_id}"),
        ],
        [
            InlineKeyboardButton("Bass Boost", callback_data=f"postdownload:bass:{correlation_id}"),
            InlineKeyboardButton("Reducir Ruido", callback_data=f"postdownload:denoise:{correlation_id}"),
            InlineKeyboardButton("Más Opciones...", callback_data=f"postdownload:more:{correlation_id}"),
        ],
        [
            InlineKeyboardButton("Descargas Recientes", callback_data=f"postdownload:recent:{correlation_id}"),
            InlineKeyboardButton("Cerrar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_postdownload_audio_more_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate extended inline keyboard for post-download audio options."""
    keyboard = [
        [
            InlineKeyboardButton("Treble Boost", callback_data=f"postdownload:treble:{correlation_id}"),
            InlineKeyboardButton("Ecualizar", callback_data=f"postdownload:equalize:{correlation_id}"),
        ],
        [
            InlineKeyboardButton("Comprimir", callback_data=f"postdownload:compress:{correlation_id}"),
            InlineKeyboardButton("Normalizar", callback_data=f"postdownload:normalize:{correlation_id}"),
        ],
        [
            InlineKeyboardButton("Volver", callback_data=f"postdownload:back_audio:{correlation_id}"),
            InlineKeyboardButton("Cerrar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_postdownload_intensity_keyboard(correlation_id: str, effect_type: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for intensity selection (bass/treble)."""
    keyboard = []
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(str(i), callback_data=f"postdownload:{effect_type}_intensity:{correlation_id}:{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton("Volver", callback_data=f"postdownload:back_audio:{correlation_id}"),
        InlineKeyboardButton("Cerrar", callback_data="cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _get_postdownload_effect_strength_keyboard(correlation_id: str, effect_type: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for effect strength selection (denoise/compress)."""
    strengths = [("Leve", "light"), ("Medio", "medium"), ("Fuerte", "strong")]
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"postdownload:{effect_type}_strength:{correlation_id}:{value}")
         for label, value in strengths]
    ]
    keyboard.append([
        InlineKeyboardButton("Volver", callback_data=f"postdownload:back_audio:{correlation_id}"),
        InlineKeyboardButton("Cerrar", callback_data="cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _get_postdownload_audio_format_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for audio format conversion."""
    keyboard = [
        [
            InlineKeyboardButton("MP3", callback_data=f"postdownload:audio_format:{correlation_id}:mp3"),
            InlineKeyboardButton("AAC", callback_data=f"postdownload:audio_format:{correlation_id}:aac"),
        ],
        [
            InlineKeyboardButton("WAV", callback_data=f"postdownload:audio_format:{correlation_id}:wav"),
            InlineKeyboardButton("OGG", callback_data=f"postdownload:audio_format:{correlation_id}:ogg"),
        ],
        [
            InlineKeyboardButton("Volver", callback_data=f"postdownload:back_audio:{correlation_id}"),
            InlineKeyboardButton("Cerrar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_postdownload_video_format_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for video format conversion."""
    keyboard = [
        [
            InlineKeyboardButton("MP4", callback_data=f"postdownload:video_format:{correlation_id}:mp4"),
            InlineKeyboardButton("AVI", callback_data=f"postdownload:video_format:{correlation_id}:avi"),
            InlineKeyboardButton("MOV", callback_data=f"postdownload:video_format:{correlation_id}:mov"),
        ],
        [
            InlineKeyboardButton("MKV", callback_data=f"postdownload:video_format:{correlation_id}:mkv"),
            InlineKeyboardButton("WEBM", callback_data=f"postdownload:video_format:{correlation_id}:webm"),
        ],
        [
            InlineKeyboardButton("Volver", callback_data=f"postdownload:back_video:{correlation_id}"),
            InlineKeyboardButton("Cerrar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_postdownload_video_audio_format_keyboard(correlation_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for audio extraction format selection."""
    keyboard = [
        [
            InlineKeyboardButton("MP3", callback_data=f"postdownload:extract_format:{correlation_id}:mp3"),
            InlineKeyboardButton("AAC", callback_data=f"postdownload:extract_format:{correlation_id}:aac"),
        ],
        [
            InlineKeyboardButton("WAV", callback_data=f"postdownload:extract_format:{correlation_id}:wav"),
            InlineKeyboardButton("OGG", callback_data=f"postdownload:extract_format:{correlation_id}:ogg"),
        ],
        [
            InlineKeyboardButton("Volver", callback_data=f"postdownload:back_video:{correlation_id}"),
            InlineKeyboardButton("Cerrar", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _get_recent_downloads_keyboard(session, page: int = 0) -> InlineKeyboardMarkup:
    """Generate inline keyboard for recent downloads list."""
    entries = session.get_recent(5)
    keyboard = []
    for i, entry in enumerate(entries, 1):
        title = entry.get_title()[:20] + "..." if len(entry.get_title()) > 20 else entry.get_title()
        platform = entry.get_platform()
        time_ago = entry.time_ago()
        label = f"{i}. {title} ({platform}) - {time_ago}"
        keyboard.append([
            InlineKeyboardButton(label, callback_data=f"reprocess:{entry.correlation_id}")
        ])
    if entries:
        keyboard.append([
            InlineKeyboardButton("Limpiar Lista", callback_data="postdownload:clear_recent:none"),
        ])
    keyboard.append([
        InlineKeyboardButton("Cerrar", callback_data="cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


async def handle_postdownload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle post-download video processing callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    if not callback_data.startswith("postdownload:"):
        logger.warning(f"Unexpected callback data: {callback_data}")
        return

    parts = callback_data.split(":")
    if len(parts) < 3:
        logger.warning(f"Invalid callback data format: {callback_data}")
        return

    action = parts[1]
    correlation_id = parts[2]

    logger.info(f"[{correlation_id}] Post-download action '{action}' selected by user {user_id}")

    from bot.downloaders import get_user_download_session
    session = get_user_download_session(context)
    entry = session.get(correlation_id)

    if not entry:
        await query.edit_message_text(
            "Error: No se encontró la información de la descarga. El archivo puede haber sido eliminado."
        )
        return

    if not os.path.exists(entry.file_path):
        await query.edit_message_text(
            "Error: El archivo ya no está disponible. Fue eliminado automáticamente."
        )
        return

    if action == "videonote":
        await _handle_postdownload_videonote(update, context, entry, correlation_id)
    elif action == "extract_audio":
        reply_markup = _get_postdownload_video_audio_format_keyboard(correlation_id)
        await query.edit_message_text("Selecciona el formato de audio:", reply_markup=reply_markup)
    elif action == "convert_video":
        reply_markup = _get_postdownload_video_format_keyboard(correlation_id)
        await query.edit_message_text("Selecciona el formato de video:", reply_markup=reply_markup)
    elif action == "recent":
        await handle_recent_downloads(update, context)
    elif action == "back_video":
        reply_markup = _get_postdownload_video_keyboard(correlation_id)
        await query.edit_message_text("¿Qué quieres hacer con este video?", reply_markup=reply_markup)


async def _handle_postdownload_videonote(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str
) -> None:
    """Convert downloaded video to video note."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text("Convirtiendo a nota de video...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"videonote_{user_id}_{correlation_id}.mp4"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Processing downloaded video to video note for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, VideoProcessor.process_video, str(file_path), str(output_path)),
                    timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise FFmpegError("El procesamiento de video falló")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending video note to user {user_id}")
            with open(output_path, "rb") as video_file:
                await query.message.reply_video_note(video_note=video_file)

            reply_markup = _get_postdownload_video_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este video?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Video note sent successfully to user {user_id}")
        except (FFmpegError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Video note conversion failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error converting to video note: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def handle_postdownload_audio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle post-download audio processing callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    if not callback_data.startswith("postdownload:"):
        logger.warning(f"Unexpected callback data: {callback_data}")
        return

    parts = callback_data.split(":")
    if len(parts) < 3:
        logger.warning(f"Invalid callback data format: {callback_data}")
        return

    action = parts[1]
    correlation_id = parts[2]

    logger.info(f"[{correlation_id}] Post-download audio action '{action}' selected by user {user_id}")

    from bot.downloaders import get_user_download_session
    session = get_user_download_session(context)
    entry = session.get(correlation_id)

    if not entry:
        await query.edit_message_text(
            "Error: No se encontró la información de la descarga. El archivo puede haber sido eliminado."
        )
        return

    if not os.path.exists(entry.file_path):
        await query.edit_message_text("Error: El archivo ya no está disponible. Fue eliminado automáticamente.")
        return

    if action == "voicenote":
        await _handle_postdownload_voicenote(update, context, entry, correlation_id)
    elif action == "convert_audio":
        reply_markup = _get_postdownload_audio_format_keyboard(correlation_id)
        await query.edit_message_text("Selecciona el formato de audio:", reply_markup=reply_markup)
    elif action == "bass":
        reply_markup = _get_postdownload_intensity_keyboard(correlation_id, "bass")
        await query.edit_message_text("Selecciona la intensidad del Bass Boost:", reply_markup=reply_markup)
    elif action == "treble":
        reply_markup = _get_postdownload_intensity_keyboard(correlation_id, "treble")
        await query.edit_message_text("Selecciona la intensidad del Treble Boost:", reply_markup=reply_markup)
    elif action == "denoise":
        reply_markup = _get_postdownload_effect_strength_keyboard(correlation_id, "denoise")
        await query.edit_message_text("Selecciona la intensidad de la reducción de ruido:", reply_markup=reply_markup)
    elif action == "compress":
        reply_markup = _get_postdownload_effect_strength_keyboard(correlation_id, "compress")
        await query.edit_message_text("Selecciona la intensidad de la compresión:", reply_markup=reply_markup)
    elif action == "normalize":
        await _handle_postdownload_normalize(update, context, entry, correlation_id)
    elif action == "equalize":
        await _handle_postdownload_equalize(update, context, entry, correlation_id)
    elif action == "more":
        reply_markup = _get_postdownload_audio_more_keyboard(correlation_id)
        await query.edit_message_text("Más opciones de procesamiento de audio:", reply_markup=reply_markup)
    elif action == "back_audio":
        reply_markup = _get_postdownload_audio_keyboard(correlation_id)
        await query.edit_message_text("¿Qué quieres hacer con este audio?", reply_markup=reply_markup)
    elif action == "recent":
        await handle_recent_downloads(update, context)
    elif action == "clear_recent":
        session.clear()
        await query.edit_message_text("Lista de descargas recientes limpiada.")


async def _handle_postdownload_voicenote(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str
) -> None:
    """Convert downloaded audio to voice note."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text("Convirtiendo a nota de voz...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"voicenote_{user_id}_{correlation_id}.ogg"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Converting audio to voice note for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = VoiceNoteConverter(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.process), timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise VoiceConversionError("No pude convertir a nota de voz")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending voice note to user {user_id}")
            with open(output_path, "rb") as voice_file:
                await query.message.reply_voice(voice=voice_file)

            reply_markup = _get_postdownload_audio_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Voice note sent successfully to user {user_id}")
        except (VoiceConversionError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Voice note conversion failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error converting to voice note: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def _handle_postdownload_normalize(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str
) -> None:
    """Normalize downloaded audio."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text("Normalizando audio...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"normalized_{user_id}_{correlation_id}.mp3"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Normalizing audio for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                effects = AudioEffects(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, effects.normalize), timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise AudioEffectsError("No pude normalizar el audio")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending normalized audio to user {user_id}")
            with open(output_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file, filename=f"normalized_{correlation_id}.mp3", title="Audio Normalizado"
                )

            reply_markup = _get_postdownload_audio_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Normalized audio sent successfully to user {user_id}")
        except (AudioEffectsError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Audio normalization failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error normalizing audio: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def _handle_postdownload_equalize(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str
) -> None:
    """Show equalizer for downloaded audio."""
    query = update.callback_query
    context.user_data["postdownload_eq"] = {"correlation_id": correlation_id, "bass": 0, "mid": 0, "treble": 0}
    reply_markup = _get_equalizer_keyboard(0, 0, 0)
    await query.edit_message_text("Ajusta el ecualizador (Bass/Mid/Treble):", reply_markup=reply_markup)


async def handle_recent_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent downloads list."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    from bot.downloaders import get_user_download_session
    session = get_user_download_session(context)
    entries = session.get_recent(5)

    if not entries:
        await query.edit_message_text(
            "No hay descargas recientes en esta sesión.\n\n"
            "Las descargas se mantienen solo durante la sesión actual "
            "y no se guardan permanentemente por privacidad.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cerrar", callback_data="cancel")]])
        )
        return

    lines = ["Descargas recientes:"]
    for i, entry in enumerate(entries, 1):
        title = entry.get_title()
        platform = entry.get_platform()
        time_ago = entry.time_ago()
        status_icon = "✅" if entry.status == "completed" else "❌"
        lines.append(f"{status_icon} {i}. {title} ({platform}) - hace {time_ago}")

    reply_markup = _get_recent_downloads_keyboard(session)
    await query.edit_message_text(
        "\n".join(lines) + "\n\nSelecciona una para reprocesar:", reply_markup=reply_markup
    )
    logger.info(f"Displayed recent downloads for user {user_id}: {len(entries)} items")


async def handle_reprocess_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle reprocessing of a recent download."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    if not callback_data.startswith("reprocess:"):
        logger.warning(f"Unexpected callback data: {callback_data}")
        return

    parts = callback_data.split(":")
    if len(parts) != 2:
        logger.warning(f"Invalid callback data format: {callback_data}")
        return

    correlation_id = parts[1]
    logger.info(f"[{correlation_id}] Reprocess requested by user {user_id}")

    from bot.downloaders import get_user_download_session
    session = get_user_download_session(context)
    entry = session.get(correlation_id)

    if not entry:
        await query.edit_message_text(
            "Error: No se encontró la descarga. Puede haber sido eliminada de la sesión."
        )
        return

    if not os.path.exists(entry.file_path):
        await query.edit_message_text(
            "Error: El archivo ya no está disponible. Fue eliminado automáticamente.\n\n"
            "Los archivos temporales se eliminan después de un tiempo. Por favor descarga el contenido nuevamente."
        )
        return

    file_ext = os.path.splitext(entry.file_path)[1].lower()
    video_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    audio_exts = {'.mp3', '.aac', '.wav', '.ogg', '.flac', '.m4a', '.opus'}

    if file_ext in video_exts:
        reply_markup = _get_postdownload_video_keyboard(correlation_id)
        await query.edit_message_text(
            f"Reprocesando: {entry.get_title()}\n\n¿Qué quieres hacer con este video?", reply_markup=reply_markup
        )
    elif file_ext in audio_exts:
        reply_markup = _get_postdownload_audio_keyboard(correlation_id)
        await query.edit_message_text(
            f"Reprocesando: {entry.get_title()}\n\n¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(
            f"Tipo de archivo no reconocido: {file_ext}\n\nSolo se pueden reprocesar videos y archivos de audio."
        )
    logger.info(f"[{correlation_id}] Reprocess menu shown to user {user_id}")


# =============================================================================
# Post-Download Format and Effect Handlers
# =============================================================================

async def handle_postdownload_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle post-download format selection callbacks.

    Handles: audio_format, video_format, extract_format callbacks
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Parse: postdownload:ACTION:CORRELATION_ID:FORMAT
    parts = callback_data.split(":")
    if len(parts) != 4:
        logger.warning(f"Invalid callback data format: {callback_data}")
        return

    action = parts[1]
    correlation_id = parts[2]
    format_type = parts[3]

    logger.info(f"[{correlation_id}] Post-download format '{format_type}' selected for {action} by user {user_id}")

    from bot.downloaders import get_user_download_session
    session = get_user_download_session(context)
    entry = session.get(correlation_id)

    if not entry:
        await query.edit_message_text(
            "Error: No se encontró la información de la descarga. El archivo puede haber sido eliminado."
        )
        return

    if not os.path.exists(entry.file_path):
        await query.edit_message_text("Error: El archivo ya no está disponible. Fue eliminado automáticamente.")
        return

    if action == "audio_format":
        await _handle_postdownload_audio_format_conversion(update, context, entry, correlation_id, format_type)
    elif action == "video_format":
        await _handle_postdownload_video_format_conversion(update, context, entry, correlation_id, format_type)
    elif action == "extract_format":
        await _handle_postdownload_extract_audio(update, context, entry, correlation_id, format_type)


async def _handle_postdownload_audio_format_conversion(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str, target_format: str
) -> None:
    """Convert downloaded audio to specified format."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text(f"Convirtiendo a formato {target_format.upper()}...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"converted_{user_id}_{correlation_id}.{target_format}"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Converting audio to {target_format} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = AudioFormatConverter(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.convert), timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise AudioFormatConversionError(f"No pude convertir a {target_format}")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending converted audio to user {user_id}")
            with open(output_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    filename=f"converted_{correlation_id}.{target_format}",
                    title=f"Audio Convertido ({target_format.upper()})"
                )

            reply_markup = _get_postdownload_audio_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Converted audio sent successfully to user {user_id}")
        except (AudioFormatConversionError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Audio format conversion failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error converting audio format: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def _handle_postdownload_video_format_conversion(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str, target_format: str
) -> None:
    """Convert downloaded video to specified format."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text(f"Convirtiendo video a formato {target_format.upper()}...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"converted_{user_id}_{correlation_id}.{target_format}"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Converting video to {target_format} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                converter = FormatConverter(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, converter.convert), timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise FormatConversionError(f"No pude convertir a {target_format}")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending converted video to user {user_id}")
            with open(output_path, "rb") as video_file:
                await query.message.reply_video(
                    video=video_file,
                    caption=f"Video convertido a {target_format.upper()}",
                    supports_streaming=True
                )

            reply_markup = _get_postdownload_video_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este video?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Converted video sent successfully to user {user_id}")
        except (FormatConversionError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Video format conversion failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error converting video format: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def _handle_postdownload_extract_audio(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str, audio_format: str
) -> None:
    """Extract audio from downloaded video."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text(f"Extrayendo audio en formato {audio_format.upper()}...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"audio_{user_id}_{correlation_id}.{audio_format}"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Extracting audio as {audio_format} for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                extractor = AudioExtractor(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, extractor.extract), timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise AudioExtractionError(f"No pude extraer el audio")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending extracted audio to user {user_id}")
            with open(output_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    filename=f"extracted_{correlation_id}.{audio_format}",
                    title=f"Audio Extraído ({audio_format.upper()})"
                )

            reply_markup = _get_postdownload_video_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este video?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Extracted audio sent successfully to user {user_id}")
        except (AudioExtractionError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Audio extraction failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error extracting audio: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def handle_postdownload_intensity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle post-download intensity selection callbacks (bass/treble boost).

    Handles: bass_intensity, treble_intensity callbacks
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Parse: postdownload:ACTION:CORRELATION_ID:INTENSITY
    parts = callback_data.split(":")
    if len(parts) != 4:
        logger.warning(f"Invalid callback data format: {callback_data}")
        return

    action = parts[1]
    correlation_id = parts[2]
    intensity = int(parts[3])

    logger.info(f"[{correlation_id}] Post-download {action} intensity {intensity} selected by user {user_id}")

    from bot.downloaders import get_user_download_session
    session = get_user_download_session(context)
    entry = session.get(correlation_id)

    if not entry:
        await query.edit_message_text(
            "Error: No se encontró la información de la descarga. El archivo puede haber sido eliminado."
        )
        return

    if not os.path.exists(entry.file_path):
        await query.edit_message_text("Error: El archivo ya no está disponible. Fue eliminado automáticamente.")
        return

    if action == "bass_intensity":
        await _handle_postdownload_bass_boost(update, context, entry, correlation_id, intensity)
    elif action == "treble_intensity":
        await _handle_postdownload_treble_boost(update, context, entry, correlation_id, intensity)


async def _handle_postdownload_bass_boost(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str, intensity: int
) -> None:
    """Apply bass boost to downloaded audio."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text(f"Aplicando Bass Boost (intensidad {intensity})...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"bass_boosted_{user_id}_{correlation_id}.mp3"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Applying bass boost (intensity {intensity}) for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                enhancer = AudioEnhancer(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: enhancer.bass_boost(intensity)),
                    timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise AudioEnhancementError("No pude aplicar el bass boost")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending bass boosted audio to user {user_id}")
            with open(output_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    filename=f"bass_boosted_{correlation_id}.mp3",
                    title=f"Bass Boost (Intensidad {intensity})"
                )

            reply_markup = _get_postdownload_audio_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Bass boosted audio sent successfully to user {user_id}")
        except (AudioEnhancementError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Bass boost failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error applying bass boost: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def _handle_postdownload_treble_boost(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str, intensity: int
) -> None:
    """Apply treble boost to downloaded audio."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    await query.edit_message_text(f"Aplicando Treble Boost (intensidad {intensity})...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"treble_boosted_{user_id}_{correlation_id}.mp3"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Applying treble boost (intensity {intensity}) for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                enhancer = AudioEnhancer(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: enhancer.treble_boost(intensity)),
                    timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise AudioEnhancementError("No pude aplicar el treble boost")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending treble boosted audio to user {user_id}")
            with open(output_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    filename=f"treble_boosted_{correlation_id}.mp3",
                    title=f"Treble Boost (Intensidad {intensity})"
                )

            reply_markup = _get_postdownload_audio_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Treble boosted audio sent successfully to user {user_id}")
        except (AudioEnhancementError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Treble boost failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error applying treble boost: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def handle_postdownload_effect_strength_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle post-download effect strength callbacks (denoise/compress).

    Handles: denoise_strength, compress_strength callbacks
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    callback_data = query.data

    # Parse: postdownload:ACTION:CORRELATION_ID:STRENGTH
    parts = callback_data.split(":")
    if len(parts) != 4:
        logger.warning(f"Invalid callback data format: {callback_data}")
        return

    action = parts[1]
    correlation_id = parts[2]
    strength = parts[3]

    logger.info(f"[{correlation_id}] Post-download {action} strength {strength} selected by user {user_id}")

    from bot.downloaders import get_user_download_session
    session = get_user_download_session(context)
    entry = session.get(correlation_id)

    if not entry:
        await query.edit_message_text(
            "Error: No se encontró la información de la descarga. El archivo puede haber sido eliminado."
        )
        return

    if not os.path.exists(entry.file_path):
        await query.edit_message_text("Error: El archivo ya no está disponible. Fue eliminado automáticamente.")
        return

    if action == "denoise_strength":
        await _handle_postdownload_denoise(update, context, entry, correlation_id, strength)
    elif action == "compress_strength":
        await _handle_postdownload_compress(update, context, entry, correlation_id, strength)


async def _handle_postdownload_denoise(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str, strength: str
) -> None:
    """Apply denoise effect to downloaded audio."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    strength_map = {"light": "leve", "medium": "media", "strong": "fuerte"}
    strength_es = strength_map.get(strength, strength)

    await query.edit_message_text(f"Reduciendo ruido (intensidad {strength_es})...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"denoised_{user_id}_{correlation_id}.mp3"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Applying denoise (strength {strength}) for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                effects = AudioEffects(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: effects.denoise(strength)),
                    timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise AudioEffectsError("No pude reducir el ruido")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending denoised audio to user {user_id}")
            with open(output_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    filename=f"denoised_{correlation_id}.mp3",
                    title=f"Audio Sin Ruido ({strength_es.capitalize()})"
                )

            reply_markup = _get_postdownload_audio_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Denoised audio sent successfully to user {user_id}")
        except (AudioEffectsError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Denoise failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error denoising audio: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")


async def _handle_postdownload_compress(
    update: Update, context: ContextTypes.DEFAULT_TYPE, entry: Any, correlation_id: str, strength: str
) -> None:
    """Apply compression effect to downloaded audio."""
    query = update.callback_query
    user_id = update.effective_user.id
    file_path = entry.file_path

    strength_map = {"light": "leve", "medium": "media", "strong": "fuerte"}
    strength_es = strength_map.get(strength, strength)

    await query.edit_message_text(f"Comprimiendo audio (intensidad {strength_es})...")

    with TempManager() as temp_mgr:
        try:
            output_filename = f"compressed_{user_id}_{correlation_id}.mp3"
            output_path = temp_mgr.get_temp_path(output_filename)

            logger.info(f"[{correlation_id}] Applying compression (strength {strength}) for user {user_id}")
            try:
                loop = asyncio.get_event_loop()
                effects = AudioEffects(str(file_path), str(output_path))
                success = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: effects.compress(strength)),
                    timeout=config.PROCESSING_TIMEOUT
                )
                if not success:
                    raise AudioEffectsError("No pude comprimir el audio")
            except asyncio.TimeoutError as e:
                raise ProcessingTimeoutError("El procesamiento tardó demasiado") from e

            logger.info(f"[{correlation_id}] Sending compressed audio to user {user_id}")
            with open(output_path, "rb") as audio_file:
                await query.message.reply_audio(
                    audio=audio_file,
                    filename=f"compressed_{correlation_id}.mp3",
                    title=f"Audio Comprimido ({strength_es.capitalize()})"
                )

            reply_markup = _get_postdownload_audio_keyboard(correlation_id)
            await query.message.reply_text(
                "¡Listo! ¿Quieres hacer algo más con este audio?", reply_markup=reply_markup
            )
            logger.info(f"[{correlation_id}] Compressed audio sent successfully to user {user_id}")
        except (AudioEffectsError, ProcessingTimeoutError) as e:
            logger.error(f"[{correlation_id}] Compression failed: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
        except Exception as e:
            logger.exception(f"[{correlation_id}] Unexpected error compressing audio: {e}")
            await query.edit_message_text("Ocurrió un error inesperado. Por favor intenta de nuevo.")
