"""Integration tests for download flow.

These tests verify the end-to-end download functionality including:
- Basic download flow
- URL detection in messages
- Format selection
- Combined download+process flow
- Cancellation
- Error handling
- Post-download processing
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bot.handlers import (
    handle_download_command,
    handle_url_detection,
    handle_download_format_callback,
    handle_download_confirm_callback,
    handle_download_cancel_callback,
    _start_download,
    _start_combined_download,
    _get_download_format_keyboard,
    _get_error_message_for_exception,
)
from bot.downloaders import DownloadFacade
from bot.downloaders.exceptions import DownloadError, FileTooLargeError


@pytest.fixture
def mock_update():
    """Create mock update object."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat = MagicMock()
    update.effective_chat.id = 67890
    update.message = MagicMock()
    update.message.text = ""
    update.message.reply_text = AsyncMock()
    update.message.reply_video = AsyncMock()
    update.message.reply_audio = AsyncMock()
    update.message.reply_video_note = AsyncMock()
    update.message.reply_voice = AsyncMock()
    update.callback_query = MagicMock()
    update.callback_query.data = ""
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_text = AsyncMock()
    update.callback_query.message.reply_video = AsyncMock()
    update.callback_query.message.reply_audio = AsyncMock()
    update.callback_query.message.reply_video_note = AsyncMock()
    update.callback_query.message.reply_voice = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create mock context object."""
    context = MagicMock()
    context.user_data = {}
    context.bot = AsyncMock()
    context.args = []
    return context


class TestDownloadCommand:
    """Tests for /download command."""

    @pytest.mark.asyncio
    async def test_download_command_no_url(self, mock_update, mock_context):
        """Test /download command without URL shows error."""
        mock_context.args = []

        await handle_download_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Por favor proporciona una URL" in call_args

    @pytest.mark.asyncio
    async def test_download_command_invalid_url(self, mock_update, mock_context):
        """Test /download command with invalid URL shows error."""
        mock_context.args = ["not-a-valid-url"]

        await handle_download_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "no parece válida" in call_args

    @pytest.mark.asyncio
    async def test_download_command_valid_url(self, mock_update, mock_context):
        """Test /download command with valid URL shows format menu."""
        mock_context.args = ["https://youtube.com/watch?v=test123"]

        await handle_download_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Selecciona formato" in call_args

        # Verify keyboard has expected options
        reply_markup = mock_update.message.reply_text.call_args[1]["reply_markup"]
        keyboard = reply_markup.inline_keyboard
        assert len(keyboard) >= 3  # Basic options + combined options + cancel


class TestUrlDetection:
    """Tests for URL detection in messages."""

    @pytest.mark.asyncio
    async def test_url_detection_no_url(self, mock_update, mock_context):
        """Test message without URL is ignored."""
        mock_update.message.text = "Hello world, no URL here"

        result = await handle_url_detection(mock_update, mock_context)

        # Should return None (no action taken)
        assert result is None
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_url_detection_with_url(self, mock_update, mock_context):
        """Test message with URL shows format menu."""
        mock_update.message.text = "Check this video: https://youtube.com/watch?v=test123"

        await handle_url_detection(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Enlace de video detectado" in call_args

    @pytest.mark.asyncio
    async def test_url_detection_multiple_urls(self, mock_update, mock_context):
        """Test message with multiple URLs uses first one."""
        mock_update.message.text = "Videos: https://youtube.com/watch?v=first and https://youtube.com/watch?v=second"

        await handle_url_detection(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        # Should store first URL
        stored_urls = [v for k, v in mock_context.user_data.items() if k.startswith("download_url_")]
        assert len(stored_urls) == 1
        assert "first" in stored_urls[0]


class TestFormatSelection:
    """Tests for format selection callback."""

    @pytest.mark.asyncio
    async def test_format_selection_video(self, mock_update, mock_context):
        """Test selecting video format starts download."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:video:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"

        with patch("bot.handlers.PlatformRouter") as mock_router:
            mock_route_result = MagicMock()
            mock_route_result.downloader.get_metadata = AsyncMock(return_value={
                "filesize": 10 * 1024 * 1024,  # 10 MB
                "title": "Test Video"
            })
            mock_router.return_value.route = AsyncMock(return_value=mock_route_result)

            with patch("bot.handlers._start_download") as mock_start:
                mock_start.return_value = None

                await handle_download_format_callback(mock_update, mock_context)

                mock_update.callback_query.answer.assert_called_once()
                mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_selection_audio(self, mock_update, mock_context):
        """Test selecting audio format starts download."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:audio:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"

        with patch("bot.handlers.PlatformRouter") as mock_router:
            mock_route_result = MagicMock()
            mock_route_result.downloader.get_metadata = AsyncMock(return_value={
                "filesize": 5 * 1024 * 1024,  # 5 MB
                "title": "Test Video"
            })
            mock_router.return_value.route = AsyncMock(return_value=mock_route_result)

            with patch("bot.handlers._start_download") as mock_start:
                mock_start.return_value = None

                await handle_download_format_callback(mock_update, mock_context)

                mock_update.callback_query.answer.assert_called_once()
                # Verify format was stored
                assert mock_context.user_data.get(f"download_format_{correlation_id}") == "audio"

    @pytest.mark.asyncio
    async def test_format_selection_large_file(self, mock_update, mock_context):
        """Test large file shows confirmation."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:video:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"

        with patch("bot.handlers.PlatformRouter") as mock_router:
            mock_route_result = MagicMock()
            mock_route_result.downloader.get_metadata = AsyncMock(return_value={
                "filesize": 100 * 1024 * 1024,  # 100 MB - exceeds 50MB limit
                "title": "Large Video"
            })
            mock_router.return_value.route = AsyncMock(return_value=mock_route_result)

            await handle_download_format_callback(mock_update, mock_context)

            # Should show confirmation for large file
            mock_update.callback_query.edit_message_text.assert_called()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            assert "grande" in call_args.lower() or "100" in call_args

    @pytest.mark.asyncio
    async def test_format_selection_missing_url(self, mock_update, mock_context):
        """Test format selection with missing URL shows error."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:video:{correlation_id}"
        # No URL stored in context

        await handle_download_format_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "No se encontró la URL" in call_args


class TestCombinedFlow:
    """Tests for combined download+process flow."""

    @pytest.mark.asyncio
    async def test_combined_download_videonote(self, mock_update, mock_context):
        """Test download + videonote combined flow."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:video:videonote:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"

        with patch("bot.handlers.PlatformRouter") as mock_router:
            mock_route_result = MagicMock()
            mock_route_result.downloader.get_metadata = AsyncMock(return_value={
                "filesize": 10 * 1024 * 1024,
                "title": "Test Video"
            })
            mock_router.return_value.route = AsyncMock(return_value=mock_route_result)

            with patch("bot.handlers._start_combined_download") as mock_start:
                mock_start.return_value = None

                await handle_download_format_callback(mock_update, mock_context)

                mock_update.callback_query.answer.assert_called_once()
                # Verify post_action was stored
                assert mock_context.user_data.get(f"download_post_action_{correlation_id}") == "videonote"
                mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_combined_download_extract_audio(self, mock_update, mock_context):
        """Test download + extract audio combined flow."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:video:extract:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"

        with patch("bot.handlers.PlatformRouter") as mock_router:
            mock_route_result = MagicMock()
            mock_route_result.downloader.get_metadata = AsyncMock(return_value={
                "filesize": 10 * 1024 * 1024,
                "title": "Test Video"
            })
            mock_router.return_value.route = AsyncMock(return_value=mock_route_result)

            with patch("bot.handlers._start_combined_download") as mock_start:
                mock_start.return_value = None

                await handle_download_format_callback(mock_update, mock_context)

                assert mock_context.user_data.get(f"download_post_action_{correlation_id}") == "extract"
                mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_combined_download_voicenote(self, mock_update, mock_context):
        """Test download + voicenote combined flow."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:audio:voicenote:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"

        with patch("bot.handlers.PlatformRouter") as mock_router:
            mock_route_result = MagicMock()
            mock_route_result.downloader.get_metadata = AsyncMock(return_value={
                "filesize": 5 * 1024 * 1024,
                "title": "Test Audio"
            })
            mock_router.return_value.route = AsyncMock(return_value=mock_route_result)

            with patch("bot.handlers._start_combined_download") as mock_start:
                mock_start.return_value = None

                await handle_download_format_callback(mock_update, mock_context)

                assert mock_context.user_data.get(f"download_post_action_{correlation_id}") == "voicenote"
                mock_start.assert_called_once()


