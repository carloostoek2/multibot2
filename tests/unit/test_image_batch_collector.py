"""Unit tests for image batch collector debounce and truncation."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import config
from bot.handlers import _schedule_image_batch_menu, _send_image_menu_message


def _update(chat_id=1, media_group_id="album-1", message_id=10, file_id="photo-1"):
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=99)
    update.message = SimpleNamespace(
        media_group_id=media_group_id,
        message_id=message_id,
        chat=SimpleNamespace(id=chat_id, type="private"),
    )
    return update


def _context(sessions=None):
    if sessions is None:
        sessions = {}
    context = MagicMock()
    context.application = MagicMock()
    context.application.bot_data = {"image_batch_sessions": sessions}
    context.application.bot.send_message = AsyncMock()
    context.application.user_data = {99: {}}
    return context


class TestImageBatchCollector:
    @pytest.mark.asyncio
    async def test_sets_truncated_flag_when_exceeding_limit(self):
        sessions = {
            f"1:album-1": {
                "file_ids": [f"id-{i}" for i in range(config.MAX_IMAGE_BATCH_SIZE)],
                "user_id": 99,
                "chat": SimpleNamespace(id=1, type="private"),
                "correlation_id": "corr-trunc",
                "last_message_id": 1,
                "debounce_task": None,
                "truncated": False,
            }
        }
        context = _context(sessions)
        update = _update(file_id="overflow-id")

        async def noop_sleep(_seconds):
            return None

        with patch("bot.handlers.asyncio.sleep", side_effect=noop_sleep):
            await _schedule_image_batch_menu(update, context, "overflow-id")

        session = sessions["1:album-1"]
        assert len(session["file_ids"]) == config.MAX_IMAGE_BATCH_SIZE
        assert session["truncated"] is True
        assert "overflow-id" not in session["file_ids"]

    @pytest.mark.asyncio
    async def test_cancelled_task_does_not_pop_session(self):
        sessions = {}
        context = _context(sessions)
        update = _update()
        release = asyncio.Event()

        async def gated_sleep(_seconds):
            await release.wait()

        with patch("bot.handlers.asyncio.sleep", side_effect=gated_sleep), patch(
            "bot.handlers._send_image_menu_message", new_callable=AsyncMock
        ):
            await _schedule_image_batch_menu(update, context, "photo-1")
            session_key = "1:album-1"
            first_task = sessions[session_key]["debounce_task"]

            await _schedule_image_batch_menu(update, context, "photo-2")
            with pytest.raises(asyncio.CancelledError):
                await first_task

            assert session_key in sessions
            release.set()
            second_task = sessions[session_key]["debounce_task"]
            await second_task
            assert session_key not in sessions

    @pytest.mark.asyncio
    async def test_active_task_pops_session_after_send(self):
        sessions = {}
        context = _context(sessions)
        update = _update()
        release = asyncio.Event()

        async def gated_sleep(_seconds):
            await release.wait()

        with patch("bot.handlers.asyncio.sleep", side_effect=gated_sleep), patch(
            "bot.handlers._send_image_menu_message", new_callable=AsyncMock
        ) as send_menu:
            await _schedule_image_batch_menu(update, context, "photo-1")
            session_key = "1:album-1"
            task = sessions[session_key]["debounce_task"]
            release.set()
            await task

        send_menu.assert_awaited_once()
        assert session_key not in sessions

    @pytest.mark.asyncio
    async def test_active_task_pops_session_on_send_failure(self):
        sessions = {}
        context = _context(sessions)
        update = _update()
        release = asyncio.Event()

        async def gated_sleep(_seconds):
            await release.wait()

        with patch("bot.handlers.asyncio.sleep", side_effect=gated_sleep), patch(
            "bot.handlers._send_image_menu_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("send failed"),
        ):
            await _schedule_image_batch_menu(update, context, "photo-1")
            session_key = "1:album-1"
            task = sessions[session_key]["debounce_task"]
            release.set()
            await task

        assert session_key not in sessions

    @pytest.mark.asyncio
    async def test_send_image_menu_message_includes_truncation_warning(self):
        application = MagicMock()
        application.bot.send_message = AsyncMock()
        application.user_data = {99: {}}
        chat = SimpleNamespace(id=1, type="private")

        await _send_image_menu_message(
            application,
            chat,
            99,
            ["f1", "f2"],
            "corr-trunc",
            truncated=True,
        )

        text = application.bot.send_message.await_args.kwargs["text"]
        assert "⚠️ Solo se procesarán las primeras" in text
        assert str(config.MAX_IMAGE_BATCH_SIZE) in text
        assert application.user_data[99]["image_menu_truncated"] is True

    @pytest.mark.asyncio
    async def test_schedule_single_image_sends_immediate_menu(self):
        context = _context()
        update = _update(media_group_id=None)

        with patch(
            "bot.handlers._send_image_menu_message", new_callable=AsyncMock
        ) as send_menu:
            await _schedule_image_batch_menu(update, context, "single-photo")

        send_menu.assert_awaited_once()
        file_ids = send_menu.await_args[0][3]
        assert file_ids == ["single-photo"]
        assert send_menu.await_args.kwargs["reply_to_message_id"] == update.message.message_id

    @pytest.mark.asyncio
    async def test_rapid_schedules_coalesce_into_one_menu_call(self):
        sessions = {}
        context = _context(sessions)
        update = _update()

        with patch("bot.handlers.IMAGE_BATCH_DEBOUNCE_SECONDS", 0), patch(
            "bot.handlers._send_image_menu_message", new_callable=AsyncMock
        ) as send_menu:
            await _schedule_image_batch_menu(update, context, "photo-1")
            await _schedule_image_batch_menu(update, context, "photo-2")
            await _schedule_image_batch_menu(update, context, "photo-3")

            task = sessions["1:album-1"]["debounce_task"]
            await task

        send_menu.assert_awaited_once()
        file_ids = send_menu.await_args[0][3]
        assert file_ids == ["photo-1", "photo-2", "photo-3"]