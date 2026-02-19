"""Error handling module for the Telegram bot.

Provides custom exceptions and centralized error handling with user-friendly
messages in Spanish.
"""
import logging
from functools import wraps
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import (
    NetworkError,
    TimedOut,
    BadRequest,
    RetryAfter,
    TelegramError,
)

# Import ValidationError from validators for error handling
from bot.validators import ValidationError

logger = logging.getLogger(__name__)


class VideoProcessingError(Exception):
    """Base exception for video processing errors."""

    def __init__(self, message: str = "Error procesando el video"):
        self.message = message
        super().__init__(self.message)


class DownloadError(VideoProcessingError):
    """Exception raised when video download fails."""

    def __init__(self, message: str = "No pude descargar el video"):
        self.message = message
        super().__init__(self.message)


class FFmpegError(VideoProcessingError):
    """Exception raised when ffmpeg processing fails."""

    def __init__(self, message: str = "Hubo un problema procesando el video"):
        self.message = message
        super().__init__(self.message)


class ProcessingTimeoutError(VideoProcessingError):
    """Exception raised when video processing times out."""

    def __init__(self, message: str = "El video tardó demasiado en procesarse"):
        self.message = message
        super().__init__(self.message)


class FormatConversionError(VideoProcessingError):
    """Exception raised when video format conversion fails."""

    def __init__(self, message: str = "Error convirtiendo el formato del video"):
        self.message = message
        super().__init__(self.message)


class AudioExtractionError(VideoProcessingError):
    """Exception raised when audio extraction fails."""

    def __init__(self, message: str = "Error extrayendo el audio del video"):
        self.message = message
        super().__init__(self.message)


class VideoSplitError(VideoProcessingError):
    """Exception raised when video splitting fails."""

    def __init__(self, message: str = "No pude dividir el video"):
        self.message = message
        super().__init__(self.message)


class VideoJoinError(VideoProcessingError):
    """Exception raised when video joining fails."""

    def __init__(self, message: str = "No pude unir los videos"):
        self.message = message
        super().__init__(self.message)


class VoiceConversionError(VideoProcessingError):
    """Exception raised when audio to voice note conversion fails."""

    def __init__(self, message: str = "Error convirtiendo audio a nota de voz"):
        self.message = message
        super().__init__(self.message)


class VoiceToMp3Error(VideoProcessingError):
    """Exception raised when voice to MP3 conversion fails."""

    def __init__(self, message: str = "Error convirtiendo nota de voz a MP3"):
        self.message = message
        super().__init__(self.message)


class AudioSplitError(VideoProcessingError):
    """Exception raised when audio splitting fails."""

    def __init__(self, message: str = "No pude dividir el audio"):
        self.message = message
        super().__init__(self.message)


class AudioJoinError(VideoProcessingError):
    """Exception raised when audio joining fails."""

    def __init__(self, message: str = "No pude unir los archivos de audio"):
        self.message = message
        super().__init__(self.message)


class AudioFormatConversionError(VideoProcessingError):
    """Exception raised when audio format conversion fails."""

    def __init__(self, message: str = "Error convirtiendo el formato del audio"):
        self.message = message
        super().__init__(self.message)


class AudioEnhancementError(VideoProcessingError):
    """Exception raised when audio enhancement fails."""

    def __init__(self, message: str = "Error aplicando mejora de audio"):
        self.message = message
        super().__init__(self.message)


