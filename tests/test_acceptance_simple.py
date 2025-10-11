"""
Simplified acceptance tests for production readiness.
These tests verify the critical "Definition of Done" criteria.

PRIORITY: P1 - Critical for production deployment.
"""

import pytest
from src.gates.category_gate import category_gate, REVIEW_REQUIRED_CATEGORIES
from src.gates.revenue_gate import revenue_gate
from src.gates.geo_gate import geo_gate
from src.core.models import LeadStatus


@pytest.mark.acceptance
class TestDefinitionOfDone:
    """Critical acceptance tests for production readiness."""

    def test_borderline_categories_require_human_review(self):
        """
        ACCEPTANCE CRITERION 1: Borderline categories must be flagged for human review.

        This ensures quality control on edge cases like funeral homes,
        franchise offices, etc.
        """
        # All borderline categories should be flagged
        for category in REVIEW_REQUIRED_CATEGORIES:
            result = category_gate(category)

            assert result.requires_review is True, \
                f"Borderline category '{category}' not flagged for review"
            assert result.suggested_status == LeadStatus.REVIEW_REQUIRED, \
                f"Borderline category '{category}' has wrong suggested status: {result.suggested_status}"
            assert result.passes is False, \
                f"Borderline category '{category}' incorrectly auto-passed"

        # Verify at least 10 borderline categories exist
        assert len(REVIEW_REQUIRED_CATEGORIES) >= 10, \
            f"Should have at least 10 borderline categories, got {len(REVIEW_REQUIRED_CATEGORIES)}"

    def test_low_revenue_confidence_blocked(self):
        """
        ACCEPTANCE CRITERION 2: Low revenue confidence must be blocked.

        Threshold is 0.6 (60%). Below this, businesses must be rejected
        regardless of other factors.
        """
        # Test with confidence below threshold
        result = revenue_gate(confidence=0.5, staff_count=50)

        assert result.passes is False, \
            "Business with 50% confidence incorrectly passed revenue gate"
        assert "confidence" in result.rejection_reason.lower(), \
            f"Rejection reason should mention confidence: {result.rejection_reason}"

    def test_high_confidence_requires_evidence(self):
        """
        ACCEPTANCE CRITERION 3: High confidence alone is not sufficient.

        Must have either staff_count or benchmark_match as supporting evidence.
        """
        # High confidence but no supporting evidence
        result = revenue_gate(confidence=0.8, staff_count=None, benchmark_match=False)

        assert result.passes is False, \
            "High confidence without evidence incorrectly passed revenue gate"
        assert ("staff" in result.rejection_reason.lower() or
                "benchmark" in result.rejection_reason.lower() or
                "signal" in result.rejection_reason.lower()), \
            f"Rejection reason should mention missing evidence: {result.rejection_reason}"

    def test_valid_revenue_data_passes(self):
        """
        ACCEPTANCE CRITERION 4: Valid revenue data passes gate.

        Confidence >= 0.6 + staff_count OR benchmark_match should pass.
        """
        # Test with staff signal
        result1 = revenue_gate(confidence=0.7, staff_count=15)
        assert result1.passes is True, \
            "Valid business (70% confidence + 15 staff) failed revenue gate"

        # Test with benchmark match
        result2 = revenue_gate(confidence=0.65, benchmark_match=True)
        assert result2.passes is True, \
            "Valid business (65% confidence + benchmark match) failed revenue gate"

    def test_allowed_cities_pass_geo_gate(self):
        """
        ACCEPTANCE CRITERION 5: Businesses in allowed cities pass geo gate.

        Hamilton area cities should pass when within radius.
        """
        # Coordinates near Hamilton
        hamilton_lat, hamilton_lon = 43.2557, -79.8711

        # Test all allowed cities
        allowed_cities = ["Hamilton", "Ancaster", "Dundas", "Stoney Creek", "Waterdown"]

        for city in allowed_cities:
            result = geo_gate(
                latitude=hamilton_lat,
                longitude=hamilton_lon,
                city=city
            )

            assert result.passes is True, \
                f"Business in allowed city '{city}' failed geo gate"

    def test_disallowed_cities_blocked(self):
        """
        ACCEPTANCE CRITERION 6: Businesses outside allowed cities blocked.

        Cities not in the allowlist should be rejected.
        """
        # Coordinates don't matter if city is not allowed
        hamilton_lat, hamilton_lon = 43.2557, -79.8711

        # Test cities that should be blocked
        blocked_cities = ["Toronto", "Mississauga", "Burlington", "Oakville"]

        for city in blocked_cities:
            result = geo_gate(
                latitude=hamilton_lat,
                longitude=hamilton_lon,
                city=city
            )

            assert result.passes is False, \
                f"Business in disallowed city '{city}' incorrectly passed geo gate"
            assert "city" in result.rejection_reason.lower(), \
                f"Rejection reason should mention city: {result.rejection_reason}"

    def test_manufacturing_passes_category_gate(self):
        """
        ACCEPTANCE CRITERION 7: Target industries pass category gate.

        Manufacturing and related industries should pass automatically.
        """
        target_industries = [
            "manufacturing",
            "industrial",
            "fabrication",
            "printing"
        ]

        for industry in target_industries:
            result = category_gate(industry)

            assert result.passes is True, \
                f"Target industry '{industry}' failed category gate"
            assert result.requires_review is False, \
                f"Target industry '{industry}' incorrectly requires review"

    def test_no_auto_pass_for_edge_cases(self):
        """
        ACCEPTANCE CRITERION 8: Edge cases never auto-qualify.

        Funeral homes, franchise offices, etc. must go through review.
        """
        edge_cases = [
            "funeral_home",
            "franchise_office",
            "real_estate_agent",
            "insurance_agent"
        ]

        for category in edge_cases:
            result = category_gate(category)

            # Must not auto-pass
            assert not (result.passes is True and result.requires_review is False), \
                f"Edge case '{category}' incorrectly auto-qualified"

            # Should be flagged for review
            assert result.requires_review is True, \
                f"Edge case '{category}' not flagged for review"