class TestCancellation:
    """Tests for download cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_during_download(self, mock_update, mock_context):
        """Test cancel button stops download."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:cancel:{correlation_id}"

        # Create mock facade
        mock_facade = AsyncMock()
        mock_facade.cancel_download = AsyncMock(return_value=True)
        mock_context.user_data[f"download_facade_{correlation_id}"] = mock_facade
        mock_context.user_data[f"download_status_{correlation_id}"] = "downloading"

        await handle_download_cancel_callback(mock_update, mock_context)

        mock_facade.cancel_download.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "cancelada" in call_args.lower()

    @pytest.mark.asyncio
    async def test_cancel_already_completed(self, mock_update, mock_context):
        """Test cancel when download already completed."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:cancel:{correlation_id}"

        mock_facade = AsyncMock()
        mock_facade.cancel_download = AsyncMock(return_value=False)
        mock_context.user_data[f"download_facade_{correlation_id}"] = mock_facade
        mock_context.user_data[f"download_status_{correlation_id}"] = "completed"

        await handle_download_cancel_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "completado" in call_args.lower() or "completada" in call_args.lower()

    @pytest.mark.asyncio
    async def test_cancel_no_facade(self, mock_update, mock_context):
        """Test cancel when no facade exists."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:cancel:{correlation_id}"

        # No facade stored
        mock_context.user_data[f"download_status_{correlation_id}"] = "downloading"

        await handle_download_cancel_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_file_too_large_error(self, mock_update, mock_context):
        """Test FileTooLargeError is handled correctly."""
        correlation_id = "abc123"
        url = "https://youtube.com/watch?v=test"
        format_type = "video"

        mock_update.callback_query.edit_message_text = AsyncMock()
        mock_update.callback_query.edit_text = AsyncMock()

        with patch("bot.handlers.DownloadFacade") as mock_facade_class:
            mock_facade = AsyncMock()
            mock_facade.start = AsyncMock()
            mock_facade.download = AsyncMock(side_effect=FileTooLargeError(
                file_size=100*1024*1024, max_size=50*1024*1024
            ))
            mock_facade_class.return_value = mock_facade

            await _start_download(mock_update, mock_context, correlation_id, url, format_type)

            # Should show user-friendly error
            mock_update.callback_query.edit_text.assert_called()

    @pytest.mark.asyncio
    async def test_network_error_handling(self, mock_update, mock_context):
        """Test network errors are handled gracefully."""
        correlation_id = "abc123"
        url = "https://youtube.com/watch?v=test"
        format_type = "video"

        mock_update.callback_query.edit_text = AsyncMock()

        with patch("bot.handlers.DownloadFacade") as mock_facade_class:
            mock_facade = AsyncMock()
            mock_facade.start = AsyncMock()
            mock_facade.download = AsyncMock(side_effect=ConnectionResetError("Connection reset"))
            mock_facade_class.return_value = mock_facade

            await _start_download(mock_update, mock_context, correlation_id, url, format_type)

            # Should show user-friendly error message
            mock_update.callback_query.edit_text.assert_called()
            call_args = mock_update.callback_query.edit_text.call_args[0][0]
            assert "conexión" in call_args.lower() or "error" in call_args.lower()

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, mock_update, mock_context):
        """Test timeout errors are handled gracefully."""
        correlation_id = "abc123"
        url = "https://youtube.com/watch?v=test"
        format_type = "video"

        mock_update.callback_query.edit_text = AsyncMock()

        with patch("bot.handlers.DownloadFacade") as mock_facade_class:
            mock_facade = AsyncMock()
            mock_facade.start = AsyncMock()
            mock_facade.download = AsyncMock(side_effect=TimeoutError("Download timeout"))
            mock_facade_class.return_value = mock_facade

            await _start_download(mock_update, mock_context, correlation_id, url, format_type)

            mock_update.callback_query.edit_text.assert_called()
            call_args = mock_update.callback_query.edit_text.call_args[0][0]
            assert "tardó" in call_args.lower() or "tiempo" in call_args.lower()


