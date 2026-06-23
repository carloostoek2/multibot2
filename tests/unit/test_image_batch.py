"""Unit tests for image batch menu behavior."""
from telegram import InlineKeyboardButton

from bot.handlers import _get_image_menu_keyboard
from bot.config import config


class TestImageBatchMenuKeyboard:
    def test_single_image_shows_full_menu(self):
        keyboard = _get_image_menu_keyboard(1)
        labels = [btn.text for row in keyboard.inline_keyboard for btn in row]
        assert "Comprimir" in labels
        assert "Convertir Formato" in labels
        assert "Redimensionar" in labels
        assert "Info de Imagen" in labels
        assert "Mejorar" in labels
        assert "Agrupar" in labels
        assert "Mejorar Imagen" not in labels

    def test_batch_menu_shows_mejorar_and_agrupar(self):
        keyboard = _get_image_menu_keyboard(3)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        assert len(buttons) == 2
        labels = [btn.text for btn in buttons]
        callback_data = [btn.callback_data for btn in buttons]
        assert labels == ["Mejorar", "Agrupar"]
        assert callback_data == ["image_action:enhance", "image_action:group"]

    def test_max_batch_size_is_telegram_album_limit(self):
        assert config.MAX_IMAGE_BATCH_SIZE <= 10