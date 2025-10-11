"""
Acceptance tests for geographic gate enforcement.
These tests define the "Definition of Done" for strict geo gate enforcement.

Per validator requirements:
- ZERO businesses outside allowed cities should be exported
- ZERO businesses outside radius should be exported
- BOTH checks must pass for export (dual enforcement)
- All rejections must have clear reasons
"""

import pytest
from src.gates.geo_gate import geo_gate, get_rejection_summary
from src.core.config import config


class TestAcceptanceNoOutsideRadius:
    """Acceptance: Zero businesses outside radius exported."""

    def test_no_business_outside_radius_passes(self):
        """Test that NO business outside radius passes."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton", "Burlington", "Stoney Creek"]

        # Test various points outside radius
        outside_locations = [
            (45.4215, -75.6972, "Hamilton"),     # Ottawa coords, ~450km
            (43.6532, -79.3832, "Hamilton"),     # Toronto coords, ~70km
            (42.9849, -81.2453, "Hamilton"),     # London coords, ~120km
            (44.3894, -79.6903, "Hamilton"),     # Barrie coords, ~130km
        ]

        for lat, lon, city in outside_locations:
            result = geo_gate(
                latitude=lat,
                longitude=lon,
                city=city,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )

            # Should fail if outside radius (even with allowed city)
            if result.distance_km > radius_km:
                assert result.passes is False, (
                    f"ACCEPTANCE FAILURE: Business at ({lat}, {lon}) "
                    f"with distance {result.distance_km:.1f}km > {radius_km}km "
                    f"passed gate (should fail)"
                )

    def test_batch_outside_radius_all_fail(self):
        """Test that a batch of businesses outside radius all fail."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton"]

        # Create 50 businesses in a ring 100km from center
        results = []
        for i in range(50):
            # Points roughly 100km away in different directions
            lat_offset = 0.9 * (i % 10 - 5) / 5  # Vary latitude
            lon_offset = 0.9 * (i // 10 - 2.5) / 2.5  # Vary longitude

            result = geo_gate(
                latitude=center_lat + lat_offset,
                longitude=center_lon + lon_offset,
                city="Hamilton",
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )
            results.append(result)

        # Count passes (should be ZERO for those outside radius)
        outside_radius_results = [r for r in results if r.distance_km > radius_km]
        passed_count = sum(1 for r in outside_radius_results if r.passes)

        assert passed_count == 0, (
            f"ACCEPTANCE FAILURE: {passed_count}/{len(outside_radius_results)} "
            f"businesses outside radius passed gate (expected 0)"
        )


class TestAcceptanceNoDisallowedCities:
    """Acceptance: Zero businesses from disallowed cities exported."""

    def test_no_disallowed_city_passes(self):
        """Test that NO business from disallowed city passes."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 100  # Large radius so city is the limiting factor
        allowed_cities = ["Hamilton", "Burlington", "Stoney Creek"]

        # Test disallowed cities (even within radius)
        disallowed_cities = [
            "Toronto",
            "Mississauga",
            "Oakville",
            "Milton",
            "Waterloo",
            "Kitchener",
            "Guelph",
            "Cambridge"
        ]

        for city in disallowed_cities:
            # Use Hamilton coordinates (definitely within radius)
            result = geo_gate(
                latitude=center_lat,
                longitude=center_lon,
                city=city,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )

            assert result.passes is False, (
                f"ACCEPTANCE FAILURE: Business with disallowed city '{city}' "
                f"passed gate (should fail)"
            )
            assert result.within_radius is True, "Should be within radius"
            assert result.city_allowed is False, "City should not be allowed"

    def test_batch_disallowed_cities_all_fail(self):
        """Test that a batch of businesses with disallowed cities all fail."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 100
        allowed_cities = ["Hamilton", "Burlington"]

        # Create 100 businesses with disallowed cities
        disallowed_cities = [
            "Toronto", "Mississauga", "Oakville", "Milton", "Waterloo",
            "Kitchener", "Guelph", "Cambridge", "London", "Niagara Falls"
        ]

        results = []
        for i in range(100):
            city = disallowed_cities[i % len(disallowed_cities)]
            result = geo_gate(
                latitude=center_lat,
                longitude=center_lon,
                city=city,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )
            results.append(result)

        # Count passes (should be ZERO)
        passed_count = sum(1 for r in results if r.passes)

        assert passed_count == 0, (
            f"ACCEPTANCE FAILURE: {passed_count}/100 businesses with disallowed cities "
            f"passed gate (expected 0)"
        )


class TestAcceptanceDualEnforcement:
    """Acceptance: BOTH radius and city checks must pass."""

    def test_dual_enforcement_all_combinations(self):
        """Test all four combinations of radius/city checks."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton"]

        # Test all four combinations
        test_cases = [
            # (lat, lon, city, expected_passes, description)
            (43.2557, -79.8711, "Hamilton", True, "Inside radius + allowed city"),
            (43.2557, -79.8711, "Toronto", False, "Inside radius + disallowed city"),
            (45.4215, -75.6972, "Hamilton", False, "Outside radius + allowed city"),
            (45.4215, -75.6972, "Toronto", False, "Outside radius + disallowed city"),
        ]

        for lat, lon, city, expected_passes, description in test_cases:
            result = geo_gate(
                latitude=lat,
                longitude=lon,
                city=city,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )

            assert result.passes == expected_passes, (
                f"ACCEPTANCE FAILURE: {description} - "
                f"expected passes={expected_passes}, got passes={result.passes}"
            )

    def test_only_both_checks_passing_exports(self):
        """Test that ONLY businesses passing BOTH checks are exported."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton", "Burlington"]

        # Create mix of businesses
        test_businesses = [
            # Format: (lat, lon, city, should_pass)
            (43.2557, -79.8711, "Hamilton", True),      # Both pass
            (43.2557, -79.8711, "Burlington", True),    # Both pass
            (43.2557, -79.8711, "Toronto", False),      # City fails
            (45.4215, -75.6972, "Hamilton", False),     # Radius fails
            (45.4215, -75.6972, "Ottawa", False),       # Both fail
        ]

        results = []
        for lat, lon, city, should_pass in test_businesses:
            result = geo_gate(
                latitude=lat,
                longitude=lon,
                city=city,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )
            results.append((result, should_pass))

        # Verify each result matches expectation
        for result, expected_pass in results:
            assert result.passes == expected_pass, (
                f"ACCEPTANCE FAILURE: Business at ({result.city}) "
                f"expected passes={expected_pass}, got passes={result.passes}"
            )

        # Verify only 2 businesses passed
        passed_count = sum(1 for r, _ in results if r.passes)
        assert passed_count == 2, (
            f"ACCEPTANCE FAILURE: Expected exactly 2 businesses to pass, got {passed_count}"
        )


