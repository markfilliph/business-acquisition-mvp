"""
Tests for geographic gate enforcement.
Validates that geo gate enforces dual requirements: radius AND city allowlist.
"""

import pytest
from src.gates.geo_gate import (
    geo_gate,
    haversine_distance,
    normalize_city_name,
    validate_coordinates,
    get_rejection_summary,
    GeoGateResult
)
from src.core.config import config


class TestHaversineDistance:
    """Test haversine distance calculation."""

    def test_hamilton_to_toronto_distance(self):
        """Test distance from Hamilton to Toronto (~59km)."""
        # Hamilton coordinates
        hamilton_lat, hamilton_lon = 43.2557, -79.8711
        # Toronto coordinates
        toronto_lat, toronto_lon = 43.6532, -79.3832

        distance = haversine_distance(
            hamilton_lat, hamilton_lon,
            toronto_lat, toronto_lon
        )

        # Should be approximately 59km
        assert 55 < distance < 65, f"Expected ~59km, got {distance:.2f}km"

    def test_zero_distance_same_point(self):
        """Test that distance between same point is zero."""
        lat, lon = 43.2557, -79.8711
        distance = haversine_distance(lat, lon, lat, lon)

        assert distance == 0.0

    def test_distance_symmetry(self):
        """Test that distance(A,B) == distance(B,A)."""
        lat1, lon1 = 43.2557, -79.8711
        lat2, lon2 = 43.6532, -79.3832

        distance_ab = haversine_distance(lat1, lon1, lat2, lon2)
        distance_ba = haversine_distance(lat2, lon2, lat1, lon1)

        assert abs(distance_ab - distance_ba) < 0.001

    def test_hamilton_to_ottawa_distance(self):
        """Test distance from Hamilton to Ottawa (~450km)."""
        hamilton_lat, hamilton_lon = 43.2557, -79.8711
        ottawa_lat, ottawa_lon = 45.4215, -75.6972

        distance = haversine_distance(
            hamilton_lat, hamilton_lon,
            ottawa_lat, ottawa_lon
        )

        # Should be approximately 450km
        assert 400 < distance < 500, f"Expected ~450km, got {distance:.2f}km"


class TestNormalizeCityName:
    """Test city name normalization."""

    def test_basic_normalization(self):
        """Test basic lowercase and strip."""
        assert normalize_city_name("Hamilton") == "hamilton"
        assert normalize_city_name("  Hamilton  ") == "hamilton"
        assert normalize_city_name("HAMILTON") == "hamilton"

    def test_remove_ontario_suffix(self):
        """Test removal of Ontario suffixes."""
        assert normalize_city_name("Hamilton, ON") == "hamilton"
        assert normalize_city_name("Hamilton, Ontario") == "hamilton"
        assert normalize_city_name("Hamilton ON") == "hamilton"
        assert normalize_city_name("Hamilton Ontario") == "hamilton"

    def test_multi_word_cities(self):
        """Test multi-word city names."""
        assert normalize_city_name("Stoney Creek") == "stoney creek"
        assert normalize_city_name("  Stoney Creek, ON  ") == "stoney creek"

    def test_extra_whitespace_removal(self):
        """Test that extra whitespace is collapsed."""
        assert normalize_city_name("Hamilton  City") == "hamilton city"
        assert normalize_city_name("  Stoney   Creek  ") == "stoney creek"

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert normalize_city_name("") == ""
        assert normalize_city_name("   ") == ""


class TestValidateCoordinates:
    """Test coordinate validation."""

    def test_valid_hamilton_coordinates(self):
        """Test that Hamilton coordinates are valid."""
        valid, error = validate_coordinates(43.2557, -79.8711)

        assert valid is True
        assert error is None

    def test_invalid_latitude_too_high(self):
        """Test that latitude > 90 is invalid."""
        valid, error = validate_coordinates(91.0, -79.8711)

        assert valid is False
        assert "latitude" in error.lower()

    def test_invalid_latitude_too_low(self):
        """Test that latitude < -90 is invalid."""
        valid, error = validate_coordinates(-91.0, -79.8711)

        assert valid is False
        assert "latitude" in error.lower()

    def test_invalid_longitude_too_high(self):
        """Test that longitude > 180 is invalid."""
        valid, error = validate_coordinates(43.2557, 181.0)

        assert valid is False
        assert "longitude" in error.lower()

    def test_invalid_longitude_too_low(self):
        """Test that longitude < -180 is invalid."""
        valid, error = validate_coordinates(43.2557, -181.0)

        assert valid is False
        assert "longitude" in error.lower()

    def test_boundary_coordinates_valid(self):
        """Test that boundary coordinates are valid."""
        # North pole
        assert validate_coordinates(90.0, 0.0)[0] is True
        # South pole
        assert validate_coordinates(-90.0, 0.0)[0] is True
        # Antimeridian
        assert validate_coordinates(0.0, 180.0)[0] is True
        assert validate_coordinates(0.0, -180.0)[0] is True


