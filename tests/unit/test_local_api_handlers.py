"""Tests for Local Bot API file handling helpers."""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bot.handlers import _media_input, _open_file_for_send, _split_file_if_needed


@pytest.fixture
def sample_video(tmp_path):
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"x" * 1024)
    return str(video_path)


def _mock_config(*, local_mode: bool, max_upload_bytes: int = 50 * 1024 * 1024):
    return SimpleNamespace(
        TELEGRAM_LOCAL_MODE=local_mode,
        telegram_max_upload_bytes=max_upload_bytes,
        TELEGRAM_MAX_UPLOAD_SIZE_MB=max_upload_bytes // (1024 * 1024),
        DOWNLOAD_MAX_SIZE_MB=500,
    )


class TestLocalApiHandlers:
    """Validate local-mode file send and split behavior."""

    def test_media_input_returns_path_in_local_mode(self, sample_video):
        with patch("bot.handlers.config", _mock_config(local_mode=True)):
            media = _media_input(sample_video)
        assert isinstance(media, Path)
        assert media == Path(os.path.abspath(sample_video))

    def test_media_input_returns_file_handle_in_cloud_mode(self, sample_video):
        with patch("bot.handlers.config", _mock_config(local_mode=False)):
            media = _media_input(sample_video)
        try:
            assert hasattr(media, "read")
        finally:
            media.close()

    def test_open_file_for_send_yields_path_in_local_mode(self, sample_video):
        with patch("bot.handlers.config", _mock_config(local_mode=True)):
            with _open_file_for_send(sample_video) as media:
                assert isinstance(media, Path)

    def test_split_skipped_in_local_mode_for_large_files(self, tmp_path):
        large_file = tmp_path / "large.mp4"
        large_file.write_bytes(b"x" * (60 * 1024 * 1024))

        with patch(
            "bot.handlers.config",
            _mock_config(local_mode=True, max_upload_bytes=50 * 1024 * 1024),
        ):
            parts = _split_file_if_needed(
                str(large_file),
                str(tmp_path / "split"),
                "test-id",
            )

        assert parts == [str(large_file)]