"""Unit tests for handle_back_callback image menu restoration."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.config import config
from bot.handlers import handle_back_callback


def _back_update(callback_data="back:image"):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=99)
    update.callback_query = MagicMock()
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    return MagicMock(user_data={})


class TestHandleBackCallbackImage:
    @pytest.mark.asyncio
    async def test_batch_menu_shows_mejorar_naturalizar_and_agrupar(self, mock_context):
        update = _back_update()
        mock_context.user_data["image_menu_file_ids"] = ["f1", "f2", "f3"]
        mock_context.user_data["image_menu_file_id"] = "f1"

        await handle_back_callback(update, mock_context)

        text, kwargs = update.callback_query.edit_message_text.await_args
        assert "3 imágenes recibidas" in text[0]
        assert "«Mejorar», «Naturalizar» y «Agrupar»" in text[0]
        keyboard = kwargs["reply_markup"].inline_keyboard
        labels = [btn.text for row in keyboard for btn in row]
        assert labels == ["Mejorar", "Naturalizar", "Agrupar"]

    @pytest.mark.asyncio
    async def test_batch_menu_includes_truncation_warning_when_stored(self, mock_context):
        update = _back_update()
        mock_context.user_data["image_menu_file_ids"] = ["f1", "f2"]
        mock_context.user_data["image_menu_file_id"] = "f1"
        mock_context.user_data["image_menu_truncated"] = True

        await handle_back_callback(update, mock_context)

        text = update.callback_query.edit_message_text.await_args[0][0]
        assert f"primeras {config.MAX_IMAGE_BATCH_SIZE} imágenes" in text

    @pytest.mark.asyncio
    async def test_single_image_shows_full_menu(self, mock_context):
        update = _back_update()
        mock_context.user_data["image_menu_file_id"] = "f1"

        await handle_back_callback(update, mock_context)

        text, kwargs = update.callback_query.edit_message_text.await_args
        assert "Imagen recibida" in text[0]
        labels = [btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row]
        assert "Comprimir" in labels
        assert "Mejorar" in labels
        assert "Naturalizar" in labels