# User-friendly error messages in Spanish
ERROR_MESSAGES = {
    DownloadError: "No pude descargar el video. Intenta con otro archivo.",
    FFmpegError: "Hubo un problema procesando el video. Asegúrate de que sea un archivo válido.",
    ProcessingTimeoutError: "El video tardó demasiado en procesarse. Intenta con uno más corto.",
    FormatConversionError: "No pude convertir el formato del video. Verifica que el formato sea válido.",
    AudioExtractionError: "No pude extraer el audio del video. Intenta con otro archivo.",
    VideoSplitError: "No pude dividir el video. Verifica que el archivo sea válido.",
    VideoJoinError: "No pude unir los videos. Verifica que los archivos sean válidos.",
    VoiceConversionError: "No pude convertir el audio a nota de voz. Verifica que el archivo sea válido.",
    VoiceToMp3Error: "No pude convertir la nota de voz a MP3. Intenta de nuevo.",
    AudioSplitError: "No pude dividir el audio. Verifica que el archivo sea válido.",
    AudioJoinError: "No pude unir los archivos de audio. Verifica que los archivos sean válidos.",
    AudioFormatConversionError: "No pude convertir el formato del audio. Verifica que el formato sea válido.",
    AudioEnhancementError: "No pude aplicar la mejora de audio. Verifica que el archivo sea válido.",
    VideoProcessingError: "Ocurrió un error al procesar el video. Por favor intenta de nuevo.",
    ValidationError: "El archivo no es válido. Verifica que sea un video correcto.",
    # Telegram API errors
    NetworkError: "Error de conexión. Por favor intenta de nuevo.",
    TimedOut: "La operación tardó demasiado. Intenta con un archivo más pequeño.",
    BadRequest: "Solicitud inválida. Verifica el archivo e intenta de nuevo.",
    RetryAfter: "Demasiadas solicitudes. Por favor espera un momento.",
    TelegramError: "Error de Telegram. Por favor intenta de nuevo.",
}

DEFAULT_ERROR_MESSAGE = "Ocurrió un error inesperado. Por favor intenta de nuevo."


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors gracefully and send user-friendly messages.

    Logs the full error for debugging and sends an appropriate
    message to the user based on the error type.

    Args:
        update: Telegram update object
        context: Telegram context object containing the error
    """
    error = context.error
    user_id = update.effective_user.id if update.effective_user else "unknown"

    # Determine user-friendly message based on error type
    user_message = DEFAULT_ERROR_MESSAGE
    is_telegram_error = isinstance(error, TelegramError)

    for error_type, message in ERROR_MESSAGES.items():
        if isinstance(error, error_type):
            user_message = message
            break

    # Log with appropriate level based on error type
    if isinstance(error, (NetworkError, TimedOut)):
        # Transient errors - log as warning
        logger.warning(f"Transient Telegram error for user {user_id}: {error}")
    elif isinstance(error, BadRequest):
        # User errors - log as info
        logger.info(f"Bad request from user {user_id}: {error}")
    elif is_telegram_error:
        # Other Telegram errors - log as error
        logger.error(f"Telegram error for user {user_id}: {error}")
    else:
        # Internal errors - log full exception
        logger.exception(f"Error handling update for user {user_id}: {error}")

    # Send message to user if we have a chat to reply to
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(user_message)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


def wrap_with_error_handler(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to wrap handlers with error handling.

    Catches exceptions and routes them through the error handler.

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            # Set the error in context and call error handler
            context.error = e
            await error_handler(update, context)
            # Re-raise to allow further handling if needed
            raise

    return wrapper


async def handle_processing_error(
    update: Update,
    error: Exception,
    user_id: int
) -> None:
    """Handle processing errors with appropriate user feedback.

    Convenience function for handling errors within video processing.

    Args:
        update: Telegram update object
        error: The exception that occurred
        user_id: ID of the user for logging
    """
    # Determine appropriate message
    user_message = DEFAULT_ERROR_MESSAGE
    is_telegram_error = isinstance(error, TelegramError)

    for error_type, message in ERROR_MESSAGES.items():
        if isinstance(error, error_type):
            user_message = message
            break

    # Log with appropriate level based on error type
    if isinstance(error, (NetworkError, TimedOut)):
        # Transient errors - log as warning
        logger.warning(f"Transient Telegram error for user {user_id}: {error}")
    elif isinstance(error, BadRequest):
        # User errors - log as info
        logger.info(f"Bad request from user {user_id}: {error}")
    elif is_telegram_error:
        # Other Telegram errors - log as error
        logger.error(f"Telegram error for user {user_id}: {error}")
    else:
        # Internal errors - log full exception
        logger.exception(f"Processing error for user {user_id}: {error}")

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(user_message)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