class TestGeoGateBasics:
    """Test basic geo gate functionality."""

    def test_inside_radius_allowed_city_passes(self):
        """Test that business inside radius + allowed city passes."""
        # Hamilton coordinates (center), "Hamilton" city
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="Hamilton",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is True
        assert result.within_radius is True
        assert result.city_allowed is True
        assert result.rejection_reason is None

    def test_inside_radius_disallowed_city_fails(self):
        """Test that business inside radius but disallowed city fails."""
        # Near Hamilton but labeled as Toronto
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="Toronto",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is False
        assert result.within_radius is True
        assert result.city_allowed is False
        assert "not in allowed list" in result.rejection_reason

    def test_outside_radius_allowed_city_fails(self):
        """Test that business outside radius but allowed city fails."""
        # Ottawa coordinates but labeled as Hamilton
        result = geo_gate(
            latitude=45.4215,
            longitude=-75.6972,
            city="Hamilton",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is False
        assert result.within_radius is False
        assert result.city_allowed is True
        assert "outside radius" in result.rejection_reason.lower()

    def test_outside_radius_disallowed_city_fails(self):
        """Test that business outside radius + disallowed city fails."""
        # Ottawa coordinates labeled as Ottawa
        result = geo_gate(
            latitude=45.4215,
            longitude=-75.6972,
            city="Ottawa",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is False
        assert result.within_radius is False
        assert result.city_allowed is False
        assert "outside radius" in result.rejection_reason.lower()
        assert "not in allowed list" in result.rejection_reason.lower()


class TestGeoGateConfigDefaults:
    """Test that geo gate uses config defaults correctly."""

    def test_uses_config_defaults(self):
        """Test that geo gate uses config defaults when not specified."""
        # Use config defaults
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="Hamilton"
        )

        # Should use config.GEO_CENTER_LAT, GEO_CENTER_LNG, GEO_RADIUS_KM, ALLOWED_CITIES
        assert result.distance_km is not None
        assert result.city is not None


class TestGeoGateCityNormalization:
    """Test that geo gate handles city name variations."""

    def test_city_with_ontario_suffix_matches(self):
        """Test that 'Hamilton, ON' matches 'Hamilton' in allowlist."""
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="Hamilton, ON",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington"]
        )

        assert result.passes is True
        assert result.city_allowed is True

    def test_uppercase_city_matches(self):
        """Test that 'HAMILTON' matches 'Hamilton' in allowlist."""
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="HAMILTON",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington"]
        )

        assert result.passes is True
        assert result.city_allowed is True

    def test_whitespace_variations_match(self):
        """Test that '  Hamilton  ' matches 'Hamilton' in allowlist."""
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="  Hamilton  ",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington"]
        )

        assert result.passes is True
        assert result.city_allowed is True


class TestGeoGateRejectionReasons:
    """Test that rejection reasons are specific and actionable."""

    def test_radius_rejection_includes_distance(self):
        """Test that radius rejection includes actual distance."""
        result = geo_gate(
            latitude=45.4215,
            longitude=-75.6972,
            city="Hamilton",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton"]
        )

        assert result.passes is False
        assert result.rejection_reason is not None
        # Should mention distance and radius
        assert "km" in result.rejection_reason.lower()
        assert "50" in result.rejection_reason

    def test_city_rejection_includes_city_name(self):
        """Test that city rejection includes city name."""
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="Toronto",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington"]
        )

        assert result.passes is False
        assert "Toronto" in result.rejection_reason

    def test_both_checks_failed_mentions_both(self):
        """Test that rejection reason mentions both failures."""
        result = geo_gate(
            latitude=45.4215,
            longitude=-75.6972,
            city="Ottawa",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington"]
        )

        assert result.passes is False
        assert "outside radius" in result.rejection_reason.lower()
        assert "not in allowed list" in result.rejection_reason.lower()


class TestGeoGateEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_at_radius_boundary_passes(self):
        """Test that business exactly at radius boundary passes."""
        # Calculate a point exactly 50km away
        center_lat, center_lon = 43.2557, -79.8711
        # Move roughly 50km north (0.45 degrees latitude ≈ 50km)
        boundary_lat = center_lat + 0.45
        boundary_lon = center_lon

        result = geo_gate(
            latitude=boundary_lat,
            longitude=boundary_lon,
            city="Hamilton",
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=50,
            allowed_cities=["Hamilton"]
        )

        # Should pass (distance <= radius)
        assert result.distance_km is not None
        # Allow small floating point variance
        assert result.distance_km <= 51

    def test_just_outside_radius_fails(self):
        """Test that business just outside radius fails."""
        center_lat, center_lon = 43.2557, -79.8711
        # Move roughly 51km north
        outside_lat = center_lat + 0.46
        outside_lon = center_lon

        result = geo_gate(
            latitude=outside_lat,
            longitude=outside_lon,
            city="Hamilton",
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=50,
            allowed_cities=["Hamilton"]
        )

        # Should fail (distance > radius)
        assert result.within_radius is False


