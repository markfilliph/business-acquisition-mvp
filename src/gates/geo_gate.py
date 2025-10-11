"""
Geographic gate for business qualification.
PRIORITY: P1 - Dual enforcement: radius AND city allowlist.

Task 8: Geo Allowlist (Dual Enforcement)
- Check 1: Business within radius (haversine distance)
- Check 2: Business city in ALLOWED_CITIES
- Both must pass for geo_ok = True
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import math
import structlog

from ..core.config import config

logger = structlog.get_logger(__name__)


@dataclass
class GeoGateResult:
    """Result of geographic gate validation."""
    passes: bool
    within_radius: bool
    city_allowed: bool
    distance_km: Optional[float] = None
    city: Optional[str] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage."""
        return {
            "passes": self.passes,
            "within_radius": self.within_radius,
            "city_allowed": self.city_allowed,
            "distance_km": self.distance_km,
            "city": self.city,
            "rejection_reason": self.rejection_reason
        }


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Calculate haversine distance between two points on Earth.

    Args:
        lat1: Latitude of point 1 (degrees)
        lon1: Longitude of point 1 (degrees)
        lat2: Latitude of point 2 (degrees)
        lon2: Longitude of point 2 (degrees)

    Returns:
        Distance in kilometers

    Example:
        >>> # Hamilton to Toronto (~70km)
        >>> distance = haversine_distance(43.2557, -79.8711, 43.6532, -79.3832)
        >>> assert 65 < distance < 75
    """
    # Earth radius in kilometers
    R = 6371.0

    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


def normalize_city_name(city: str) -> str:
    """
    Normalize city name for comparison.

    Args:
        city: City name to normalize

    Returns:
        Normalized city name (lowercase, stripped, punctuation removed)

    Example:
        >>> normalize_city_name("  Hamilton, ON  ")
        'hamilton'
        >>> normalize_city_name("Stoney Creek")
        'stoney creek'
    """
    if not city:
        return ""

    # Convert to lowercase and strip
    normalized = city.lower().strip()

    # Remove extra whitespace first
    normalized = " ".join(normalized.split())

    # Remove common suffixes (ON, Ontario, etc.)
    suffixes = [", on", ", ontario", " on", " ontario"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
            break  # Only remove one suffix

    return normalized


def geo_gate(
    latitude: float,
    longitude: float,
    city: str,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    radius_km: Optional[float] = None,
    allowed_cities: Optional[list[str]] = None
) -> GeoGateResult:
    """
    Validate business location against geographic requirements.

    DUAL ENFORCEMENT - Both checks must pass:
    1. Business within radius from center point (haversine distance)
    2. Business city in ALLOWED_CITIES list

    Args:
        latitude: Business latitude
        longitude: Business longitude
        city: Business city name
        center_lat: Center point latitude (defaults to config)
        center_lon: Center point longitude (defaults to config)
        radius_km: Maximum radius in km (defaults to config)
        allowed_cities: List of allowed cities (defaults to config)

    Returns:
        GeoGateResult with pass/fail and rejection reason

    Examples:
        >>> # Pass: Inside radius + allowed city
        >>> result = geo_gate(43.2557, -79.8711, "Hamilton")
        >>> assert result.passes is True

        >>> # Fail: Inside radius but disallowed city
        >>> result = geo_gate(43.6532, -79.3832, "Toronto")
        >>> assert result.passes is False
        >>> assert "city not allowed" in result.rejection_reason

        >>> # Fail: Allowed city but outside radius
        >>> result = geo_gate(45.4215, -75.6972, "Hamilton")  # Ottawa coords
        >>> assert result.passes is False
        >>> assert "outside radius" in result.rejection_reason
    """
    # Use config defaults if not provided
    center_lat = center_lat or config.GEO_CENTER_LAT
    center_lon = center_lon or config.GEO_CENTER_LNG
    radius_km = radius_km or config.GEO_RADIUS_KM
    allowed_cities = allowed_cities or config.ALLOWED_CITIES

    # Normalize city name
    normalized_city = normalize_city_name(city)

    # Check 1: Within radius
    distance_km = haversine_distance(latitude, longitude, center_lat, center_lon)
    within_radius = distance_km <= radius_km

    # Check 2: City in allowlist
    # Normalize allowed cities for comparison
    normalized_allowed = [normalize_city_name(c) for c in allowed_cities]
    city_allowed = normalized_city in normalized_allowed

    # Determine pass/fail
    passes = within_radius and city_allowed

    # Build rejection reason
    rejection_reason = None
    if not passes:
        if not within_radius and not city_allowed:
            rejection_reason = (
                f"Outside radius ({distance_km:.1f}km > {radius_km}km) "
                f"AND city '{city}' not in allowed list {allowed_cities}"
            )
        elif not within_radius:
            rejection_reason = (
                f"Outside radius: {distance_km:.1f}km > {radius_km}km from center "
                f"(city '{city}' is allowed but too far)"
            )
        elif not city_allowed:
            rejection_reason = (
                f"City '{city}' not in allowed list {allowed_cities} "
                f"(distance {distance_km:.1f}km is within radius)"
            )

    # Log result
    if passes:
        logger.info(
            "geo_gate_passed",
            latitude=latitude,
            longitude=longitude,
            city=city,
            distance_km=round(distance_km, 2),
            within_radius=within_radius,
            city_allowed=city_allowed
        )
    else:
        logger.info(
            "geo_gate_failed",
            latitude=latitude,
            longitude=longitude,
            city=city,
            distance_km=round(distance_km, 2),
            within_radius=within_radius,
            city_allowed=city_allowed,
            reason=rejection_reason
        )

    return GeoGateResult(
        passes=passes,
        within_radius=within_radius,
        city_allowed=city_allowed,
        distance_km=distance_km,
        city=city,
        rejection_reason=rejection_reason
    )


def validate_coordinates(latitude: float, longitude: float) -> Tuple[bool, Optional[str]]:
    """
    Validate that coordinates are valid.

    Args:
        latitude: Latitude to validate
        longitude: Longitude to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> valid, error = validate_coordinates(43.2557, -79.8711)
        >>> assert valid is True
        >>> assert error is None

        >>> valid, error = validate_coordinates(91.0, -79.8711)
        >>> assert valid is False
        >>> assert "latitude" in error.lower()
    """
    if not -90 <= latitude <= 90:
        return False, f"Invalid latitude: {latitude} (must be between -90 and 90)"

    if not -180 <= longitude <= 180:
        return False, f"Invalid longitude: {longitude} (must be between -180 and 180)"

    return True, None


def get_rejection_summary(results: list[GeoGateResult]) -> dict:
    """
    Get summary statistics of geo gate rejections.

    Args:
        results: List of GeoGateResult objects

    Returns:
        Dict with rejection statistics

    Example:
        >>> results = [
        ...     geo_gate(43.2557, -79.8711, "Hamilton"),
        ...     geo_gate(43.6532, -79.3832, "Toronto")
        ... ]
        >>> summary = get_rejection_summary(results)
        >>> summary['total_checked']
        2
    """
    total = len(results)
    passed = sum(1 for r in results if r.passes)
    failed = total - passed

    # Categorize rejection reasons
    outside_radius = sum(1 for r in results if not r.passes and not r.within_radius)
    city_not_allowed = sum(1 for r in results if not r.passes and not r.city_allowed)
    both_failed = sum(
        1 for r in results
        if not r.passes and not r.within_radius and not r.city_allowed
    )

    # Calculate average distance for passed/failed
    passed_distances = [r.distance_km for r in results if r.passes and r.distance_km is not None]
    failed_distances = [r.distance_km for r in results if not r.passes and r.distance_km is not None]

    return {
        "total_checked": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total > 0 else 0.0,
        "rejection_rate": failed / total if total > 0 else 0.0,
        "rejections_by_reason": {
            "outside_radius": outside_radius,
            "city_not_allowed": city_not_allowed,
            "both_checks_failed": both_failed
        },
        "avg_distance_passed_km": sum(passed_distances) / len(passed_distances) if passed_distances else None,
        "avg_distance_failed_km": sum(failed_distances) / len(failed_distances) if failed_distances else None
    }
