"""Unit tests for handle_audio_document routing and menu flow."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import (
    handle_audio_document,
    handle_join_audio_file,
    handle_merge_audio_received,
)


def _document(file_id="doc-mp3", file_size=1024):
    return SimpleNamespace(
        file_name="song.mp3",
        mime_type="application/octet-stream",
        file_id=file_id,
        file_size=file_size,
        file_unique_id="uniq-doc",
    )


@pytest.fixture
def mock_update():
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=12345)
    update.message = MagicMock()
    update.message.document = _document()
    update.message.audio = None
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    return context


class TestHandleAudioDocumentRouting:
    @pytest.mark.asyncio
    async def test_routes_to_join_session(self, mock_update, mock_context):
        mock_context.user_data["join_audio_session"] = {"audios": []}

        with patch("bot.handlers.handle_join_audio_file", new_callable=AsyncMock) as join_mock:
            await handle_audio_document(mock_update, mock_context)

        join_mock.assert_awaited_once_with(mock_update, mock_context)
        mock_update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_routes_to_merge_session(self, mock_update, mock_context):
        mock_context.user_data["merge_video_file_id"] = "video-id"

        with patch("bot.handlers.handle_merge_audio_received", new_callable=AsyncMock) as merge_mock:
            await handle_audio_document(mock_update, mock_context)

        merge_mock.assert_awaited_once_with(mock_update, mock_context)

    @pytest.mark.asyncio
    async def test_shows_menu_for_valid_document(self, mock_update, mock_context):
        await handle_audio_document(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert mock_context.user_data["audio_menu_file_id"] == "doc-mp3"
        assert "audio_menu_correlation_id" in mock_context.user_data

    @pytest.mark.asyncio
    async def test_rejects_oversized_document(self, mock_update, mock_context):
        mock_update.message.document = _document(file_size=50 * 1024 * 1024)

        await handle_audio_document(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "audio_menu_file_id" not in mock_context.user_data

    @pytest.mark.asyncio
    async def test_ignores_non_audio_document(self, mock_update, mock_context):
        mock_update.message.document = SimpleNamespace(
            file_name="readme.pdf",
            mime_type="application/pdf",
            file_id="pdf-id",
            file_size=100,
            file_unique_id="uniq-pdf",
        )

        await handle_audio_document(mock_update, mock_context)

        mock_update.message.reply_text.assert_not_awaited()


class TestMergeJoinWithDocument:
    @pytest.mark.asyncio
    async def test_merge_uses_document_file_id(self, mock_context, tmp_path):
        video_path = tmp_path / "video.mp4"
        audio_path = tmp_path / "audio.mp3"
        output_path = tmp_path / "merged.mp4"
        video_path.write_bytes(b"video")
        audio_path.write_bytes(b"audio")

        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=12345),
            effective_message=SimpleNamespace(reply_text=AsyncMock()),
            message=SimpleNamespace(
                audio=None,
                document=_document(file_id="merge-doc-id"),
                reply_text=AsyncMock(),
                reply_video=AsyncMock(),
            ),
        )
        mock_context.user_data["merge_video_file_id"] = "video-id"
        mock_context.user_data["merge_video_correlation_id"] = "corr1"

        download_file = MagicMock()
        download_file.download_to_drive = AsyncMock(return_value=None)
        mock_context.bot.get_file = AsyncMock(return_value=download_file)

        with patch("bot.handlers.TempManager") as temp_mgr_cls, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.validate_video_file", return_value=(True, None)
        ), patch(
            "bot.handlers.validate_audio_file", return_value=(True, None)
        ), patch(
            "bot.handlers.check_disk_space", return_value=(True, None)
        ), patch(
            "bot.handlers.estimate_required_space", return_value=10
        ), patch(
            "bot.handlers.VideoAudioMerger"
        ) as merger_cls, patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock:
            temp_mgr = MagicMock()
            temp_mgr.__enter__ = MagicMock(return_value=temp_mgr)
            temp_mgr.__exit__ = MagicMock(return_value=False)
            def resolve_path(name):
                if name.startswith("merge_video"):
                    return str(video_path)
                if name.startswith("merge_audio"):
                    return str(audio_path)
                if name.startswith("merged"):
                    return str(output_path)
                return str(tmp_path / name)

            temp_mgr.get_temp_path.side_effect = resolve_path
            temp_mgr_cls.return_value = temp_mgr

            merger = MagicMock()
            merger.merge.return_value = True
            merger_cls.return_value = merger

            loop = MagicMock()
            loop.run_in_executor = AsyncMock(return_value=True)
            loop_mock.return_value = loop

            output_path.write_bytes(b"merged")
            with patch("builtins.open", MagicMock()):
                await handle_merge_audio_received(update, mock_context)

        mock_context.bot.get_file.assert_any_await("merge-doc-id")

    @pytest.mark.asyncio
    async def test_join_downloads_document_file_id(self, mock_update, mock_context):
        mock_update.message = SimpleNamespace(
            audio=None,
            document=_document(file_id="join-doc-id"),
            reply_text=AsyncMock(),
        )

        temp_mgr = MagicMock()
        temp_mgr.get_temp_path.return_value = "/tmp/join_audio.mp3"
        temp_mgr.track_file = MagicMock()

        session = {
            "audios": [],
            "temp_mgr": temp_mgr,
            "last_activity": 0,
        }
        mock_context.user_data["join_audio_session"] = session

        mock_context.bot.get_file = AsyncMock(return_value=MagicMock())

        with patch("bot.handlers.config") as cfg, patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock, patch(
            "bot.handlers._download_with_retry", new_callable=AsyncMock
        ), patch(
            "bot.handlers.validate_audio_file", return_value=(True, None)
        ):
            cfg.JOIN_SESSION_TIMEOUT = 3600
            cfg.JOIN_MAX_AUDIO_FILES = 20
            cfg.MAX_AUDIO_FILE_SIZE_MB = 20
            loop = MagicMock()
            loop.time.return_value = 100
            loop_mock.return_value = loop

            await handle_join_audio_file(mock_update, mock_context)

        mock_context.bot.get_file.assert_awaited_once_with("join-doc-id")
        assert len(session["audios"]) == 1

    @pytest.mark.asyncio
    async def test_join_rejects_non_audio_document(self, mock_update, mock_context):
        mock_update.message = SimpleNamespace(
            audio=None,
            document=SimpleNamespace(
                file_name="readme.pdf",
                mime_type="application/pdf",
                file_id="pdf-id",
                file_size=100,
                file_unique_id="uniq-pdf",
            ),
            reply_text=AsyncMock(),
        )
        temp_mgr = MagicMock()
        session = {
            "audios": [],
            "temp_mgr": temp_mgr,
            "last_activity": 0,
        }
        mock_context.user_data["join_audio_session"] = session

        with patch("bot.handlers.config") as cfg, patch(
            "bot.handlers.asyncio.get_event_loop"
        ) as loop_mock:
            cfg.JOIN_SESSION_TIMEOUT = 3600
            cfg.JOIN_MAX_AUDIO_FILES = 20
            loop = MagicMock()
            loop.time.return_value = 100
            loop_mock.return_value = loop

            await handle_join_audio_file(mock_update, mock_context)

        mock_update.message.reply_text.assert_awaited_once()
        assert "audio válido" in mock_update.message.reply_text.await_args[0][0]
        assert len(session["audios"]) == 0

    @pytest.mark.asyncio
    async def test_merge_rejects_non_audio_document(self, mock_context):
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=12345),
            message=SimpleNamespace(
                audio=None,
                document=SimpleNamespace(
                    file_name="notes.txt",
                    mime_type="text/plain",
                    file_id="txt-id",
                    file_size=50,
                    file_unique_id="uniq-txt",
                ),
                reply_text=AsyncMock(),
            ),
        )
        mock_context.user_data["merge_video_file_id"] = "video-id"
        mock_context.user_data["merge_video_correlation_id"] = "corr1"

        await handle_merge_audio_received(update, mock_context)

        update.message.reply_text.assert_awaited_once()
        assert "audio" in update.message.reply_text.await_args[0][0].lower()
        assert "merge_video_file_id" not in mock_context.user_data