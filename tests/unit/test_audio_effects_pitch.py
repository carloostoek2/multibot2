"""Unit tests for AudioEffects.pitch_shift with mocked ffmpeg."""
import math
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


class TestAudioEffectsPitchShift:
    @patch("bot.audio_effects.subprocess.run")
    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    def test_valid_intensity_agudo_uses_correct_ratio(self, _ffmpeg, mock_run, input_file, tmp_path):
        output_path = tmp_path / "output.mp3"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        effects = AudioEffects(str(input_file), str(output_path))
        result = effects.pitch_shift("agudo")

        assert result is effects
        cmd = mock_run.call_args[0][0]
        af_filter = cmd[cmd.index("-af") + 1]
        ratio = 2 ** (3.5 / 12.0)
        expected = f"asetrate=44100*{ratio},atempo={ratio}"
        assert af_filter == expected

    @patch("bot.audio_effects.subprocess.run")
    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    def test_valid_intensity_grave_uses_correct_ratio(self, _ffmpeg, mock_run, input_file, tmp_path):
        output_path = tmp_path / "output.mp3"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        effects = AudioEffects(str(input_file), str(output_path))
        effects.pitch_shift("grave")

        cmd = mock_run.call_args[0][0]
        af_filter = cmd[cmd.index("-af") + 1]
        ratio = 2 ** (-3.5 / 12.0)
        expected = f"asetrate=44100*{ratio},atempo={ratio}"
        assert af_filter == expected

    @patch("bot.audio_effects.subprocess.run")
    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    def test_valid_intensity_muy_agudo_uses_correct_ratio(self, _ffmpeg, mock_run, input_file, tmp_path):
        output_path = tmp_path / "output.mp3"
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        effects = AudioEffects(str(input_file), str(output_path))
        effects.pitch_shift("muy_agudo")

        cmd = mock_run.call_args[0][0]
        af_filter = cmd[cmd.index("-af") + 1]
        ratio = 2 ** (6.5 / 12.0)
        expected = f"asetrate=44100*{ratio},atempo={ratio}"
        assert af_filter == expected

    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    def test_invalid_intensity_raises(self, _ffmpeg, input_file, tmp_path):
        output_path = tmp_path / "output.mp3"
        effects = AudioEffects(str(input_file), str(output_path))

        with pytest.raises(AudioEffectsError, match="Intensidad"):
            effects.pitch_shift("extremo")

    @patch("bot.audio_effects.subprocess.run")
    @patch("bot.audio_effects.AudioEffects._check_ffmpeg", return_value=True)
    def test_called_process_error_raises_audio_effects_error(
        self, _ffmpeg, mock_run, input_file, tmp_path
    ):
        import subprocess

        output_path = tmp_path / "output.mp3"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="Invalid data found when processing input"
        )

        effects = AudioEffects(str(input_file), str(output_path))
        with pytest.raises(AudioEffectsError, match="Error aplicando cambio de tono"):
            effects.pitch_shift("agudo")
