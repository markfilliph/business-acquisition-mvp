"""
Canada411.ca business directory scraper.
Free business directory with good coverage of Canadian businesses.
"""
import asyncio
import aiohttp
from typing import List, Dict, Any
from urllib.parse import quote_plus
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class Canada411Searcher:
    """
    Search Canada411.ca business directory.

    Free directory with good B2B coverage.
    """

    def __init__(self):
        self.base_url = "https://www.canada411.ca"
        self.search_url = f"{self.base_url}/search/si/1/"
        self.timeout = aiohttp.ClientTimeout(total=30, connect=10)

    async def search_businesses(
        self,
        query: str,
        location: str = "Hamilton, ON",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses on Canada411.

        Args:
            query: Search term (e.g., "manufacturing", "machine shop")
            location: Location to search in
            max_results: Maximum number of results

        Returns:
            List of business dictionaries
        """

        businesses = []

        # Build search URL
        search_params = f"{quote_plus(query)}/{quote_plus(location)}"
        url = f"{self.search_url}{search_params}"

        logger.info("canada411_search_started", query=query, location=location)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://www.canada411.ca/'
                }

                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning("canada411_request_failed", status=response.status, url=url)
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find business listings
                    listings = soup.find_all('article', class_='c411Listing')

                    if not listings:
                        # Try alternative selectors
                        listings = soup.find_all('div', class_='listing')

                    logger.info("canada411_results_found", count=len(listings))

                    for listing in listings[:max_results]:
                        try:
                            business = self._parse_listing(listing)
                            if business:
                                businesses.append(business)
                        except Exception as e:
                            logger.warning("canada411_listing_parse_failed", error=str(e))
                            continue

        except asyncio.TimeoutError:
            logger.warning("canada411_request_timeout")
        except Exception as e:
            logger.error("canada411_search_failed", error=str(e))

        logger.info("canada411_search_complete", businesses_found=len(businesses))
        return businesses

    def _parse_listing(self, listing) -> Dict[str, Any]:
        """Parse a single business listing."""

        business = {}

        # Business name
        name_elem = listing.find('h3', class_='c411ListedName')
        if not name_elem:
            name_elem = listing.find('a', class_='listing-name')
        if name_elem:
            business['name'] = name_elem.get_text(strip=True)

        # Address
        address_elem = listing.find('span', itemprop='streetAddress')
        if address_elem:
            business['street'] = address_elem.get_text(strip=True)

        # City
        city_elem = listing.find('span', itemprop='addressLocality')
        if city_elem:
            business['city'] = city_elem.get_text(strip=True)

        # Province
        province_elem = listing.find('span', itemprop='addressRegion')
        if province_elem:
            business['province'] = province_elem.get_text(strip=True)

        # Postal code
        postal_elem = listing.find('span', itemprop='postalCode')
        if postal_elem:
            business['postal_code'] = postal_elem.get_text(strip=True)

        # Phone
        phone_elem = listing.find('a', {'data-c411-tracking': 'phone'})
        if not phone_elem:
            phone_elem = listing.find('span', itemprop='telephone')
        if phone_elem:
            business['phone'] = phone_elem.get_text(strip=True)

        # Website
        website_elem = listing.find('a', {'data-c411-tracking': 'website'})
        if website_elem:
            business['website'] = website_elem.get('href', '')

        return business if business.get('name') else None


async def test_canada411():
    """Test function."""
    searcher = Canada411Searcher()

    print("Testing Canada411 search for Hamilton manufacturing businesses...")
    results = await searcher.search_businesses("manufacturing", "Hamilton, ON", max_results=10)

    print(f"\nFound {len(results)} businesses:")
    for i, biz in enumerate(results, 1):
        print(f"\n{i}. {biz.get('name')}")
        print(f"   Address: {biz.get('street', 'N/A')}, {biz.get('city', 'N/A')}")
        print(f"   Phone: {biz.get('phone', 'N/A')}")
        print(f"   Website: {biz.get('website', 'N/A')}")


if __name__ == '__main__':
    asyncio.run(test_canada411())
