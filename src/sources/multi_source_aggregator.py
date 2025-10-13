"""
Multi-Source Business Discovery Aggregator

Orchestrates discovery across multiple sources with:
- Priority-based source ordering
- Fallback logic when sources fail
- Deduplication across sources
- Performance tracking per source
"""
import asyncio
from typing import List, Dict, Optional, Set
from datetime import datetime
import structlog

from src.sources.base_source import BaseBusinessSource, BusinessData
from src.sources.sources_config import SourceManager, SOURCES_CONFIG
from src.sources.hamilton_seed_list import HamiltonSeedListSource
from src.sources.cme_members import CMECSVImporter
from src.sources.innovation_canada import InnovationCanadaCSVImporter

logger = structlog.get_logger(__name__)


class MultiSourceAggregator:
    """
    Aggregates business data from multiple sources.

    Features:
    - Tries sources in priority order
    - Falls back to next source if one fails
    - Deduplicates across sources
    - Tracks source performance
    - Stops when target count reached
    """

    def __init__(self):
        self.source_manager = SourceManager(SOURCES_CONFIG)
        self.sources: Dict[str, BaseBusinessSource] = {}
        self.logger = logger

        # Initialize available sources
        self._initialize_sources()

    def _initialize_sources(self):
        """Initialize all available source implementations."""

        # Always available: Seed list
        self.sources['manual_seed_list'] = HamiltonSeedListSource()

        # CSV importers (available if files exist)
        self.sources['cme_csv_import'] = CMECSVImporter()
        self.sources['innovation_canada_csv'] = InnovationCanadaCSVImporter()

        # Note: Add more source implementations here as they're created
        # self.sources['yellowpages'] = YellowPagesSource()
        # self.sources['hamilton_chamber'] = HamiltonChamberSource()
        # etc.

        self.logger.info(
            "sources_initialized",
            available_sources=list(self.sources.keys())
        )

    def get_available_sources(self) -> List[BaseBusinessSource]:
        """
        Get all available and enabled sources, sorted by priority.

        Returns:
            List of source objects, highest priority first
        """
        available = []

        for name, source in self.sources.items():
            config = self.source_manager.get_source_by_name(name)

            if not config:
                continue

            if not config.enabled:
                self.logger.debug("source_disabled", source=name)
                continue

            if not source.is_available():
                self.logger.debug("source_not_available", source=name)
                continue

            available.append(source)

        # Sort by priority (highest first)
        available.sort(key=lambda s: s.priority, reverse=True)

        self.logger.info(
            "available_sources_found",
            count=len(available),
            sources=[s.name for s in available]
        )

        return available

    async def fetch_from_all_sources(
        self,
        target_count: int = 50,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None
    ) -> List[BusinessData]:
        """
        Fetch businesses from all available sources until target reached.

        Strategy:
        1. Try highest priority source first
        2. If fails or insufficient results, try next source
        3. Deduplicate across sources (by name + city)
        4. Stop when target count reached

        Args:
            target_count: Target number of unique businesses
            location: Location filter
            industry: Industry filter

        Returns:
            List of unique BusinessData objects
        """
        start_time = datetime.utcnow()
        all_businesses = []
        seen_keys: Set[str] = set()  # For deduplication

        sources = self.get_available_sources()

        if not sources:
            self.logger.error("no_sources_available")
            return []

        self.logger.info(
            "multi_source_fetch_started",
            target_count=target_count,
            sources_available=len(sources),
            location=location,
            industry=industry
        )

        for source in sources:
            if len(all_businesses) >= target_count:
                self.logger.info(
                    "target_reached",
                    count=len(all_businesses),
                    target=target_count
                )
                break

            try:
                # Calculate how many more we need from this source
                remaining = target_count - len(all_businesses)
                fetch_count = min(remaining * 2, 100)  # Fetch 2x to account for dupes

                self.logger.info(
                    "fetching_from_source",
                    source=source.name,
                    priority=source.priority,
                    fetch_count=fetch_count
                )

                # Fetch from source
                businesses = await source.fetch_businesses(
                    location=location,
                    industry=industry,
                    max_results=fetch_count
                )

                # Deduplicate
                new_businesses = []
                for biz in businesses:
                    # Create deduplication key (name + city, normalized)
                    key = self._create_dedup_key(biz)

                    if key not in seen_keys:
                        seen_keys.add(key)
                        new_businesses.append(biz)

                all_businesses.extend(new_businesses)

                self.logger.info(
                    "source_fetch_complete",
                    source=source.name,
                    fetched=len(businesses),
                    unique=len(new_businesses),
                    duplicates=len(businesses) - len(new_businesses),
                    total_so_far=len(all_businesses)
                )

            except Exception as e:
                self.logger.error(
                    "source_fetch_failed",
                    source=source.name,
                    error=str(e)
                )
                # Continue to next source
                continue

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        self.logger.info(
            "multi_source_fetch_complete",
            total_businesses=len(all_businesses),
            target=target_count,
            sources_used=len(sources),
            elapsed_seconds=elapsed
        )

        return all_businesses[:target_count]

    def _create_dedup_key(self, business: BusinessData) -> str:
        """
        Create deduplication key from business data.

        Uses normalized name + city to identify duplicates across sources.
        """
        name = business.name.lower().strip()
        # Remove common suffixes
        for suffix in [' inc', ' inc.', ' ltd', ' ltd.', ' corp', ' corp.', ' llc']:
            name = name.replace(suffix, '')
        name = ''.join(c for c in name if c.isalnum() or c.isspace())
        name = ' '.join(name.split())  # Normalize whitespace

        city = (business.city or '').lower().strip()

        return f"{name}|{city}"

    def get_source_metrics(self) -> List[Dict]:
        """Get performance metrics for all sources."""
        metrics = []

        for source in self.sources.values():
            metrics.append(source.get_metrics())

        # Sort by businesses found
        metrics.sort(key=lambda m: m['businesses_found'], reverse=True)

        return metrics

    def print_source_performance(self):
        """Print source performance report."""
        metrics = self.get_source_metrics()

        print("\n" + "=" * 80)
        print("📊 SOURCE PERFORMANCE REPORT")
        print("=" * 80)

        print(f"\n{'Source':<25} {'Businesses':<12} {'Runs':<8} {'Avg Time':<12} {'Errors'}")
        print("-" * 80)

        for m in metrics:
            if m['businesses_found'] > 0 or m['errors'] > 0:
                print(
                    f"{m['source_name']:<25} "
                    f"{m['businesses_found']:<12} "
                    f"{m['run_count']:<8} "
                    f"{m['avg_fetch_time']:<12.2f}s "
                    f"{m['errors']}"
                )

        print("=" * 80)


