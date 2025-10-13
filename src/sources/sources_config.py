"""
Source configuration and priority management.

Defines which sources to use, in what order, and with what settings.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SourceConfig:
    """Configuration for a business data source."""
    name: str
    enabled: bool
    priority: int  # Higher = checked first (0-100)
    cost_per_request: float = 0.0  # USD
    rate_limit_per_day: Optional[int] = None
    requires_api_key: bool = False
    is_scraper: bool = False
    target_industries: List[str] = None

    def __post_init__(self):
        if self.target_industries is None:
            self.target_industries = []


# Priority levels:
# 90-100: Premium/Paid sources (high accuracy, fresh data)
# 70-89: Government databases (high accuracy, may be outdated)
# 50-69: Industry associations (medium accuracy, member lists)
# 30-49: Free scrapers (varies, needs validation)
# 10-29: Search engines (low accuracy, lots of noise)

SOURCES_CONFIG = {
    # ============================================
    # TIER 1: Premium/Commercial Sources (90-100)
    # ============================================
    'scotts_directory': SourceConfig(
        name='scotts_directory',
        enabled=False,  # Requires paid subscription
        priority=95,
        cost_per_request=0.50,
        requires_api_key=False,
        is_scraper=True,
        target_industries=['manufacturing', 'industrial', 'wholesale']
    ),

    'dnb': SourceConfig(
        name='dnb',  # Dun & Bradstreet
        enabled=False,  # Requires paid API
        priority=98,
        cost_per_request=2.00,
        requires_api_key=True,
        target_industries=['manufacturing', 'wholesale', 'professional_services']
    ),

    'zoominfo': SourceConfig(
        name='zoominfo',
        enabled=False,  # Requires paid subscription
        priority=97,
        cost_per_request=1.50,
        requires_api_key=True,
        target_industries=['manufacturing', 'wholesale', 'professional_services']
    ),

    # ============================================
    # TIER 2: Government Databases (70-89)
    # ============================================
    'innovation_canada': SourceConfig(
        name='innovation_canada',
        enabled=True,  # Free, public database
        priority=85,
        cost_per_request=0.0,
        requires_api_key=False,
        is_scraper=True,
        target_industries=['manufacturing', 'technology', 'research']
    ),

    'ic_company_directory': SourceConfig(
        name='ic_company_directory',  # Innovation, Science & Economic Development Canada
        enabled=True,
        priority=82,
        cost_per_request=0.0,
        is_scraper=True,
        target_industries=['manufacturing', 'export', 'technology']
    ),

    # ============================================
    # TIER 3: Industry Associations (50-69)
    # ============================================
    'cme_members': SourceConfig(
        name='cme_members',  # Canadian Manufacturers & Exporters
        enabled=True,
        priority=80,
        cost_per_request=0.0,
        is_scraper=True,
        target_industries=['manufacturing', 'export']
    ),

    'hamilton_chamber': SourceConfig(
        name='hamilton_chamber',
        enabled=True,
        priority=75,
        cost_per_request=0.0,
        is_scraper=True,
        target_industries=['all']
    ),

    'ontario_chamber': SourceConfig(
        name='ontario_chamber',
        enabled=True,
        priority=72,
        cost_per_request=0.0,
        is_scraper=True,
        target_industries=['all']
    ),

    # ============================================
    # TIER 4: Business Directories (30-49)
    # ============================================
    'yellowpages': SourceConfig(
        name='yellowpages',
        enabled=True,
        priority=60,
        cost_per_request=0.0,
        is_scraper=True,
        target_industries=['all']
    ),

    'canada411': SourceConfig(
        name='canada411',
        enabled=True,
        priority=58,
        cost_per_request=0.0,
        is_scraper=True,
        target_industries=['all']
    ),

    'linkedin_company_search': SourceConfig(
        name='linkedin_company_search',
        enabled=False,  # Requires LinkedIn account + possible scraping issues
        priority=65,
        cost_per_request=0.0,
        is_scraper=True,
        rate_limit_per_day=100,
        target_industries=['all']
    ),

    'google_places': SourceConfig(
        name='google_places',
        enabled=True,
        priority=55,
        cost_per_request=0.017,  # $17 per 1000 requests
        requires_api_key=True,
        rate_limit_per_day=1000,
        target_industries=['all']
    ),

    # ============================================
    # TIER 5: Map Data (30-49)
    # ============================================
    'openstreetmap': SourceConfig(
        name='openstreetmap',
        enabled=True,
        priority=45,
        cost_per_request=0.0,
        target_industries=['industrial', 'commercial']
    ),

    # ============================================
    # TIER 6: Search Engines (10-29) - LAST RESORT
    # ============================================
    'duckduckgo': SourceConfig(
        name='duckduckgo',
        enabled=False,  # Too low accuracy for B2B
        priority=20,
        cost_per_request=0.0,
        target_industries=['all']
    ),

    'bing_search': SourceConfig(
        name='bing_search',
        enabled=False,
        priority=18,
        requires_api_key=True,
        target_industries=['all']
    ),

    # ============================================
    # SEED LISTS (100)
    # ============================================
    'manual_seed_list': SourceConfig(
        name='manual_seed_list',
        enabled=True,
        priority=100,  # Always try first
        cost_per_request=0.0,
        target_industries=['all']
    ),
}


class SourceManager:
    """Manages source configuration and prioritization."""

    def __init__(self, config: Dict[str, SourceConfig] = None):
        self.config = config or SOURCES_CONFIG
        self.logger = logger

    def get_enabled_sources(self, sort_by_priority: bool = True) -> List[SourceConfig]:
        """
        Get all enabled sources.

        Args:
            sort_by_priority: If True, return sorted by priority (highest first)

        Returns:
            List of enabled SourceConfig objects
        """
        enabled = [cfg for cfg in self.config.values() if cfg.enabled]

        if sort_by_priority:
            enabled.sort(key=lambda x: x.priority, reverse=True)

        return enabled

    def get_source_by_name(self, name: str) -> Optional[SourceConfig]:
        """Get source config by name."""
        return self.config.get(name)

    def enable_source(self, name: str):
        """Enable a source."""
        if name in self.config:
            self.config[name].enabled = True
            self.logger.info("source_enabled", source=name)
        else:
            self.logger.warning("source_not_found", source=name)

    def disable_source(self, name: str):
        """Disable a source."""
        if name in self.config:
            self.config[name].enabled = False
            self.logger.info("source_disabled", source=name)

    def get_sources_for_industry(self, industry: str) -> List[SourceConfig]:
        """
        Get sources that are good for a specific industry.

        Args:
            industry: Industry type (e.g., 'manufacturing', 'wholesale')

        Returns:
            List of enabled sources sorted by priority
        """
        matching = []
        for cfg in self.config.values():
            if not cfg.enabled:
                continue

            if 'all' in cfg.target_industries or industry in cfg.target_industries:
                matching.append(cfg)

        matching.sort(key=lambda x: x.priority, reverse=True)
        return matching

    def get_free_sources(self) -> List[SourceConfig]:
        """Get all free (zero-cost) enabled sources."""
        free = [
            cfg for cfg in self.config.values()
            if cfg.enabled and cfg.cost_per_request == 0.0
        ]
        free.sort(key=lambda x: x.priority, reverse=True)
        return free

    def estimate_cost(self, source_name: str, num_requests: int) -> float:
        """
        Estimate cost for using a source.

        Args:
            source_name: Name of source
            num_requests: Number of API requests/fetches

        Returns:
            Estimated cost in USD
        """
        cfg = self.get_source_by_name(source_name)
        if not cfg:
            return 0.0

        return cfg.cost_per_request * num_requests

    def print_source_summary(self):
        """Print summary of all sources."""
        print("\n📊 Available Business Data Sources")
        print("=" * 80)

        enabled = self.get_enabled_sources()
        disabled = [cfg for cfg in self.config.values() if not cfg.enabled]

        print(f"\n✅ ENABLED SOURCES ({len(enabled)}):")
        print(f"{'Priority':<10} {'Name':<25} {'Cost':<12} {'Type':<15}")
        print("-" * 80)
        for cfg in enabled:
            cost_str = f"${cfg.cost_per_request:.2f}" if cfg.cost_per_request > 0 else "FREE"
            type_str = "Scraper" if cfg.is_scraper else ("API" if cfg.requires_api_key else "Public")
            print(f"{cfg.priority:<10} {cfg.name:<25} {cost_str:<12} {type_str:<15}")

        print(f"\n❌ DISABLED SOURCES ({len(disabled)}):")
        for cfg in disabled:
            reason = []
            if cfg.requires_api_key:
                reason.append("needs API key")
            if cfg.cost_per_request > 0:
                reason.append(f"costs ${cfg.cost_per_request}/req")
            reason_str = f"({', '.join(reason)})" if reason else ""
            print(f"  • {cfg.name} {reason_str}")

        print("\n" + "=" * 80)


if __name__ == '__main__':
    # Demo
    manager = SourceManager()
    manager.print_source_summary()

    print("\n\n🏭 Best sources for MANUFACTURING:")
    for cfg in manager.get_sources_for_industry('manufacturing')[:5]:
        print(f"  {cfg.priority}: {cfg.name}")

    print("\n\n💰 Free sources only:")
    for cfg in manager.get_free_sources()[:10]:
        print(f"  {cfg.priority}: {cfg.name}")
