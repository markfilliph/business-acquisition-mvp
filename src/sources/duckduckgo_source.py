"""
DuckDuckGo source adapter - wraps DuckDuckGoBusinessSearcher for aggregator compatibility.
"""
from typing import List, Optional
import structlog

from .base_source import BaseBusinessSource, BusinessData
from .duckduckgo_businesses import DuckDuckGoBusinessSearcher

logger = structlog.get_logger(__name__)


class DuckDuckGoSource(BaseBusinessSource):
    """
    Adapter for DuckDuckGoBusinessSearcher to work with MultiSourceAggregator.

    Wraps the existing DuckDuckGoBusinessSearcher and converts results
    to BusinessData format.
    """

    def __init__(self):
        super().__init__(name='duckduckgo', priority=20)
        self.searcher = DuckDuckGoBusinessSearcher()

    def validate_config(self) -> bool:
        """DuckDuckGo requires no configuration."""
        return True

    async def fetch_businesses(
        self,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None,
        max_results: int = 50
    ) -> List[BusinessData]:
        """
        Fetch businesses using DuckDuckGo search.

        Args:
            location: Location filter
            industry: Industry filter
            max_results: Maximum results

        Returns:
            List of BusinessData objects
        """
        try:
            # Use the searcher
            if industry == 'manufacturing':
                results = await self.searcher.search_hamilton_manufacturing(
                    max_results=max_results
                )
            else:
                # Generic search
                query = f"{industry} business" if industry else "business"
                results = await self.searcher.search_businesses(
                    query=query,
                    location=location,
                    max_results=max_results
                )

            # Convert to BusinessData
            businesses = []
            for result in results:
                business = BusinessData(
                    name=result.get('name', ''),
                    source='duckduckgo',
                    source_url=result.get('website', ''),
                    confidence=0.50,  # Lower confidence for search results
                    street=result.get('street', ''),
                    city=result.get('city', 'Hamilton'),
                    province='ON',
                    phone=result.get('phone'),
                    website=result.get('website'),
                    industry=industry or 'general_business',
                    raw_data=result
                )
                businesses.append(business)

            self.update_metrics(len(businesses), 0)
            return businesses

        except Exception as e:
            self.logger.error("duckduckgo_fetch_failed", error=str(e))
            self.update_metrics(0, 0, errors=1)
            return []
