"""
OpenStreetMap Overpass API integration for business discovery.
Uses publicly accessible Overpass API - no authentication required.
"""
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class OpenStreetMapSearcher:
    """
    Searches OpenStreetMap for businesses using Overpass API.

    Overpass API is free and public - no API key required.
    """

    def __init__(self):
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        self.timeout = aiohttp.ClientTimeout(total=60, connect=15)

    async def search_businesses(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 15000,
        tags: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses near a location using Overpass API.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_meters: Search radius in meters (default 15km)
            tags: OSM tags to filter by (e.g., {"industrial": "yes"})

        Returns:
            List of business dictionaries
        """

        # Build Overpass query - optimized for Hamilton area
        # Use a bounding box around Hamilton (43.2557, -79.8711)
        # Approximate 15km radius = ~0.135 degrees
        bbox = f"{latitude-0.135},{longitude-0.135},{latitude+0.135},{longitude+0.135}"

        if tags:
            # Custom tags provided - single query
            tag_str = ''.join([f'["{k}"="{v}"]' for k, v in tags.items()])
            overpass_query = f"""
            [out:json][timeout:60];
            (
                node{tag_str}({bbox});
                way{tag_str}({bbox});
            );
            out body;
            >;
            out skel qt;
            """
        else:
            # Default: comprehensive business search in single query
            overpass_query = f"""
            [out:json][timeout:60];
            (
                node["industrial"]({bbox});
                way["industrial"]({bbox});
                node["craft"]({bbox});
                way["craft"]({bbox});
                node["man_made"="works"]({bbox});
                way["man_made"="works"]({bbox});
                node["office"~"company|manufacturer|distributor"]({bbox});
                way["office"~"company|manufacturer|distributor"]({bbox});
                node["shop"="wholesale"]({bbox});
                way["shop"="wholesale"]({bbox});
            );
            out body;
            >;
            out skel qt;
            """

        logger.info("osm_search_started", lat=latitude, lon=longitude, radius=radius_meters)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(
                    self.overpass_url,
                    data={"data": overpass_query},
                    headers={
                        'User-Agent': 'Business Research Bot (Educational)',
                        'Accept': 'application/json'
                    }
                ) as response:

                    if response.status != 200:
                        logger.warning("osm_request_failed", status=response.status)
                        return []

                    data = await response.json()
                    elements = data.get('elements', [])

                    logger.info("osm_results_found", count=len(elements))

                    # Parse results
                    businesses = []
                    for element in elements:
                        tags_data = element.get('tags', {})

                        # Extract business info
                        name = tags_data.get('name')
                        if not name:
                            continue  # Skip unnamed entities

                        business = {
                            'name': name,
                            'street': self._build_address(tags_data),
                            'city': tags_data.get('addr:city', 'Hamilton'),
                            'postal_code': tags_data.get('addr:postcode'),
                            'phone': tags_data.get('phone') or tags_data.get('contact:phone'),
                            'website': tags_data.get('website') or tags_data.get('contact:website'),
                            'latitude': element.get('lat'),
                            'longitude': element.get('lon'),
                            'osm_type': element.get('type'),
                            'osm_id': element.get('id'),
                            'tags': tags_data
                        }

                        businesses.append(business)

                    logger.info("osm_search_complete", businesses_found=len(businesses))
                    return businesses

        except asyncio.TimeoutError:
            logger.warning("osm_request_timeout")
            return []
        except Exception as e:
            logger.error("osm_search_failed", error=str(e))
            return []

    def _build_address(self, tags: Dict[str, str]) -> Optional[str]:
        """Build full street address from OSM tags."""
        parts = []

        if tags.get('addr:housenumber'):
            parts.append(tags['addr:housenumber'])
        if tags.get('addr:street'):
            parts.append(tags['addr:street'])

        return ' '.join(parts) if parts else None

    async def search_hamilton_area(
        self,
        industry_types: Optional[List[str]] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses in Hamilton area.

        Single comprehensive query for all business types - much faster than
        multiple sequential queries.

        Args:
            industry_types: List of industry types (ignored - searches all)
            max_results: Maximum number of results

        Returns:
            List of business dictionaries
        """

        # Hamilton coordinates
        hamilton_lat = 43.2557
        hamilton_lon = -79.8711

        # Do a single comprehensive search for all industrial/commercial entities
        # This is much faster than multiple queries and doesn't hit rate limits
        results = await self.search_businesses(
            latitude=hamilton_lat,
            longitude=hamilton_lon,
            radius_meters=15000,
            tags=None  # None = comprehensive search
        )

        logger.info("hamilton_area_search_complete", total_found=len(results))

        # Deduplicate by OSM ID
        seen_ids = set()
        unique_businesses = []
        for biz in results:
            osm_id = biz.get('osm_id')
            if osm_id and osm_id not in seen_ids:
                seen_ids.add(osm_id)
                unique_businesses.append(biz)

        return unique_businesses[:max_results]


async def test_osm_search():
    """Test function to verify OSM search works."""
    searcher = OpenStreetMapSearcher()

    print("Testing OSM search for Hamilton manufacturing businesses...")
    results = await searcher.search_hamilton_area(
        industry_types=['manufacturing', 'printing', 'wholesale'],
        max_results=20
    )

    print(f"\nFound {len(results)} businesses")
    for i, biz in enumerate(results[:5], 1):
        print(f"\n{i}. {biz.get('name')}")
        print(f"   Address: {biz.get('street', 'N/A')}, {biz.get('city', 'N/A')}")
        print(f"   Phone: {biz.get('phone', 'N/A')}")
        print(f"   Website: {biz.get('website', 'N/A')}")


if __name__ == '__main__':
    asyncio.run(test_osm_search())
