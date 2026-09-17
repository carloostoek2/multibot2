"""Unit tests for bot.voice_clone helpers (no live Replicate calls)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot.voice_clone import (
    VoiceCloneError,
    FREEVC_MODEL,
    FREEVC_MODEL_TYPE,
    has_reference,
    save_reference,
    get_user_ref_path,
    get_voice_refs_root,
    clone_voice_pipeline,
    run_freevc,
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


class TestFreeVCPipeline:
    def test_clone_pipeline_calls_freevc_only(self, tmp_path):
        src = tmp_path / "src.oga"
        ref = tmp_path / "ref.mp3"
        out = tmp_path / "out.mp3"
        src.write_bytes(b"a")
        ref.write_bytes(b"b")

        def fake_wav(s, d):
            Path(d).write_bytes(b"RIFF")

        with patch("bot.voice_clone._convert_to_wav", side_effect=fake_wav), patch(
            "bot.voice_clone.run_freevc", return_value="https://example.com/out.wav"
        ) as freevc, patch(
            "bot.voice_clone.download_url_to_file"
        ) as download, patch(
            "bot.voice_clone.ensure_mp3"
        ) as ensure:
            def _dl(url, dest):
                Path(dest).write_bytes(b"raw")
                return Path(dest)

            def _mp3(s, d):
                Path(d).write_bytes(b"mp3")
                return Path(d)

            download.side_effect = _dl
            ensure.side_effect = _mp3

            result = clone_voice_pipeline(
                src, ref, out, api_token="r8_test", correlation_id="cid1"
            )

        assert result == out
        freevc.assert_called_once()
        kwargs = freevc.call_args.kwargs
        assert kwargs["model_type"] == FREEVC_MODEL_TYPE
        assert kwargs["api_token"] == "r8_test"
        assert kwargs["correlation_id"] == "cid1"

    def test_run_freevc_passes_pinned_model_and_inputs(self, tmp_path):
        src = tmp_path / "src.wav"
        ref = tmp_path / "ref.wav"
        src.write_bytes(b"src")
        ref.write_bytes(b"ref")

        mock_replicate = MagicMock()
        mock_replicate.run.return_value = "https://example.com/converted.wav"

        with patch.dict("sys.modules", {"replicate": mock_replicate}), patch(
            "bot.voice_clone._open_audio_for_replicate",
            side_effect=lambda p: open(p, "rb"),
        ):
            url = run_freevc(src, ref, api_token="r8_test", correlation_id="x")

        assert url == "https://example.com/converted.wav"
        mock_replicate.run.assert_called_once()
        model_arg = mock_replicate.run.call_args.args[0]
        assert model_arg == FREEVC_MODEL
        assert ":" in model_arg
        inputs = mock_replicate.run.call_args.kwargs["input"]
        assert inputs["model_type"] == "FreeVC (24kHz)"
        assert "source_audio" in inputs
        assert "reference_audio" in inputs


class TestVoiceRefsDirEnv:
    def test_voice_refs_dir_env_overrides_default(self, tmp_path, monkeypatch):
        root = tmp_path / "persistent" / "voice_refs"
        monkeypatch.setenv("VOICE_REFS_DIR", str(root))
        from bot.voice_clone import get_voice_refs_root, get_user_ref_path

        assert get_voice_refs_root() == root
        assert get_user_ref_path(42) == root / "42" / "reference.mp3"
