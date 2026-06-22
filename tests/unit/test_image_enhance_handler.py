"""Unit tests for handle_image_enhance_callback batch path."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from bot.handlers import handle_image_enhance_callback


@pytest.fixture
def mock_query_update():
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.callback_query = MagicMock()
    update.callback_query.data = "image_enhance:equilibrado"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_document = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {
        "image_menu_file_ids": ["f1", "f2"],
        "image_menu_file_id": "f1",
        "image_menu_correlation_id": "corr-batch",
    }
    context.bot = AsyncMock()
    context.bot.get_file = AsyncMock(return_value=MagicMock())
    return context


class TestHandleImageEnhanceCallback:
    @pytest.mark.asyncio
    async def test_rejects_batch_when_disk_space_insufficient(
        self, mock_query_update, mock_context
    ):
        with patch("bot.handlers.check_disk_space", return_value=(False, "Sin espacio")):
            await handle_image_enhance_callback(mock_query_update, mock_context)

        mock_query_update.callback_query.edit_message_text.assert_awaited()
        assert "Sin espacio" in mock_query_update.callback_query.edit_message_text.await_args[0][0]

    @pytest.mark.asyncio
    async def test_batch_enhance_processes_all_images(self, mock_query_update, mock_context):
        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers._send_images_in_albums", new_callable=AsyncMock
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

            await handle_image_enhance_callback(mock_query_update, mock_context)

        send_albums.assert_awaited_once()
        assert mock_context.bot.get_file.await_count == 2

    @pytest.mark.asyncio
    async def test_enhance_timeout_uses_remaining_budget_after_download(
        self, mock_query_update, mock_context
    ):
        wait_for_mock = AsyncMock(return_value=(True, None))

        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.ImageProcessor.enhance", return_value=(True, None)
        ), patch("bot.handlers.time.monotonic", side_effect=[0, 40]), patch(
            "bot.handlers.asyncio.wait_for", wait_for_mock
        ), patch("builtins.open", MagicMock()):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            mock_context.user_data["image_menu_file_ids"] = ["f1"]

            await handle_image_enhance_callback(mock_query_update, mock_context)

        assert wait_for_mock.await_args.kwargs["timeout"] == 5

    @pytest.mark.asyncio
    async def test_raises_processing_timeout_when_deadline_exceeded_after_download(
        self, mock_query_update, mock_context
    ):
        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch("bot.handlers.time.monotonic", side_effect=[0, 200, 200]), patch(
            "bot.handlers.get_user_error_message",
            return_value="La mejora tardó demasiado. Intenta con menos imágenes o más pequeñas.",
        ):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            mock_context.user_data["image_menu_file_ids"] = ["f1"]

            await handle_image_enhance_callback(mock_query_update, mock_context)

        error_text = mock_query_update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "La mejora tardó demasiado" in error_text

    @pytest.mark.asyncio
    async def test_enhancement_failure_surfaces_custom_error_message(
        self, mock_query_update, mock_context
    ):
        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.ImageProcessor.enhance",
            return_value=(False, "cannot identify image file"),
        ), patch("bot.handlers.time.monotonic", side_effect=[0, 1, 2]), patch(
            "bot.handlers.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=(False, "cannot identify image file"),
        ), patch(
            "bot.handlers.get_user_error_message",
            side_effect=lambda exc: exc.message,
        ):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            mock_context.user_data["image_menu_file_ids"] = ["f1"]

            await handle_image_enhance_callback(mock_query_update, mock_context)

        error_text = mock_query_update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "cannot identify image file" in error_text

    @pytest.mark.asyncio
    async def test_single_image_uses_reply_document(self, mock_query_update, mock_context):
        mock_context.user_data = {
            "image_menu_file_id": "f1",
            "image_menu_correlation_id": "corr-single",
        }

        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers._send_images_in_albums", new_callable=AsyncMock
        ) as send_albums, patch(
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

            await handle_image_enhance_callback(mock_query_update, mock_context)

        mock_query_update.callback_query.message.reply_document.assert_awaited_once()
        send_albums.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_wait_for_timeout_error_surfaces_spanish_message(
        self, mock_query_update, mock_context
    ):
        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch("bot.handlers.time.monotonic", side_effect=[0, 1, 2]), patch(
            "bot.handlers.asyncio.wait_for", side_effect=asyncio.TimeoutError()
        ):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            mock_context.user_data["image_menu_file_ids"] = ["f1"]

            await handle_image_enhance_callback(mock_query_update, mock_context)

        error_text = mock_query_update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "La mejora tardó demasiado" in error_text

    @pytest.mark.asyncio
    async def test_batch_partial_failure_on_second_image_aborts(
        self, mock_query_update, mock_context
    ):
        mock_context.user_data["image_menu_file_ids"] = ["f1", "f2", "f3"]

        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers._send_images_in_albums", new_callable=AsyncMock
        ) as send_albums, patch("bot.handlers.time.monotonic", side_effect=[0, 1, 2, 3, 4, 5]), patch(
            "bot.handlers.asyncio.wait_for",
            new_callable=AsyncMock,
            side_effect=[
                (True, None),
                (False, "cannot identify image file"),
            ],
        ), patch(
            "bot.handlers.get_user_error_message",
            side_effect=lambda exc: exc.message,
        ):
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            await handle_image_enhance_callback(mock_query_update, mock_context)

        error_text = mock_query_update.callback_query.edit_message_text.await_args_list[-1][0][0]
        assert "cannot identify image file" in error_text
        send_albums.assert_not_awaited()
        assert mock_context.bot.get_file.await_count == 2