"""
Tests for multi-source business discovery system.
"""
import pytest
import asyncio
from src.sources.hamilton_seed_list import HamiltonSeedListSource
from src.sources.multi_source_aggregator import MultiSourceAggregator
from src.sources.sources_config import SourceManager
from src.enrichment.contact_enrichment import ContactEnricher


class TestHamiltonSeedList:
    """Test the Hamilton manufacturer seed list."""

    @pytest.mark.asyncio
    async def test_seed_list_available(self):
        """Test that seed list is available and has data."""
        source = HamiltonSeedListSource()

        assert source.validate_config() is True
        assert source.is_available() is True
        assert source.get_total_count() > 0

    @pytest.mark.asyncio
    async def test_seed_list_fetch(self):
        """Test fetching businesses from seed list."""
        source = HamiltonSeedListSource()

        businesses = await source.fetch_businesses(max_results=10)

        assert len(businesses) > 0
        assert len(businesses) <= 10

        # Check first business has required fields
        biz = businesses[0]
        assert biz.name is not None
        assert biz.source == 'manual_seed_list'
        assert biz.confidence >= 0.9  # Seed list has high confidence
        assert biz.city in ['Hamilton', 'Dundas', 'Ancaster', 'Stoney Creek', 'Waterdown']

    @pytest.mark.asyncio
    async def test_seed_list_industry_filter(self):
        """Test industry filtering works."""
        source = HamiltonSeedListSource()

        # Fetch all
        all_businesses = await source.fetch_businesses(max_results=50)

        # Fetch steel only
        steel_businesses = await source.fetch_businesses(
            industry='steel',
            max_results=50
        )

        assert len(steel_businesses) < len(all_businesses)
        assert all('steel' in b.industry.lower() for b in steel_businesses if b.industry)

    @pytest.mark.asyncio
    async def test_seed_list_data_quality(self):
        """Test that seed list has good data quality."""
        source = HamiltonSeedListSource()

        businesses = await source.fetch_businesses(max_results=20)

        # Check data completeness
        with_website = sum(1 for b in businesses if b.website)
        with_phone = sum(1 for b in businesses if b.phone)
        with_street = sum(1 for b in businesses if b.street)

        # Seed list should have >80% completeness
        assert with_website / len(businesses) > 0.8
        assert with_phone / len(businesses) > 0.8
        assert with_street / len(businesses) > 0.8


class TestSourceConfiguration:
    """Test source configuration and management."""

    def test_source_manager_initialization(self):
        """Test source manager initializes correctly."""
        manager = SourceManager()

        enabled = manager.get_enabled_sources()
        assert len(enabled) > 0

        # Check priority ordering
        priorities = [s.priority for s in enabled]
        assert priorities == sorted(priorities, reverse=True)

    def test_get_free_sources(self):
        """Test getting free sources."""
        manager = SourceManager()

        free_sources = manager.get_free_sources()

        # All should have zero cost
        assert all(s.cost_per_request == 0.0 for s in free_sources)

    def test_get_sources_for_industry(self):
        """Test getting sources for specific industry."""
        manager = SourceManager()

        manufacturing_sources = manager.get_sources_for_industry('manufacturing')

        assert len(manufacturing_sources) > 0
        # Seed list should be highest priority
        assert manufacturing_sources[0].priority == 100

    def test_enable_disable_source(self):
        """Test enabling/disabling sources."""
        manager = SourceManager()

        # Get initial count
        initial_count = len(manager.get_enabled_sources())

        # Disable a source
        manager.disable_source('manual_seed_list')
        after_disable = len(manager.get_enabled_sources())
        assert after_disable == initial_count - 1

        # Re-enable
        manager.enable_source('manual_seed_list')
        after_enable = len(manager.get_enabled_sources())
        assert after_enable == initial_count