class TestAcceptanceRejectionReasons:
    """Acceptance: All rejections have clear reasons."""

    def test_all_rejections_have_reasons(self):
        """Test that all failed results have rejection reasons."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton"]

        # Create various failing scenarios
        failing_cases = [
            (45.4215, -75.6972, "Hamilton", "outside radius, allowed city"),
            (43.2557, -79.8711, "Toronto", "inside radius, disallowed city"),
            (45.4215, -75.6972, "Ottawa", "outside radius, disallowed city"),
        ]

        for lat, lon, city, description in failing_cases:
            result = geo_gate(
                latitude=lat,
                longitude=lon,
                city=city,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )

            assert result.passes is False, f"Case '{description}' should fail"
            assert result.rejection_reason is not None, (
                f"ACCEPTANCE FAILURE: Rejected business ({description}) "
                f"has no rejection reason"
            )
            assert len(result.rejection_reason) > 0, (
                f"ACCEPTANCE FAILURE: Rejected business ({description}) "
                f"has empty rejection reason"
            )

    def test_rejection_reasons_are_specific(self):
        """Test that rejection reasons are specific and actionable."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton"]

        # Outside radius case
        outside_result = geo_gate(
            latitude=45.4215,
            longitude=-75.6972,
            city="Hamilton",
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            allowed_cities=allowed_cities
        )
        assert "km" in outside_result.rejection_reason.lower()
        assert "radius" in outside_result.rejection_reason.lower()

        # Disallowed city case
        city_result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="Toronto",
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            allowed_cities=allowed_cities
        )
        assert "Toronto" in city_result.rejection_reason
        assert "allowed" in city_result.rejection_reason.lower()

    def test_rejection_reasons_include_values(self):
        """Test that rejection reasons include actual values."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton"]

        result = geo_gate(
            latitude=45.4215,
            longitude=-75.6972,
            city="Hamilton",
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            allowed_cities=allowed_cities
        )

        # Should mention the radius value
        assert "50" in result.rejection_reason


class TestAcceptanceGoldenTestCases:
    """Acceptance: Test against golden set of known good/bad cases."""

    def test_golden_good_case_1_hamilton_downtown(self):
        """Golden good case: Business in downtown Hamilton (should pass)."""
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

    def test_golden_good_case_2_burlington(self):
        """Golden good case: Business in Burlington (should pass)."""
        # Burlington City Hall coordinates
        result = geo_gate(
            latitude=43.3255,
            longitude=-79.7990,
            city="Burlington",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is True
        assert result.within_radius is True
        assert result.city_allowed is True

    def test_golden_good_case_3_stoney_creek(self):
        """Golden good case: Business in Stoney Creek (should pass)."""
        # Stoney Creek coordinates
        result = geo_gate(
            latitude=43.2229,
            longitude=-79.7441,
            city="Stoney Creek",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is True
        assert result.within_radius is True
        assert result.city_allowed is True

    def test_golden_bad_case_1_toronto(self):
        """Golden bad case: Business in Toronto (should fail - disallowed city)."""
        result = geo_gate(
            latitude=43.6532,
            longitude=-79.3832,
            city="Toronto",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=50,
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is False
        assert "Toronto" in result.rejection_reason

    def test_golden_bad_case_2_ottawa(self):
        """Golden bad case: Business in Ottawa (should fail - both checks)."""
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

    def test_golden_bad_case_3_mississauga(self):
        """Golden bad case: Business in Mississauga (should fail - city check)."""
        result = geo_gate(
            latitude=43.5890,
            longitude=-79.6441,
            city="Mississauga",
            center_lat=43.2557,
            center_lon=-79.8711,
            radius_km=100,  # Large radius
            allowed_cities=["Hamilton", "Burlington", "Stoney Creek"]
        )

        assert result.passes is False
        assert result.city_allowed is False


class TestAcceptanceCityNormalization:
    """Acceptance: City name variations are handled correctly."""

    def test_city_name_variations_accepted(self):
        """Test that various city name formats are accepted."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton"]

        # Various formats that should all match "Hamilton"
        city_variations = [
            "Hamilton",
            "hamilton",
            "HAMILTON",
            "Hamilton, ON",
            "Hamilton, Ontario",
            "Hamilton ON",
            "  Hamilton  ",
            "Hamilton  ,  ON",
        ]

        for city in city_variations:
            result = geo_gate(
                latitude=center_lat,
                longitude=center_lon,
                city=city,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
                allowed_cities=allowed_cities
            )

            assert result.passes is True, (
                f"ACCEPTANCE FAILURE: City variation '{city}' was not accepted "
                f"(should match 'Hamilton')"
            )
            assert result.city_allowed is True


