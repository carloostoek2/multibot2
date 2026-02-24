"""Downloader-specific exceptions with user-friendly error messages.

This module provides a comprehensive exception hierarchy for download operations.
All exceptions support correlation IDs for request tracing and provide both
technical details (for logs) and user-friendly messages (for display).

Exception Hierarchy:
    DownloadError (base)
        URLValidationError
        MetadataExtractionError
        FileTooLargeError
        UnsupportedURLError
        DownloadFailedError
        NetworkError
"""
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Base exception for all download-related errors.

    Attributes:
        message: Technical error message for logging
        url: The URL that was being processed (if available)
        correlation_id: Unique identifier for request tracing (per DM-02)
    """

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        self.message = message
        self.url = url
        self.correlation_id = correlation_id or self._generate_correlation_id()
        super().__init__(self.message)

    @staticmethod
    def _generate_correlation_id() -> str:
        """Generate a unique correlation ID for request tracing."""
        return str(uuid.uuid4())[:8]

    def to_user_message(self) -> str:
        """Return a user-friendly error message.

        Override in subclasses to provide specific messages.

        Returns:
            Human-readable error message for display to users.
        """
        return "Ocurrió un error al descargar el archivo. Por favor intenta de nuevo."

    def __str__(self) -> str:
        """String representation with technical details for logging."""
        parts = [self.message]
        if self.url:
            parts.append(f"url={self.url}")
        if self.correlation_id:
            parts.append(f"correlation_id={self.correlation_id}")
        return f"[{self.__class__.__name__}] {' | '.join(parts)}"


class URLValidationError(DownloadError):
    """Raised when URL is malformed or invalid.

    Per EH-02: Clear error messages for unsupported/invalid URLs.

    Attributes:
        message: Technical description of the validation failure
        url: The invalid URL
        correlation_id: Request tracing ID
    """

    def __init__(
        self,
        message: str = "URL validation failed",
        url: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(message, url, correlation_id)

    def to_user_message(self) -> str:
        """Return user-friendly message for invalid URLs."""
        return "La URL parece ser inválida. Por favor verifica e intenta de nuevo."


class MetadataExtractionError(DownloadError):
    """Raised when metadata cannot be extracted from a URL.

    Per DL-03: Metadata extraction requirement. This error indicates
    the URL might be valid but the content is inaccessible (private,
    deleted, or restricted).

    Attributes:
        message: Technical description of the extraction failure
        url: The URL that failed metadata extraction
        correlation_id: Request tracing ID
    """

    def __init__(
        self,
        message: str = "Failed to extract metadata",
        url: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(message, url, correlation_id)

    def to_user_message(self) -> str:
        """Return user-friendly message for metadata extraction failures."""
        return (
            "No pude obtener información del video. "
            "El contenido puede ser privado o no estar disponible."
        )


class FileTooLargeError(DownloadError):
    """Raised when file exceeds Telegram limits.

    Per QF-05: File size validation against Telegram limits (50MB).

    Attributes:
        file_size: Actual file size in bytes
        max_size: Maximum allowed size in bytes
        message: Technical description
        url: The URL of the oversized file
        correlation_id: Request tracing ID
    """

    def __init__(
        self,
        file_size: int,
        max_size: int,
        message: Optional[str] = None,
        url: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        self.file_size = file_size
        self.max_size = max_size
        msg = message or f"File size {file_size} exceeds max {max_size}"
        super().__init__(msg, url, correlation_id)

    def to_user_message(self) -> str:
        """Return user-friendly message with size information."""
        file_mb = self.file_size / (1024 * 1024)
        max_mb = self.max_size / (1024 * 1024)
        return (
            f"El archivo es muy grande ({file_mb:.1f} MB). "
            f"Telegram limita el tamaño a {max_mb:.0f} MB."
        )


class UnsupportedURLError(DownloadError):
    """Raised when URL is valid but not from a supported platform.

    Per EH-02: Clear error messages for unsupported URLs.

    Attributes:
        message: Technical description
        url: The unsupported URL
        correlation_id: Request tracing ID
        supported_platforms: List of supported platform names
    """

    def __init__(
        self,
        message: str = "URL platform not supported",
        url: Optional[str] = None,
        correlation_id: Optional[str] = None,
        supported_platforms: Optional[list] = None
    ):
        self.supported_platforms = supported_platforms or [
            "YouTube", "Instagram", "TikTok", "Twitter/X",
            "Facebook", "Enlaces de video directos"
        ]
        super().__init__(message, url, correlation_id)

    def to_user_message(self) -> str:
        """Return user-friendly message listing supported platforms."""
        platforms = ", ".join(self.supported_platforms)
        return (
            f"Esta URL no es de una plataforma soportada. "
            f"Soportadas: {platforms}."
        )


class DownloadFailedError(DownloadError):
    """Raised when download fails after all retries.

    Per EH-01: Retry logic with clear failure messages.

    Attributes:
        attempts_made: Number of retry attempts made
        last_error: The last error that caused failure
        message: Technical description
        url: The URL that failed to download
        correlation_id: Request tracing ID
    """

    def __init__(
        self,
        attempts_made: int,
        last_error: Optional[Exception] = None,
        message: Optional[str] = None,
        url: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        self.attempts_made = attempts_made
        self.last_error = last_error
        msg = message or f"Download failed after {attempts_made} attempts"
        if last_error:
            msg += f": {last_error}"
        super().__init__(msg, url, correlation_id)

    def to_user_message(self) -> str:
        """Return user-friendly message with attempt count."""
        return (
            f"La descarga falló después de {self.attempts_made} intentos. "
            f"Por favor intenta de nuevo más tarde."
        )


class NetworkError(DownloadError):
    """Raised for transient network failures.

    Per EH-03: Network error handling with retry indication.
    This error indicates the operation might succeed on retry.

    Attributes:
        message: Technical description of the network failure
        url: The URL being accessed when the error occurred
        correlation_id: Request tracing ID
        retry_suggested: Whether retry is recommended
    """

    def __init__(
        self,
        message: str = "Network error occurred",
        url: Optional[str] = None,
        correlation_id: Optional[str] = None,
        retry_suggested: bool = True
    ):
        self.retry_suggested = retry_suggested
        super().__init__(message, url, correlation_id)

    def to_user_message(self) -> str:
        """Return user-friendly message indicating retry."""
        if self.retry_suggested:
            return "Error de red. Reintentando..."
        return "Error de conexión. Por favor verifica tu conexión e intenta de nuevo."


class RateLimitError(DownloadError):
    """Raised when rate limit is exceeded by a platform.

    This error is raised when platforms (YouTube, Instagram, TikTok, Twitter/X)
    or generic HTTP services return rate limit responses (HTTP 429) or indicate
    that too many requests have been made.

    The error includes retry_after information when available from platform
    headers or error messages, allowing for intelligent backoff strategies.

    Attributes:
        message: Technical description of the rate limit
        url: The URL being accessed when rate limited
        correlation_id: Request tracing ID
        retry_after: Seconds to wait before retry (from platform headers if available)
        platform: Platform that issued the rate limit (e.g., "youtube", "instagram")

    Examples:
        YouTube rate limiting:
            - HTTP 429 responses from youtube.com
            - "Too many requests" error messages

        Instagram rate limiting:
            - GraphQL rate limit exceeded
            - "Please wait a few minutes" messages

        TikTok rate limiting:
            - Captcha challenges after rapid requests
            - "Rate limit exceeded" responses

        Generic HTTP 429 responses:
            - Any service returning HTTP 429 Too Many Requests
            - Retry-After header values
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        url: Optional[str] = None,
        correlation_id: Optional[str] = None,
        retry_after: Optional[int] = None,
        platform: Optional[str] = None
    ):
        self.retry_after = retry_after
        self.platform = platform
        super().__init__(message, url, correlation_id)

    def to_user_message(self) -> str:
        """Return user-friendly message in Spanish with retry information."""
        if self.retry_after:
            return f"Límite de descargas alcanzado. Por favor espera {self.retry_after} segundos."
        return "Límite de descargas alcanzado. Por favor intenta más tarde."


# For backwards compatibility with existing code
# These aliases maintain compatibility with code using the old names
URLDetectionError = URLValidationError


__all__ = [
    # Base exception
    "DownloadError",
    # Specific exceptions
    "URLValidationError",
    "MetadataExtractionError",
    "FileTooLargeError",
    "UnsupportedURLError",
    "DownloadFailedError",
    "NetworkError",
    "RateLimitError",
    # Backwards compatibility
    "URLDetectionError",
]