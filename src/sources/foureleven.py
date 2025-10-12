"""
411.ca business directory searcher.
Alternative Canadian business directory (19M people, 1.1M businesses).
"""
import asyncio
import aiohttp
from typing import List, Dict, Any
from urllib.parse import quote_plus
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class FourElevenSearcher:
    """
    Search 411.ca business directory.

    Claims 1.1M businesses in Canada.
    """

    def __init__(self):
        self.base_url = "https://411.ca"
        self.search_url = f"{self.base_url}/business"
        self.timeout = aiohttp.ClientTimeout(total=30, connect=10)

    async def search_businesses(
        self,
        query: str,
        location: str = "Hamilton, ON",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for businesses on 411.ca.

        Args:
            query: Search term (e.g., "manufacturing")
            location: Location to search
            max_results: Maximum results

        Returns:
            List of business dictionaries
        """

        businesses = []

        # Build search URL with query parameters
        params = f"?what={quote_plus(query)}&where={quote_plus(location)}"
        url = f"{self.search_url}{params}"

        logger.info("411ca_search_started", query=query, location=location)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml',
                    'Accept-Language': 'en-CA,en;q=0.9',
                }

                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning("411ca_request_failed", status=response.status)
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find business listings (will need to inspect actual HTML structure)
                    listings = soup.find_all('div', class_='listing')
                    if not listings:
                        listings = soup.find_all('article')
                    if not listings:
                        listings = soup.find_all('div', class_='business-result')

                    logger.info("411ca_results_found", count=len(listings))

                    for listing in listings[:max_results]:
                        try:
                            business = self._parse_listing(listing)
                            if business:
                                businesses.append(business)
                        except Exception as e:
                            logger.warning("411ca_listing_parse_failed", error=str(e))

        except Exception as e:
            logger.error("411ca_search_failed", error=str(e))

        logger.info("411ca_search_complete", businesses_found=len(businesses))
        return businesses

    def _parse_listing(self, listing) -> Dict[str, Any]:
        """Parse business listing from HTML."""
        business = {}

        # Name
        name_elem = listing.find('h2') or listing.find('h3') or listing.find('a', class_='business-name')
        if name_elem:
            business['name'] = name_elem.get_text(strip=True)

        # Address elements
        address_elem = listing.find('address') or listing.find('div', class_='address')
        if address_elem:
            address_text = address_elem.get_text(strip=True)
            business['street'] = address_text

        # Phone
        phone_elem = listing.find('a', href=lambda h: h and 'tel:' in h)
        if phone_elem:
            business['phone'] = phone_elem.get_text(strip=True)

        return business if business.get('name') else None


async def test_foureleven():
    """Test function."""
    searcher = FourElevenSearcher()

    print("Testing 411.ca search...")
    results = await searcher.search_businesses("manufacturing", "Hamilton, ON", max_results=10)

    print(f"\nFound {len(results)} businesses")
    for i, biz in enumerate(results[:5], 1):
        print(f"\n{i}. {biz.get('name')}")
        print(f"   Address: {biz.get('street', 'N/A')}")
        print(f"   Phone: {biz.get('phone', 'N/A')}")


if __name__ == '__main__':
    asyncio.run(test_foureleven())