class TestAcceptanceStatistics:
    """Acceptance: Validate rejection statistics are accurate."""

    def test_rejection_statistics_accuracy(self):
        """Test that rejection statistics accurately reflect results."""
        center_lat, center_lon = 43.2557, -79.8711
        radius_km = 50
        allowed_cities = ["Hamilton", "Burlington"]

        # Create known distribution
        results = [
            geo_gate(43.2557, -79.8711, "Hamilton", center_lat, center_lon, radius_km, allowed_cities),  # Pass
            geo_gate(43.2557, -79.8711, "Burlington", center_lat, center_lon, radius_km, allowed_cities),  # Pass
            geo_gate(43.6532, -79.3832, "Toronto", center_lat, center_lon, radius_km, allowed_cities),  # Fail: both (outside radius AND city)
            geo_gate(45.4215, -75.6972, "Hamilton", center_lat, center_lon, radius_km, allowed_cities),  # Fail: radius
            geo_gate(45.4215, -75.6972, "Ottawa", center_lat, center_lon, radius_km, allowed_cities),  # Fail: both
            geo_gate(43.2557, -79.8711, "Hamilton", center_lat, center_lon, radius_km, allowed_cities),  # Pass
        ]

        summary = get_rejection_summary(results)

        assert summary["total_checked"] == 6
        assert summary["passed"] == 3
        assert summary["failed"] == 3
        assert summary["pass_rate"] == 0.5
        assert summary["rejection_rate"] == 0.5

        # Check specific rejection reasons
        assert summary["rejections_by_reason"]["outside_radius"] >= 2
        assert summary["rejections_by_reason"]["city_not_allowed"] >= 2
        assert summary["rejections_by_reason"]["both_checks_failed"] >= 2


class TestAcceptanceConfigDefaults:
    """Acceptance: Test that config defaults are used correctly."""

    def test_uses_config_defaults_correctly(self):
        """Test that geo gate uses config defaults when not specified."""
        # This test uses actual config values
        # Should not raise any errors and should use config.ALLOWED_CITIES etc.
        result = geo_gate(
            latitude=43.2557,
            longitude=-79.8711,
            city="Hamilton"
        )

        # Result should have valid distance and city
        assert result.distance_km is not None
        assert result.city is not None
        assert isinstance(result.passes, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
