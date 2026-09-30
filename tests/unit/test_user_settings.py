"""Unit tests for disk-backed per-user settings (album_auto_pipeline)."""
import json
from pathlib import Path

import pytest

from bot.user_settings import (
    ALBUM_AUTO_PIPELINE_KEY,
    get_album_auto_pipeline,
    get_user_settings_path,
    get_user_settings_root,
    set_album_auto_pipeline,
)


@pytest.fixture(autouse=True)
def _isolate_settings_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
    yield tmp_path


class TestUserSettingsRoot:
    def test_honours_env_override(self, tmp_path):
        assert get_user_settings_root() == tmp_path

    def test_per_user_path(self, tmp_path):
        assert get_user_settings_path(123) == tmp_path / "123.json"


class TestAlbumAutoPipelinePersistence:
    def test_default_off_when_missing(self):
        assert get_album_auto_pipeline(7) is False

    def test_set_true_writes_json(self, tmp_path):
        assert set_album_auto_pipeline(7, True) is True
        path = tmp_path / "7.json"
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data[ALBUM_AUTO_PIPELINE_KEY] is True
        assert get_album_auto_pipeline(7) is True

    def test_set_false_overwrites(self, tmp_path):
        set_album_auto_pipeline(7, True)
        assert set_album_auto_pipeline(7, False) is False
        data = json.loads((tmp_path / "7.json").read_text(encoding="utf-8"))
        assert data[ALBUM_AUTO_PIPELINE_KEY] is False
        assert get_album_auto_pipeline(7) is False

    def test_users_are_isolated(self):
        set_album_auto_pipeline(1, True)
        set_album_auto_pipeline(2, False)
        assert get_album_auto_pipeline(1) is True
        assert get_album_auto_pipeline(2) is False

    def test_corrupt_json_defaults_off(self, tmp_path):
        path = tmp_path / "9.json"
        path.write_text("{not-json", encoding="utf-8")
        assert get_album_auto_pipeline(9) is False

    def test_survives_process_restart_simulation(self, tmp_path, monkeypatch):
        set_album_auto_pipeline(55, True)
        # Simulate new process: only env + disk remain
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        assert get_album_auto_pipeline(55) is True
