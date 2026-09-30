"""Unit tests for image-batch disk preflight budgeting and TEMP_DIR."""
import os
from unittest.mock import MagicMock, patch

import pytest

from bot.temp_manager import work_temp_root
from bot.validators import (
    IMAGE_BATCH_PER_FILE_MB,
    check_disk_space,
    estimate_image_batch_space,
)


class TestEstimateImageBatchSpace:
    def test_default_copies_is_two(self):
        assert estimate_image_batch_space(5) == 5 * IMAGE_BATCH_PER_FILE_MB * 2

    def test_pipeline_uses_three_copies(self):
        # Album pipeline previously used count * max_incoming (2000) * 3
        # and false-failed; budget is now ~100MB per file per copy.
        assert estimate_image_batch_space(5, copies=3) == 5 * 100 * 3
        assert estimate_image_batch_space(5, copies=3) == 1500

    def test_enhance_noise_uses_two_copies(self):
        assert estimate_image_batch_space(3, copies=2) == 600

    def test_floors_count_and_copies_at_one(self):
        assert estimate_image_batch_space(0, copies=0) == IMAGE_BATCH_PER_FILE_MB
        assert estimate_image_batch_space(-2, copies=-1) == IMAGE_BATCH_PER_FILE_MB

    def test_much_smaller_than_local_api_cap_budget(self):
        local_api_cap_budget = 5 * 2000 * 3  # old formula
        assert estimate_image_batch_space(5, copies=3) < local_api_cap_budget
        assert estimate_image_batch_space(5, copies=3) == local_api_cap_budget // 20


class TestCheckDiskSpaceTempDir:
    def test_defaults_to_temp_dir_when_set_and_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEMP_DIR", str(tmp_path))
        fake_stat = MagicMock()
        fake_stat.f_frsize = 1024
        fake_stat.f_bavail = 50 * 1024  # 50 MiB

        with patch("bot.validators.os.statvfs", return_value=fake_stat) as statvfs:
            ok, err = check_disk_space(10)
            assert ok is True
            assert err is None
            statvfs.assert_called_once_with(str(tmp_path))

    def test_falls_back_to_system_temp_when_temp_dir_missing(self, monkeypatch):
        monkeypatch.setenv("TEMP_DIR", "/nonexistent/temp/dir/xyz")
        fake_stat = MagicMock()
        fake_stat.f_frsize = 1024
        fake_stat.f_bavail = 50 * 1024

        with patch("bot.validators.os.statvfs", return_value=fake_stat) as statvfs, patch(
            "bot.validators.tempfile.gettempdir", return_value="/system/tmp"
        ):
            ok, err = check_disk_space(10)
            assert ok is True
            statvfs.assert_called_once_with("/system/tmp")


class TestWorkTempRoot:
    def test_prefers_temp_dir_and_creates_it(self, tmp_path, monkeypatch):
        target = tmp_path / "work"
        monkeypatch.setenv("TEMP_DIR", str(target))
        assert not target.exists()
        assert work_temp_root() == str(target)
        assert target.is_dir()

    def test_falls_back_without_temp_dir(self, monkeypatch):
        monkeypatch.delenv("TEMP_DIR", raising=False)
        with patch("bot.temp_manager.tempfile.gettempdir", return_value="/system/tmp"):
            assert work_temp_root() == "/system/tmp"
