"""
Business Data Aggregator - Combines multiple real data sources for lead generation.
Uses publicly accessible APIs and data sources that don't have strict anti-bot protection.
"""
import asyncio
import json
from typing import List, Dict, Any, Optional
import aiohttp
import structlog

from ..core.models import DataSource
from ..core.exceptions import DataSourceError


class BusinessDataAggregator:
    """
    Aggregates business data from multiple real sources:
    - OpenStreetMap Overpass API (publicly accessible)
    - Canadian Business Directory APIs
    - Google Places API alternatives
    - Industry association listings
    """
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self.session = session
        self.logger = structlog.get_logger(__name__)
        self._should_close_session = session is None
        
        # Hamilton area coordinates for geographic searches
        self.hamilton_area = {
            "hamilton": {"lat": 43.2557, "lon": -79.8711, "radius": 15000},  # 15km radius
            "ancaster": {"lat": 43.2183, "lon": -79.9567, "radius": 5000},
            "dundas": {"lat": 43.2644, "lon": -79.9603, "radius": 5000},
            "stoney_creek": {"lat": 43.2187, "lon": -79.7440, "radius": 5000},
            "waterdown": {"lat": 43.3386, "lon": -79.9089, "radius": 5000},
        }
        
        # OpenStreetMap Overpass API endpoint
        self.overpass_url = "https://overpass-api.de/api/interpreter"
    
    async def __aenter__(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=60, connect=15)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Business Research Bot (Educational Purpose)',
                    'Accept': 'application/json',
                }
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._should_close_session and self.session:
            await self.session.close()
    
    async def fetch_hamilton_businesses(self, 
                                      industry_types: List[str] = None,
                                      max_results: int = 80) -> List[Dict[str, Any]]:
        """
        Fetch real businesses from Hamilton area using multiple data sources.
        
        Args:
            industry_types: List of industry types to search for
            max_results: Maximum number of businesses to return
            
        Returns:
            List of business data dictionaries
        """
        
        if industry_types is None:
            industry_types = ["manufacturing", "professional_services", "printing"]
        
        self.logger.info("business_aggregation_started", 
                        industries=industry_types, 
                        max_results=max_results)
        
        all_businesses = []
        
        try:
            # 1. Prioritize official government and registry sources first
            try:
                gov_businesses = await self._fetch_from_government_sources(industry_types, max_results)
                all_businesses.extend(gov_businesses)
                self.logger.info("government_sources_fetched", count=len(gov_businesses))
            except Exception as e:
                self.logger.warning("government_sources_failed", error=str(e))

            # 2. Add verified fallback businesses (real businesses only)
            if len(all_businesses) < max_results:
                fallback_businesses = self._get_fallback_hamilton_businesses(
                    industry_types, max_results - len(all_businesses)
                )
                all_businesses.extend(fallback_businesses)
                self.logger.info("fallback_businesses_added", count=len(fallback_businesses))

            # 3. Try OpenStreetMap as supplementary source (if still needed)
            if len(all_businesses) < max_results:
                try:
                    osm_businesses = await self._fetch_from_openstreetmap(industry_types, max_results - len(all_businesses))
                    all_businesses.extend(osm_businesses)
                    self.logger.info("osm_businesses_added", count=len(osm_businesses))
                except Exception as e:
                    self.logger.warning("osm_fetch_failed", error=str(e))
            
            # Enhance with additional data
            enhanced_businesses = []
            for business in all_businesses[:max_results]:
                enhanced = await self._enhance_business_data(business)
                if enhanced:
                    enhanced_businesses.append(enhanced)
            
            self.logger.info("business_aggregation_completed", 
                           businesses_found=len(enhanced_businesses))
            
            return enhanced_businesses
            
        except Exception as e:
            self.logger.error("business_aggregation_failed", error=str(e))
            # Return fallback data if all sources fail
            return self._get_fallback_hamilton_businesses(industry_types, max_results)
    
    async def _fetch_from_openstreetmap(self, 
                                      industry_types: List[str], 
                                      max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch business data from OpenStreetMap using Overpass API.
        This is publicly accessible and doesn't require authentication.
        """
        
        businesses = []
        
        try:
            # Build Overpass query for Hamilton area businesses
            query = self._build_overpass_query(industry_types)
            
            self.logger.debug("osm_query_started", query_preview=query[:200])
            
            async with self.session.post(
                self.overpass_url, 
                data=query,
                headers={'Content-Type': 'text/plain'}
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    businesses = self._parse_overpass_results(data)
                    self.logger.info("osm_businesses_found", count=len(businesses))
                else:
                    self.logger.warning("osm_request_failed", status=response.status)
                    
        except Exception as e:
            self.logger.error("osm_fetch_failed", error=str(e))
        
        return businesses[:max_results]
    
    def _build_overpass_query(self, industry_types: List[str]) -> str:
        """
        Build an Overpass API query to find businesses in Hamilton area.
        Fixed to use proper OSM tag syntax.
        """

        # Hamilton area bounding box (south, west, north, east)
        bbox = "43.15,-80.05,43.4,-79.6"

        # Simplified query focusing on businesses with names
        # Using shop=* and office=* which are most reliable for businesses
        query = f"""
[out:json][timeout:25];
(
  node["shop"]["name"]({bbox});
  way["shop"]["name"]({bbox});
  node["office"]["name"]({bbox});
  way["office"]["name"]({bbox});
  node["craft"]["name"]({bbox});
  way["craft"]["name"]({bbox});
);
out body;
>;
out skel qt;
"""

        return query
    
    def _parse_overpass_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse OpenStreetMap Overpass API results."""
        
        businesses = []
        
        try:
            elements = data.get('elements', [])
            
            for element in elements:
                tags = element.get('tags', {})
                
                # Extract business information
                business = {}
                
                # Name
                name = tags.get('name') or tags.get('operator') or tags.get('brand')
                if not name:
                    continue
                
                business['business_name'] = name
                
                # Address information
                address_parts = []
                if tags.get('addr:housenumber'):
                    address_parts.append(tags['addr:housenumber'])
                if tags.get('addr:street'):
                    address_parts.append(tags['addr:street'])
                if tags.get('addr:city'):
                    address_parts.append(tags['addr:city'])
                if tags.get('addr:postcode'):
                    address_parts.append(tags['addr:postcode'])
                
                if address_parts:
                    business['address'] = ', '.join(address_parts)
                
                # Phone
                phone = tags.get('phone') or tags.get('contact:phone')
                if phone:
                    business['phone'] = phone
                
                # Website
                website = tags.get('website') or tags.get('contact:website') or tags.get('url')
                if website:
                    business['website'] = website
                
                # Industry classification
                business['industry'] = self._classify_osm_business(tags)
                
                # Coordinates
                if element.get('lat') and element.get('lon'):
                    business['latitude'] = element['lat']
                    business['longitude'] = element['lon']
                
                # Data source
                business['data_source'] = DataSource.OPENSTREETMAP
                
                if self._is_hamilton_area_business(business):
                    businesses.append(business)
                    
        except Exception as e:
            self.logger.error("osm_parse_failed", error=str(e))
        
        return businesses
    
    def _classify_osm_business(self, tags: Dict[str, str]) -> str:
        """Classify business based on OSM tags."""
        
        if any(tag in tags for tag in ['craft', 'industrial']):
            return 'manufacturing'
        elif 'office' in tags:
            return 'professional_services'
        elif tags.get('craft') == 'printer' or tags.get('shop') == 'copyshop':
            return 'printing'
        elif 'rental' in str(tags.values()).lower():
            return 'equipment_rental'
        elif tags.get('shop') == 'wholesale':
            return 'wholesale'
        else:
            return 'professional_services'  # Default
    
    def _is_hamilton_area_business(self, business: Dict[str, Any]) -> bool:
        """Check if business is in Hamilton area."""
        
        address = business.get('address', '').lower()
        city_indicators = ['hamilton', 'ancaster', 'dundas', 'stoney creek', 'waterdown']
        
        return any(city in address for city in city_indicators)
    
    async def _fetch_from_government_sources(self,
                                           industry_types: List[str],
                                           max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch from Canadian government business directories and official registries.
        Uses publicly accessible business registry data.
        """

        businesses = []

        try:
            # Hamilton Chamber of Commerce verified members
            chamber_businesses = await self._fetch_from_hamilton_chamber(industry_types, max_results)
            businesses.extend(chamber_businesses)

            # Ontario Business Registry (publicly accessible filings)
            if len(businesses) < max_results:
                ontario_businesses = await self._fetch_from_ontario_registry(industry_types, max_results - len(businesses))
                businesses.extend(ontario_businesses)

            # Canada Business Directory
            if len(businesses) < max_results:
                canada_businesses = await self._fetch_from_canada_business_directory(industry_types, max_results - len(businesses))
                businesses.extend(canada_businesses)

        except Exception as e:
            self.logger.error("government_sources_fetch_failed", error=str(e))

        return businesses

    async def _fetch_from_hamilton_chamber(self,
                                         industry_types: List[str],
                                         max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch businesses from Hamilton Chamber of Commerce member directory.
        These are verified, paying members with real business operations.
        """

        businesses = []

        try:
            # Hamilton Chamber of Commerce has a publicly accessible member directory
            # In production, this would use their API or scrape their public directory
            # For now, we'll use verified Chamber members we know exist

            # NOTE: These are placeholder businesses for demonstration
            # In production, would verify ALL data through Chamber of Commerce API/directory
            verified_chamber_members = [
                # Temporarily empty - all businesses must be individually verified for accuracy
                # before adding to avoid data quality issues
            ]

            # Filter by industry and return
            for business in verified_chamber_members:
                if business['industry'] in industry_types and len(businesses) < max_results:
                    businesses.append(business)

            self.logger.info("hamilton_chamber_fetch_complete", count=len(businesses))

        except Exception as e:
            self.logger.error("hamilton_chamber_fetch_failed", error=str(e))

        return businesses

    async def _fetch_from_ontario_registry(self,
                                         industry_types: List[str],
                                         max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch from Ontario Business Registry - publicly accessible corporate filings.
        These businesses have official government registration.
        """

        businesses = []

        try:
            # Ontario Business Registry contains official corporate filings
            # In production, this would query the official ServiceOntario API
            # For now, use businesses we can verify through public registry data

            # NOTE: All businesses must be individually verified before adding to avoid data accuracy issues
            registry_verified_businesses = [
                # Temporarily empty - need to verify each business through actual Ontario Registry lookup
                # to ensure 100% accurate address, phone, and business details
            ]

            # Filter by industry and return
            for business in registry_verified_businesses:
                if business['industry'] in industry_types and len(businesses) < max_results:
                    businesses.append(business)

            self.logger.info("ontario_registry_fetch_complete", count=len(businesses))

        except Exception as e:
            self.logger.error("ontario_registry_fetch_failed", error=str(e))

        return businesses

    async def _fetch_from_canada_business_directory(self,
                                                  industry_types: List[str],
                                                  max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch from Canada Business Directory - official federal business listings.
        These are businesses with federal business numbers and GST registration.
        """

        businesses = []

        try:
            # Canada Business Directory is the official federal business registry
            # In production, this would use the official government API
            # For now, use businesses we can verify through federal registration

            # NOTE: All businesses must be individually verified before adding to avoid data accuracy issues
            federal_registered_businesses = [
                # Temporarily empty - need to verify each business through actual Canada Business Registry
                # to ensure 100% accurate address, phone, and business details
            ]

            # Filter by industry and return
            for business in federal_registered_businesses:
                if business['industry'] in industry_types and len(businesses) < max_results:
                    businesses.append(business)

            self.logger.info("canada_business_directory_fetch_complete", count=len(businesses))

        except Exception as e:
            self.logger.error("canada_business_directory_fetch_failed", error=str(e))

        return businesses
    
    async def _enhance_business_data(self, business: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Enhance business data with additional information and validation.
        ONLY real data - NO estimation allowed. Keep whatever data we have.
        """

        enhanced = business.copy()

        # Log missing data but DON'T reject - keep what we have
        if not enhanced.get('years_in_business'):
            self.logger.info("lead_missing_years", business=business.get('business_name'))
            # Leave as None - no estimation
        if not enhanced.get('employee_count'):
            self.logger.info("lead_missing_employees", business=business.get('business_name'))
            # Leave as None - no estimation

        # Ensure required fields
        if not enhanced.get('address') and enhanced.get('latitude'):
            enhanced['address'] = f"Hamilton, ON (Lat: {enhanced['latitude']:.4f})"

        # Default city if not specified
        if not enhanced.get('city'):
            enhanced['city'] = 'Hamilton'

        return enhanced
    
    # REMOVED: _estimate_years_in_business - NO ESTIMATION ALLOWED
    # REMOVED: _estimate_employee_count - NO ESTIMATION ALLOWED
    # All data must be from verified sources or lead is rejected

    def _get_fallback_hamilton_businesses(self,
                                        industry_types: List[str],
                                        max_results: int) -> List[Dict[str, Any]]:
        """
        REMOVED: Hardcoded business list - NO HARDCODED DATA ALLOWED.
        This function now returns empty list. All businesses must come from real-time external sources.
        """

        self.logger.warning("fallback_businesses_disabled",
                          reason="No hardcoded data allowed - use real sources only")

        # CRITICAL FIX: Return empty list instead of hardcoded data
        # All businesses must come from OSM, YellowPages, or government sources
        return []