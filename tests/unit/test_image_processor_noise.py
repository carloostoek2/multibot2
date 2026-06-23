"""Unit tests for ImageProcessor.add_noise."""
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from bot.image_processor import NOISE_STRENGTH_LEVELS, ImageProcessor


def _create_test_image(path: Path, color=(120, 80, 200)) -> None:
    Image.new("RGB", (64, 64), color=color).save(path, format="JPEG")


def _mean_difference(left: Path, right: Path) -> float:
    with Image.open(left) as before, Image.open(right) as after:
        diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
        return ImageStat.Stat(diff).mean[0]


class TestImageProcessorNoise:
    def test_add_noise_supported_strength(self, tmp_path):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / "output.jpg"
        _create_test_image(input_path)

        success, error = ImageProcessor.add_noise(str(input_path), str(output_path), 2)

        assert success is True
        assert error is None
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        assert _mean_difference(input_path, output_path) > 0

    def test_add_noise_rejects_invalid_strength(self, tmp_path):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / "output.jpg"
        _create_test_image(input_path)

        success, error = ImageProcessor.add_noise(str(input_path), str(output_path), 9)

        assert success is False
        assert "no soportada" in (error or "").lower()

    def test_higher_strength_changes_image_more(self, tmp_path):
        input_path = tmp_path / "input.jpg"
        subtle_path = tmp_path / "subtle.jpg"
        strong_path = tmp_path / "strong.jpg"
        _create_test_image(input_path)

        assert ImageProcessor.add_noise(str(input_path), str(subtle_path), 1)[0] is True
        assert ImageProcessor.add_noise(str(input_path), str(strong_path), 5)[0] is True

        assert _mean_difference(input_path, strong_path) > _mean_difference(
            input_path, subtle_path
        )

    @pytest.mark.parametrize("strength", list(NOISE_STRENGTH_LEVELS.keys()))
    def test_add_noise_all_strengths_succeed(self, tmp_path, strength):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / f"output_{strength}.jpg"
        _create_test_image(input_path)

        success, error = ImageProcessor.add_noise(str(input_path), str(output_path), strength)

        assert success is True
        assert error is None
        assert output_path.exists()

    def test_add_noise_rejects_corrupt_input(self, tmp_path):
        input_path = tmp_path / "corrupt.jpg"
        output_path = tmp_path / "output.jpg"
        input_path.write_bytes(b"not-an-image")

        success, error = ImageProcessor.add_noise(str(input_path), str(output_path), 2)

        assert success is False
        assert error is not None