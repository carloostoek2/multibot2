"""Unit tests for AudioEffects.stereo_3d with mocked ffmpeg/ffprobe."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot.audio_effects import AudioEffects
from bot.error_handler import AudioEffectsError


@pytest.fixture
def input_file(tmp_path):
    path = tmp_path / "input.mp3"
    path.write_bytes(b"fake-audio")
    return path


class TestAudioEffectsStereo3d:
    @patch("bot.audio_effects.subprocess.run")
    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    @patch("bot.audio_effects.AudioEffects._get_audio_channels", return_value=1)
    def test_mono_source_uses_upmix_filter(self, _channels, _ffmpeg, mock_run, input_file, tmp_path):
        output_path = tmp_path / "output.mp3"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        effects = AudioEffects(str(input_file), str(output_path))
        result = effects.stereo_3d("medio")

        assert result is effects
        cmd = mock_run.call_args[0][0]
        assert "pan=stereo|c0=c0|c1=c0" in cmd[cmd.index("-af") + 1]
        assert "-q:a" not in cmd
        assert "-b:a" in cmd

    @patch("bot.audio_effects.subprocess.run")
    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    @patch("bot.audio_effects.AudioEffects._get_audio_channels", return_value=2)
    def test_stereo_source_skips_upmix(self, _channels, _ffmpeg, mock_run, input_file, tmp_path):
        output_path = tmp_path / "output.mp3"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        effects = AudioEffects(str(input_file), str(output_path))
        effects.stereo_3d("suave")

        cmd = mock_run.call_args[0][0]
        af_filter = cmd[cmd.index("-af") + 1]
        assert "pan=stereo" not in af_filter
        assert "apulsator=mode=sine:amount=1:speed=0.15" in af_filter

    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    def test_invalid_intensity_raises(self, _ffmpeg, input_file, tmp_path):
        output_path = tmp_path / "output.mp3"
        effects = AudioEffects(str(input_file), str(output_path))

        with pytest.raises(AudioEffectsError, match="Intensidad"):
            effects.stereo_3d("extremo")

    @patch("bot.audio_effects.shutil.which", return_value="/usr/bin/ffprobe")
    @patch("bot.audio_effects.subprocess.run")
    def test_get_audio_channels_parses_ffprobe_output(self, mock_run, _which):
        mock_run.return_value = MagicMock(stdout="2\n", returncode=0)
        channels = AudioEffects._get_audio_channels(Path("/tmp/test.mp3"))
        assert channels == 2

    @patch("bot.audio_effects.subprocess.run")
    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    @patch("bot.audio_effects.AudioEffects._get_audio_channels", return_value=2)
    def test_stereo_3d_called_process_error_raises_audio_effects_error(
        self, _channels, _ffmpeg, mock_run, input_file, tmp_path
    ):
        import subprocess

        output_path = tmp_path / "output.mp3"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="Invalid data found when processing input"
        )

        effects = AudioEffects(str(input_file), str(output_path))
        with pytest.raises(AudioEffectsError, match="Error aplicando efecto 3D"):
            effects.stereo_3d("medio")