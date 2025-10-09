"""
Multi-source place type lookup with canonical mapping.
PRIORITY: P0 - Critical for category validation.
"""

import aiohttp
import json
from typing import List, Optional, Dict, Set
import structlog

from ..core.resilience import call_with_retry, google_places_limiter

logger = structlog.get_logger(__name__)

# Canonical type vocabulary mapping
GOOGLE_TO_CANONICAL = {
    'accounting': 'business_consulting',
    'business_consultant': 'business_consulting',
    'consultant': 'business_consulting',
    'car_dealer': 'car_dealer',
    'car_dealership': 'auto_dealership',
    'convenience_store': 'convenience_store',
    'gas_station': 'gas_station',
    'store': 'retail_general',
    'food': 'restaurant',
    'restaurant': 'restaurant',
    'cafe': 'cafe',
    'bar': 'bar',
    'manufacturing': 'manufacturing',
    'printer': 'printing',
    'sign_shop': 'sign_shop',
    'industrial_equipment_supplier': 'industrial_equipment',
    'equipment_rental_agency': 'equipment_rental',
    'warehouse': 'warehousing',
    'logistics_service': 'logistics',
    'beauty_salon': 'salon',
    'hair_salon': 'salon',
    'nail_salon': 'nail_salon',
    'spa': 'spa',
    'funeral_home': 'funeral_home',
    'insurance_agency': 'insurance_agent',
    'real_estate_agency': 'real_estate_agent',
    'auto_repair': 'auto_repair',
    'electrician': 'electrical',
    'plumber': 'plumbing',
    'hvac_contractor': 'hvac',
    'roofing_contractor': 'roofing',
}

YELP_TO_CANONICAL = {
    'business-consulting': 'business_consulting',
    'auto-dealers': 'car_dealer',
    'convenience-stores': 'convenience_store',
    'gas-stations': 'gas_station',
    'manufacturing': 'manufacturing',
    'printing': 'printing',
    'signmaking': 'sign_shop',
    'warehouse': 'warehousing',
    'logistics': 'logistics',
    'beauty-salon': 'salon',
    'nail-salon': 'nail_salon',
    'funeral-services': 'funeral_home',
    'insurance': 'insurance_agent',
    'real-estate': 'real_estate_agent',
}

OSM_TO_CANONICAL = {
    'office=consulting': 'business_consulting',
    'shop=car': 'car_dealer',
    'shop=convenience': 'convenience_store',
    'amenity=fuel': 'gas_station',
    'craft=manufacturing': 'manufacturing',
    'craft=printer': 'printing',
    'shop=signs': 'sign_shop',
    'building=warehouse': 'warehousing',
    'office=logistics': 'logistics',
}


