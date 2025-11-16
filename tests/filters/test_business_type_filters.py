"""
Unit tests for business type filtering.
Tests retail detection and location label detection.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.filters.business_type_filters import BusinessTypeFilter


class TestRetailFilter:
    """Test retail business detection."""

    def setUp(self):
        """Set up test fixture."""
        self.filter = BusinessTypeFilter()

    def test_detect_shopify_container57(self):
        """Container57 should be detected as retail (Shopify)."""
        filter = BusinessTypeFilter()
        is_retail, reason = filter.is_retail_business(
            business_name="Container57",
            industry="Retail",
            website="https://60424e-3.myshopify.com/"
        )

        assert is_retail is True
        assert "shopify.com" in reason.lower()

    def test_detect_shopify_subdomain(self):
        """Should detect Shopify subdomains."""
        filter = BusinessTypeFilter()
        is_retail, reason = filter.is_retail_business(
            business_name="Example Store",
            industry="General",
            website="https://mystore.myshopify.com/"
        )

        assert is_retail is True
        # Should detect either shopify.com or myshopify.com
        assert "shopify.com" in reason.lower()

    def test_detect_retail_industry(self):
        """Should detect retail from industry classification."""
        filter = BusinessTypeFilter()
        is_retail, reason = filter.is_retail_business(
            business_name="The Shop",
            industry="Retail",
            website="https://example.com/"
        )

        assert is_retail is True
        assert "retail" in reason.lower()

    def test_allow_b2b_manufacturing_abarth(self):
        """Abarth Machining should NOT be detected as retail."""
        filter = BusinessTypeFilter()
        is_retail, reason = filter.is_retail_business(
            business_name="Abarth Machining Inc",
            industry="Manufacturing",
            website="https://abarthmachining.com/"
        )

        assert is_retail is False
        assert reason is None

    def test_allow_b2b_manufacturing_stolk(self):
        """Stolk Machine Shop should NOT be detected as retail."""
        filter = BusinessTypeFilter()
        is_retail, reason = filter.is_retail_business(
            business_name="Stolk Machine Shop Ltd",
            industry="Manufacturing",
            website="http://www.stolkmachine.com/"
        )

        assert is_retail is False

    def test_allow_wholesale_gsdunn(self):
        """G.S. Dunn (wholesale) should NOT be detected as retail."""
        filter = BusinessTypeFilter()
        is_retail, reason = filter.is_retail_business(
            business_name="G. S. Dunn Ltd.",
            industry="Wholesale",
            website="http://gsdunn.com/"
        )

        assert is_retail is False

    def test_detect_other_ecommerce_platforms(self):
        """Should detect other e-commerce platforms."""
        filter = BusinessTypeFilter()

        # BigCartel
        is_retail, _ = filter.is_retail_business(
            "Store", None, "https://mystore.bigcartel.com/"
        )
        assert is_retail is True

        # Wix online store
        is_retail, _ = filter.is_retail_business(
            "Store", None, "https://example.wix.com/online-store"
        )
        assert is_retail is True

    def test_no_false_positives_on_manufacturing(self):
        """Should not flag manufacturing businesses as retail."""
        filter = BusinessTypeFilter()

        test_cases = [
            ("All Tool Manufacturing Inc", "Manufacturing", "http://www.alltoolgroup.com/"),
            ("Millen Manufacturing Inc", "Manufacturing", "http://www.millenmfg.com/"),
            ("North Star Technical Inc", "Manufacturing", "http://northstartech.ca/"),
        ]

        for name, industry, website in test_cases:
            is_retail, _ = filter.is_retail_business(name, industry, website)
            assert is_retail is False, f"{name} incorrectly flagged as retail"


class TestLocationLabelFilter:
    """Test location label detection."""

    def test_detect_emerald_site(self):
        """Emerald Manufacturing Site should be detected as location label."""
        filter = BusinessTypeFilter()
        is_location, reason = filter.is_location_label(
            business_name="Emerald Manufacturing Site",
            website=None,
            review_count=1
        )

        assert is_location is True
        assert "site" in reason.lower()

    def test_detect_facility_with_no_website(self):
        """Should detect 'facility' keyword with no website."""
        filter = BusinessTypeFilter()
        is_location, reason = filter.is_location_label(
            business_name="ABC Manufacturing Facility",
            website=None,
            review_count=0
        )

        assert is_location is True
        assert "facility" in reason.lower()

    def test_detect_industrial_complex(self):
        """Should detect 'complex' keyword patterns."""
        filter = BusinessTypeFilter()
        is_location, reason = filter.is_location_label(
            business_name="Hamilton Industrial Complex",
            website="N/A",
            review_count=1
        )

        assert is_location is True

    def test_allow_real_business_north_star(self):
        """North Star Technical should NOT be flagged as location."""
        filter = BusinessTypeFilter()
        is_location, reason = filter.is_location_label(
            business_name="North Star Technical Inc",
            website="http://northstartech.ca/",
            review_count=11
        )

        assert is_location is False

    def test_allow_real_business_with_site_but_website(self):
        """Should allow businesses with 'site' keyword if they have website."""
        filter = BusinessTypeFilter()
        is_location, reason = filter.is_location_label(
            business_name="Worksite Solutions Inc",
            website="https://worksitesolutions.com/",
            review_count=15
        )

        # Has website and reviews, so not a location label
        assert is_location is False

    def test_detect_suspicious_patterns(self):
        """Should detect suspicious location patterns."""
        filter = BusinessTypeFilter()

        patterns = [
            "Manufacturing Site",
            "Production Facility",
            "Industrial Site",
            "Business Park"
        ]

        for pattern in patterns:
            is_location, _ = filter.is_location_label(
                business_name=f"ABC {pattern}",
                website=None,
                review_count=0
            )
            assert is_location is True, f"'{pattern}' not detected as location label"


class TestComprehensiveExclusion:
    """Test comprehensive should_exclude logic."""

    def test_exclude_container57_retail(self):
        """Container57 should be excluded as retail."""
        filter = BusinessTypeFilter()
        should_exclude, reason = filter.should_exclude(
            business_name="Container57",
            industry="Retail",
            website="https://60424e-3.myshopify.com/",
            review_count=4
        )

        assert should_exclude is True
        assert "RETAIL" in reason

    def test_exclude_emerald_site_location(self):
        """Emerald Manufacturing Site should be excluded as location label."""
        filter = BusinessTypeFilter()
        should_exclude, reason = filter.should_exclude(
            business_name="Emerald Manufacturing Site",
            industry=None,
            website="N/A",
            review_count=1
        )

        assert should_exclude is True
        assert "LOCATION LABEL" in reason

    def test_allow_abarth_machining(self):
        """Abarth Machining should pass all filters."""
        filter = BusinessTypeFilter()
        should_exclude, reason = filter.should_exclude(
            business_name="Abarth Machining Inc",
            industry="Manufacturing",
            website="https://abarthmachining.com/",
            review_count=3
        )

        assert should_exclude is False
        assert reason == "PASSED"

    def test_allow_all_core_leads(self):
        """All core A-list leads should pass filters."""
        filter = BusinessTypeFilter()

        core_leads = [
            ("Abarth Machining Inc", "Manufacturing", "https://abarthmachining.com/", 3),
            ("Stolk Machine Shop Ltd", "Manufacturing", "http://www.stolkmachine.com/", 3),
            ("All Tool Manufacturing Inc", "Manufacturing", "http://www.alltoolgroup.com/", 2),
            ("Millen Manufacturing Inc", "Manufacturing", "http://www.millenmfg.com/", 2),
            ("North Star Technical Inc", "Manufacturing", "http://northstartech.ca/", 8),
            ("G. S. Dunn Ltd.", "Wholesale", "http://gsdunn.com/", 9),
        ]

        for name, industry, website, reviews in core_leads:
            should_exclude, reason = filter.should_exclude(name, industry, website, reviews)
            assert should_exclude is False, f"{name} incorrectly excluded: {reason}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
