"""
Hamilton Chamber of Commerce Member Directory Integration.
PRIORITY: HIGH - Verified member businesses with high quality data.

Hamilton Chamber members are paying, verified businesses - excellent for B2B leads.
Free web scraping of public member directory.
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
import structlog
from bs4 import BeautifulSoup
import re

logger = structlog.get_logger(__name__)


class HamiltonChamberSearcher:
    """
    Hamilton Chamber of Commerce member directory integration.

    Scrapes public member directory for verified Hamilton businesses.
    Members are paying, verified companies - high quality leads.
    """

    def __init__(self):
        self.base_url = "https://www.hamiltonchamber.ca"
        self.logger = logger

    async def search_members(
        self,
        industry_type: str = None,
        max_results: int = 50
    ) -> List[Dict]:
        """
        Search Hamilton Chamber member directory.

        Args:
            industry_type: Industry filter (e.g., "manufacturing", "wholesale")
            max_results: Maximum results to return

        Returns:
            List of member business dictionaries
        """
        self.logger.info("hamilton_chamber_search_started",
                        industry=industry_type,
                        max_results=max_results)

        businesses = []

        try:
            async with aiohttp.ClientSession() as session:
                # Hamilton Chamber member directory URL
                # Note: Actual URL structure needs verification
                search_url = f"{self.base_url}/members"

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }

                async with session.get(
                    search_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:

                    if response.status == 200:
                        html = await response.text()
                        businesses = self._parse_member_directory(html, industry_type)
                        self.logger.info("hamilton_chamber_results_found", count=len(businesses))
                    else:
                        self.logger.warning("hamilton_chamber_request_failed", status=response.status)

        except asyncio.TimeoutError:
            self.logger.error("hamilton_chamber_timeout")
        except Exception as e:
            self.logger.error("hamilton_chamber_search_failed", error=str(e))

        return businesses[:max_results]

    def _parse_member_directory(self, html: str, industry_filter: str = None) -> List[Dict]:
        """Parse Hamilton Chamber member directory HTML."""
        businesses = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find member listings
            # Note: Actual selectors need to be updated based on site structure
            listings = soup.find_all('div', class_='member-listing')

            if not listings:
                # Try alternative selectors
                listings = soup.find_all('div', class_='business-card')

            if not listings:
                # Try generic approach
                listings = soup.find_all(['article', 'div'], class_=re.compile(r'(member|business|company)'))

            for listing in listings:
                try:
                    business = self._extract_member_data(listing)

                    if business and business.get('name'):
                        # Apply industry filter if specified
                        if industry_filter:
                            if self._matches_industry(business, industry_filter):
                                businesses.append(business)
                        else:
                            businesses.append(business)

                except Exception as e:
                    self.logger.debug("member_parse_failed", error=str(e))
                    continue

        except Exception as e:
            self.logger.error("html_parse_failed", error=str(e))

        return businesses

    def _extract_member_data(self, listing) -> Optional[Dict]:
        """Extract business data from a member listing."""
        business = {}

        try:
            # Business name
            name_elem = (
                listing.find('h2') or
                listing.find('h3') or
                listing.find('a', class_=re.compile(r'(name|title|business)'))
            )

            if name_elem:
                business['name'] = name_elem.get_text(strip=True)

            # Address
            address_elem = listing.find(class_=re.compile(r'address'))
            if address_elem:
                address_text = address_elem.get_text(strip=True)
                business['address'] = address_text

                # Try to extract city and postal code
                if 'Hamilton' in address_text:
                    business['city'] = 'Hamilton'

                postal_match = re.search(r'L[0-9][A-Z]\s*[0-9][A-Z][0-9]', address_text)
                if postal_match:
                    business['postal_code'] = postal_match.group(0)

            # Phone
            phone_elem = listing.find(['a', 'span'], class_=re.compile(r'phone'))
            if not phone_elem:
                # Try finding phone by pattern
                phone_match = listing.find(string=re.compile(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'))
                if phone_match:
                    phone_text = str(phone_match)
                    phone_num = re.search(r'(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', phone_text)
                    if phone_num:
                        business['phone'] = phone_num.group(1)
            elif phone_elem:
                business['phone'] = phone_elem.get_text(strip=True)

            # Website
            website_elem = listing.find('a', href=re.compile(r'http'))
            if website_elem:
                website_url = website_elem.get('href', '')
                # Filter out internal chamber links
                if 'hamiltonchamber' not in website_url.lower():
                    business['website'] = website_url

            # Industry/Category
            category_elem = listing.find(class_=re.compile(r'(category|industry|type)'))
            if category_elem:
                business['category'] = category_elem.get_text(strip=True)

            # Description (helps with LLM classification)
            desc_elem = listing.find(['p', 'div'], class_=re.compile(r'(description|about|summary)'))
            if desc_elem:
                business['description'] = desc_elem.get_text(strip=True)[:500]

            return business if business.get('name') else None

        except Exception as e:
            self.logger.debug("member_extraction_failed", error=str(e))
            return None

    def _matches_industry(self, business: Dict, industry_type: str) -> bool:
        """Check if business matches industry type."""
        industry_keywords = {
            'manufacturing': ['manufacturing', 'manufacturer', 'factory', 'production', 'fabrication'],
            'wholesale': ['wholesale', 'distributor', 'supplier', 'distribution'],
            'printing': ['printing', 'print', 'publisher', 'graphics'],
            'equipment_rental': ['rental', 'equipment', 'lease'],
            'professional_services': ['consulting', 'services', 'professional', 'advisory']
        }

        keywords = industry_keywords.get(industry_type, [industry_type])

        # Check in category
        category = business.get('category', '').lower()
        if any(keyword in category for keyword in keywords):
            return True

        # Check in description
        description = business.get('description', '').lower()
        if any(keyword in description for keyword in keywords):
            return True

        # Check in name
        name = business.get('name', '').lower()
        if any(keyword in name for keyword in keywords):
            return True

        return False


async def search_hamilton_members(
    industry_type: str = None,
    max_results: int = 50
) -> List[Dict]:
    """
    Convenience function to search Hamilton Chamber members.

    Args:
        industry_type: Industry filter
        max_results: Maximum results

    Returns:
        List of member businesses
    """
    searcher = HamiltonChamberSearcher()

    all_businesses = []

    # If specific industry requested, search for that
    if industry_type:
        results = await searcher.search_members(industry_type, max_results)
        all_businesses.extend(results)
    else:
        # Search multiple B2B industries
        industries = [
            'manufacturing',
            'wholesale',
            'printing',
            'equipment_rental',
            'professional_services'
        ]

        for industry in industries:
            results = await searcher.search_members(industry, max_results // len(industries))
            all_businesses.extend(results)

            # Rate limiting - be respectful
            await asyncio.sleep(3)

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