class PlacesService:
    """Multi-source place type lookup."""

    def __init__(self, google_api_key: Optional[str] = None, yelp_api_key: Optional[str] = None):
        self.google_api_key = google_api_key
        self.yelp_api_key = yelp_api_key
        self.logger = logger

    async def get_google_place_types(self, name: str, address: str) -> List[str]:
        """Query Google Places API for business types."""
        if not self.google_api_key:
            self.logger.warning("google_places_api_key_missing")
            return []

        try:
            await google_places_limiter.acquire('google_places')

            async with aiohttp.ClientSession() as session:
                # Use Place Search to find the business
                search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
                params = {
                    'input': f"{name} {address}",
                    'inputtype': 'textquery',
                    'fields': 'place_id,types',
                    'key': self.google_api_key
                }

                async with session.get(search_url, params=params) as response:
                    if response.status != 200:
                        self.logger.error("google_places_api_error", status=response.status)
                        return []

                    data = await response.json()

                    if data.get('status') != 'OK' or not data.get('candidates'):
                        return []

                    types = data['candidates'][0].get('types', [])
                    return types

        except Exception as e:
            self.logger.error("google_places_lookup_failed", error=str(e))
            return []

    async def get_yelp_categories(self, name: str, address: str) -> List[str]:
        """Query Yelp API for categories."""
        if not self.yelp_api_key:
            self.logger.warning("yelp_api_key_missing")
            return []

        try:
            async with aiohttp.ClientSession() as session:
                search_url = "https://api.yelp.com/v3/businesses/search"
                headers = {'Authorization': f'Bearer {self.yelp_api_key}'}
                params = {
                    'term': name,
                    'location': address,
                    'limit': 1
                }

                async with session.get(search_url, headers=headers, params=params) as response:
                    if response.status != 200:
                        self.logger.error("yelp_api_error", status=response.status)
                        return []

                    data = await response.json()

                    if not data.get('businesses'):
                        return []

                    business = data['businesses'][0]
                    categories = [cat['alias'] for cat in business.get('categories', [])]
                    return categories

        except Exception as e:
            self.logger.error("yelp_lookup_failed", error=str(e))
            return []

    async def get_osm_tags(self, name: str, address: str) -> List[str]:
        """Query OpenStreetMap for tags."""
        try:
            async with aiohttp.ClientSession() as session:
                search_url = "https://nominatim.openstreetmap.org/search"
                params = {
                    'q': f"{name} {address}",
                    'format': 'json',
                    'limit': 1
                }
                headers = {'User-Agent': 'LeadGenerationPipeline/1.0'}

                async with session.get(search_url, params=params, headers=headers) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()

                    if not data:
                        return []

                    # OSM doesn't return detailed business types in search
                    # Would need to query by place_id for full details
                    osm_type = data[0].get('type', '')
                    return [osm_type] if osm_type else []

        except Exception as e:
            self.logger.error("osm_lookup_failed", error=str(e))
            return []

    def map_place_types(self, raw_types: List[str], source: str) -> Set[str]:
        """Map raw place types from source to canonical vocabulary."""
        mapping = {
            'google': GOOGLE_TO_CANONICAL,
            'yelp': YELP_TO_CANONICAL,
            'osm': OSM_TO_CANONICAL,
        }.get(source, {})

        canonical = set()
        for raw_type in raw_types:
            if raw_type in mapping:
                canonical.add(mapping[raw_type])
            else:
                # Log unmapped types for manual review
                self.logger.debug("unmapped_place_type", source=source, type=raw_type)
                # Still add raw type in case it matches whitelist/blacklist directly
                canonical.add(raw_type.lower().replace('-', '_'))

        return canonical

    async def get_merged_types(self, name: str, address: str) -> List[str]:
        """
        Query all sources, normalize, merge.
        Returns union of all types found.
        """
        all_types = set()

        # Query Google Places
        google_types = await self.get_google_place_types(name, address)
        if google_types:
            mapped = self.map_place_types(google_types, 'google')
            all_types.update(mapped)
            self.logger.debug("google_types_mapped", count=len(mapped), types=list(mapped)[:5])

        # Query Yelp
        yelp_types = await self.get_yelp_categories(name, address)
        if yelp_types:
            mapped = self.map_place_types(yelp_types, 'yelp')
            all_types.update(mapped)
            self.logger.debug("yelp_types_mapped", count=len(mapped), types=list(mapped)[:5])

        # Query OSM
        osm_types = await self.get_osm_tags(name, address)
        if osm_types:
            mapped = self.map_place_types(osm_types, 'osm')
            all_types.update(mapped)
            self.logger.debug("osm_types_mapped", count=len(mapped), types=list(mapped)[:5])

        return list(all_types)


async def get_place_data(name: str, address: str, google_key: Optional[str] = None, yelp_key: Optional[str] = None) -> Dict:
    """
    Convenience function to get comprehensive place data.

    Returns:
        {
            'types': List[str],  # Canonical types
            'sources': List[str]  # Which sources returned data
        }
    """
    service = PlacesService(google_api_key=google_key, yelp_api_key=yelp_key)
    types = await service.get_merged_types(name, address)

    sources = []
    if google_key:
        sources.append('google_places')
    if yelp_key:
        sources.append('yelp')

    return {
        'types': types,
        'sources': sources
    }
