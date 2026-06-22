"""Unit tests for get_user_error_message specificity and custom messages."""
from bot.error_handler import (
    ERROR_MESSAGES,
    ImageEnhancementError,
    ImageProcessingError,
    ProcessingTimeoutError,
    get_user_error_message,
)
from bot.validators import ValidationError


class TestGetUserErrorMessage:
    def test_image_enhancement_error_uses_specific_default(self):
        error = ImageEnhancementError()
        assert get_user_error_message(error) == ERROR_MESSAGES[ImageEnhancementError]

    def test_image_enhancement_error_prefers_custom_message(self):
        error = ImageEnhancementError("No se pudo leer la imagen corrupta.")
        assert get_user_error_message(error) == "No se pudo leer la imagen corrupta."

    def test_processing_timeout_prefers_context_specific_message(self):
        error = ProcessingTimeoutError(
            "La mejora tardó demasiado. Intenta con menos imágenes o más pequeñas."
        )
        assert get_user_error_message(error) == error.message
        assert get_user_error_message(error) != ERROR_MESSAGES[ProcessingTimeoutError]

    def test_validation_error_uses_message_attribute(self):
        error = ValidationError("El archivo no es un audio válido.")
        assert get_user_error_message(error) == "El archivo no es un audio válido."

    def test_subclass_beats_parent_generic_message(self):
        error = ImageEnhancementError("Detalle específico de mejora.")
        message = get_user_error_message(error)
        assert message == "Detalle específico de mejora."
        assert message != ERROR_MESSAGES[ImageProcessingError]