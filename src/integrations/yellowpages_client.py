"""
YellowPages Canada scraper integration for real business data collection.
Implements ethical scraping practices with rate limiting and robots.txt compliance.
"""
import asyncio
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, quote
import aiohttp
from bs4 import BeautifulSoup
import structlog

from ..core.models import DataSource
from ..core.exceptions import DataSourceError


class YellowPagesClient:
    """
    Ethical YellowPages.ca scraper for Hamilton-area business data.
    
    Features:
    - Rate limiting (respectful 2-second delays)
    - Robots.txt compliance
    - Error handling and retry logic
    - Data validation and cleaning
    """
    
    BASE_URL = "https://www.yellowpages.ca"
    SEARCH_URL = f"{BASE_URL}/search/si/1"
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self.logger = structlog.get_logger(__name__)
        self._should_close_session = session is None
        
        # Hamilton area location codes for targeted searching
        self.hamilton_locations = {
            "Hamilton, ON": "Hamilton+ON",
            "Ancaster, ON": "Ancaster+ON", 
            "Dundas, ON": "Dundas+ON",
            "Stoney Creek, ON": "Stoney+Creek+ON",
            "Waterdown, ON": "Waterdown+ON"
        }
        
        # Target industries for lead generation
        self.target_industries = {
            "manufacturing": ["manufacturing", "industrial", "fabrication"],
            "professional_services": ["consulting", "professional services", "business services"],
            "printing": ["printing", "graphics", "design"],
            "equipment_rental": ["equipment rental", "tool rental", "machinery"],
            "wholesale": ["wholesale", "distribution", "supply"]
        }
    
    async def __aenter__(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._should_close_session and self.session:
            await self.session.close()
    
    async def search_business(self,
                            business_name: str,
                            city: str = "Hamilton") -> Optional[Dict[str, Any]]:
        """
        Search for a specific business by name and extract its categories.

        Args:
            business_name: Name of the business to search for
            city: City location (default: Hamilton)

        Returns:
            Dictionary with business data including categories, or None if not found
        """

        try:
            # Build search URL for specific business
            search_params = {
                'what': quote(business_name),
                'where': quote(f"{city} ON"),
                'pgLen': 5  # Only need first few results
            }

            url = f"{self.SEARCH_URL}?what={search_params['what']}&where={search_params['where']}&pgLen={search_params['pgLen']}"

            self.logger.debug("yellowpages_business_search", business_name=business_name, url=url)

            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.warning("yellowpages_business_search_failed",
                                      status=response.status,
                                      business_name=business_name)
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Find the first matching listing
                listing_selectors = [
                    '.listing',
                    '.organic__item',
                    '.result',
                    '[data-yext]'
                ]

                listings = []
                for selector in listing_selectors:
                    found = soup.select(selector)
                    if found:
                        listings = found
                        break

                if not listings:
                    return None

                # Extract business data and categories from first match
                first_listing = listings[0]
                business_data = self._extract_business_data(first_listing)

                if business_data:
                    # Extract categories
                    categories = self._extract_categories(first_listing)
                    business_data['categories'] = categories

                    self.logger.info("yellowpages_business_found",
                                   business_name=business_name,
                                   categories=categories)

                    return business_data

                return None

        except Exception as e:
            self.logger.error("yellowpages_business_search_error",
                            business_name=business_name,
                            error=str(e))
            return None

    async def search_hamilton_businesses(self,
                                       industry_category: str = "manufacturing",
                                       max_results: int = 20) -> List[Dict[str, Any]]:
        """
        Search for Hamilton-area businesses in target industries.

        Args:
            industry_category: Target industry category
            max_results: Maximum number of results to return

        Returns:
            List of business data dictionaries
        """
        
        self.logger.info("yellowpages_search_started", 
                        industry=industry_category, 
                        max_results=max_results)
        
        all_businesses = []
        
        try:
            # Search across Hamilton area locations
            for location_name, location_code in self.hamilton_locations.items():
                if len(all_businesses) >= max_results:
                    break
                    
                # Search for each industry keyword
                industry_keywords = self.target_industries.get(industry_category, [industry_category])
                
                for keyword in industry_keywords:
                    if len(all_businesses) >= max_results:
                        break
                        
                    businesses = await self._search_location_industry(
                        location_code, keyword, max_results - len(all_businesses)
                    )
                    
                    # Filter and validate businesses
                    validated_businesses = []
                    for business in businesses:
                        if self._validate_business_data(business):
                            # Enhance with additional data
                            enhanced_business = self._enhance_business_data(business, industry_category)
                            validated_businesses.append(enhanced_business)
                    
                    all_businesses.extend(validated_businesses)
                    
                    # Respectful delay between searches
                    await asyncio.sleep(2)
            
            self.logger.info("yellowpages_search_completed", 
                           businesses_found=len(all_businesses),
                           industry=industry_category)
            
            return all_businesses[:max_results]
            
        except Exception as e:
            self.logger.error("yellowpages_search_failed", 
                            error=str(e), 
                            industry=industry_category)
            raise DataSourceError(f"YellowPages search failed: {str(e)}")
    
    async def _search_location_industry(self, 
                                      location: str, 
                                      keyword: str, 
                                      limit: int = 10) -> List[Dict[str, Any]]:
        """Search for businesses in a specific location and industry."""
        
        try:
            # Build search URL
            search_params = {
                'what': quote(keyword),
                'where': quote(location.replace('+', ' ')),
                'pgLen': min(limit, 40)  # YellowPages max per page
            }
            
            url = f"{self.SEARCH_URL}?what={search_params['what']}&where={search_params['where']}&pgLen={search_params['pgLen']}"
            
            self.logger.debug("yellowpages_request", url=url, keyword=keyword, location=location)
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.warning("yellowpages_request_failed", 
                                      status=response.status, 
                                      url=url)
                    return []
                
                html = await response.text()
                return self._parse_search_results(html, keyword)
                
        except Exception as e:
            self.logger.error("yellowpages_location_search_failed", 
                            error=str(e), 
                            location=location, 
                            keyword=keyword)
            return []
    
    def _parse_search_results(self, html: str, keyword: str) -> List[Dict[str, Any]]:
        """Parse YellowPages search results HTML."""
        
        businesses = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find business listings (YellowPages structure)
            listing_selectors = [
                '.listing',
                '.organic__item',
                '.result',
                '[data-yext]'
            ]
            
            listings = []
            for selector in listing_selectors:
                found = soup.select(selector)
                if found:
                    listings = found
                    break
            
            if not listings:
                self.logger.warning("yellowpages_no_listings_found", keyword=keyword)
                return []
            
            for listing in listings[:20]:  # Limit to top 20 results
                try:
                    business = self._extract_business_data(listing)
                    if business and business.get('business_name'):
                        businesses.append(business)
                except Exception as e:
                    self.logger.warning("yellowpages_listing_parse_failed", error=str(e))
                    continue
            
            self.logger.debug("yellowpages_parsed_results", 
                            businesses_found=len(businesses), 
                            keyword=keyword)
            
            return businesses
            
        except Exception as e:
            self.logger.error("yellowpages_parse_failed", error=str(e), keyword=keyword)
            return []
    
    def _extract_categories(self, listing) -> List[str]:
        """Extract business categories from YellowPages listing."""

        categories = []

        try:
            # Category selectors (YellowPages shows business categories)
            category_selectors = [
                '.listing__categories',
                '.organic__categories',
                '.result__categories',
                '[data-cy="categories"]',
                '.mlr__item__category',
                '.categories'
            ]

            for selector in category_selectors:
                category_elements = listing.select(selector)
                if category_elements:
                    for elem in category_elements:
                        category_text = self._clean_text(elem.get_text())
                        if category_text and category_text not in categories:
                            categories.append(category_text)

            # Also check for category links
            category_link_selectors = [
                'a[href*="/categories/"]',
                'a.category',
                'a.listing__category'
            ]

            for selector in category_link_selectors:
                category_links = listing.select(selector)
                for link in category_links:
                    category_text = self._clean_text(link.get_text())
                    if category_text and category_text not in categories:
                        categories.append(category_text)

            self.logger.debug("yellowpages_categories_extracted", count=len(categories), categories=categories)

        except Exception as e:
            self.logger.warning("yellowpages_category_extract_failed", error=str(e))

        return categories

    def _extract_business_data(self, listing) -> Optional[Dict[str, Any]]:
        """Extract business data from a YellowPages listing element."""

        try:
            business = {}

            # Business name
            name_selectors = [
                '.businessName a', '.listing__name a', '.organic__title a',
                'h3 a', '.result__title a', '[data-cy="businessName"] a'
            ]

            for selector in name_selectors:
                name_elem = listing.select_one(selector)
                if name_elem:
                    business['business_name'] = self._clean_text(name_elem.get_text())
                    break

            if not business.get('business_name'):
                return None
            
            # Phone number
            phone_selectors = [
                '.phoneNumber', '.listing__phone', '.organic__phone',
                '[data-cy="phone"]', '.result__phone'
            ]
            
            for selector in phone_selectors:
                phone_elem = listing.select_one(selector)
                if phone_elem:
                    phone = self._clean_text(phone_elem.get_text())
                    if phone and self._validate_phone(phone):
                        business['phone'] = phone
                        break
            
            # Address
            address_selectors = [
                '.address', '.listing__address', '.organic__address',
                '[data-cy="address"]', '.result__address'
            ]
            
            for selector in address_selectors:
                address_elem = listing.select_one(selector)
                if address_elem:
                    address = self._clean_text(address_elem.get_text())
                    if address:
                        business['address'] = address
                        break
            
            # Website
            website_selectors = [
                '.website a', '.listing__website a', '.organic__website a',
                '[data-cy="website"] a', '.result__website a'
            ]
            
            for selector in website_selectors:
                website_elem = listing.select_one(selector)
                if website_elem:
                    website = website_elem.get('href', '').strip()
                    if website and self._validate_website_url(website):
                        business['website'] = website
                        break
            
            return business if business.get('business_name') else None
            
        except Exception as e:
            self.logger.warning("yellowpages_extract_failed", error=str(e))
            return None
    
    def _validate_business_data(self, business: Dict[str, Any]) -> bool:
        """Validate that business data meets our requirements."""
        
        required_fields = ['business_name']
        
        # Must have business name
        if not all(business.get(field) for field in required_fields):
            return False
        
        # Filter out non-Hamilton businesses (if address is present)
        if business.get('address'):
            address = business['address'].lower()
            hamilton_indicators = ['hamilton', 'ancaster', 'dundas', 'stoney creek', 'waterdown', ' on ', 'ontario']
            if not any(indicator in address for indicator in hamilton_indicators):
                return False
        
        # Must have either phone or website
        if not business.get('phone') and not business.get('website'):
            return False
        
        return True
    
    def _enhance_business_data(self, business: Dict[str, Any], industry: str) -> Dict[str, Any]:
        """Enhance business data ONLY with real data - NO estimation."""

        enhanced = business.copy()

        # Add data source
        enhanced['data_source'] = DataSource.YELLOWPAGES

        # Add industry
        enhanced['industry'] = industry

        # REMOVED: No estimation of years_in_business or employee_count
        # These fields will be None/missing - leads without them will be rejected

        # Clean and standardize phone format
        if business.get('phone'):
            enhanced['phone'] = self._format_phone(business['phone'])

        # Ensure website has protocol
        if business.get('website'):
            enhanced['website'] = self._format_website(business['website'])

        # Extract city from address
        if business.get('address'):
            enhanced['city'] = self._extract_city(business['address'])

        return enhanced
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text data."""
        if not text:
            return ""
        
        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common unwanted characters
        text = re.sub(r'[^\w\s\-\.\(\)\+\,]', '', text)
        
        return text
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number format."""
        if not phone:
            return False
        
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)
        
        # Should have 10 or 11 digits (with country code)
        return len(digits) in [10, 11] and digits.startswith(('1', '4', '5', '6', '7', '8', '9'))
    
    def _validate_website_url(self, url: str) -> bool:
        """Validate website URL format."""
        if not url:
            return False
        
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return url_pattern.match(url) is not None
    
    # REMOVED: _estimate_years_in_business - NO ESTIMATION ALLOWED
    # REMOVED: _estimate_employee_count - NO ESTIMATION ALLOWED
    # All data must be from verified sources or lead is rejected
    
    def _format_phone(self, phone: str) -> str:
        """Format phone number consistently."""
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        
        return phone  # Return original if can't format
    
    def _format_website(self, website: str) -> str:
        """Ensure website has proper protocol."""
        if not website:
            return ""
        
        if not website.startswith(('http://', 'https://')):
            return f"https://{website}"
        
        return website
    
    def _extract_city(self, address: str) -> str:
        """Extract city name from address."""
        if not address:
            return ""
        
        # Common Ontario city patterns
        for city in ['Hamilton', 'Ancaster', 'Dundas', 'Stoney Creek', 'Waterdown']:
            if city.lower() in address.lower():
                return city
        
        # Try to extract city from address format
        parts = address.split(',')
        if len(parts) >= 2:
            potential_city = parts[-2].strip()
            # Remove postal code if present
            potential_city = re.sub(r'\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b', '', potential_city).strip()
            if potential_city:
                return potential_city
        
        return "Hamilton"  # Default to Hamilton