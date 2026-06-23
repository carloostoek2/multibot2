"""Unit tests for pitch shift handler dual-send behavior."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from bot.error_handler import AudioEffectsError, ERROR_MESSAGES
from bot.handlers import (
    _handle_postdownload_pitch_shift,
    handle_audio_pitch_selection,
    handle_postdownload_pitch_shift_intensity_callback,
)


def _callback_update(callback_data="audio_pitch:agudo"):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=7)
    update.effective_chat = SimpleNamespace(id=99)
    update.callback_query = MagicMock()
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_audio = AsyncMock()
    update.callback_query.message.reply_document = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {
        "effect_audio_file_id": "audio-file",
        "effect_audio_correlation_id": "corr-pitch",
        "effect_type": "pitch_shift",
    }
    context.bot = AsyncMock()
    context.bot.get_file = AsyncMock(return_value=MagicMock())
    context.bot.send_audio = AsyncMock()
    context.bot.send_document = AsyncMock()
    return context


class TestHandleAudioPitchSelectionDualSend:
    @pytest.mark.asyncio
    async def test_sends_audio_and_document(self, mock_context):
        update = _callback_update()

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch("bot.handlers.validate_audio_file", return_value=(True, None)), patch(
            "bot.handlers.check_disk_space", return_value=(True, None)
        ), patch("bot.handlers.estimate_required_space", return_value=10), patch(
            "bot.handlers.Path"
        ) as path_cls, patch("bot.handlers.AudioEffects") as effects_cls, patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock, patch("builtins.open", mock_open(read_data=b"mp3")):
            path_instance = MagicMock()
            path_instance.stat.return_value = MagicMock(st_size=1024)
            path_cls.return_value = path_instance
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            effects = MagicMock()
            effects.pitch_shift.return_value = effects
            effects_cls.return_value = effects

            loop = MagicMock()
            loop.run_in_executor = AsyncMock(return_value=None)
            loop_mock.return_value = loop

            await handle_audio_pitch_selection(update, mock_context)

        update.callback_query.edit_message_text.assert_awaited()
        mock_context.bot.send_audio.assert_awaited_once()
        mock_context.bot.send_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_success_when_document_fails(self, mock_context):
        update = _callback_update()

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch("bot.handlers.validate_audio_file", return_value=(True, None)), patch(
            "bot.handlers.check_disk_space", return_value=(True, None)
        ), patch("bot.handlers.estimate_required_space", return_value=10), patch(
            "bot.handlers.Path"
        ) as path_cls, patch("bot.handlers.AudioEffects"), patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock, patch("builtins.open", mock_open(read_data=b"mp3")):
            path_instance = MagicMock()
            path_instance.stat.return_value = MagicMock(st_size=1024)
            path_cls.return_value = path_instance

            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            loop = MagicMock()
            loop.run_in_executor = AsyncMock(return_value=None)
            loop_mock.return_value = loop

            mock_context.bot.send_document.side_effect = RuntimeError("document failed")

            await handle_audio_pitch_selection(update, mock_context)

        final_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "Listo" in final_text
        assert "documento" in final_text.lower()

    @pytest.mark.asyncio
    async def test_uses_error_messages_for_audio_effects_error(self, mock_context):
        update = _callback_update()

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch("bot.handlers.validate_audio_file", return_value=(True, None)), patch(
            "bot.handlers.check_disk_space", return_value=(True, None)
        ), patch("bot.handlers.estimate_required_space", return_value=10), patch(
            "bot.handlers.Path"
        ) as path_cls, patch("bot.handlers.AudioEffects"), patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock:
            path_instance = MagicMock()
            path_instance.stat.return_value = MagicMock(st_size=1024)
            path_cls.return_value = path_instance

            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            loop = MagicMock()
            loop.run_in_executor = AsyncMock(
                side_effect=AudioEffectsError("ffmpeg stderr junk")
            )
            loop_mock.return_value = loop

            await handle_audio_pitch_selection(update, mock_context)

        error_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "ffmpeg stderr junk" in error_text

    @pytest.mark.asyncio
    async def test_uses_default_error_message_for_generic_audio_effects_error(
        self, mock_context
    ):
        update = _callback_update()

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch("bot.handlers.validate_audio_file", return_value=(True, None)), patch(
            "bot.handlers.check_disk_space", return_value=(True, None)
        ), patch("bot.handlers.estimate_required_space", return_value=10), patch(
            "bot.handlers.Path"
        ) as path_cls, patch("bot.handlers.AudioEffects"), patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock:
            path_instance = MagicMock()
            path_instance.stat.return_value = MagicMock(st_size=1024)
            path_cls.return_value = path_instance

            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            loop = MagicMock()
            loop.run_in_executor = AsyncMock(side_effect=AudioEffectsError())
            loop_mock.return_value = loop

            await handle_audio_pitch_selection(update, mock_context)

        error_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert ERROR_MESSAGES[AudioEffectsError] in error_text


class TestPostdownloadPitchShiftDualSend:
    @pytest.mark.asyncio
    async def test_sends_audio_and_document(self, mock_context):
        update = _callback_update("postdownload:pitch_shift_intensity:corr:agudo")
        entry = SimpleNamespace(file_path="/tmp/source.mp3")

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers.Path"
        ) as path_cls, patch("bot.handlers.AudioEffects"), patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock, patch("builtins.open", mock_open(read_data=b"mp3")):
            path_instance = MagicMock()
            path_instance.stat.return_value = MagicMock(st_size=1024)
            path_cls.return_value = path_instance
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.return_value = "/tmp/out.mp3"
            temp_mgr_cls.return_value = temp_mgr

            loop = MagicMock()
            loop.run_in_executor = AsyncMock(return_value=None)
            loop_mock.return_value = loop

            await _handle_postdownload_pitch_shift(
                update, mock_context, entry, "corr", "agudo", "Agudo"
            )

        update.callback_query.message.reply_audio.assert_awaited_once()
        update.callback_query.message.reply_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_postdownload_pitch_shift_surfaces_audio_effects_error(self, mock_context):
        update = _callback_update("postdownload:pitch_shift_intensity:corr:agudo")
        entry = SimpleNamespace(file_path="/tmp/source.mp3")

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers.Path"
        ) as path_cls, patch("bot.handlers.AudioEffects"), patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock:
            path_instance = MagicMock()
            path_instance.stat.return_value = MagicMock(st_size=1024)
            path_cls.return_value = path_instance
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.return_value = "/tmp/out.mp3"
            temp_mgr_cls.return_value = temp_mgr

            loop = MagicMock()
            loop.run_in_executor = AsyncMock(
                side_effect=AudioEffectsError("Error aplicando cambio de tono: ffmpeg failed")
            )
            loop_mock.return_value = loop

            await _handle_postdownload_pitch_shift(
                update, mock_context, entry, "corr", "agudo", "Agudo"
            )

        error_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "Error aplicando cambio de tono: ffmpeg failed" in error_text


class TestPostdownloadPitchShiftIntensityCallbackValidation:
    @pytest.mark.asyncio
    async def test_malformed_callback_data_shows_invalid_selection_error(self, mock_context):
        update = _callback_update("postdownload:bad")

        await handle_postdownload_pitch_shift_intensity_callback(update, mock_context)

        error_text = update.callback_query.edit_message_text.await_args[0][0]
        assert "selección inválida" in error_text

    @pytest.mark.asyncio
    async def test_unknown_intensity_shows_invalid_intensity_error(self, mock_context):
        update = _callback_update("postdownload:pitch_shift_intensity:corr:extreme")

        await handle_postdownload_pitch_shift_intensity_callback(update, mock_context)

        error_text = update.callback_query.edit_message_text.await_args[0][0]
        assert "intensidad inválida" in error_text
