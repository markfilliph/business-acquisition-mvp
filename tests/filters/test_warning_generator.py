"""
Unit tests for warning generation system.
Tests all warning types and edge cases.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.enrichment.warning_generator import generate_warnings, apply_warnings
from src.core.models import BusinessLead, RevenueEstimate, ContactInfo, LocationInfo


class TestHighVisibilityWarning:
    """Test HIGH_VISIBILITY warning for high review counts."""

    def test_warn_karma_candy_high_reviews(self):
        """Karma Candy (76 reviews) should get HIGH_VISIBILITY warning."""
        lead = BusinessLead(
            business_name="Karma Candy Inc",
            revenue_estimate=RevenueEstimate(estimated_amount=1_310_000),
            employee_count=16,
            review_count=76,
            contact=ContactInfo(),
            location=LocationInfo()
        )

        warnings = generate_warnings(lead)

        high_vis_warnings = [w for w in warnings if "HIGH_VISIBILITY" in w]
        assert len(high_vis_warnings) > 0
        assert "20+ reviews" in high_vis_warnings[0]

    def test_warn_ontario_ravioli_high_reviews(self):
        """Ontario Ravioli (73 reviews) should get HIGH_VISIBILITY warning."""
        lead_data = {
            'business_name': 'Ontario Ravioli',
            'revenue_estimate': 1_310_000,
            'employee_count': 16,
            'review_count': 73,
            'website': 'http://ontarioravioli.com/'
        }

        warnings = generate_warnings(lead_data)

        assert any("HIGH_VISIBILITY" in w for w in warnings)

    def test_no_warn_low_reviews(self):
        """Should not warn on businesses with <20 reviews."""
        lead_data = {
            'business_name': 'Abarth Machining',
            'revenue_estimate': 1_160_000,
            'employee_count': 10,
            'review_count': 3,
            'website': 'https://abarthmachining.com/'
        }

        warnings = generate_warnings(lead_data)

        assert not any("HIGH_VISIBILITY" in w for w in warnings)


class TestUpperRangeWarning:
    """Test UPPER_RANGE warning for revenue near cap."""

    def test_warn_karma_candy_upper_range(self):
        """Karma Candy ($1.31M) should get UPPER_RANGE warning."""
        lead_data = {
            'revenue_estimate': 1_310_000,
            'employee_count': 16
        }

        warnings = generate_warnings(lead_data)

        assert any("UPPER_RANGE" in w for w in warnings)
        assert any("$1.3M near $1.5M cap" in w for w in warnings)

    def test_warn_advantage_machining_upper_range(self):
        """Advantage Machining ($1.32M) should get UPPER_RANGE warning."""
        lead_data = {
            'revenue_estimate': 1_320_000,
            'employee_count': 16
        }

        warnings = generate_warnings(lead_data)

        assert any("UPPER_RANGE" in w for w in warnings)

    def test_no_warn_below_threshold(self):
        """Should not warn on revenue below $1.2M."""
        lead_data = {
            'revenue_estimate': 1_000_000,
            'employee_count': 10
        }

        warnings = generate_warnings(lead_data)

        assert not any("UPPER_RANGE" in w for w in warnings)


class TestVerifySizeWarning:
    """Test VERIFY_SIZE warning for employee + review mismatch."""

    def test_warn_karma_candy_verify_size(self):
        """Karma Candy (16 employees, 76 reviews) should get VERIFY_SIZE warning."""
        lead_data = {
            'employee_count': 16,
            'review_count': 76
        }

        warnings = generate_warnings(lead_data)

        verify_warnings = [w for w in warnings if "VERIFY_SIZE" in w]
        assert len(verify_warnings) > 0
        assert "location headcount only" in verify_warnings[0]

    def test_warn_ontario_ravioli_verify_size(self):
        """Ontario Ravioli (16 employees, 73 reviews) should get VERIFY_SIZE warning."""
        lead_data = {
            'employee_count': 16,
            'review_count': 73
        }

        warnings = generate_warnings(lead_data)

        assert any("VERIFY_SIZE" in w for w in warnings)

    def test_no_warn_low_employees_high_reviews(self):
        """Should not warn if employees <15 even with high reviews."""
        lead_data = {
            'employee_count': 10,
            'review_count': 50
        }

        warnings = generate_warnings(lead_data)

        # Should not trigger VERIFY_SIZE (employees must be >15)
        assert not any("VERIFY_SIZE" in w for w in warnings)

    def test_no_warn_high_employees_low_reviews(self):
        """Should not warn if reviews <20 even with high employees."""
        lead_data = {
            'employee_count': 20,
            'review_count': 10
        }

        warnings = generate_warnings(lead_data)

        # Should not trigger VERIFY_SIZE (reviews must be >20)
        assert not any("VERIFY_SIZE" in w for w in warnings)


class TestNoWebsiteWarning:
    """Test NO_WEBSITE warning."""

    def test_warn_no_website(self):
        """Should warn when website is missing."""
        lead_data = {
            'website': None
        }

        warnings = generate_warnings(lead_data)

        assert any("NO_WEBSITE" in w for w in warnings)

    def test_warn_na_website(self):
        """Should warn when website is 'N/A'."""
        lead_data = {
            'website': 'N/A'
        }

        warnings = generate_warnings(lead_data)

        assert any("NO_WEBSITE" in w for w in warnings)

    def test_no_warn_with_website(self):
        """Should not warn when website exists."""
        lead = BusinessLead(
            business_name="Test Business",
            contact=ContactInfo(website="https://example.com/"),
            location=LocationInfo()
        )

        warnings = generate_warnings(lead)

        assert not any("NO_WEBSITE" in w for w in warnings)


class TestBusinessAgeWarnings:
    """Test NEW_BUSINESS and ESTABLISHED warnings."""

    def test_warn_new_business(self):
        """Should warn for businesses <2 years old."""
        lead_data = {
            'years_in_business': 1
        }

        warnings = generate_warnings(lead_data)

        assert any("NEW_BUSINESS" in w for w in warnings)
        assert any("Less than 2 years old" in w for w in warnings)

    def test_warn_established_business(self):
        """Should warn for businesses >40 years old (succession opportunity)."""
        lead_data = {
            'years_in_business': 45
        }

        warnings = generate_warnings(lead_data)

        assert any("ESTABLISHED" in w for w in warnings)
        assert any("40+ years old" in w for w in warnings)

    def test_no_warn_normal_age(self):
        """Should not warn for businesses 2-40 years old."""
        lead_data = {
            'years_in_business': 25
        }

        warnings = generate_warnings(lead_data)

        # Should have no age-related warnings
        assert not any("NEW_BUSINESS" in w for w in warnings)
        assert not any("ESTABLISHED" in w for w in warnings)


class TestApplyWarnings:
    """Test applying warnings to BusinessLead objects."""

    def test_apply_warnings_to_lead(self):
        """Should add warnings to BusinessLead.warnings list."""
        lead = BusinessLead(
            business_name="Test Business",
            revenue_estimate=RevenueEstimate(estimated_amount=1_300_000),
            employee_count=16,
            review_count=50,
            contact=ContactInfo(),
            location=LocationInfo()
        )

        # Apply warnings
        lead = apply_warnings(lead)

        # Should have warnings
        assert len(lead.warnings) > 0
        # Should have HIGH_VISIBILITY and UPPER_RANGE at minimum
        assert any("HIGH_VISIBILITY" in w for w in lead.warnings)
        assert any("UPPER_RANGE" in w for w in lead.warnings)

    def test_clean_lead_no_warnings(self):
        """Clean lead should have no warnings."""
        lead = BusinessLead(
            business_name="Abarth Machining Inc",
            revenue_estimate=RevenueEstimate(estimated_amount=1_000_000),
            employee_count=10,
            review_count=3,
            contact=ContactInfo(website="https://abarthmachining.com/"),
            location=LocationInfo()
        )

        lead = apply_warnings(lead)

        assert len(lead.warnings) == 0


class TestMultipleWarnings:
    """Test leads that should trigger multiple warnings."""

    def test_karma_candy_three_warnings(self):
        """Karma Candy should trigger 3 warnings."""
        lead = BusinessLead(
            business_name="Karma Candy Inc",
            revenue_estimate=RevenueEstimate(estimated_amount=1_310_000),
            employee_count=16,
            review_count=76,
            contact=ContactInfo(website="http://www.karmacandy.ca/"),
            location=LocationInfo()
        )

        warnings = generate_warnings(lead)

        # Should have HIGH_VISIBILITY, UPPER_RANGE, VERIFY_SIZE
        assert len(warnings) == 3
        assert any("HIGH_VISIBILITY" in w for w in warnings)
        assert any("UPPER_RANGE" in w for w in warnings)
        assert any("VERIFY_SIZE" in w for w in warnings)

    def test_ontario_ravioli_three_warnings(self):
        """Ontario Ravioli should trigger 3 warnings."""
        lead = BusinessLead(
            business_name="Ontario Ravioli",
            revenue_estimate=RevenueEstimate(estimated_amount=1_310_000),
            employee_count=16,
            review_count=73,
            contact=ContactInfo(website="http://ontarioravioli.com/"),
            location=LocationInfo()
        )

        warnings = generate_warnings(lead)

        assert len(warnings) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
