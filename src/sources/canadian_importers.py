"""
Canadian Importers Database (CID) Integration.
PRIORITY: HIGH - Government data, official and free.

Industry Canada maintains database of companies importing goods into Canada.
Good for identifying manufacturers who import materials/equipment.
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
import structlog
from bs4 import BeautifulSoup
import re

logger = structlog.get_logger(__name__)


class CanadianImportersSearcher:
    """
    Canadian Importers Database integration.

    Industry Canada's official database of Canadian importers.
    Searchable by product, city, and country of origin.
    """

    def __init__(self):
        self.base_url = "https://ised-isde.canada.ca/app/ixb/cid-bdic"
        self.logger = logger

    async def search_importers(
        self,
        city: str = "Hamilton",
        province: str = "Ontario",
        product_keywords: List[str] = None,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Search Canadian Importers Database.

        Args:
            city: City to search (default: Hamilton)
            province: Province (default: Ontario)
            product_keywords: Product types to search for
            max_results: Maximum results to return

        Returns:
            List of importer company dictionaries
        """
        if product_keywords is None:
            # Manufacturing-related import categories
            product_keywords = [
                'machinery',
                'equipment',
                'metal',
                'steel',
                'industrial',
                'tools',
                'raw materials'
            ]

        self.logger.info("canadian_importers_search_started",
                        city=city,
                        province=province,
                        products=len(product_keywords))

        businesses = []

        try:
            async with aiohttp.ClientSession() as session:
                # CID search by city
                search_url = f"{self.base_url}/importingCity.html"

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }

                # Search for each product keyword
                for keyword in product_keywords:
                    params = {
                        'city': city,
                        'province': province,
                        'product': keyword
                    }

                    try:
                        async with session.get(
                            search_url,
                            params=params,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=20)
                        ) as response:

                            if response.status == 200:
                                html = await response.text()
                                results = self._parse_importer_results(html)
                                businesses.extend(results)
                                self.logger.info("cid_results_found",
                                               keyword=keyword,
                                               count=len(results))
                            else:
                                self.logger.warning("cid_request_failed",
                                                  keyword=keyword,
                                                  status=response.status)

                        # Rate limiting - government site
                        await asyncio.sleep(2)

                        if len(businesses) >= max_results:
                            break

                    except Exception as e:
                        self.logger.debug("cid_keyword_search_failed",
                                        keyword=keyword,
                                        error=str(e))
                        continue

        except Exception as e:
            self.logger.error("canadian_importers_search_failed", error=str(e))

        # Deduplicate
        unique_businesses = self._deduplicate_businesses(businesses)

        return unique_businesses[:max_results]

    def _parse_importer_results(self, html: str) -> List[Dict]:
        """Parse CID search results HTML."""
        businesses = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find company listings in results table
            # CID typically uses tables for results
            table = soup.find('table', class_=re.compile(r'results|data'))

            if table:
                rows = table.find_all('tr')[1:]  # Skip header row

                for row in rows:
                    try:
                        business = self._extract_importer_data(row)
                        if business and business.get('name'):
                            businesses.append(business)
                    except Exception as e:
                        self.logger.debug("row_parse_failed", error=str(e))
                        continue

            else:
                # Try alternative structure - list format
                listings = soup.find_all('div', class_=re.compile(r'(company|importer|business)'))

                for listing in listings:
                    try:
                        business = self._extract_importer_from_div(listing)
                        if business and business.get('name'):
                            businesses.append(business)
                    except Exception as e:
                        self.logger.debug("listing_parse_failed", error=str(e))
                        continue

        except Exception as e:
            self.logger.error("cid_html_parse_failed", error=str(e))

        return businesses

    def _extract_importer_data(self, row) -> Optional[Dict]:
        """Extract business data from table row."""
        business = {}

        try:
            cells = row.find_all(['td', 'th'])

            if len(cells) >= 3:
                # Typical CID format: Company Name | City | Province | Products
                business['name'] = cells[0].get_text(strip=True)
                business['city'] = cells[1].get_text(strip=True)
                business['province'] = cells[2].get_text(strip=True)

                if len(cells) >= 4:
                    business['products_imported'] = cells[3].get_text(strip=True)

                # Try to find contact info in row
                phone_link = row.find('a', href=re.compile(r'tel:'))
                if phone_link:
                    phone = phone_link.get('href', '').replace('tel:', '')
                    business['phone'] = phone

                website_link = row.find('a', href=re.compile(r'http'))
                if website_link and 'canada.ca' not in website_link.get('href', ''):
                    business['website'] = website_link.get('href', '')

            return business if business.get('name') else None

        except Exception as e:
            self.logger.debug("importer_extraction_failed", error=str(e))
            return None

    def _extract_importer_from_div(self, listing) -> Optional[Dict]:
        """Extract business data from div listing."""
        business = {}

        try:
            # Company name
            name_elem = listing.find(['h2', 'h3', 'strong'])
            if name_elem:
                business['name'] = name_elem.get_text(strip=True)

            # Address/Location
            location_elem = listing.find(class_=re.compile(r'(location|address|city)'))
            if location_elem:
                location_text = location_elem.get_text(strip=True)
                business['address'] = location_text

                if 'Hamilton' in location_text:
                    business['city'] = 'Hamilton'
                if 'Ontario' in location_text or 'ON' in location_text:
                    business['province'] = 'Ontario'

            # Products
            products_elem = listing.find(class_=re.compile(r'(product|import|category)'))
            if products_elem:
                business['products_imported'] = products_elem.get_text(strip=True)

            return business if business.get('name') else None

        except Exception as e:
            self.logger.debug("div_extraction_failed", error=str(e))
            return None

    def _deduplicate_businesses(self, businesses: List[Dict]) -> List[Dict]:
        """Remove duplicate businesses."""
        seen_names = set()
        unique = []

        for biz in businesses:
            name = biz.get('name', '').lower().strip()
            if name and name not in seen_names:
                seen_names.add(name)
                unique.append(biz)

        return unique


async def search_hamilton_importers(
    product_types: List[str] = None,
    max_results: int = 50
) -> List[Dict]:
    """
    Convenience function to search Hamilton importers.

    Args:
        product_types: Product categories to search
        max_results: Maximum results

    Returns:
        List of importer businesses in Hamilton
    """
    if product_types is None:
        # Manufacturing-related product categories
        product_types = [
            'machinery',
            'industrial equipment',
            'metal products',
            'steel',
            'raw materials',
            'manufacturing supplies',
            'tools and equipment'
        ]

    searcher = CanadianImportersSearcher()

    results = await searcher.search_importers(
        city='Hamilton',
        province='Ontario',
        product_keywords=product_types,
        max_results=max_results
    )

    return results