class TestMultiSourceAggregator:
    """Test multi-source aggregation."""

    @pytest.mark.asyncio
    async def test_aggregator_initialization(self):
        """Test aggregator initializes with available sources."""
        aggregator = MultiSourceAggregator()

        available = aggregator.get_available_sources()

        # Should have at least seed list
        assert len(available) > 0

        source_names = [s.name for s in available]
        assert 'manual_seed_list' in source_names

    @pytest.mark.asyncio
    async def test_fetch_from_all_sources(self):
        """Test fetching from multiple sources."""
        aggregator = MultiSourceAggregator()

        # Fetch small number
        businesses = await aggregator.fetch_from_all_sources(
            target_count=10,
            location="Hamilton, ON"
        )

        assert len(businesses) > 0
        assert len(businesses) <= 10

        # Check for valid data
        for biz in businesses:
            assert biz.name is not None
            assert biz.source is not None
            assert biz.confidence > 0

    @pytest.mark.asyncio
    async def test_deduplication_across_sources(self):
        """Test that duplicates are removed across sources."""
        aggregator = MultiSourceAggregator()

        businesses = await aggregator.fetch_from_all_sources(
            target_count=20,
            location="Hamilton, ON"
        )

        # Check for duplicates (same name + city)
        seen = set()
        duplicates = 0

        for biz in businesses:
            key = f"{biz.name.lower()}|{(biz.city or '').lower()}"
            if key in seen:
                duplicates += 1
            seen.add(key)

        # Should have no duplicates
        assert duplicates == 0

    @pytest.mark.asyncio
    async def test_source_metrics_tracking(self):
        """Test that source metrics are tracked."""
        aggregator = MultiSourceAggregator()

        # Fetch some businesses
        await aggregator.fetch_from_all_sources(
            target_count=10,
            location="Hamilton, ON"
        )

        # Get metrics
        metrics = aggregator.get_source_metrics()

        assert len(metrics) > 0

        # Check seed list has metrics
        seed_metrics = next((m for m in metrics if m['source_name'] == 'manual_seed_list'), None)
        assert seed_metrics is not None
        assert seed_metrics['businesses_found'] > 0
        assert seed_metrics['run_count'] > 0


class TestContactEnrichment:
    """Test contact enrichment functionality."""

    @pytest.mark.asyncio
    async def test_email_pattern_generation(self):
        """Test generating email patterns."""
        enricher = ContactEnricher()

        patterns = enricher._generate_email_patterns('example.com')

        assert len(patterns) > 0
        assert 'info@example.com' in patterns
        assert 'contact@example.com' in patterns
        assert 'sales@example.com' in patterns

    def test_email_extraction(self):
        """Test extracting emails from HTML."""
        enricher = ContactEnricher()

        html = """
        <html>
        <body>
            <p>Contact us at info@example.com</p>
            <p>Sales: sales@example.com</p>
            <p>Ignore: test@example.com (this is a placeholder)</p>
        </body>
        </html>
        """

        emails = enricher._extract_emails(html)

        assert 'info@example.com' in emails
        assert 'sales@example.com' in emails

    def test_phone_extraction(self):
        """Test extracting phone numbers from HTML."""
        enricher = ContactEnricher()

        html = """
        <html>
        <body>
            <p>Call us at 905-544-4122</p>
            <p>Or: (905) 662-3143</p>
            <p>Mobile: 9056623143</p>
        </body>
        </html>
        """

        phones = enricher._extract_phones(html)

        assert len(phones) > 0
        # Should extract all three formats

    def test_url_cleaning(self):
        """Test URL cleaning/normalization."""
        enricher = ContactEnricher()

        assert enricher._clean_url('example.com') == 'https://example.com'
        assert enricher._clean_url('www.example.com') == 'https://www.example.com'
        assert enricher._clean_url('http://example.com') == 'http://example.com'
        assert enricher._clean_url('https://example.com') == 'https://example.com'


class TestIntegration:
    """Integration tests for full pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_discovery(self):
        """Test complete discovery flow."""
        aggregator = MultiSourceAggregator()

        # Discover businesses
        businesses = await aggregator.fetch_from_all_sources(
            target_count=5,
            location="Hamilton, ON",
            industry="manufacturing"
        )

        assert len(businesses) > 0

        # Check data quality
        for biz in businesses:
            assert biz.name is not None
            assert biz.source is not None
            assert biz.confidence > 0
            assert biz.city in ['Hamilton', 'Dundas', 'Ancaster', 'Stoney Creek', 'Waterdown', None]

    @pytest.mark.asyncio
    async def test_source_fallback_logic(self):
        """Test that pipeline falls back to next source if one fails."""
        aggregator = MultiSourceAggregator()

        # Should still get results even if some sources fail
        businesses = await aggregator.fetch_from_all_sources(
            target_count=10,
            location="Hamilton, ON"
        )

        # Should have at least seed list results
        assert len(businesses) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
