"""Unit tests for voice-note menu UX and voice-clone gating."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import (
    handle_voice_message,
    handle_voice_menu_callback,
)


def _voice_update(file_id="voice-file-1", file_size=12_000):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.message = MagicMock()
    update.message.voice = SimpleNamespace(file_id=file_id, file_size=file_size, file_unique_id="uniq1")
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _callback_update(callback_data: str):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.callback_query = MagicMock()
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_audio = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    update.message = None
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    return context


class TestHandleVoiceMessageMenu:
    @pytest.mark.asyncio
    async def test_shows_menu_does_not_run_enhancer(self, mock_context):
        update = _voice_update()

        with patch("bot.handlers.validate_file_size", return_value=(True, None)), patch(
            "bot.handlers.AudioEnhancer"
        ) as enhancer_cls, patch("bot.handlers.VoiceToMp3Converter") as converter_cls, patch(
            "bot.handlers.AudioEffects"
        ) as effects_cls, patch(
            "bot.handlers._run_voice_podcast_pipeline", new_callable=AsyncMock
        ) as pipeline:
            await handle_voice_message(update, mock_context)

        update.message.reply_text.assert_awaited()
        text = update.message.reply_text.await_args.args[0]
        assert "¿Qué hago con tu nota de voz?" in text

        kwargs = update.message.reply_text.await_args.kwargs
        markup = kwargs.get("reply_markup")
        assert markup is not None
        button_labels = [btn.text for row in markup.inline_keyboard for btn in row]
        assert any("Convertir y normalizar" in label for label in button_labels)
        assert any("Clonar voz" in label for label in button_labels)
        assert any("Cancelar" in label for label in button_labels)

        assert mock_context.user_data.get("voice_menu_file_id") == "voice-file-1"
        assert "voice_menu_correlation_id" in mock_context.user_data

        enhancer_cls.assert_not_called()
        converter_cls.assert_not_called()
        effects_cls.assert_not_called()
        pipeline.assert_not_awaited()


class TestVoiceMenuConvertCallback:
    @pytest.mark.asyncio
    async def test_convert_invokes_podcast_pipeline(self, mock_context):
        mock_context.user_data = {
            "voice_menu_file_id": "voice-file-1",
            "voice_menu_correlation_id": "abcd1234",
        }
        update = _callback_update("voice_menu:convert:abcd1234")

        with patch(
            "bot.handlers._run_voice_podcast_pipeline", new_callable=AsyncMock
        ) as pipeline, patch(
            "bot.handlers._run_voice_clone_pipeline", new_callable=AsyncMock
        ) as clone:
            await handle_voice_menu_callback(update, mock_context)

        pipeline.assert_awaited_once()
        kwargs = pipeline.await_args.kwargs
        assert kwargs["file_id"] == "voice-file-1"
        assert kwargs["correlation_id"] == "abcd1234"
        assert kwargs["user_id"] == 42
        clone.assert_not_awaited()


class TestVoiceMenuCloneWithoutRef:
    @pytest.mark.asyncio
    async def test_clone_without_ref_asks_for_voz_ref(self, mock_context):
        mock_context.user_data = {
            "voice_menu_file_id": "voice-file-1",
            "voice_menu_correlation_id": "abcd1234",
        }
        update = _callback_update("voice_menu:clone:abcd1234")

        with patch("bot.handlers.has_reference", return_value=False), patch(
            "bot.handlers._run_voice_clone_pipeline", new_callable=AsyncMock
        ) as clone, patch(
            "bot.handlers._run_voice_podcast_pipeline", new_callable=AsyncMock
        ) as pipeline:
            await handle_voice_menu_callback(update, mock_context)

        update.callback_query.edit_message_text.assert_awaited()
        text = update.callback_query.edit_message_text.await_args.args[0]
        assert "/voz_ref" in text
        assert "referencia" in text.lower()
        clone.assert_not_awaited()
        pipeline.assert_not_awaited()
