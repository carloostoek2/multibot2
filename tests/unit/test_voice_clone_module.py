"""Unit tests for bot.voice_clone helpers (no live Replicate calls)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot.voice_clone import (
    VoiceCloneError,
    has_reference,
    save_reference,
    get_user_ref_path,
    get_voice_refs_root,
    clone_voice_pipeline,
)


class TestReferenceManagement:
    def test_has_reference_false_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert has_reference(99) is False

    def test_save_reference_writes_mp3(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "in.wav"
        src.write_bytes(b"fake")

        with patch("bot.voice_clone._convert_to_mp3") as convert:
            def _fake_convert(s, d):
                Path(d).parent.mkdir(parents=True, exist_ok=True)
                Path(d).write_bytes(b"mp3data")

            convert.side_effect = _fake_convert
            dest = save_reference(7, src)

        assert dest == get_user_ref_path(7)
        assert dest.is_file()
        assert has_reference(7) is True


class TestClonePipelineGating:
    def test_missing_token_raises_spanish_error(self, tmp_path):
        src = tmp_path / "src.oga"
        ref = tmp_path / "ref.mp3"
        out = tmp_path / "out.mp3"
        src.write_bytes(b"a")
        ref.write_bytes(b"b")

        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("REPLICATE_API_TOKEN", None)
            with pytest.raises(VoiceCloneError, match="REPLICATE_API_TOKEN"):
                clone_voice_pipeline(src, ref, out, api_token=None)


class TestVoiceRefsDirEnv:
    def test_voice_refs_dir_env_overrides_default(self, tmp_path, monkeypatch):
        root = tmp_path / "persistent" / "voice_refs"
        monkeypatch.setenv("VOICE_REFS_DIR", str(root))
        from bot.voice_clone import get_voice_refs_root, get_user_ref_path

        assert get_voice_refs_root() == root
        assert get_user_ref_path(42) == root / "42" / "reference.mp3"
