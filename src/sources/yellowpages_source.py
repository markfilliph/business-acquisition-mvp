"""
YellowPages Source - BaseBusinessSource wrapper for YellowPagesSearcher
"""
from typing import List, Optional
import structlog

from .base_source import BaseBusinessSource, BusinessData
from .yellowpages import YellowPagesSearcher

logger = structlog.get_logger(__name__)


class YellowPagesSource(BaseBusinessSource):
    """
    YellowPages business directory source.

    Free, no API key required. Good coverage of Canadian businesses.
    """

    def __init__(self):
        super().__init__(name='yellowpages', priority=60)
        self.searcher = YellowPagesSearcher()

    def validate_config(self) -> bool:
        """YellowPages is always available (no API key needed)."""
        return True

    async def fetch_businesses(
        self,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None,
        max_results: int = 50
    ) -> List[BusinessData]:
        """
        Fetch businesses from YellowPages.

        Args:
            location: Location filter
            industry: Industry filter
            max_results: Maximum results

        Returns:
            List of BusinessData objects
        """
        import asyncio
        start_time = asyncio.get_event_loop().time()

        try:
            # Map industry to search terms
            search_term = self._get_search_term(industry)

            # Fetch from YellowPages
            raw_businesses = await self.searcher.search_businesses(
                query=search_term,
                location=location,
                max_results=max_results
            )

            # Convert to BusinessData format
            businesses = []
            for raw in raw_businesses:
                business = self._convert_to_business_data(raw)
                if business:
                    businesses.append(business)

            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(len(businesses), fetch_time)

            self.logger.info(
                "yellowpages_fetch_complete",
                businesses_found=len(businesses),
                fetch_time=fetch_time
            )

            return businesses

        except Exception as e:
            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(0, fetch_time, errors=1)
            self.logger.error("yellowpages_fetch_failed", error=str(e))
            return []

    def _get_search_term(self, industry: Optional[str]) -> str:
        """Map industry to YellowPages search term."""
        industry_map = {
            'manufacturing': 'manufacturing',
            'printing': 'printing services',
            'wholesale': 'wholesale distributor',
            'equipment_rental': 'equipment rental',
            'professional_services': 'business services',
            'metal_fabrication': 'metal fabrication',
            'machine_shop': 'machine shop'
        }
        return industry_map.get(industry, 'business')

    def _convert_to_business_data(self, raw: dict) -> Optional[BusinessData]:
        """Convert YellowPages format to BusinessData."""
        try:
            name = raw.get('name')
            if not name:
                return None

            return BusinessData(
                name=name,
                source='yellowpages',
                source_url='https://www.yellowpages.ca',
                confidence=0.75,  # YellowPages has good but not perfect data
                street=raw.get('street'),
                city=raw.get('city', 'Hamilton'),
                province='ON',
                postal_code=raw.get('postal_code'),
                phone=raw.get('phone'),
                website=raw.get('website'),
                industry=raw.get('categories', ['general_business'])[0] if raw.get('categories') else 'general_business',
                raw_data=raw
            )

        except Exception as e:
            self.logger.error("yellowpages_conversion_error", error=str(e))
            return None
