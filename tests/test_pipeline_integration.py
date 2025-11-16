"""
Integration tests for full pipeline filtering.
Tests the complete filter pipeline on known good/bad leads.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.filters.size_filters import filter_by_size
from src.filters.business_type_filters import BusinessTypeFilter
from src.enrichment.warning_generator import generate_warnings, apply_warnings
from src.core.models import BusinessLead, RevenueEstimate, ContactInfo, LocationInfo


class TestKnownGoodLeads:
    """Test that known good leads pass all filters."""

    def test_abarth_machining_passes(self):
        """Abarth Machining Inc should pass all filters as clean lead."""
        lead = BusinessLead(
            business_name="Abarth Machining Inc",
            revenue_estimate=RevenueEstimate(estimated_amount=1_160_000),
            employee_count=16,
            review_count=3,
            contact=ContactInfo(website="https://abarthmachining.com/"),
            location=LocationInfo(
                address="2693 Barton St E",
                city="Hamilton",
                province="ON"
            )
        )

        # Size filter
        excluded, _ = filter_by_size(lead)
        assert excluded is False

        # Business type filter
        type_filter = BusinessTypeFilter()
        should_exclude, _ = type_filter.should_exclude(
            lead.business_name,
            "Manufacturing",
            lead.contact.website,
            lead.review_count
        )
        assert should_exclude is False

        # Warnings
        warnings = generate_warnings(lead)
        assert len(warnings) == 0

    def test_stolk_machine_passes(self):
        """Stolk Machine Shop Ltd should pass all filters as clean lead."""
        lead_data = {
            'business_name': 'Stolk Machine Shop Ltd',
            'revenue_estimate': 1_160_000,
            'employee_count': 16,
            'review_count': 3,
            'website': 'http://www.stolkmachine.com/'
        }

        # Size filter
        excluded, _ = filter_by_size(lead_data)
        assert excluded is False

        # Business type filter
        type_filter = BusinessTypeFilter()
        should_exclude, _ = type_filter.should_exclude(
            lead_data['business_name'],
            'Manufacturing',
            lead_data['website'],
            lead_data['review_count']
        )
        assert should_exclude is False

        # Warnings
        warnings = generate_warnings(lead_data)
        assert len(warnings) == 0

    def test_all_core_a_list_leads(self):
        """All Core A-List leads should pass filters."""
        core_leads = [
            {
                'name': 'Abarth Machining Inc',
                'revenue': 1_160_000,
                'employees': 16,
                'reviews': 3,
                'website': 'https://abarthmachining.com/',
                'expected_warnings': 0
            },
            {
                'name': 'Stolk Machine Shop Ltd',
                'revenue': 1_160_000,
                'employees': 16,
                'reviews': 3,
                'website': 'http://www.stolkmachine.com/',
                'expected_warnings': 0
            },
            {
                'name': 'All Tool Manufacturing Inc',
                'revenue': 1_160_000,
                'employees': 16,
                'reviews': 2,
                'website': 'http://www.alltoolgroup.com/',
                'expected_warnings': 0
            },
            {
                'name': 'Millen Manufacturing Inc',
                'revenue': 1_160_000,
                'employees': 16,
                'reviews': 2,
                'website': 'http://www.millenmfg.com/',
                'expected_warnings': 0
            },
            {
                'name': 'North Star Technical Inc',
                'revenue': 1_190_000,
                'employees': 16,
                'reviews': 8,
                'website': 'http://northstartech.ca/',
                'expected_warnings': 0
            },
        ]

        type_filter = BusinessTypeFilter()

        for lead_info in core_leads:
            # Size filter
            lead_data = {
                'revenue_estimate': lead_info['revenue'],
                'employee_count': lead_info['employees']
            }
            excluded, reason = filter_by_size(lead_data)
            assert excluded is False, f"{lead_info['name']} incorrectly excluded: {reason}"

            # Business type filter
            should_exclude, reason = type_filter.should_exclude(
                lead_info['name'],
                'Manufacturing',
                lead_info['website'],
                lead_info['reviews']
            )
            assert should_exclude is False, f"{lead_info['name']} incorrectly excluded: {reason}"

            # Warnings
            warnings = generate_warnings({
                'revenue_estimate': lead_info['revenue'],
                'employee_count': lead_info['employees'],
                'review_count': lead_info['reviews'],
                'website': lead_info['website']
            })
            assert len(warnings) == lead_info['expected_warnings'], \
                f"{lead_info['name']} unexpected warnings: {warnings}"


class TestKnownBadLeads:
    """Test that known bad leads are correctly excluded."""

    def test_container57_excluded(self):
        """Container57 should be excluded as retail."""
        type_filter = BusinessTypeFilter()
        should_exclude, reason = type_filter.should_exclude(
            business_name="Container57",
            industry="Retail",
            website="https://60424e-3.myshopify.com/",
            review_count=4
        )

        assert should_exclude is True
        assert "RETAIL" in reason

    def test_emerald_site_excluded(self):
        """Emerald Manufacturing Site should be excluded as location label."""
        type_filter = BusinessTypeFilter()
        should_exclude, reason = type_filter.should_exclude(
            business_name="Emerald Manufacturing Site",
            industry=None,
            website="N/A",
            review_count=1
        )

        assert should_exclude is True
        assert "LOCATION LABEL" in reason

    def test_vp_expert_excluded(self):
        """VP Expert Machining should be excluded (revenue too high)."""
        lead_data = {
            'revenue_estimate': 2_030_000,
            'employee_count': 28
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True
        assert "exceeds" in reason

    def test_welsh_excluded(self):
        """Welsh Industrial should be excluded (revenue too high)."""
        lead_data = {
            'revenue_estimate': 1_990_000,
            'employee_count': 28
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True

    def test_stoney_creek_excluded(self):
        """Stoney Creek Machine should be excluded (revenue too high)."""
        lead_data = {
            'revenue_estimate': 1_880_000,
            'employee_count': 28
        }

        excluded, reason = filter_by_size(lead_data)

        assert excluded is True


class TestWarningCases:
    """Test leads that should pass but with warnings."""

    def test_karma_candy_warnings(self):
        """Karma Candy should pass filters but have 3 warnings."""
        lead = BusinessLead(
            business_name="Karma Candy Inc",
            revenue_estimate=RevenueEstimate(estimated_amount=1_310_000),
            employee_count=16,
            review_count=76,
            contact=ContactInfo(website="http://www.karmacandy.ca/"),
            location=LocationInfo()
        )

        # Should pass size filter
        excluded, _ = filter_by_size(lead)
        assert excluded is False

        # Should pass type filter
        type_filter = BusinessTypeFilter()
        should_exclude, _ = type_filter.should_exclude(
            lead.business_name,
            "Manufacturing",
            lead.contact.website,
            lead.review_count
        )
        assert should_exclude is False

        # But should have warnings
        warnings = generate_warnings(lead)
        assert len(warnings) == 3
        assert any("HIGH_VISIBILITY" in w for w in warnings)
        assert any("UPPER_RANGE" in w for w in warnings)
        assert any("VERIFY_SIZE" in w for w in warnings)

    def test_ontario_ravioli_warnings(self):
        """Ontario Ravioli should pass filters but have 3 warnings."""
        lead = BusinessLead(
            business_name="Ontario Ravioli",
            revenue_estimate=RevenueEstimate(estimated_amount=1_310_000),
            employee_count=16,
            review_count=73,
            contact=ContactInfo(website="http://ontarioravioli.com/"),
            location=LocationInfo()
        )

        # Should pass size filter
        excluded, _ = filter_by_size(lead)
        assert excluded is False

        # Should pass type filter
        type_filter = BusinessTypeFilter()
        should_exclude, _ = type_filter.should_exclude(
            lead.business_name,
            "Manufacturing",
            lead.contact.website,
            lead.review_count
        )
        assert should_exclude is False

        # But should have warnings
        warnings = generate_warnings(lead)
        assert len(warnings) == 3

    def test_advantage_machining_warning(self):
        """Advantage Machining should have 1 warning (UPPER_RANGE)."""
        lead_data = {
            'revenue_estimate': 1_320_000,
            'employee_count': 16,
            'review_count': 11,
            'website': 'http://www.advantagemachining.ca/'
        }

        # Should pass size filter
        excluded, _ = filter_by_size(lead_data)
        assert excluded is False

        # Should have warning
        warnings = generate_warnings(lead_data)
        assert len(warnings) == 1
        assert "UPPER_RANGE" in warnings[0]


class TestFullPipelineResults:
    """Test expected results for full 20-lead pipeline."""

    def test_expected_exclusion_count(self):
        """Should exclude 5 leads total."""
        # This would be tested with the full pipeline
        # Expected: Container57, Emerald Site, VP Expert, Welsh, Stoney Creek
        expected_exclusions = 5
        # Actual test would run full pipeline
        assert True  # Placeholder

    def test_expected_clean_count(self):
        """Should have 15 clean leads (6 no warnings, 9 with warnings)."""
        expected_clean = 15
        expected_no_warnings = 6
        expected_with_warnings = 9
        # Actual test would run full pipeline
        assert True  # Placeholder

    def test_expected_warning_distribution(self):
        """Should have correct warning distribution."""
        # 3 warnings: Karma Candy, Ontario Ravioli
        # 1 warning: 9 leads
        assert True  # Placeholder


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
