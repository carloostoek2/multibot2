"""Unit and integration tests for the ported candid engine."""

from __future__ import annotations

from pathlib import Path
from random import Random
from unittest.mock import patch

import pytest
from PIL import Image

from bot import candid_engine
from bot.candid_engine import (
    DEFAULT_PRESET,
    PRESET_LABELS,
    PRESET_NAMES,
    CandidError,
    CandidProcessingError,
    CandidUnavailableError,
    apply_effect,
)


def _make_image(path: Path, size: tuple[int, int] = (320, 240)) -> Path:
    """Create a small RGB JPEG with some structure for the effect chain."""
    image = Image.linear_gradient("L").resize(size).convert("RGB")
    image.save(path, quality=95)
    return path


class TestPresetCatalog:
    def test_expected_presets(self):
        assert PRESET_NAMES == ("subtle", "medium", "strong")

    def test_labels_cover_every_preset(self):
        assert set(PRESET_LABELS) == set(PRESET_NAMES)

    def test_default_is_medium(self):
        assert DEFAULT_PRESET == "medium"


class TestApplyEffectValidation:
    def test_rejects_unknown_preset(self, tmp_path):
        with pytest.raises(CandidError, match="no soportado"):
            apply_effect(tmp_path / "in.jpg", tmp_path / "out.jpg", preset="extremo")

    def test_rejects_unknown_engine(self, tmp_path):
        with pytest.raises(CandidError, match="no soportado"):
            apply_effect(
                tmp_path / "in.jpg", tmp_path / "out.jpg", engine="filtro-magico"
            )

    def test_missing_magick_raises_unavailable(self, tmp_path):
        with patch.object(candid_engine, "is_available", return_value=False):
            with pytest.raises(CandidUnavailableError):
                apply_effect(tmp_path / "in.jpg", tmp_path / "out.jpg")

    def test_rejects_oversized_images(self, tmp_path):
        source = _make_image(tmp_path / "in.jpg")
        with patch.object(candid_engine, "is_available", return_value=True), patch.object(
            candid_engine, "image_size", return_value=(10_000, 5_000)
        ):
            with pytest.raises(CandidError, match="demasiado grande"):
                apply_effect(source, tmp_path / "out.jpg")

    def test_rejects_missing_input(self, tmp_path):
        with patch.object(candid_engine, "is_available", return_value=True):
            with pytest.raises(CandidError, match="No encontré"):
                apply_effect(tmp_path / "nope.jpg", tmp_path / "out.jpg")


class TestGmicFallback:
    def test_falls_back_to_imagemagick_when_gmic_fails(self, tmp_path):
        source = _make_image(tmp_path / "in.jpg")
        destination = tmp_path / "out.jpg"
        engines: list[str] = []

        def fake_process(src, dst, preset, rng, keep_jpeg_history, engine, **kwargs):
            engines.append(engine)
            if engine == "gmic":
                raise RuntimeError("gmic: filtro desconocido")
            Path(dst).write_bytes(b"jpeg")
            return Path(dst)

        with patch.object(candid_engine, "is_available", return_value=True), patch.object(
            candid_engine, "gmic_available", return_value=True
        ), patch.object(candid_engine, "process_one", side_effect=fake_process):
            result = apply_effect(source, destination, preset="medium", seed=7)

        assert result == destination
        assert engines == ["gmic", "imagemagick"]

    def test_processing_failure_is_wrapped(self, tmp_path):
        source = _make_image(tmp_path / "in.jpg")

        with patch.object(candid_engine, "is_available", return_value=True), patch.object(
            candid_engine, "gmic_available", return_value=False
        ), patch.object(
            candid_engine, "process_one", side_effect=RuntimeError("magick exploded")
        ):
            with pytest.raises(CandidProcessingError, match="magick exploded"):
                apply_effect(source, tmp_path / "out.jpg")


@pytest.mark.skipif(
    not candid_engine.is_available(), reason="requiere ImageMagick 7 (magick)"
)
class TestRealPipeline:
    def test_imagemagick_engine_writes_jpeg(self, tmp_path):
        source = _make_image(tmp_path / "in.jpg")
        destination = tmp_path / "out.jpg"

        result = apply_effect(
            source, destination, preset="subtle", seed=123, engine="imagemagick"
        )

        assert result == destination
        assert destination.is_file() and destination.stat().st_size > 0
        with Image.open(destination) as output:
            assert output.format == "JPEG"
            assert output.size == (320, 240)

    def test_same_seed_builds_same_command(self, tmp_path):
        # The Python seed fixes parameter sampling. ImageMagick's own grain RNG
        # is independent, so pixel-identical output is not guaranteed.
        preset = candid_engine.PRESETS["medium"]
        source = tmp_path / "in.jpg"
        destination = tmp_path / "out.jpg"

        first = candid_engine.build_command(
            source, destination, preset, (320, 240), Random(99), 1.0, 1.0
        )
        second = candid_engine.build_command(
            source, destination, preset, (320, 240), Random(99), 1.0, 1.0
        )

        assert first == second

    def test_different_seeds_sample_different_parameters(self, tmp_path):
        preset = candid_engine.PRESETS["medium"]
        source = tmp_path / "in.jpg"
        destination = tmp_path / "out.jpg"

        first = candid_engine.build_command(
            source, destination, preset, (320, 240), Random(1), 1.0, 1.0
        )
        second = candid_engine.build_command(
            source, destination, preset, (320, 240), Random(2), 1.0, 1.0
        )

        assert first != second

    def test_png_output_is_lossless_container(self, tmp_path):
        source = _make_image(tmp_path / "in.jpg")
        destination = tmp_path / "out.png"

        apply_effect(
            source, destination, preset="subtle", seed=3, engine="imagemagick"
        )

        with Image.open(destination) as output:
            assert output.format == "PNG"
            assert output.size == (320, 240)

    @pytest.mark.skipif(
        not candid_engine.gmic_available(), reason="requiere G'MIC"
    )
    def test_gmic_grain_engine_runs(self, tmp_path):
        source = _make_image(tmp_path / "in.jpg", size=(160, 120))
        destination = tmp_path / "out.jpg"

        apply_effect(source, destination, preset="subtle", seed=5, engine="gmic")

        assert destination.is_file() and destination.stat().st_size > 0
