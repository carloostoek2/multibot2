"""Unit tests for _send_images_in_albums album splitting and fallback."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from bot.handlers import _send_images_in_albums


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

        with patch("builtins.open", mock_open(read_data=b"img")):
            await _send_images_in_albums(
                update,
                mock_context,
                paths,
                "corr-split",
                caption_prefix="Mejorada",
            )

        assert update.callback_query.message.reply_media_group.await_count == 2

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

        with patch("builtins.open", mock_open(read_data=b"img")):
            await _send_images_in_albums(
                update,
                mock_context,
                [str(path)],
                "corr-fallback",
            )

        update.callback_query.message.reply_photo.assert_awaited_once()