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
        assert "Mejorar Imagen" not in labels

    def test_batch_menu_only_shows_mejorar(self):
        keyboard = _get_image_menu_keyboard(3)
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        assert len(buttons) == 1
        assert isinstance(buttons[0], InlineKeyboardButton)
        assert buttons[0].text == "Mejorar"
        assert buttons[0].callback_data == "image_action:enhance"

    def test_max_batch_size_is_telegram_album_limit(self):
        assert config.MAX_IMAGE_BATCH_SIZE <= 10