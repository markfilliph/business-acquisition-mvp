"""
Geoapify Places API Source - Free alternative to Google Places
FREE tier: 3,000 credits/day (~60,000 places)
No IP restrictions, no credit card required
"""
import asyncio
from typing import List, Optional
import aiohttp
import structlog

from .base_source import BaseBusinessSource, BusinessData
from ..core.config import config
from ..core.resilience import call_with_retry

logger = structlog.get_logger(__name__)


class GeoapifySource(BaseBusinessSource):
    """
    Fetch businesses from Geoapify Places API.

    Features:
    - Free tier: 3,000 credits/day
    - 20 places per credit
    - 500+ business categories
    - No IP restrictions
    - Better data quality than DuckDuckGo

    API Documentation:
    https://apidocs.geoapify.com/docs/places/
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name='geoapify', priority=60)
        self.api_key = api_key or getattr(config, 'GEOAPIFY_API_KEY', None)
        self.base_url = "https://api.geoapify.com/v2/places"

        # Hamilton coordinates
        self.hamilton_coords = {
            'lat': 43.2557,
            'lon': -79.8711,
            'radius': 15000  # 15km
        }

        # Industry to Geoapify category mapping
        # Full list: https://apidocs.geoapify.com/docs/places/categories/
        self.industry_categories = {
            'manufacturing': ['production.factory', 'production.winery', 'production.brewery', 'commercial.vehicle'],
            'printing': ['commercial.books', 'commercial.stationery'],
            'wholesale': ['commercial.trade', 'commercial'],
            'equipment_rental': ['rental', 'service.vehicle'],
            'professional_services': ['office.consulting', 'office.accountant', 'office.lawyer'],
            'retail': ['commercial.shopping_mall', 'commercial.marketplace', 'commercial.supermarket'],
            'all': ['commercial', 'office.company']  # Broad search
        }

    def validate_config(self) -> bool:
        """Validate that API key is configured."""
        if not self.api_key:
            self.logger.warning("geoapify_api_key_missing")
            return False
        return True

    async def fetch_businesses(
        self,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None,
        max_results: int = 50
    ) -> List[BusinessData]:
        """
        Fetch businesses from Geoapify Places API.

        Args:
            location: Location filter (city)
            industry: Industry filter
            max_results: Maximum results to return

        Returns:
            List of BusinessData objects
        """
        if not self.validate_config():
            return []

        start_time = asyncio.get_event_loop().time()
        all_businesses = []

        try:
            # Get categories for industry
            categories = self.industry_categories.get(industry, self.industry_categories['all'])

            self.logger.info(
                "geoapify_fetch_started",
                location=location,
                industry=industry,
                categories=categories,
                max_results=max_results
            )

            # Search for each category
            for category in categories:
                if len(all_businesses) >= max_results:
                    break

                search_results = await self._search_places(
                    category=category,
                    max_results=max_results - len(all_businesses)
                )

                all_businesses.extend(search_results)

                # Rate limiting between searches
                await asyncio.sleep(0.5)

            # Deduplicate by name and address
            unique_businesses = self._deduplicate_businesses(all_businesses)

            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(len(unique_businesses), fetch_time)

            self.logger.info(
                "geoapify_fetch_complete",
                businesses_found=len(unique_businesses),
                fetch_time=fetch_time
            )

            return unique_businesses[:max_results]

        except Exception as e:
            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(0, fetch_time, errors=1)
            self.logger.error("geoapify_fetch_failed", error=str(e))
            return []

    async def _search_places(
        self,
        category: str,
        max_results: int = 20
    ) -> List[BusinessData]:
        """
        Search for places by category.

        Args:
            category: Geoapify category
            max_results: Maximum results

        Returns:
            List of BusinessData objects
        """
        businesses = []

        try:
            async with aiohttp.ClientSession() as session:
                url = self.base_url

                # Build request parameters
                params = {
                    'categories': category,
                    'filter': f"circle:{self.hamilton_coords['lon']},{self.hamilton_coords['lat']},{self.hamilton_coords['radius']}",
                    'bias': f"proximity:{self.hamilton_coords['lon']},{self.hamilton_coords['lat']}",
                    'limit': min(max_results, 20),  # API limit is 20 per request
                    'apiKey': self.api_key
                }

                response = await call_with_retry(
                    session.get,
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                )

                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(
                        "geoapify_api_error",
                        status=response.status,
                        category=category,
                        error=error_text
                    )
                    return []

                data = await response.json()

                # Parse results
                features = data.get('features', [])

                if not features:
                    self.logger.debug(
                        "geoapify_no_results",
                        category=category
                    )
                    return []

                for feature in features:
                    business = self._parse_place(feature)
                    if business:
                        businesses.append(business)

                self.logger.debug(
                    "geoapify_search_complete",
                    category=category,
                    results=len(businesses)
                )

        except Exception as e:
            self.logger.error(
                "geoapify_search_failed",
                error=str(e),
                category=category
            )

        return businesses

    def _parse_place(self, feature: dict) -> Optional[BusinessData]:
        """
        Parse a place from Geoapify response.

        Args:
            feature: GeoJSON feature from API response

        Returns:
            BusinessData object or None
        """
        try:
            properties = feature.get('properties', {})
            geometry = feature.get('geometry', {})

            # Extract name
            name = properties.get('name')
            if not name:
                return None

            # Skip if it's just a generic category name
            if name.lower() in ['commercial', 'industrial', 'factory', 'shop']:
                return None

            # Extract address components
            street = properties.get('address_line1', '')
            city = properties.get('city', 'Hamilton')
            province = properties.get('state_code', 'ON')
            postal_code = properties.get('postcode')

            # Get full formatted address as fallback
            if not street:
                street = properties.get('formatted', '').split(',')[0]

            # Extract coordinates
            coordinates = geometry.get('coordinates', [])
            lon = coordinates[0] if len(coordinates) > 0 else None
            lat = coordinates[1] if len(coordinates) > 1 else None

            # Extract contact info
            phone = properties.get('contact', {}).get('phone')
            website = properties.get('website')

            # Infer industry from categories
            categories = properties.get('categories', [])
            industry = self._infer_industry_from_categories(categories)

            # Build source URL
            place_id = properties.get('place_id', '')
            source_url = f"https://www.geoapify.com/place/{place_id}" if place_id else None

            # Create BusinessData
            business = BusinessData(
                name=name,
                source='geoapify',
                source_url=source_url,
                confidence=0.85,  # Geoapify has good data quality
                street=street,
                city=city,
                province=province,
                postal_code=postal_code,
                phone=phone,
                website=website,
                latitude=lat,
                longitude=lon,
                industry=industry,
                raw_data={
                    'place_id': place_id,
                    'categories': categories,
                    'datasource': properties.get('datasource', {})
                }
            )

            return business

        except Exception as e:
            self.logger.error("geoapify_parse_error", error=str(e), data=str(feature)[:200])
            return None

    def _infer_industry_from_categories(self, categories: List[str]) -> str:
        """
        Infer industry from Geoapify categories.

        Args:
            categories: List of category strings

        Returns:
            Industry classification
        """
        categories_str = ','.join(categories).lower()

        if any(term in categories_str for term in ['industrial', 'factory', 'production']):
            return 'manufacturing'
        elif 'printing' in categories_str:
            return 'printing'
        elif any(term in categories_str for term in ['wholesaler', 'distribution']):
            return 'wholesale'
        elif 'rental' in categories_str:
            return 'equipment_rental'
        elif any(term in categories_str for term in ['consulting', 'accountant', 'professional']):
            return 'professional_services'
        else:
            return 'commercial'

    def _deduplicate_businesses(self, businesses: List[BusinessData]) -> List[BusinessData]:
        """
        Remove duplicate businesses based on name and location.

        Args:
            businesses: List of businesses

        Returns:
            Deduplicated list
        """
        seen = set()
        unique = []

        for biz in businesses:
            # Create a key from name and address
            key = f"{biz.name.lower()}|{biz.street.lower() if biz.street else ''}"

            if key not in seen:
                seen.add(key)
                unique.append(biz)

        return unique


async def test_geoapify():
    """Test function."""
    import os

    # Use API key from parameter or environment
    api_key = os.getenv('GEOAPIFY_API_KEY')

    if not api_key:
        print("❌ No API key found. Set GEOAPIFY_API_KEY environment variable.")
        return

    source = GeoapifySource(api_key=api_key)

    print("Testing Geoapify Places API for Hamilton manufacturers...")
    print("=" * 70)

    results = await source.fetch_businesses(
        location='Hamilton, ON',
        industry='manufacturing',
        max_results=10
    )

    print(f"\n✅ Found {len(results)} businesses\n")

    for i, biz in enumerate(results, 1):
        print(f"{i}. {biz.name}")
        print(f"   Address: {biz.street}, {biz.city}")
        print(f"   Phone: {biz.phone or 'N/A'}")
        print(f"   Website: {biz.website or 'N/A'}")
        print(f"   Industry: {biz.industry}")
        print()


if __name__ == '__main__':
    asyncio.run(test_geoapify())
