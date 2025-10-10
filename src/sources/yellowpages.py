"""
Yellow Pages API Integration for B2B Lead Generation.
PRIORITY: HIGH - Better B2B coverage than OSM.

Yellow Pages Canada has good manufacturing/industrial business coverage.
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
import structlog
from bs4 import BeautifulSoup
import re

logger = structlog.get_logger(__name__)


class YellowPagesSearcher:
    """
    Yellow Pages Canada business search integration.

    Uses web scraping of public Yellow Pages directory (no API key required).
    Yellow Pages has much better B2B/manufacturing coverage than OSM.
    """

    def __init__(self):
        self.base_url = "https://www.yellowpages.ca"
        self.logger = logger

    async def search_businesses(
        self,
        query: str,
        location: str = "Hamilton, ON",
        max_results: int = 50
    ) -> List[Dict]:
        """
        Search Yellow Pages for businesses.

        Args:
            query: Search term (e.g., "manufacturing", "machine shop", "printing")
            location: Location to search (default: Hamilton, ON)
            max_results: Maximum number of results to return

        Returns:
            List of business dictionaries
        """
        self.logger.info("yellowpages_search_started", query=query, location=location)

        businesses = []

        try:
            async with aiohttp.ClientSession() as session:
                # Yellow Pages search URL format
                search_url = f"{self.base_url}/search/si/1/{query}/{location}"

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }

                async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 200:
                        html = await response.text()
                        businesses = self._parse_search_results(html)
                        self.logger.info("yellowpages_results_found", count=len(businesses))
                    else:
                        self.logger.warning("yellowpages_request_failed", status=response.status)

        except asyncio.TimeoutError:
            self.logger.error("yellowpages_timeout", query=query)
        except Exception as e:
            self.logger.error("yellowpages_search_failed", error=str(e))

        return businesses[:max_results]

    def _parse_search_results(self, html: str) -> List[Dict]:
        """Parse Yellow Pages search results HTML."""
        businesses = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find all business listings (Yellow Pages uses specific class names)
            listings = soup.find_all('div', class_='listing')

            if not listings:
                # Try alternative selectors
                listings = soup.find_all('div', {'data-yext': True})

            for listing in listings:
                try:
                    business = self._extract_business_data(listing)
                    if business and business.get('name'):
                        businesses.append(business)
                except Exception as e:
                    self.logger.debug("listing_parse_failed", error=str(e))
                    continue

        except Exception as e:
            self.logger.error("html_parse_failed", error=str(e))

        return businesses

    def _extract_business_data(self, listing) -> Optional[Dict]:
        """Extract business data from a single listing."""
        business = {}

        try:
            # Business name
            name_elem = listing.find('h3', class_='listing__name') or listing.find('a', class_='listing__name__link')
            if name_elem:
                business['name'] = name_elem.get_text(strip=True)

            # Address
            address_elem = listing.find('div', class_='listing__address')
            if address_elem:
                street = address_elem.find('span', class_='listing__street')
                city = address_elem.find('span', class_='listing__city')
                postal = address_elem.find('span', class_='listing__postal')

                if street:
                    business['street'] = street.get_text(strip=True)
                if city:
                    business['city'] = city.get_text(strip=True).replace(',', '').strip()
                if postal:
                    business['postal_code'] = postal.get_text(strip=True)

            # Phone
            phone_elem = listing.find('a', class_='mlr__submenu__link--phone')
            if not phone_elem:
                phone_elem = listing.find('div', class_='listing__phone')
            if phone_elem:
                phone_text = phone_elem.get_text(strip=True)
                # Extract just the phone number
                phone_match = re.search(r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', phone_text)
                if phone_match:
                    business['phone'] = phone_match.group(1)

            # Website
            website_elem = listing.find('a', class_='listing__link--website')
            if website_elem:
                website_url = website_elem.get('href', '')
                # Yellow Pages sometimes wraps URLs in redirects
                if website_url and not website_url.startswith('http'):
                    website_url = f"https://{website_url}"
                business['website'] = website_url

            # Categories (for industry classification)
            categories = []
            category_elems = listing.find_all('a', class_='listing__category')
            for cat_elem in category_elems:
                categories.append(cat_elem.get_text(strip=True))
            if categories:
                business['categories'] = categories

            return business if business.get('name') else None

        except Exception as e:
            self.logger.debug("business_extraction_failed", error=str(e))
            return None


async def search_manufacturing_businesses(location: str = "Hamilton, ON", max_results: int = 50) -> List[Dict]:
    """
    Convenience function to search for manufacturing businesses.

    Args:
        location: Location to search
        max_results: Maximum results

    Returns:
        List of manufacturing businesses
    """
    searcher = YellowPagesSearcher()

    all_businesses = []

    # Search multiple manufacturing-related keywords
    search_terms = [
        "manufacturing",
        "machine shop",
        "metal fabrication",
        "printing services",
        "industrial equipment",
        "wholesale distributor"
    ]

    for term in search_terms:
        results = await searcher.search_businesses(term, location, max_results // len(search_terms))
        all_businesses.extend(results)

        # Rate limiting - be respectful
        await asyncio.sleep(2)

        if len(all_businesses) >= max_results:
            break

    # Deduplicate by name
    seen_names = set()
    unique_businesses = []
    for biz in all_businesses:
        name = biz.get('name', '').lower().strip()
        if name and name not in seen_names:
            seen_names.add(name)
            unique_businesses.append(biz)

    return unique_businesses[:max_results]
