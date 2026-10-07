"""Unit tests for minute:second input in the split (cut) handlers.

The handlers used to read the cut point with ``float(message.text)``, so only
bare seconds worked. They now share ``parse_time_value``, which also accepts
``M:SS`` and ``M:SS.d``.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from bot.handlers import (
    SPLIT_WAITING_END_TIME,
    SPLIT_WAITING_START_TIME,
    handle_audio_split_end_time,
    handle_audio_split_start_time,
    handle_video_split_end_time,
    handle_video_split_start_time,
)


def _text_update(text):
    """Build a text-message update, mirroring tests/unit/test_image_group.py."""
    reply_text = AsyncMock()
    # The end-time handlers await processing_message.delete().
    reply_text.return_value.delete = AsyncMock()

    update = MagicMock()
    update.effective_user = SimpleNamespace(id=42)
    update.message = SimpleNamespace(
        text=text,
        reply_text=reply_text,
        reply_video=AsyncMock(),
        reply_audio=AsyncMock(),
    )
    return update


def _context(session_key, **session):
    context = MagicMock()
    context.user_data = {session_key: session}
    return context


def _video_session(**overrides):
    session = {
        "type": "video",
        "correlation_id": "corr",
        "state": SPLIT_WAITING_START_TIME,
        "duration": 300.0,
    }
    session.update(overrides)
    return _context("split_video_session", **session)


def _audio_session(**overrides):
    session = {
        "correlation_id": "corr",
        "state": SPLIT_WAITING_START_TIME,
        "duration": 300.0,
    }
    session.update(overrides)
    return _context("split_audio_session", **session)


class TestVideoSplitStartTime:
    @pytest.mark.asyncio
    async def test_minutes_and_seconds_are_stored_as_seconds(self):
        context = _video_session()
        update = _text_update("1:24")

        await handle_video_split_start_time(update, context)

        session = context.user_data["split_video_session"]
        assert session["start_time"] == 84.0
        assert session["state"] == SPLIT_WAITING_END_TIME

    @pytest.mark.asyncio
    async def test_tenths_are_kept(self):
        context = _video_session()
        update = _text_update("2:34.5")

        await handle_video_split_start_time(update, context)

        assert context.user_data["split_video_session"]["start_time"] == 154.5

    @pytest.mark.asyncio
    async def test_plain_seconds_still_work(self):
        context = _video_session()
        update = _text_update("30.5")

        await handle_video_split_start_time(update, context)

        assert context.user_data["split_video_session"]["start_time"] == 30.5

    @pytest.mark.asyncio
    async def test_invalid_input_does_not_advance_state(self):
        context = _video_session()
        update = _text_update("abc")

        await handle_video_split_start_time(update, context)

        session = context.user_data["split_video_session"]
        assert "start_time" not in session
        assert session["state"] == SPLIT_WAITING_START_TIME
        text = update.message.reply_text.await_args[0][0]
        assert "abc" in text
        assert "1:24" in text  # the accepted formats are explained back

    @pytest.mark.asyncio
    async def test_start_time_beyond_duration_is_rejected(self):
        context = _video_session()
        update = _text_update("10:00")

        await handle_video_split_start_time(update, context)

        session = context.user_data["split_video_session"]
        assert "start_time" not in session
        assert session["state"] == SPLIT_WAITING_START_TIME
        assert "duración del video" in update.message.reply_text.await_args[0][0]


class TestVideoSplitEndTime:
    @pytest.mark.asyncio
    async def test_cut_uses_the_parsed_minutes_and_seconds(self, tmp_path):
        context = _video_session(
            state=SPLIT_WAITING_END_TIME,
            start_time=84.0,
            input_path=str(tmp_path / "in.mp4"),
        )
        update = _text_update("2:10.5")

        temp_mgr = MagicMock()
        temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
        temp_mgr.__exit__ = MagicMock(return_value=False)
        temp_mgr.get_temp_path.side_effect = lambda name: str(tmp_path / name)

        with patch("bot.handlers.TempManager", return_value=temp_mgr), patch(
            "bot.handlers.VideoSplitter"
        ) as splitter_cls, patch("builtins.open", mock_open(read_data=b"mp4")):
            await handle_video_split_end_time(update, context)

        splitter_cls.return_value.split_by_time_range.assert_called_once_with(84.0, 130.5)

    @pytest.mark.asyncio
    async def test_end_before_start_is_rejected(self):
        context = _video_session(
            state=SPLIT_WAITING_END_TIME, start_time=200.0
        )
        update = _text_update("1:00")

        await handle_video_split_end_time(update, context)

        session = context.user_data["split_video_session"]
        assert "end_time" not in session
        assert session["state"] == SPLIT_WAITING_END_TIME
        assert "mayor al tiempo de inicio" in update.message.reply_text.await_args[0][0]

    @pytest.mark.asyncio
    async def test_invalid_input_does_not_advance_state(self):
        context = _video_session(state=SPLIT_WAITING_END_TIME, start_time=84.0)
        update = _text_update("1:60")

        await handle_video_split_end_time(update, context)

        session = context.user_data["split_video_session"]
        assert "end_time" not in session
        assert session["state"] == SPLIT_WAITING_END_TIME
        assert "menores a 60" in update.message.reply_text.await_args[0][0]


class TestAudioSplitStartTime:
    @pytest.mark.asyncio
    async def test_minutes_and_seconds_are_stored_as_seconds(self):
        context = _audio_session()
        update = _text_update("2:34.5")

        await handle_audio_split_start_time(update, context)

        session = context.user_data["split_audio_session"]
        assert session["start_time"] == 154.5
        assert session["state"] == SPLIT_WAITING_END_TIME

    @pytest.mark.asyncio
    async def test_invalid_input_does_not_advance_state(self):
        context = _audio_session()
        update = _text_update("1:2:3")

        await handle_audio_split_start_time(update, context)

        session = context.user_data["split_audio_session"]
        assert "start_time" not in session
        assert session["state"] == SPLIT_WAITING_START_TIME
        assert "Formato inválido" in update.message.reply_text.await_args[0][0]


class TestAudioSplitEndTime:
    @pytest.mark.asyncio
    async def test_cut_uses_the_parsed_minutes_and_seconds(self, tmp_path):
        context = _audio_session(
            state=SPLIT_WAITING_END_TIME,
            start_time=5.0,
            input_path=str(tmp_path / "in.mp3"),
        )
        update = _text_update("1:30")

        temp_mgr = MagicMock()
        temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
        temp_mgr.__exit__ = MagicMock(return_value=False)
        temp_mgr.get_temp_path.side_effect = lambda name: str(tmp_path / name)

        with patch("bot.handlers.TempManager", return_value=temp_mgr), patch(
            "bot.handlers.AudioSplitter"
        ) as splitter_cls, patch("builtins.open", mock_open(read_data=b"mp3")):
            await handle_audio_split_end_time(update, context)

        splitter_cls.return_value.split_by_time_range.assert_called_once_with(5.0, 90.0)
