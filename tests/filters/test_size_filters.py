"""
Unit tests for size filtering.
Tests revenue caps, employee caps, and edge cases.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.filters.size_filters import filter_by_size, check_revenue_fit, check_employee_fit
from src.core.models import BusinessLead, RevenueEstimate, ContactInfo, LocationInfo


class TestSizeFilters:
    """Test size filtering logic."""

    def test_exclude_oversized_revenue_vp_expert(self):
        """VP Expert Machining should be excluded (revenue $2.0M > $1.5M cap)."""
        lead_data = {
            'revenue_estimate': 2_000_000,
            'employee_count': 28
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True
        assert "2.0M exceeds" in reason
        assert "$1.4M cap" in reason or "$1.5M cap" in reason

    def test_exclude_oversized_revenue_welsh(self):
        """Welsh Industrial should be excluded (revenue $2.0M > $1.5M cap)."""
        lead_data = {
            'revenue_estimate': 1_990_000,
            'employee_count': 28
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True
        assert "exceeds" in reason

    def test_exclude_oversized_revenue_stoney_creek(self):
        """Stoney Creek Machine should be excluded (revenue $1.9M > $1.5M cap)."""
        lead_data = {
            'revenue_estimate': 1_880_000,
            'employee_count': 28
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True
        assert "1.9M" in reason or "1.8M" in reason

    def test_exclude_oversized_employees(self):
        """Should exclude if >25 employees."""
        lead_data = {
            'revenue_estimate': 1_000_000,
            'employee_count': 26  # 26 > 25 cap
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True
        assert "26 employees" in reason
        assert "25 employee cap" in reason

    def test_allow_target_range_abarth(self):
        """Abarth Machining should pass (revenue $1.16M, 16 employees)."""
        lead = BusinessLead(
            business_name="Abarth Machining Inc",
            revenue_estimate=RevenueEstimate(estimated_amount=1_160_000),
            employee_count=16,
            contact=ContactInfo(),
            location=LocationInfo()
        )

        excluded, reason = filter_by_size(lead)

        assert excluded is False
        assert reason == "PASSED"

    def test_allow_target_range_stolk(self):
        """Stolk Machine Shop should pass (revenue $1.16M, 16 employees)."""
        lead_data = {
            'revenue_estimate': 1_160_000,
            'employee_count': 16
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is False
        assert reason == "PASSED"

    def test_allow_upper_edge_advantage(self):
        """Advantage Machining should pass (revenue $1.32M near cap)."""
        lead_data = {
            'revenue_estimate': 1_320_000,
            'employee_count': 16
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is False
        assert reason == "PASSED"

    def test_allow_lower_edge(self):
        """Should allow revenue at lower edge of range."""
        lead_data = {
            'revenue_estimate': 800_000,
            'employee_count': 5
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is False

    def test_allow_exactly_at_cap(self):
        """Should allow revenue exactly at $1.5M cap (filter checks > not >=)."""
        lead_data = {
            'revenue_estimate': 1_500_000,  # Exactly at $1.5M cap
            'employee_count': 25  # Exactly at 25 employee cap
        }

        excluded, reason = filter_by_size(lead_data)

        # At exactly the cap (not over), should pass (filter checks > not >=)
        assert excluded is False

    def test_exclude_just_over_cap(self):
        """Should exclude revenue just over $1.5M cap."""
        lead_data = {
            'revenue_estimate': 1_500_001,
            'employee_count': 20
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True

    def test_no_revenue_data(self):
        """Should allow leads with no revenue data (pass to manual review)."""
        lead_data = {
            'revenue_estimate': None,
            'employee_count': 10
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is False

    def test_no_employee_data(self):
        """Should allow leads with no employee data."""
        lead_data = {
            'revenue_estimate': 1_000_000,
            'employee_count': None
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is False


class TestRevenueChecks:
    """Test revenue fit checking."""

    def test_revenue_in_range(self):
        """$1.2M revenue should fit target range."""
        fits, reason = check_revenue_fit(1_200_000)

        assert fits is True
        assert "fits target range" in reason

    def test_revenue_below_range(self):
        """$500K revenue should be below minimum."""
        fits, reason = check_revenue_fit(500_000)

        assert fits is False
        assert "below minimum" in reason

    def test_revenue_above_range(self):
        """$2.0M revenue should be above maximum."""
        fits, reason = check_revenue_fit(2_000_000)

        assert fits is False
        assert "above maximum" in reason


class TestEmployeeChecks:
    """Test employee count fit checking."""

    def test_employee_in_range(self):
        """15 employees should fit target range."""
        fits, reason = check_employee_fit(15)

        assert fits is True
        assert "fits target range" in reason

    def test_employee_below_range(self):
        """2 employees should be below minimum."""
        fits, reason = check_employee_fit(2)

        assert fits is False
        assert "below minimum" in reason

    def test_employee_above_range(self):
        """50 employees should be above maximum."""
        fits, reason = check_employee_fit(50)

        assert fits is False
        assert "above maximum" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
