"""Unit tests for album auto-pipeline preference, menu, and runner."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import (
    ALBUM_AUTO_PIPELINE_PREF_KEY,
    ALBUM_PIPELINE_ENHANCE_PROFILE,
    ALBUM_PIPELINE_MIN_IMAGES,
    ALBUM_PIPELINE_NOISE_STRENGTH,
    _get_image_menu_keyboard,
    _is_album_auto_pipeline_enabled,
    _run_image_album_pipeline,
    _schedule_image_batch_menu,
    _set_album_auto_pipeline_enabled,
    handle_config_callback,
    handle_config_command,
    handle_image_menu_callback,
)


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    context.bot.get_file = AsyncMock(return_value=MagicMock())
    context.application = MagicMock()
    context.application.user_data = {99: context.user_data}
    context.application.bot = context.bot
    context.application.bot_data = {"image_batch_sessions": {}}
    return context


def _config_update():
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=99)
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _config_callback_update(data="config_toggle:album_auto"):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=99)
    update.callback_query = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


class TestAlbumAutoPreference:
    def test_default_is_off(self, tmp_path, monkeypatch):
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        ud = {}
        assert _is_album_auto_pipeline_enabled(42, ud) is False
        assert ud[ALBUM_AUTO_PIPELINE_PREF_KEY] is False

    def test_toggle_persists_to_disk_and_user_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        ud = {}
        assert _set_album_auto_pipeline_enabled(42, True, ud) is True
        assert ud[ALBUM_AUTO_PIPELINE_PREF_KEY] is True
        assert _is_album_auto_pipeline_enabled(42, {}) is True
        # Survives "restart": empty user_data still reads disk
        assert _is_album_auto_pipeline_enabled(42, {}) is True
        assert _set_album_auto_pipeline_enabled(42, False, ud) is False
        assert _is_album_auto_pipeline_enabled(42, {}) is False

    def test_presets_match_product_definitions(self):
        assert ALBUM_PIPELINE_NOISE_STRENGTH == 2  # Sutil
        assert ALBUM_PIPELINE_ENHANCE_PROFILE == "equilibrado"
        assert ALBUM_PIPELINE_MIN_IMAGES == 2


class TestConfigCommand:
    @pytest.mark.asyncio
    async def test_config_command_shows_toggle_off_by_default(
        self, mock_context, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        update = _config_update()
        await handle_config_command(update, mock_context)
        text, kwargs = update.message.reply_text.await_args
        assert "Pipeline automático de álbumes" in text[0]
        assert "Desactivado" in text[0]
        btn = kwargs["reply_markup"].inline_keyboard[0][0]
        assert btn.callback_data == "config_toggle:album_auto"
        assert "OFF" in btn.text

    @pytest.mark.asyncio
    async def test_config_toggle_flips_preference_and_disk(
        self, mock_context, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        update = _config_callback_update()
        await handle_config_callback(update, mock_context)
        assert mock_context.user_data[ALBUM_AUTO_PIPELINE_PREF_KEY] is True
        text, kwargs = update.callback_query.edit_message_text.await_args
        assert "Activado" in text[0]
        assert "ON" in kwargs["reply_markup"].inline_keyboard[0][0].text
        # Disk file exists and survives empty cache
        assert (tmp_path / "99.json").is_file()
        assert _is_album_auto_pipeline_enabled(99, {}) is True

        await handle_config_callback(update, mock_context)
        assert mock_context.user_data[ALBUM_AUTO_PIPELINE_PREF_KEY] is False
        assert _is_album_auto_pipeline_enabled(99, {}) is False


class TestAlbumMenuPipelineButton:
    def test_album_keyboard_includes_pipeline(self):
        labels = [b.text for row in _get_image_menu_keyboard(4).inline_keyboard for b in row]
        assert "⚡ Pipeline (Naturalizar + Mejorar)" in labels

    def test_single_image_keyboard_omits_pipeline(self):
        labels = [b.text for row in _get_image_menu_keyboard(1).inline_keyboard for b in row]
        assert "⚡ Pipeline (Naturalizar + Mejorar)" not in labels


class TestAlbumPipelineRunner:
    @pytest.mark.asyncio
    async def test_pipeline_naturalize_then_enhance_then_send(self, mock_context):
        chat = SimpleNamespace(id=1, type="private")
        mock_context.application.user_data = {99: mock_context.user_data}
        status = MagicMock()
        status.edit_text = AsyncMock()
        status.reply_text = AsyncMock()
        status.chat = chat

        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=99),
            effective_chat=chat,
            message=None,
            callback_query=None,
        )

        noise = MagicMock(return_value=(True, None))
        enhance = MagicMock(return_value=(True, None))

        async def fake_wait_for(coro, timeout=None):
            # run_in_executor already scheduled; call the wrapped lambda via result
            # Prefer invoking the submitted callable when possible.
            if asyncio.isfuture(coro):
                # Cancel real executor work; invoke patched processors via call tracking below
                coro.cancel()
                # Infer step from call order using a side channel
                return (True, None)
            return await coro

        call_order = []

        def fake_run_in_executor(executor, fn):
            result = fn()
            call_order.append(result)
            fut = asyncio.get_running_loop().create_future()
            fut.set_result(result)
            return fut

        with patch("bot.handlers.check_disk_space", return_value=(True, None)), patch(
            "bot.handlers.TempManager"
        ) as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.ImageProcessor.add_noise", noise
        ), patch(
            "bot.handlers.ImageProcessor.enhance", enhance
        ), patch(
            "bot.handlers.time.monotonic", return_value=0
        ), patch(
            "bot.handlers._send_images_in_albums",
            new_callable=AsyncMock,
            return_value=["sent1", "sent2"],
        ) as send_albums, patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as get_loop:
            loop = MagicMock()
            loop.run_in_executor.side_effect = fake_run_in_executor
            get_loop.return_value = loop

            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            temp_mgr.get_temp_path.side_effect = lambda name: f"/tmp/{name}"
            temp_mgr_cls.return_value = temp_mgr

            await _run_image_album_pipeline(
                update,
                mock_context,
                file_ids=["a", "b"],
                user_id=99,
                correlation_id="corr1",
                status_message=status,
                chat_id=1,
            )

        assert noise.call_count == 2
        assert enhance.call_count == 2
        for call in enhance.call_args_list:
            assert call.args[2] == "equilibrado"
        for call in noise.call_args_list:
            assert call.args[2] == 2
        send_albums.assert_awaited_once()
        assert mock_context.user_data["image_menu_file_ids"] == ["sent1", "sent2"]
        assert "¡Listo!" in status.edit_text.await_args_list[-1].args[0]

    @pytest.mark.asyncio
    async def test_pipeline_rejects_single_image(self, mock_context):
        status = MagicMock()
        status.edit_text = AsyncMock()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=99),
            effective_chat=SimpleNamespace(id=1, type="private"),
            message=None,
            callback_query=None,
        )
        await _run_image_album_pipeline(
            update,
            mock_context,
            file_ids=["only-one"],
            user_id=99,
            correlation_id="corr1",
            status_message=status,
            chat_id=1,
        )
        assert "solo aplica a álbumes" in status.edit_text.await_args.args[0].lower()


class TestAlbumAutoBranchOnReceive:
    @pytest.mark.asyncio
    async def test_auto_on_runs_pipeline_for_album(
        self, mock_context, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        _set_album_auto_pipeline_enabled(99, True, mock_context.user_data)
        chat = SimpleNamespace(id=1, type="private")
        mock_context.application.user_data = {99: mock_context.user_data}
        status_msg = MagicMock()
        mock_context.application.bot.send_message = AsyncMock(return_value=status_msg)

        update = MagicMock()
        update.effective_user = SimpleNamespace(id=99)
        update.message = SimpleNamespace(
            media_group_id="mg-1",
            message_id=10,
            chat=chat,
        )

        sessions = mock_context.application.bot_data["image_batch_sessions"]
        sessions["1:mg-1"] = {
            "file_ids": ["p1"],
            "user_id": 99,
            "chat": chat,
            "correlation_id": "corr-auto",
            "last_message_id": 9,
            "debounce_task": None,
            "truncated": False,
        }

        async def noop_sleep(_):
            return None

        with patch("bot.handlers.asyncio.sleep", side_effect=noop_sleep), patch(
            "bot.handlers._run_image_album_pipeline", new_callable=AsyncMock
        ) as run_pipe, patch(
            "bot.handlers._send_image_menu_message", new_callable=AsyncMock
        ) as send_menu:
            await _schedule_image_batch_menu(update, mock_context, "p2")
            # Let the debounce task finish
            task = sessions.get("1:mg-1", {}).get("debounce_task")
            if task:
                await task

        run_pipe.assert_awaited_once()
        send_menu.assert_not_awaited()
        assert run_pipe.await_args.kwargs["file_ids"] == ["p1", "p2"]

    @pytest.mark.asyncio
    async def test_auto_off_shows_menu_for_album(
        self, mock_context, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        chat = SimpleNamespace(id=1, type="private")
        mock_context.application.user_data = {99: mock_context.user_data}

        update = MagicMock()
        update.effective_user = SimpleNamespace(id=99)
        update.message = SimpleNamespace(
            media_group_id="mg-2",
            message_id=10,
            chat=chat,
        )

        sessions = mock_context.application.bot_data["image_batch_sessions"]
        sessions["1:mg-2"] = {
            "file_ids": ["p1"],
            "user_id": 99,
            "chat": chat,
            "correlation_id": "corr-menu",
            "last_message_id": 9,
            "debounce_task": None,
            "truncated": False,
        }

        async def noop_sleep(_):
            return None

        with patch("bot.handlers.asyncio.sleep", side_effect=noop_sleep), patch(
            "bot.handlers._run_image_album_pipeline", new_callable=AsyncMock
        ) as run_pipe, patch(
            "bot.handlers._send_image_menu_message", new_callable=AsyncMock
        ) as send_menu:
            await _schedule_image_batch_menu(update, mock_context, "p2")
            task = sessions.get("1:mg-2", {}).get("debounce_task")
            if task:
                await task

        send_menu.assert_awaited_once()
        run_pipe.assert_not_awaited()


class TestImageMenuPipelineAction:
    @pytest.mark.asyncio
    async def test_menu_pipeline_action_runs_runner(self, mock_context):
        mock_context.user_data["image_menu_file_ids"] = ["a", "b", "c"]
        mock_context.user_data["image_menu_file_id"] = "a"
        mock_context.user_data["image_menu_correlation_id"] = "corr-m"

        update = MagicMock()
        update.effective_user = SimpleNamespace(id=99)
        update.callback_query = MagicMock()
        update.callback_query.data = "image_action:pipeline"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.message = MagicMock()
        update.callback_query.message.chat_id = 1

        with patch(
            "bot.handlers._run_image_album_pipeline", new_callable=AsyncMock
        ) as run_pipe:
            await handle_image_menu_callback(update, mock_context)

        run_pipe.assert_awaited_once()
        assert run_pipe.await_args.kwargs["file_ids"] == ["a", "b", "c"]
