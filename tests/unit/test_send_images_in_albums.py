"""Unit tests for _send_images_in_albums album splitting and fallback."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from bot.handlers import _send_images_in_albums


def _photo_message(file_id: str):
    return SimpleNamespace(photo=[SimpleNamespace(file_id=f"{file_id}_small"), SimpleNamespace(file_id=file_id)])


def _callback_update():
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.callback_query = MagicMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_media_group = AsyncMock()
    update.callback_query.message.reply_photo = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    return MagicMock()


class TestSendImagesInAlbums:
    @pytest.mark.asyncio
    async def test_splits_large_batches_into_multiple_albums(self, mock_context, tmp_path):
        update = _callback_update()
        paths = []
        for i in range(12):
            path = tmp_path / f"img_{i}.jpg"
            path.write_bytes(b"img")
            paths.append(str(path))

        update.callback_query.message.reply_media_group.side_effect = [
            [_photo_message(f"a{i}") for i in range(10)],
            [_photo_message(f"b{i}") for i in range(2)],
        ]

        with patch("builtins.open", mock_open(read_data=b"img")):
            file_ids = await _send_images_in_albums(
                update,
                mock_context,
                paths,
                "corr-split",
                caption_prefix="Mejorada",
            )

        assert update.callback_query.message.reply_media_group.await_count == 2
        assert file_ids == [f"a{i}" for i in range(10)] + [f"b{i}" for i in range(2)]

    @pytest.mark.asyncio
    async def test_falls_back_to_individual_photos_on_album_failure(
        self, mock_context, tmp_path
    ):
        update = _callback_update()
        path = tmp_path / "img.jpg"
        path.write_bytes(b"img")
        update.callback_query.message.reply_media_group.side_effect = RuntimeError(
            "album failed"
        )
        update.callback_query.message.reply_photo.return_value = _photo_message("fallback1")

        with patch("builtins.open", mock_open(read_data=b"img")):
            file_ids = await _send_images_in_albums(
                update,
                mock_context,
                [str(path)],
                "corr-fallback",
            )

        update.callback_query.message.reply_photo.assert_awaited_once()
        assert file_ids == ["fallback1"]

    @pytest.mark.asyncio
    async def test_preserves_album_order_across_messages(self, mock_context, tmp_path):
        update = _callback_update()
        paths = []
        for i in range(3):
            path = tmp_path / f"img_{i}.jpg"
            path.write_bytes(b"img")
            paths.append(str(path))

        update.callback_query.message.reply_media_group.return_value = [
            _photo_message("id0"),
            _photo_message("id1"),
            _photo_message("id2"),
        ]

        with patch("builtins.open", mock_open(read_data=b"img")):
            file_ids = await _send_images_in_albums(
                update, mock_context, paths, "corr-order"
            )

        assert file_ids == ["id0", "id1", "id2"]
