"""Unit tests for image-menu result chaining (promote file_ids)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from bot.handlers import (
    _promote_image_menu_results,
    handle_image_compress_callback,
    handle_image_enhance_callback,
    handle_image_noise_callback,
)


def _sent_document(file_id: str):
    return SimpleNamespace(document=SimpleNamespace(file_id=file_id))


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {
        "image_menu_file_ids": ["orig1"],
        "image_menu_file_id": "orig1",
        "image_menu_correlation_id": "corr-chain",
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
    update.callback_query.message.reply_text = AsyncMock()
    return update


class TestPromoteImageMenuResults:
    def test_promotes_and_snapshots_originals_once(self, mock_context):
        _promote_image_menu_results(mock_context, ["new1", "new2"])
        assert mock_context.user_data["image_menu_file_ids"] == ["new1", "new2"]
        assert mock_context.user_data["image_menu_file_id"] == "new1"
        assert mock_context.user_data["image_menu_original_file_ids"] == ["orig1"]
        assert mock_context.user_data["image_menu_original_file_id"] == "orig1"

        _promote_image_menu_results(mock_context, ["newer"])
        assert mock_context.user_data["image_menu_file_ids"] == ["newer"]
        assert mock_context.user_data["image_menu_original_file_ids"] == ["orig1"]

    def test_noop_on_empty(self, mock_context):
        _promote_image_menu_results(mock_context, [])
        assert mock_context.user_data["image_menu_file_id"] == "orig1"
        assert "image_menu_original_file_ids" not in mock_context.user_data


class TestImageMenuChainHandlers:
    @pytest.mark.asyncio
    async def test_compress_promotes_sent_document_file_id(self, mock_context):
        update = _query_update("image_compress:80")

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.ImageProcessor.compress", return_value=(True, None)
        ), patch("bot.handlers.asyncio.wait_for", new_callable=AsyncMock, return_value=(True, None)), patch(
            "bot.handlers.os.path.getsize", side_effect=[1000, 400]
        ), patch("builtins.open", mock_open(read_data=b"jpg")):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            await handle_image_compress_callback(update, mock_context)

        assert mock_context.user_data["image_menu_file_id"] == "sent-doc-1"
        assert mock_context.user_data["image_menu_file_ids"] == ["sent-doc-1"]
        assert mock_context.user_data["image_menu_original_file_ids"] == ["orig1"]

    @pytest.mark.asyncio
    async def test_enhance_single_promotes_sent_document_file_id(self, mock_context):
        update = _query_update("image_enhance:equilibrado")
        mock_context.user_data["image_menu_file_ids"] = ["orig1"]

        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.ImageProcessor.enhance", return_value=(True, None)
        ), patch("bot.handlers.time.monotonic", side_effect=[0, 1, 2]), patch(
            "bot.handlers.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=(True, None),
        ), patch("builtins.open", mock_open(read_data=b"jpg")):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            await handle_image_enhance_callback(update, mock_context)

        assert mock_context.user_data["image_menu_file_id"] == "sent-doc-1"
        assert mock_context.user_data["image_menu_file_ids"] == ["sent-doc-1"]
        assert mock_context.user_data["image_menu_original_file_ids"] == ["orig1"]

    @pytest.mark.asyncio
    async def test_enhance_batch_promotes_album_file_ids(self, mock_context):
        update = _query_update("image_enhance:equilibrado")
        mock_context.user_data["image_menu_file_ids"] = ["f1", "f2"]
        mock_context.user_data["image_menu_file_id"] = "f1"

        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers._send_images_in_albums",
            new_callable=AsyncMock,
            return_value=["album1", "album2"],
        ) as send_albums, patch(
            "bot.handlers.ImageProcessor.enhance", return_value=(True, None)
        ), patch("bot.handlers.time.monotonic", side_effect=[0, 1, 2, 3, 4, 5]), patch(
            "bot.handlers.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            await handle_image_enhance_callback(update, mock_context)

        send_albums.assert_awaited_once()
        assert mock_context.user_data["image_menu_file_ids"] == ["album1", "album2"]
        assert mock_context.user_data["image_menu_file_id"] == "album1"
        assert mock_context.user_data["image_menu_original_file_ids"] == ["f1", "f2"]

    @pytest.mark.asyncio
    async def test_noise_batch_promotes_album_file_ids(self, mock_context):
        update = _query_update("image_noise:2")
        mock_context.user_data["image_menu_file_ids"] = ["n1", "n2", "n3"]
        mock_context.user_data["image_menu_file_id"] = "n1"

        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers._send_images_in_albums",
            new_callable=AsyncMock,
            return_value=["out1", "out2", "out3"],
        ), patch(
            "bot.handlers.ImageProcessor.add_noise", return_value=(True, None)
        ), patch("bot.handlers.time.monotonic", side_effect=list(range(20))), patch(
            "bot.handlers.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=(True, None),
        ):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            await handle_image_noise_callback(update, mock_context)

        assert mock_context.user_data["image_menu_file_ids"] == ["out1", "out2", "out3"]
        assert mock_context.user_data["image_menu_file_id"] == "out1"
        assert mock_context.user_data["image_menu_original_file_ids"] == ["n1", "n2", "n3"]
