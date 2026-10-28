"""Unit tests for disk-backed per-user settings (album_auto_pipeline)."""
import json
from pathlib import Path

import pytest

from bot.user_settings import (
    ALBUM_AUTO_PIPELINE_KEY,
    IMAGE_CANDID_PRESET_KEY,
    IMAGE_CANDID_DELIVERY_KEY,
    get_album_auto_pipeline,
    get_image_candid_preset,
    get_image_candid_delivery,
    get_user_settings_path,
    get_user_settings_root,
    set_album_auto_pipeline,
    set_image_candid_preset,
    set_image_candid_delivery,
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


class TestImageCandidPresetPersistence:
    def test_default_is_medium_when_missing(self):
        assert get_image_candid_preset(7) == "medium"

    def test_set_preset_writes_json(self, tmp_path):
        assert set_image_candid_preset(7, "strong") == "strong"
        data = json.loads((tmp_path / "7.json").read_text(encoding="utf-8"))
        assert data[IMAGE_CANDID_PRESET_KEY] == "strong"
        assert get_image_candid_preset(7) == "strong"

    def test_invalid_preset_in_file_falls_back_to_medium(self, tmp_path):
        (tmp_path / "9.json").write_text(
            json.dumps({IMAGE_CANDID_PRESET_KEY: "extremo"}), encoding="utf-8"
        )
        assert get_image_candid_preset(9) == "medium"

    def test_rejects_unknown_preset(self):
        with pytest.raises(ValueError):
            set_image_candid_preset(7, "extremo")

    def test_users_are_isolated(self):
        set_image_candid_preset(1, "subtle")
        set_image_candid_preset(2, "strong")
        assert get_image_candid_preset(1) == "subtle"
        assert get_image_candid_preset(2) == "strong"

    def test_survives_process_restart_simulation(self, tmp_path, monkeypatch):
        set_image_candid_preset(55, "strong")
        monkeypatch.setenv("USER_SETTINGS_DIR", str(tmp_path))
        assert get_image_candid_preset(55) == "strong"


class TestImageCandidDeliveryPersistence:
    def test_default_is_document_when_missing(self):
        assert get_image_candid_delivery(7) == "document"

    def test_set_delivery_writes_json(self, tmp_path):
        assert set_image_candid_delivery(7, "photo") == "photo"
        data = json.loads((tmp_path / "7.json").read_text(encoding="utf-8"))
        assert data[IMAGE_CANDID_DELIVERY_KEY] == "photo"
        assert get_image_candid_delivery(7) == "photo"

    def test_invalid_delivery_in_file_falls_back_to_document(self, tmp_path):
        (tmp_path / "9.json").write_text(
            json.dumps({IMAGE_CANDID_DELIVERY_KEY: "fax"}), encoding="utf-8"
        )
        assert get_image_candid_delivery(9) == "document"

    def test_rejects_unknown_delivery(self):
        with pytest.raises(ValueError):
            set_image_candid_delivery(7, "fax")

    def test_delivery_and_preset_coexist(self, tmp_path):
        set_image_candid_preset(7, "strong")
        set_image_candid_delivery(7, "photo")
        data = json.loads((tmp_path / "7.json").read_text(encoding="utf-8"))
        assert data[IMAGE_CANDID_PRESET_KEY] == "strong"
        assert data[IMAGE_CANDID_DELIVERY_KEY] == "photo"
