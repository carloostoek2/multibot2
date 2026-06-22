"""Unit tests for ImageProcessor.enhance."""
from pathlib import Path

import pytest
from PIL import Image

from bot.image_processor import (
    BRIGHT_LUMINANCE_THRESHOLD,
    ENHANCEMENT_PROFILES,
    ImageProcessor,
)


def _create_test_image(path: Path, color=(120, 80, 200)) -> None:
    Image.new("RGB", (32, 32), color=color).save(path, format="JPEG")


def _create_bright_image(path: Path) -> None:
    Image.new("RGB", (32, 32), color=(250, 245, 240)).save(path, format="JPEG")


class TestImageProcessorEnhance:
    def test_enhance_supported_profile(self, tmp_path):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / "output.jpg"
        _create_test_image(input_path)

        success, error = ImageProcessor.enhance(str(input_path), str(output_path), "equilibrado")

        assert success is True
        assert error is None
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_enhance_rejects_unknown_profile(self, tmp_path):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / "output.jpg"
        _create_test_image(input_path)

        success, error = ImageProcessor.enhance(str(input_path), str(output_path), "invalid")

        assert success is False
        assert "no soportado" in (error or "").lower()

    def test_bright_image_uses_reduced_scaling(self):
        scale = ImageProcessor._bright_image_scale(BRIGHT_LUMINANCE_THRESHOLD + 40)
        assert scale < 1.0
        assert scale >= 0.35

    def test_bright_brillo_produces_valid_output(self, tmp_path):
        input_path = tmp_path / "bright.jpg"
        output_path = tmp_path / "bright_out.jpg"
        _create_bright_image(input_path)

        success, error = ImageProcessor.enhance(str(input_path), str(output_path), "brillo")

        assert success is True
        assert error is None
        assert output_path.exists()

    @pytest.mark.parametrize("profile", list(ENHANCEMENT_PROFILES.keys()))
    def test_enhance_all_profiles_succeed(self, tmp_path, profile):
        input_path = tmp_path / "input.jpg"
        output_path = tmp_path / f"output_{profile}.jpg"
        _create_test_image(input_path)

        success, error = ImageProcessor.enhance(str(input_path), str(output_path), profile)

        assert success is True
        assert error is None
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_enhance_rejects_corrupt_input(self, tmp_path):
        input_path = tmp_path / "corrupt.jpg"
        output_path = tmp_path / "output.jpg"
        input_path.write_bytes(b"not-an-image")

        success, error = ImageProcessor.enhance(str(input_path), str(output_path), "equilibrado")

        assert success is False
        assert error

    def test_enhance_rgba_input_saves_as_jpeg(self, tmp_path):
        input_path = tmp_path / "rgba.png"
        output_path = tmp_path / "output.jpg"
        Image.new("RGBA", (32, 32), color=(120, 80, 200, 128)).save(input_path, format="PNG")

        success, error = ImageProcessor.enhance(str(input_path), str(output_path), "equilibrado")

        assert success is True
        assert error is None
        assert output_path.exists()
        with Image.open(output_path) as img:
            assert img.mode == "RGB"