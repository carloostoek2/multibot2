"""Unit tests for image group (album creation) flow."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import config
from bot.handlers import (
    _get_image_group_keyboard,
    _send_album_from_file_ids,
    _start_image_group_session,
    _try_collect_image_for_group_session,
    handle_image_group_callback,
    handle_image_menu_callback,
)


def _callback_update(callback_data="image_group_action:done"):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.effective_chat = SimpleNamespace(id=1)
    update.callback_query = MagicMock()
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_media_group = AsyncMock()
    update.callback_query.message.edit_message_text = AsyncMock()
    return update


def _photo_update(file_id="photo-1", media_group_id=None):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.message = SimpleNamespace(
        media_group_id=media_group_id,
        reply_text=AsyncMock(),
        photo=[SimpleNamespace(file_id=file_id, file_size=1000)],
    )
    return update


@pytest.fixture
def mock_context():
    return MagicMock(user_data={})


class TestImageGroupKeyboard:
    def test_keyboard_has_listo_and_cancelar(self):
        keyboard = _get_image_group_keyboard(2)
        labels = [btn.text for row in keyboard.inline_keyboard for btn in row]
        callback_data = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
        assert labels == ["✅ Listo", "❌ Cancelar"]
        assert callback_data == ["image_group_action:done", "image_group_action:cancel"]


class TestImageGroupMenuAction:
    @pytest.mark.asyncio
    async def test_group_action_starts_session_with_existing_file_ids(self, mock_context):
        update = _callback_update("image_action:group")
        update.callback_query.edit_message_text = AsyncMock()
        mock_context.user_data["image_menu_file_ids"] = ["f1", "f2"]
        mock_context.user_data["image_menu_file_id"] = "f1"
        mock_context.user_data["image_menu_correlation_id"] = "corr-1"

        await handle_image_menu_callback(update, mock_context)

        session = mock_context.user_data["image_group_session"]
        assert session["file_ids"] == ["f1", "f2"]
        text = update.callback_query.edit_message_text.await_args[0][0]
        assert "Modo agrupación activado" in text
        assert "2" in text


class TestImageGroupCollection:
    @pytest.mark.asyncio
    async def test_collects_additional_images_in_active_session(self, mock_context):
        update = _photo_update("photo-2")
        _start_image_group_session(mock_context, ["photo-1"], "corr-1")

        handled = await _try_collect_image_for_group_session(
            update, mock_context, "photo-2"
        )

        assert handled is True
        assert mock_context.user_data["image_group_session"]["file_ids"] == [
            "photo-1",
            "photo-2",
        ]
        update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_without_active_session(self, mock_context):
        update = _photo_update("photo-1")

        handled = await _try_collect_image_for_group_session(
            update, mock_context, "photo-1"
        )

        assert handled is False


class TestImageGroupDone:
    @pytest.mark.asyncio
    async def test_done_sends_album_and_clears_session(self, mock_context):
        update = _callback_update("image_group_action:done")
        update.callback_query.edit_message_text = AsyncMock()
        _start_image_group_session(mock_context, ["f1", "f2", "f3"], "corr-done")

        with patch(
            "bot.handlers._send_album_from_file_ids", new_callable=AsyncMock
        ) as send_album:
            await handle_image_group_callback(update, mock_context)

        send_album.assert_awaited_once_with(
            update, mock_context, ["f1", "f2", "f3"], "corr-done"
        )
        assert "image_group_session" not in mock_context.user_data
        final_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "Álbum enviado" in final_text

    @pytest.mark.asyncio
    async def test_done_requires_at_least_two_images(self, mock_context):
        update = _callback_update("image_group_action:done")
        update.callback_query.edit_message_text = AsyncMock()
        _start_image_group_session(mock_context, ["f1"], "corr-one")

        await handle_image_group_callback(update, mock_context)

        alert_call = update.callback_query.answer.await_args_list[-1]
        assert alert_call.kwargs.get("show_alert") is True
        alert_text = alert_call.args[0] if alert_call.args else alert_call.kwargs["text"]
        assert "2 imágenes" in alert_text
        assert mock_context.user_data["image_group_session"]["file_ids"] == ["f1"]

    @pytest.mark.asyncio
    async def test_cancel_clears_session(self, mock_context):
        update = _callback_update("image_group_action:cancel")
        update.callback_query.edit_message_text = AsyncMock()
        _start_image_group_session(mock_context, ["f1", "f2"], "corr-cancel")

        await handle_image_group_callback(update, mock_context)

        assert "image_group_session" not in mock_context.user_data
        assert "cancelada" in update.callback_query.edit_message_text.await_args[0][0].lower()


class TestSendAlbumFromFileIds:
    @pytest.mark.asyncio
    async def test_sends_media_group_with_file_ids(self, mock_context):
        update = _callback_update()
        file_ids = [f"id-{i}" for i in range(4)]

        await _send_album_from_file_ids(update, mock_context, file_ids, "corr-send")

        update.callback_query.message.reply_media_group.assert_awaited_once()
        media = update.callback_query.message.reply_media_group.await_args.kwargs["media"]
        assert len(media) == 4
        assert [item.media for item in media] == file_ids

    @pytest.mark.asyncio
    async def test_splits_more_than_ten_images(self, mock_context):
        update = _callback_update()
        file_ids = [f"id-{i}" for i in range(12)]

        await _send_album_from_file_ids(update, mock_context, file_ids, "corr-split")

        assert update.callback_query.message.reply_media_group.await_count == 2
        first_batch = (
            update.callback_query.message.reply_media_group.await_args_list[0]
            .kwargs["media"]
        )
        second_batch = (
            update.callback_query.message.reply_media_group.await_args_list[1]
            .kwargs["media"]
        )
        assert len(first_batch) == config.MAX_IMAGE_BATCH_SIZE
        assert len(second_batch) == 2