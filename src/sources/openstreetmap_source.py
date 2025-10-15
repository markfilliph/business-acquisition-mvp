"""
OpenStreetMap Source - BaseBusinessSource wrapper for OpenStreetMapSearcher
"""
from typing import List, Optional
import structlog

from .base_source import BaseBusinessSource, BusinessData
from .openstreetmap import OpenStreetMapSearcher

logger = structlog.get_logger(__name__)


class OpenStreetMapSource(BaseBusinessSource):
    """
    OpenStreetMap business discovery source.

    Free, open data. Good for geographic-based discovery.
    """

    def __init__(self):
        super().__init__(name='openstreetmap', priority=45)
        self.searcher = OpenStreetMapSearcher()

    def validate_config(self) -> bool:
        """OpenStreetMap is always available (no API key needed)."""
        return True

    async def fetch_businesses(
        self,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None,
        max_results: int = 50
    ) -> List[BusinessData]:
        """
        Fetch businesses from OpenStreetMap.

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
            # Map industry to OSM types
            industry_types = self._get_osm_types(industry)

            # Fetch from OpenStreetMap
            raw_businesses = await self.searcher.search_hamilton_area(
                industry_types=industry_types,
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
                "openstreetmap_fetch_complete",
                businesses_found=len(businesses),
                fetch_time=fetch_time
            )

            return businesses

        except Exception as e:
            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(0, fetch_time, errors=1)
            self.logger.error("openstreetmap_fetch_failed", error=str(e))
            return []

    def _get_osm_types(self, industry: Optional[str]) -> List[str]:
        """Map industry to OSM types."""
        if not industry:
            return ['industrial', 'commercial']

        industry_map = {
            'manufacturing': ['industrial', 'factory'],
            'printing': ['craft=printer'],
            'wholesale': ['wholesale'],
            'equipment_rental': ['rental']
        }
        return industry_map.get(industry, ['commercial'])

    def _convert_to_business_data(self, raw: dict) -> Optional[BusinessData]:
        """Convert OpenStreetMap format to BusinessData."""
        try:
            name = raw.get('name')
            if not name:
                return None

            return BusinessData(
                name=name,
                source='openstreetmap',
                source_url='https://www.openstreetmap.org',
                confidence=0.65,  # OSM data quality varies
                street=raw.get('street'),
                city=raw.get('city', 'Hamilton'),
                province='ON',
                postal_code=raw.get('postal_code'),
                phone=raw.get('phone'),
                website=raw.get('website'),
                latitude=raw.get('latitude'),
                longitude=raw.get('longitude'),
                industry=raw.get('industry', 'general'),
                raw_data=raw
            )

        except Exception as e:
            self.logger.error("openstreetmap_conversion_error", error=str(e))
            return None