async def demo_aggregator():
    """Demo the multi-source aggregator."""
    aggregator = MultiSourceAggregator()

    print("\n" + "=" * 80)
    print("🔍 MULTI-SOURCE BUSINESS DISCOVERY DEMO")
    print("=" * 80)

    # Show available sources
    available = aggregator.get_available_sources()
    print(f"\n✅ Available sources: {len(available)}")
    for source in available:
        print(f"   {source.priority}: {source.name}")

    # Fetch businesses
    print(f"\n🎯 Fetching 30 businesses from Hamilton...")
    print("-" * 80)

    businesses = await aggregator.fetch_from_all_sources(
        target_count=30,
        location="Hamilton, ON",
        industry="manufacturing"
    )

    print(f"\n✅ Retrieved {len(businesses)} unique businesses")

    # Show first 10
    print("\n📋 First 10 businesses:")
    for i, biz in enumerate(businesses[:10], 1):
        print(f"\n{i}. {biz.name} (from {biz.source})")
        print(f"   {biz.street}, {biz.city}")
        print(f"   Industry: {biz.industry or 'N/A'}")
        print(f"   Confidence: {biz.confidence:.0%}")

    # Show performance
    print("\n")
    aggregator.print_source_performance()


if __name__ == '__main__':
    asyncio.run(demo_aggregator())
