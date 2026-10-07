"""Unit tests for the shared time input parser and formatter."""
import pytest

from bot.time_parser import format_time, parse_time_value


class TestParseTimeValueSeconds:
    """A bare number is always seconds, whatever its magnitude."""

    def test_integer_seconds(self):
        assert parse_time_value("30") == (30.0, None)

    def test_decimal_seconds(self):
        assert parse_time_value("30.5") == (30.5, None)

    def test_bare_number_above_a_minute_stays_seconds(self):
        assert parse_time_value("90") == (90.0, None)

    def test_surrounding_whitespace_is_ignored(self):
        assert parse_time_value("  30.5  ") == (30.5, None)

    def test_negative_is_parsed_so_callers_can_reject_it(self):
        assert parse_time_value("-5") == (-5.0, None)


class TestParseTimeValueMinutesSeconds:
    """A colon switches to minutes:seconds."""

    def test_minutes_and_seconds(self):
        assert parse_time_value("1:24") == (84.0, None)

    def test_tenths_of_a_second(self):
        assert parse_time_value("2:34.5") == (154.5, None)

    def test_zero_padded_seconds(self):
        assert parse_time_value("0:05") == (5.0, None)

    def test_seconds_as_a_single_digit(self):
        assert parse_time_value("3:7") == (187.0, None)

    def test_minutes_above_sixty_are_how_hours_are_written(self):
        assert parse_time_value("90:00") == (5400.0, None)


class TestParseTimeValueErrors:
    @pytest.mark.parametrize("text", ["", "   ", None])
    def test_missing_input(self, text):
        value, error = parse_time_value(text)
        assert value is None
        assert error == "No recibí ningún tiempo."

    def test_seconds_out_of_range(self):
        value, error = parse_time_value("1:60")
        assert value is None
        assert "menores a 60" in error

    def test_rejects_hours_format(self):
        value, error = parse_time_value("1:2:3")
        assert value is None
        assert "Formato inválido" in error

    def test_rejects_non_numeric(self):
        value, error = parse_time_value("abc")
        assert value is None
        assert "abc" in error

    def test_rejects_comma_as_decimal_separator(self):
        # The comma separates values in the screenshot session, so it cannot
        # also mean a decimal point.
        value, error = parse_time_value("2:34,5")
        assert value is None
        assert error

    @pytest.mark.parametrize(
        "text",
        ["", "  ", None, ":", "::", "1:", ":30", "1.2.3", "1:2:3", "abc", "1:60", "1:--"],
    )
    def test_always_returns_exactly_one_of_value_or_error(self, text):
        value, error = parse_time_value(text)
        assert (value is None) is not (error is None)


class TestFormatTime:
    def test_under_a_minute_shows_seconds(self):
        assert format_time(45) == "45s"
        assert format_time(45.5) == "45.5s"

    def test_a_minute_or_more_uses_minutes_and_seconds(self):
        assert format_time(84) == "1:24"
        assert format_time(154.5) == "2:34.5"
        assert format_time(328) == "5:28"

    def test_seconds_are_zero_padded(self):
        assert format_time(61) == "1:01"
        assert format_time(65.5) == "1:05.5"

    def test_over_an_hour_keeps_counting_minutes(self):
        assert format_time(5400) == "90:00"

    def test_rounds_to_tenths_of_a_second(self):
        assert format_time(154.53) == "2:34.5"

    def test_rounding_can_push_into_the_next_minute(self):
        assert format_time(59.96) == "1:00"

    def test_round_trips_with_the_parser_for_minute_values(self):
        # Values under a minute get an "s" suffix, which is display-only; the
        # colon form must survive a format/parse round trip untouched.
        for text in ["1:24", "2:34.5", "90:00"]:
            seconds, _ = parse_time_value(text)
            assert parse_time_value(format_time(seconds)) == (seconds, None)