class TestGeoGateResult:
    """Test GeoGateResult dataclass."""

    def test_result_to_dict(self):
        """Test that result converts to dict correctly."""
        result = GeoGateResult(
            passes=True,
            within_radius=True,
            city_allowed=True,
            distance_km=25.5,
            city="Hamilton",
            rejection_reason=None
        )

        result_dict = result.to_dict()

        assert result_dict["passes"] is True
        assert result_dict["within_radius"] is True
        assert result_dict["city_allowed"] is True
        assert result_dict["distance_km"] == 25.5
        assert result_dict["city"] == "Hamilton"
        assert result_dict["rejection_reason"] is None

    def test_failed_result_to_dict(self):
        """Test that failed result converts to dict with reason."""
        result = GeoGateResult(
            passes=False,
            within_radius=False,
            city_allowed=True,
            distance_km=75.0,
            city="Hamilton",
            rejection_reason="Outside radius: 75.0km > 50km"
        )

        result_dict = result.to_dict()

        assert result_dict["passes"] is False
        assert result_dict["rejection_reason"] == "Outside radius: 75.0km > 50km"


class TestRejectionSummary:
    """Test rejection summary statistics."""

    def test_all_passed_summary(self):
        """Test summary when all results pass."""
        results = [
            geo_gate(43.2557, -79.8711, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"]),
            geo_gate(43.2557, -79.8711, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"]),
            geo_gate(43.2557, -79.8711, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"])
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 3
        assert summary["passed"] == 3
        assert summary["failed"] == 0
        assert summary["pass_rate"] == 1.0
        assert summary["rejection_rate"] == 0.0

    def test_all_failed_summary(self):
        """Test summary when all results fail."""
        results = [
            geo_gate(45.4215, -75.6972, "Ottawa", 43.2557, -79.8711, 50, ["Hamilton"]),
            geo_gate(43.6532, -79.3832, "Toronto", 43.2557, -79.8711, 50, ["Hamilton"]),
            geo_gate(43.2557, -79.8711, "Mississauga", 43.2557, -79.8711, 50, ["Hamilton"])
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 3
        assert summary["passed"] == 0
        assert summary["failed"] == 3
        assert summary["pass_rate"] == 0.0
        assert summary["rejection_rate"] == 1.0

    def test_mixed_results_summary(self):
        """Test summary with mixed pass/fail results."""
        results = [
            geo_gate(43.2557, -79.8711, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"]),  # Pass
            geo_gate(45.4215, -75.6972, "Ottawa", 43.2557, -79.8711, 50, ["Hamilton"]),    # Fail: radius + city
            geo_gate(43.6532, -79.3832, "Toronto", 43.2557, -79.8711, 100, ["Hamilton"]),  # Fail: city only
            geo_gate(43.2557, -79.8711, "Burlington", 43.2557, -79.8711, 50, ["Hamilton", "Burlington"])  # Pass
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 4
        assert summary["passed"] == 2
        assert summary["failed"] == 2
        assert summary["pass_rate"] == 0.5
        assert summary["rejection_rate"] == 0.5

    def test_rejection_reason_categorization(self):
        """Test that rejections are categorized by reason."""
        results = [
            geo_gate(43.2557, -79.8711, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"]),  # Pass
            geo_gate(45.4215, -75.6972, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"]),  # Fail: outside radius
            geo_gate(43.2557, -79.8711, "Toronto", 43.2557, -79.8711, 50, ["Hamilton"]),   # Fail: city not allowed
            geo_gate(45.4215, -75.6972, "Ottawa", 43.2557, -79.8711, 50, ["Hamilton"])     # Fail: both
        ]

        summary = get_rejection_summary(results)

        assert summary["rejections_by_reason"]["outside_radius"] >= 1
        assert summary["rejections_by_reason"]["city_not_allowed"] >= 1
        assert summary["rejections_by_reason"]["both_checks_failed"] >= 1

    def test_average_distance_calculation(self):
        """Test that average distances are calculated correctly."""
        results = [
            geo_gate(43.2557, -79.8711, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"]),  # 0km, pass
            geo_gate(43.3, -79.8711, "Hamilton", 43.2557, -79.8711, 50, ["Hamilton"]),     # ~5km, pass
            geo_gate(45.4215, -75.6972, "Ottawa", 43.2557, -79.8711, 50, ["Hamilton"])     # ~450km, fail
        ]

        summary = get_rejection_summary(results)

        assert summary["avg_distance_passed_km"] is not None
        assert summary["avg_distance_passed_km"] < 10  # Average of 0 and ~5
        assert summary["avg_distance_failed_km"] is not None
        assert summary["avg_distance_failed_km"] > 400  # ~450km

    def test_empty_results_summary(self):
        """Test summary with empty results list."""
        results = []
        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 0
        assert summary["pass_rate"] == 0.0
        assert summary["rejection_rate"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