@pytest.mark.acceptance
class TestGatesIndependence:
    """Verify that gates enforce criteria independently."""

    def test_revenue_gate_independent_of_category(self):
        """
        ACCEPTANCE: Revenue gate enforces regardless of category.

        Low confidence fails even for perfect categories.
        """
        # Perfect category, bad revenue
        category_result = category_gate("manufacturing")
        revenue_result = revenue_gate(confidence=0.3)

        assert category_result.passes is True
        assert revenue_result.passes is False

    def test_geo_gate_independent_of_revenue(self):
        """
        ACCEPTANCE: Geo gate enforces regardless of revenue.

        Wrong location fails even with perfect revenue.
        """
        # Perfect revenue, wrong location
        revenue_result = revenue_gate(confidence=0.9, staff_count=50)
        geo_result = geo_gate(
            latitude=43.6532,  # Toronto
            longitude=-79.3832,
            city="Toronto"
        )

        assert revenue_result.passes is True
        assert geo_result.passes is False

    def test_all_gates_must_pass(self):
        """
        ACCEPTANCE: A business must pass ALL gates to qualify.

        Failing any single gate disqualifies the business.
        """
        # Pass all gates
        category_pass = category_gate("manufacturing")
        revenue_pass = revenue_gate(confidence=0.8, staff_count=20)
        geo_pass = geo_gate(43.2557, -79.8711, "Hamilton")

        assert category_pass.passes is True
        assert revenue_pass.passes is True
        assert geo_pass.passes is True

        # Fail geo gate
        geo_fail = geo_gate(43.6532, -79.3832, "Toronto")
        assert geo_fail.passes is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "acceptance"])
