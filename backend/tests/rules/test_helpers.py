"""
Unit tests for deterministic shared fraud rule helpers.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest

from app.rules.helpers import (
    calculate_median,
    haversine_distance_km,
    is_within_operating_hours,
    score_to_severity,
)
from app.schemas.merchant import OperatingHours
from app.schemas.rule import Severity


class TestHaversineDistance:
    def test_same_location_returns_zero(self):
        dist = haversine_distance_km(19.0760, 72.8777, 19.0760, 72.8777)
        assert dist == 0.0

    def test_known_distance_mumbai_to_delhi(self):
        # Mumbai: 19.0760° N, 72.8777° E
        # Delhi: 28.6139° N, 77.2090° E
        # Expected great-circle distance is approx 1148-1155 km
        dist = haversine_distance_km(19.0760, 72.8777, 28.6139, 77.2090)
        assert 1140.0 <= dist <= 1160.0

    def test_known_distance_ny_to_london(self):
        # New York: 40.7128, -74.0060
        # London: 51.5074, -0.1278
        # Expected distance approx 5570 - 5590 km
        dist = haversine_distance_km(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5560.0 <= dist <= 5600.0

    def test_poles_distance(self):
        # North Pole (90, 0) to South Pole (-90, 0) -> Half Earth circumference approx 20015 km
        dist = haversine_distance_km(90.0, 0.0, -90.0, 0.0)
        assert 20000.0 <= dist <= 20030.0


class TestCalculateMedian:
    def test_odd_count_median(self):
        values = [Decimal("100.00"), Decimal("50.00"), Decimal("200.00")]
        assert calculate_median(values) == Decimal("100.00")

    def test_even_count_median(self):
        values = [Decimal("10.00"), Decimal("20.00"), Decimal("30.00"), Decimal("40.00")]
        assert calculate_median(values) == Decimal("25.00")

    def test_single_value(self):
        values = [Decimal("99.99")]
        assert calculate_median(values) == Decimal("99.99")

    def test_empty_sequence_raises_error(self):
        with pytest.raises(ValueError, match="Cannot calculate median of an empty sequence"):
            calculate_median([])

    def test_duplicate_values(self):
        values = [Decimal("50.00"), Decimal("50.00"), Decimal("50.00")]
        assert calculate_median(values) == Decimal("50.00")


class TestScoreToSeverity:
    @pytest.mark.parametrize(
        "score, expected",
        [
            (0, Severity.NONE),
            (-5, Severity.NONE),
            (1, Severity.LOW),
            (25, Severity.LOW),
            (39, Severity.LOW),
            (40, Severity.MEDIUM),
            (55, Severity.MEDIUM),
            (69, Severity.MEDIUM),
            (70, Severity.HIGH),
            (80, Severity.HIGH),
            (89, Severity.HIGH),
            (90, Severity.CRITICAL),
            (95, Severity.CRITICAL),
            (100, Severity.CRITICAL),
        ],
    )
    def test_score_mapping(self, score: int, expected: Severity):
        assert score_to_severity(score) == expected


class TestIsWithinOperatingHours:
    def test_none_operating_hours(self):
        now = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        assert is_within_operating_hours(now, None) is None

    def test_daytime_operating_hours_within(self):
        op_hours = OperatingHours(start_time="09:00", end_time="21:00", timezone="UTC")
        tx_time = datetime(2026, 3, 15, 14, 30, tzinfo=timezone.utc)
        assert is_within_operating_hours(tx_time, op_hours) is True

    def test_daytime_operating_hours_outside(self):
        op_hours = OperatingHours(start_time="09:00", end_time="21:00", timezone="UTC")
        tx_time = datetime(2026, 3, 15, 22, 30, tzinfo=timezone.utc)
        assert is_within_operating_hours(tx_time, op_hours) is False

    def test_daytime_operating_hours_boundaries(self):
        op_hours = OperatingHours(start_time="09:00", end_time="21:00", timezone="UTC")
        tx_start = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
        tx_end = datetime(2026, 3, 15, 21, 0, tzinfo=timezone.utc)
        assert is_within_operating_hours(tx_start, op_hours) is True
        assert is_within_operating_hours(tx_end, op_hours) is True

    def test_overnight_operating_hours_within(self):
        # e.g., Night club: 21:00 to 04:00
        op_hours = OperatingHours(start_time="21:00", end_time="04:00", timezone="UTC")
        tx_time1 = datetime(2026, 3, 15, 23, 30, tzinfo=timezone.utc)
        tx_time2 = datetime(2026, 3, 16, 2, 15, tzinfo=timezone.utc)
        assert is_within_operating_hours(tx_time1, op_hours) is True
        assert is_within_operating_hours(tx_time2, op_hours) is True

    def test_overnight_operating_hours_outside(self):
        op_hours = OperatingHours(start_time="21:00", end_time="04:00", timezone="UTC")
        tx_time = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        assert is_within_operating_hours(tx_time, op_hours) is False