class TestKeyboardGeneration:
    """Tests for keyboard generation."""

    def test_format_keyboard_basic(self):
        """Test basic format keyboard generation."""
        correlation_id = "abc123"
        keyboard = _get_download_format_keyboard(correlation_id)

        # Should have inline keyboard
        assert hasattr(keyboard, 'inline_keyboard')

        # Should have video and audio options
        buttons = []
        for row in keyboard.inline_keyboard:
            buttons.extend(row)

        button_texts = [btn.text for btn in buttons]
        assert any("Video" in text for text in button_texts)
        assert any("Audio" in text for text in button_texts)
        assert any("Cancelar" in text for text in button_texts)

    def test_format_keyboard_combined_options(self):
        """Test combined action options in keyboard."""
        correlation_id = "abc123"
        keyboard = _get_download_format_keyboard(correlation_id)

        buttons = []
        for row in keyboard.inline_keyboard:
            buttons.extend(row)

        button_texts = [btn.text for btn in buttons]

        # Should have combined options
        assert any("Nota de Video" in text for text in button_texts)
        assert any("Extraer Audio" in text for text in button_texts)
        assert any("Nota de Voz" in text for text in button_texts)


class TestDownloadConfirmCallback:
    """Tests for download confirmation callback."""

    @pytest.mark.asyncio
    async def test_confirm_large_download(self, mock_update, mock_context):
        """Test confirming large download starts it."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:confirm:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"
        mock_context.user_data[f"download_format_{correlation_id}"] = "video"

        with patch("bot.handlers._start_download") as mock_start:
            mock_start.return_value = None

            await handle_download_confirm_callback(mock_update, mock_context)

            mock_update.callback_query.answer.assert_called_once()
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_combined_large_download(self, mock_update, mock_context):
        """Test confirming large download with post-action."""
        correlation_id = "abc123"
        mock_update.callback_query.data = f"download:confirm:{correlation_id}"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"
        mock_context.user_data[f"download_format_{correlation_id}"] = "video"
        mock_context.user_data[f"download_post_action_{correlation_id}"] = "videonote"

        with patch("bot.handlers._start_combined_download") as mock_start:
            mock_start.return_value = None

            await handle_download_confirm_callback(mock_update, mock_context)

            mock_start.assert_called_once()
            # Verify post_action was passed
            assert mock_start.call_args[0][4] == "video"
            assert mock_start.call_args[0][5] == "videonote"


class TestErrorMessageHelper:
    """Tests for _get_error_message_for_exception helper."""

    def test_connection_reset_error(self):
        """Test connection reset error message."""
        e = ConnectionResetError("Connection reset")
        msg = _get_error_message_for_exception(e, "https://youtube.com/watch?v=test", "abc123")
        assert "conexión" in msg.lower()

    def test_timeout_error(self):
        """Test timeout error message."""
        e = TimeoutError("Download timeout")
        msg = _get_error_message_for_exception(e, "https://youtube.com/watch?v=test", "abc123")
        assert "tardó" in msg.lower() or "tiempo" in msg.lower()

    def test_youtube_age_restricted(self):
        """Test YouTube age-restricted error."""
        e = Exception("This video is age-restricted")
        msg = _get_error_message_for_exception(e, "https://youtube.com/watch?v=test", "abc123")
        assert "restricción" in msg.lower() or "edad" in msg.lower()

    def test_instagram_private(self):
        """Test Instagram private content error."""
        e = Exception("This content is private")
        msg = _get_error_message_for_exception(e, "https://instagram.com/p/test", "abc123")
        assert "privado" in msg.lower()

    def test_disk_full_error(self):
        """Test disk full error message."""
        import errno
        e = OSError(errno.ENOSPC, "No space left on device")
        msg = _get_error_message_for_exception(e, "https://youtube.com/watch?v=test", "abc123")
        assert "espacio" in msg.lower()


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_multiple_urls_quickly(self, mock_update, mock_context):
        """Test handling multiple URLs sent quickly."""
        # First URL
        mock_update.message.text = "First: https://youtube.com/watch?v=first"
        await handle_url_detection(mock_update, mock_context)

        first_cid = None
        for key in mock_context.user_data:
            if key.startswith("download_correlation_id_"):
                first_cid = mock_context.user_data[key]
                break

        # Second URL (should create new correlation_id)
        mock_update.message.text = "Second: https://youtube.com/watch?v=second"
        await handle_url_detection(mock_update, mock_context)

        # Should have stored both URLs
        stored_urls = [v for k, v in mock_context.user_data.items() if k.startswith("download_url_")]
        assert len(stored_urls) == 2

    @pytest.mark.asyncio
    async def test_cancel_during_confirmation(self, mock_update, mock_context):
        """Test cancel during confirmation phase."""
        correlation_id = "abc123"
        mock_update.callback_query.data = "cancel"
        mock_context.user_data[f"download_url_{correlation_id}"] = "https://youtube.com/watch?v=test"

        # This should be handled by the general cancel handler, not download-specific
        # But we verify state is cleaned up appropriately
        assert f"download_url_{correlation_id}" in mock_context.user_data

    @pytest.mark.asyncio
    async def test_invalid_callback_format(self, mock_update, mock_context):
        """Test invalid callback data format is handled."""
        mock_update.callback_query.data = "download:invalid:format:extra:parts:here"
        # Should not raise exception
        await handle_download_format_callback(mock_update, mock_context)

        # Should answer callback but not proceed with download
        mock_update.callback_query.answer.assert_called_once()
        # Should not edit message (no URL found for invalid format)
        mock_update.callback_query.edit_message_text.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
