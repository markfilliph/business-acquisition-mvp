"""
Google Places API Source - Fetch businesses using Places API (New)

Uses Google Places API v2 (New) with Text Search and Place Details.
Migration from legacy API completed.
"""
import asyncio
from typing import List, Optional
import aiohttp
import structlog

from .base_source import BaseBusinessSource, BusinessData
from ..core.config import config
from ..core.resilience import call_with_retry, google_places_limiter

logger = structlog.get_logger(__name__)


class GooglePlacesSource(BaseBusinessSource):
    """
    Fetch businesses from Google Places API (New).

    Features:
    - Text Search API (New) - replaces legacy Nearby Search
    - Place Details API (New) - enhanced field masking
    - POST requests with JSON body
    - Required field masks for response filtering
    - Rate limiting integration
    - Retry logic with exponential backoff

    API Documentation:
    https://developers.google.com/maps/documentation/places/web-service/text-search
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name='google_places', priority=55)
        self.api_key = api_key or config.GOOGLE_PLACES_API_KEY
        # New API v2 base URL
        self.base_url = "https://places.googleapis.com/v1"

        # Hamilton coordinates
        self.hamilton_coords = {
            'lat': 43.2557,
            'lng': -79.8711,
            'radius': 15000  # 15km
        }

        # Industry to Google Places type mapping
        self.industry_types = {
            'manufacturing': ['factory', 'industrial_manufacturer', 'machine_shop', 'metal_fabricator'],
            'printing': ['print_shop', 'printer', 'printing_service'],
            'wholesale': ['wholesaler', 'distributor'],
            'equipment_rental': ['equipment_rental_agency'],
            'professional_services': ['business_consultant', 'consultant', 'accounting'],
            'all': ['establishment']  # Broad search
        }

    def validate_config(self) -> bool:
        """Validate that API key is configured."""
        if not self.api_key:
            self.logger.warning("google_places_api_key_missing")
            return False
        return True

    async def fetch_businesses(
        self,
        location: str = "Hamilton, ON",
        industry: Optional[str] = None,
        max_results: int = 50
    ) -> List[BusinessData]:
        """
        Fetch businesses from Google Places API.

        Strategy:
        1. Use Nearby Search for radius-based discovery
        2. Fall back to Text Search for specific queries
        3. Fetch detailed information for each place

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
            # Get place types for industry
            place_types = self.industry_types.get(industry, self.industry_types['all'])

            self.logger.info(
                "google_places_fetch_started",
                location=location,
                industry=industry,
                place_types=place_types,
                max_results=max_results
            )

            # Search for each place type
            for place_type in place_types:
                if len(all_businesses) >= max_results:
                    break

                # Text search with new API (includes phone/website via field mask)
                search_results = await self._nearby_search(
                    place_type=place_type,
                    max_results=max_results - len(all_businesses)
                )

                all_businesses.extend(search_results)

                # Rate limiting between type searches
                await asyncio.sleep(0.5)

            # New API returns complete data with field mask, no need for details call
            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(len(all_businesses), fetch_time)

            self.logger.info(
                "google_places_fetch_complete",
                businesses_found=len(all_businesses),
                fetch_time=fetch_time
            )

            return all_businesses[:max_results]

        except Exception as e:
            fetch_time = asyncio.get_event_loop().time() - start_time
            self.update_metrics(0, fetch_time, errors=1)
            self.logger.error("google_places_fetch_failed", error=str(e))
            return []

    async def _nearby_search(
        self,
        place_type: str,
        max_results: int = 20
    ) -> List[BusinessData]:
        """
        Perform text search for businesses using new API.

        Uses Text Search (New) API with POST request and field masking.

        Args:
            place_type: Google Places type (or industry query)
            max_results: Maximum results

        Returns:
            List of basic BusinessData (will be enriched with details later)
        """
        businesses = []

        try:
            # Rate limiting
            await google_places_limiter.acquire('google_places')

            async with aiohttp.ClientSession() as session:
                # New API uses POST with JSON body
                url = f"{self.base_url}/places:searchText"

                # Request body for Text Search (New)
                request_body = {
                    "textQuery": f"{place_type} in Hamilton Ontario",
                    "locationBias": {
                        "circle": {
                            "center": {
                                "latitude": self.hamilton_coords['lat'],
                                "longitude": self.hamilton_coords['lng']
                            },
                            "radius": float(self.hamilton_coords['radius'])
                        }
                    },
                    "maxResultCount": min(max_results, 20),  # API limit is 20
                    "languageCode": "en"
                }

                # Required headers for new API
                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    # Field mask - specify which fields to return (includes addressComponents for postal codes)
                    "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.addressComponents,places.location,places.types,places.nationalPhoneNumber,places.internationalPhoneNumber,places.websiteUri,places.businessStatus,places.userRatingCount,places.rating"
                }

                response = await call_with_retry(
                    session.post,
                    url,
                    json=request_body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                )

                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(
                        "google_places_api_error",
                        status=response.status,
                        place_type=place_type,
                        error=error_text
                    )
                    return []

                data = await response.json()

                # New API returns places array directly (no status field)
                places = data.get('places', [])

                if not places:
                    self.logger.debug(
                        "google_places_no_results",
                        place_type=place_type
                    )
                    return []

                # Parse results
                for place_data in places[:max_results]:
                    business = self._parse_place_result_v2(place_data)
                    if business:
                        businesses.append(business)

                self.logger.debug(
                    "google_places_text_search_complete",
                    place_type=place_type,
                    results=len(businesses)
                )

        except Exception as e:
            self.logger.error(
                "google_places_text_search_failed",
                error=str(e),
                place_type=place_type
            )

        return businesses

    def _parse_place_result_v2(self, place_data: dict) -> Optional[BusinessData]:
        """
        Parse a place result from Google Places API (New).

        New API format uses different field names:
        - displayName instead of name
        - formattedAddress instead of vicinity
        - location.latitude/longitude instead of geometry.location

        Args:
            place_data: Raw place data from new API

        Returns:
            BusinessData object or None
        """
        try:
            # Extract basic info
            place_id = place_data.get('id')
            if not place_id:
                return None

            # New API uses displayName.text
            name = place_data.get('displayName', {}).get('text', '')
            if not name:
                return None

            # Location - new format
            location = place_data.get('location', {})
            lat = location.get('latitude')
            lng = location.get('longitude')

            # Address
            formatted_address = place_data.get('formattedAddress', '')

            # Parse address components
            street = ''
            city = 'Hamilton'
            province = 'ON'
            postal_code = None

            # Extract from addressComponents if available (preferred method)
            address_components = place_data.get('addressComponents', [])
            if address_components:
                for component in address_components:
                    types = component.get('types', [])

                    if 'postal_code' in types:
                        postal_code = component.get('longText') or component.get('shortText')
                    elif 'locality' in types:
                        city = component.get('longText', city)
                    elif 'administrative_area_level_1' in types:
                        province = component.get('shortText', province)
                    elif 'route' in types:
                        street_number = next(
                            (c.get('longText') for c in address_components
                             if 'street_number' in c.get('types', [])),
                            ''
                        )
                        route = component.get('longText', '')
                        street = f"{street_number} {route}".strip()

            # Fallback: Extract street from formatted address if not found
            if not street and formatted_address:
                parts = formatted_address.split(',')
                if len(parts) >= 1:
                    street = parts[0].strip()
                if len(parts) >= 2 and city == 'Hamilton':  # Only override if still default
                    city = parts[1].strip()

            # Business types
            types = place_data.get('types', [])
            industry = self._infer_industry_from_types(types)

            # Phone and website (already in response with field mask)
            phone = place_data.get('nationalPhoneNumber') or place_data.get('internationalPhoneNumber')
            website = place_data.get('websiteUri')

            # Review count and rating (NEW - for revenue estimation)
            review_count = place_data.get('userRatingCount', 0)
            rating = place_data.get('rating')

            # Create BusinessData
            business = BusinessData(
                name=name,
                source='google_places',
                source_url=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                confidence=0.90,  # New API has even better data quality
                street=street,
                city=city,
                province=province,
                postal_code=postal_code,
                phone=phone,
                website=website,
                latitude=lat,
                longitude=lng,
                industry=industry,
                review_count=review_count,
                rating=rating,
                raw_data={
                    'place_id': place_id,
                    'types': types,
                    'business_status': place_data.get('businessStatus'),
                    'formatted_address': formatted_address,
                    'review_count': review_count,
                    'rating': rating
                }
            )

            return business

        except Exception as e:
            self.logger.error("google_places_parse_error_v2", error=str(e), data=str(place_data)[:200])
            return None

    def _parse_place_result(self, result: dict) -> Optional[BusinessData]:
        """
        Parse a place result from Google Places API (LEGACY - kept for compatibility).

        Args:
            result: Raw result from API

        Returns:
            BusinessData object or None
        """
        try:
            # Extract basic info
            place_id = result.get('place_id')
            if not place_id:
                return None

            name = result.get('name', '')
            if not name:
                return None

            # Location
            location = result.get('geometry', {}).get('location', {})
            lat = location.get('lat')
            lng = location.get('lng')

            # Address components
            address = result.get('vicinity', '')

            # Business types
            types = result.get('types', [])
            industry = self._infer_industry_from_types(types)

            # Create BusinessData
            business = BusinessData(
                name=name,
                source='google_places',
                source_url=f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                confidence=0.85,  # Google Places has high data quality
                street=address,
                city='Hamilton',  # We're searching in Hamilton
                province='ON',
                latitude=lat,
                longitude=lng,
                industry=industry,
                raw_data={
                    'place_id': place_id,
                    'types': types,
                    'rating': result.get('rating'),
                    'user_ratings_total': result.get('user_ratings_total'),
                    'business_status': result.get('business_status')
                }
            )

            return business

        except Exception as e:
            self.logger.error("google_places_parse_error", error=str(e))
            return None

    async def _get_place_details(self, business: BusinessData) -> Optional[BusinessData]:
        """
        Get detailed information for a place.

        Enriches basic business data with:
        - Phone number
        - Website
        - Full address
        - Opening hours
        - More detailed types

        Args:
            business: Basic BusinessData with place_id

        Returns:
            Enriched BusinessData or None
        """
        place_id = business.raw_data.get('place_id')
        if not place_id:
            return business

        try:
            # Rate limiting
            await google_places_limiter.acquire('google_places')

            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/details/json"
                params = {
                    'place_id': place_id,
                    'fields': 'name,formatted_address,formatted_phone_number,website,address_components,types',
                    'key': self.api_key
                }

                response = await call_with_retry(
                    session.get,
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                )

                if response.status != 200:
                    self.logger.warning(
                        "google_places_details_error",
                        status=response.status,
                        place_id=place_id
                    )
                    return business

                data = await response.json()

                if data.get('status') != 'OK':
                    return business

                result = data.get('result', {})

                # Enrich business data
                if result.get('formatted_phone_number'):
                    business.phone = result['formatted_phone_number']

                if result.get('website'):
                    business.website = result['website']

                # Parse address components for better accuracy
                for component in result.get('address_components', []):
                    types = component.get('types', [])

                    if 'postal_code' in types:
                        business.postal_code = component.get('long_name')
                    elif 'locality' in types:
                        business.city = component.get('long_name')
                    elif 'administrative_area_level_1' in types:
                        business.province = component.get('short_name')
                    elif 'route' in types or 'street_address' in types:
                        street_number = next(
                            (c.get('long_name') for c in result.get('address_components', [])
                             if 'street_number' in c.get('types', [])),
                            ''
                        )
                        street_name = component.get('long_name')
                        if street_number and street_name:
                            business.street = f"{street_number} {street_name}"
                        elif street_name:
                            business.street = street_name

                self.logger.debug(
                    "google_places_details_enriched",
                    place_id=place_id,
                    has_phone=bool(business.phone),
                    has_website=bool(business.website)
                )

                return business

        except Exception as e:
            self.logger.error(
                "google_places_details_fetch_failed",
                error=str(e),
                place_id=place_id
            )
            return business

    def _infer_industry_from_types(self, types: List[str]) -> str:
        """
        Infer industry from Google Places types.

        Args:
            types: List of Google Places types

        Returns:
            Industry classification
        """
        # Priority mapping
        if any(t in types for t in ['factory', 'industrial_manufacturer', 'machine_shop']):
            return 'manufacturing'
        elif any(t in types for t in ['print_shop', 'printer', 'printing_service']):
            return 'printing'
        elif any(t in types for t in ['metal_fabricator', 'welding']):
            return 'metal_fabrication'
        elif any(t in types for t in ['equipment_rental_agency']):
            return 'equipment_rental'
        elif any(t in types for t in ['wholesaler', 'distributor']):
            return 'wholesale'
        elif any(t in types for t in ['business_consultant', 'consultant', 'accounting']):
            return 'professional_services'
        else:
            return 'general_business'
