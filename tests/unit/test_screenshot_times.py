"""Unit tests for manual screenshot timestamp parsing.

``_parse_screenshot_times`` now delegates to the shared ``parse_time_value``,
so it accepts tenths of a second in the ``M:SS.d`` form on top of what it
already accepted.
"""
import pytest

from bot.handlers import _parse_screenshot_times


class TestParseScreenshotTimes:
    @pytest.mark.asyncio
    async def test_minutes_and_seconds(self):
        timestamps, error = await _parse_screenshot_times("1:30, 3:45")
        assert (timestamps, error) == ([90.0, 225.0], "")

    @pytest.mark.asyncio
    async def test_seconds_only(self):
        timestamps, error = await _parse_screenshot_times("85, 160")
        assert (timestamps, error) == ([85.0, 160.0], "")

    @pytest.mark.asyncio
    async def test_mixed_formats(self):
        timestamps, error = await _parse_screenshot_times("1:30, 85, 3:45")
        assert (timestamps, error) == ([90.0, 85.0, 225.0], "")

    @pytest.mark.asyncio
    async def test_accepts_tenths_of_a_second(self):
        timestamps, error = await _parse_screenshot_times("2:34.5")
        assert (timestamps, error) == ([154.5], "")

    @pytest.mark.asyncio
    async def test_spaces_inside_a_value_are_ignored(self):
        timestamps, error = await _parse_screenshot_times("1: 30")
        assert (timestamps, error) == ([90.0], "")

    @pytest.mark.asyncio
    async def test_empty_parts_are_skipped(self):
        timestamps, error = await _parse_screenshot_times("1:30, , 85")
        assert (timestamps, error) == ([90.0, 85.0], "")

    @pytest.mark.asyncio
    async def test_no_valid_timestamps(self):
        timestamps, error = await _parse_screenshot_times("  ,  ")
        assert timestamps == []
        assert "No se encontraron tiempos válidos" in error

    @pytest.mark.asyncio
    async def test_rejects_hours_format(self):
        timestamps, error = await _parse_screenshot_times("1:2:3")
        assert timestamps == []
        assert "Formato inválido" in error

    @pytest.mark.asyncio
    async def test_rejects_seconds_out_of_range(self):
        timestamps, error = await _parse_screenshot_times("1:60")
        assert timestamps == []
        assert "menores a 60" in error

    @pytest.mark.asyncio
    async def test_rejects_non_numeric(self):
        timestamps, error = await _parse_screenshot_times("abc")
        assert timestamps == []
        assert "abc" in error
