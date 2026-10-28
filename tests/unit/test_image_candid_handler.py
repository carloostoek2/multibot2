"""Unit tests for the «Fotográfico» image-menu flow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from bot.handlers import handle_image_candid_callback, handle_image_menu_callback


def _sent_document(file_id: str):
    return SimpleNamespace(document=SimpleNamespace(file_id=file_id))


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {
        "image_menu_file_ids": ["f1"],
        "image_menu_file_id": "f1",
        "image_menu_correlation_id": "corr-candid",
    }
    context.bot = AsyncMock()
    context.bot.get_file = AsyncMock(return_value=MagicMock())
    return context


def _query_update(callback_data: str):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.callback_query = MagicMock()
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_document = AsyncMock(
        return_value=_sent_document("sent-doc-1")
    )
    update.callback_query.message.reply_photo = AsyncMock(
        return_value=SimpleNamespace(
            photo=[SimpleNamespace(file_id="sent-photo-1")]
        )
    )
    update.callback_query.message.reply_text = AsyncMock()
    return update


def _temp_manager():
    temp_mgr = MagicMock()
    temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
    temp_mgr.__exit__ = MagicMock(return_value=False)
    temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
    return temp_mgr


class TestCandidSubmenu:
    @pytest.mark.asyncio
    async def test_shows_presets_and_delivery_with_current_marked(self, mock_context):
        update = _query_update("image_action:candid")

        with patch("bot.handlers.candid_available", return_value=True), patch(
            "bot.handlers.get_image_candid_preset", return_value="medium"
        ), patch(
            "bot.handlers.get_image_candid_delivery", return_value="document"
        ):
            await handle_image_menu_callback(update, mock_context)

        text = update.callback_query.edit_message_text.await_args[0][0]
        keyboard = update.callback_query.edit_message_text.await_args.kwargs["reply_markup"]
        callback_data = [
            button.callback_data for row in keyboard.inline_keyboard for button in row
        ]
        labels = [button.text for row in keyboard.inline_keyboard for button in row]

        assert "Fotográfico" in text
        assert "Archivo PNG" in text
        assert callback_data == [
            "image_candid:delivery:document",
            "image_candid:delivery:photo",
            "image_candid:subtle",
            "image_candid:medium",
            "image_candid:strong",
            "back:image",
            "cancel",
        ]
        assert "📄 Archivo PNG ✓" in labels
        assert "🖼️ Imagen" in labels
        assert "Media ✓" in labels
        assert "Sutil" in labels and "Fuerte" in labels

    @pytest.mark.asyncio
    async def test_delivery_toggle_persists_and_rerenders(self, mock_context):
        update = _query_update("image_candid:delivery:photo")
        set_delivery = MagicMock()

        with patch("bot.handlers.set_image_candid_delivery", set_delivery), patch(
            "bot.handlers.get_image_candid_preset", return_value="strong"
        ), patch("bot.handlers.get_image_candid_delivery"):
            await handle_image_candid_callback(update, mock_context)

        set_delivery.assert_called_once_with(42, "photo")
        text = update.callback_query.edit_message_text.await_args[0][0]
        keyboard = update.callback_query.edit_message_text.await_args.kwargs["reply_markup"]
        labels = [button.text for row in keyboard.inline_keyboard for button in row]
        assert "Entrega actual: 🖼️ Imagen" in text
        assert "🖼️ Imagen ✓" in labels
        assert "Fuerte ✓" in labels

    @pytest.mark.asyncio
    async def test_invalid_delivery_mode_is_rejected(self, mock_context):
        update = _query_update("image_candid:delivery:fax")

        await handle_image_candid_callback(update, mock_context)

        text = update.callback_query.edit_message_text.await_args[0][0]
        assert "modo de entrega inválido" in text

    @pytest.mark.asyncio
    async def test_unavailable_engine_reports_error(self, mock_context):
        update = _query_update("image_action:candid")

        with patch("bot.handlers.candid_available", return_value=False):
            await handle_image_menu_callback(update, mock_context)

        text = update.callback_query.edit_message_text.await_args[0][0]
        assert "no está disponible" in text


class TestCandidProcessing:
    @pytest.mark.asyncio
    async def test_single_image_sends_document_and_persists_preset(self, mock_context):
        update = _query_update("image_candid:strong")
        set_preset = MagicMock()

        with patch("bot.handlers.candid_available", return_value=True), patch(
            "bot.handlers.set_image_candid_preset", set_preset
        ), patch(
            "bot.handlers.get_image_candid_delivery", return_value="document"
        ), patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager", return_value=_temp_manager()
        ), patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.apply_candid_effect", return_value=Path("/tmp/out.jpg")
        ), patch(
            "builtins.open", mock_open(read_data=b"jpg")
        ):
            await handle_image_candid_callback(update, mock_context)

        set_preset.assert_called_once_with(42, "strong")
        update.callback_query.message.reply_document.assert_awaited_once()
        assert (
            update.callback_query.message.reply_document.await_args.kwargs["filename"]
            == "fotografica_corr-candid.png"
        )
        assert mock_context.user_data["image_menu_file_id"] == "sent-doc-1"
        assert mock_context.user_data["image_menu_original_file_ids"] == ["f1"]
        final_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "Fuerte" in final_text
        assert "archivo PNG" in final_text

    @pytest.mark.asyncio
    async def test_photo_delivery_sends_photo_without_document(self, mock_context):
        update = _query_update("image_candid:medium")

        with patch("bot.handlers.candid_available", return_value=True), patch(
            "bot.handlers.set_image_candid_preset"
        ), patch(
            "bot.handlers.get_image_candid_delivery", return_value="photo"
        ), patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager", return_value=_temp_manager()
        ), patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.apply_candid_effect", return_value=Path("/tmp/out.jpg")
        ), patch("builtins.open", mock_open(read_data=b"jpg")):
            await handle_image_candid_callback(update, mock_context)

        update.callback_query.message.reply_photo.assert_awaited_once()
        update.callback_query.message.reply_document.assert_not_awaited()
        assert mock_context.user_data["image_menu_file_id"] == "sent-photo-1"
        final_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "imagen" in final_text

    @pytest.mark.asyncio
    async def test_album_processes_every_image(self, mock_context):
        mock_context.user_data["image_menu_file_ids"] = ["f1", "f2"]
        update = _query_update("image_candid:medium")

        with patch("bot.handlers.candid_available", return_value=True), patch(
            "bot.handlers.set_image_candid_preset"
        ), patch(
            "bot.handlers.get_image_candid_delivery", return_value="document"
        ), patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager", return_value=_temp_manager()
        ), patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.apply_candid_effect", return_value=Path("/tmp/out.jpg")
        ), patch(
            "bot.handlers._send_images_in_albums",
            new_callable=AsyncMock,
            return_value=["sent-a", "sent-b"],
        ) as send_albums:
            await handle_image_candid_callback(update, mock_context)

        assert mock_context.bot.get_file.await_count == 2
        send_albums.assert_awaited_once()
        assert send_albums.await_args.kwargs["as_documents"] is True
        assert mock_context.user_data["image_menu_file_ids"] == ["sent-a", "sent-b"]

    @pytest.mark.asyncio
    async def test_invalid_preset_is_rejected(self, mock_context):
        update = _query_update("image_candid:extremo")

        with patch("bot.handlers.candid_available", return_value=True):
            await handle_image_candid_callback(update, mock_context)

        text = update.callback_query.edit_message_text.await_args[0][0]
        assert "no soportada" in text

    @pytest.mark.asyncio
    async def test_insufficient_disk_space_stops_processing(self, mock_context):
        update = _query_update("image_candid:medium")

        with patch("bot.handlers.candid_available", return_value=True), patch(
            "bot.handlers.set_image_candid_preset"
        ), patch(
            "bot.handlers.get_image_candid_delivery", return_value="document"
        ), patch(
            "bot.handlers.check_disk_space", return_value=(False, "Sin espacio")
        ), patch(
            "bot.handlers.apply_candid_effect"
        ) as apply_mock:
            await handle_image_candid_callback(update, mock_context)

        apply_mock.assert_not_called()
        text = update.callback_query.edit_message_text.await_args[0][0]
        assert "Sin espacio" in text

    @pytest.mark.asyncio
    async def test_processing_error_is_reported(self, mock_context):
        update = _query_update("image_candid:medium")

        with patch("bot.handlers.candid_available", return_value=True), patch(
            "bot.handlers.set_image_candid_preset"
        ), patch(
            "bot.handlers.get_image_candid_delivery", return_value="document"
        ), patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager", return_value=_temp_manager()
        ), patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.apply_candid_effect", return_value=Path("/tmp/out.jpg")
        ), patch(
            "bot.handlers.asyncio.wait_for", side_effect=RuntimeError("fallo inesperado")
        ):
            await handle_image_candid_callback(update, mock_context)

        final_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "error inesperado" in final_text
