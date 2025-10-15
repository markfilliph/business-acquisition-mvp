"""
Canada411 Source - BaseBusinessSource wrapper for Canada411Searcher
"""
from typing import List, Optional
import structlog

from .base_source import BaseBusinessSource, BusinessData
from .canada411 import Canada411Searcher

logger = structlog.get_logger(__name__)


class Canada411Source(BaseBusinessSource):
    """
    Canada411 business directory source.

    Free Canadian business directory with good B2B coverage.
    """

    def __init__(self):
        super().__init__(name='canada411', priority=58)
        self.searcher = Canada411Searcher()

    def validate_config(self) -> bool:
        """Canada411 is always available (no API key needed)."""
        return True

    async def fetch_businesses(
        self,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None,
        max_results: int = 50
    ) -> List[BusinessData]:
        """
        Fetch businesses from Canada411.

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

            # Fetch from Canada411
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
                "canada411_fetch_complete",
                businesses_found=len(businesses),
                fetch_time=fetch_time
            )

            return businesses

        except Exception as e:
            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(0, fetch_time, errors=1)
            self.logger.error("canada411_fetch_failed", error=str(e))
            return []

    def _get_search_term(self, industry: Optional[str]) -> str:
        """Map industry to Canada411 search term."""
        industry_map = {
            'manufacturing': 'manufacturing',
            'printing': 'printing',
            'wholesale': 'wholesale',
            'equipment_rental': 'equipment rental',
            'professional_services': 'business services'
        }
        return industry_map.get(industry, 'business')

    def _convert_to_business_data(self, raw: dict) -> Optional[BusinessData]:
        """Convert Canada411 format to BusinessData."""
        try:
            name = raw.get('name')
            if not name:
                return None

            return BusinessData(
                name=name,
                source='canada411',
                source_url='https://www.canada411.ca',
                confidence=0.70,  # Canada411 has decent data quality
                street=raw.get('street'),
                city=raw.get('city', 'Hamilton'),
                province='ON',
                postal_code=raw.get('postal_code'),
                phone=raw.get('phone'),
                website=raw.get('website'),
                industry=raw.get('category', 'general'),
                raw_data=raw
            )

        except Exception as e:
            self.logger.error("canada411_conversion_error", error=str(e))
            return None
