"""
Deterministic shared helpers for fraud rule evaluations.
Includes Haversine distance, median calculation, score-to-severity mapping,
and operating hours evaluation.
"""

from datetime import datetime, time as dt_time
from decimal import Decimal
import math
from typing import Optional, Sequence
import zoneinfo

from app.schemas.merchant import OperatingHours
from app.schemas.rule import Severity


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate the great-circle distance between two geographical points on Earth
    using the Haversine formula.

    Earth radius: 6371.0 km

    Returns:
        float: Distance in kilometers.
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    earth_radius_km = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    # Guard against precision errors exceeding [0.0, 1.0]
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(earth_radius_km * c, 4)


def calculate_median(values: Sequence[Decimal]) -> Decimal:
    """
    Compute the median of a sequence of Decimal amounts preserving exact monetary precision.

    Raises:
        ValueError: If values sequence is empty.
    """
    if not values:
        raise ValueError("Cannot calculate median of an empty sequence")

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2

    if n % 2 == 1:
        return sorted_vals[mid]
    else:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / Decimal("2")


def score_to_severity(score: int) -> Severity:
    """
    Map a deterministic risk signal score (0-100) to standard Severity:
    0       -> NONE
    1-39    -> LOW
    40-69   -> MEDIUM
    70-89   -> HIGH
    90-100  -> CRITICAL
    """
    if score <= 0:
        return Severity.NONE
    elif score <= 39:
        return Severity.LOW
    elif score <= 69:
        return Severity.MEDIUM
    elif score <= 89:
        return Severity.HIGH
    else:
        return Severity.CRITICAL


def is_within_operating_hours(
    transaction_time: datetime,
    operating_hours: Optional[OperatingHours],
) -> Optional[bool]:
    """
    Determine whether a transaction timestamp falls within a merchant's operating hours.
    Handles daytime ranges (e.g. 09:00 to 21:00) and overnight ranges (e.g. 21:00 to 04:00).

    Returns:
        bool: True if within hours, False if outside.
        None: If operating_hours is not provided or timezone is invalid.
    """
    if operating_hours is None:
        return None

    try:
        tz = zoneinfo.ZoneInfo(operating_hours.timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    local_dt = transaction_time.astimezone(tz)
    tx_time = local_dt.time()

    try:
        start_h, start_m = map(int, operating_hours.start_time.split(":"))
        end_h, end_m = map(int, operating_hours.end_time.split(":"))
        start = dt_time(start_h, start_m)
        end = dt_time(end_h, end_m)
    except Exception:
        return None

    if start <= end:
        # Standard daytime hours (e.g. 09:00 to 21:00)
        return start <= tx_time <= end
    else:
        # Overnight operating hours (e.g. 21:00 to 04:00)
        return tx_time >= start or tx_time <= end
