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
from ..sources.openstreetmap import OpenStreetMapSearcher
from ..sources.duckduckgo_businesses import DuckDuckGoBusinessSearcher
from ..sources.yellowpages import YellowPagesSearcher
from ..sources.hamilton_chamber import HamiltonChamberSearcher
from ..sources.canadian_importers import CanadianImportersSearcher
from ..services.source_validator import SourceCrossValidator
from ..utils.fingerprinting import compute_business_fingerprint, businesses_are_duplicates


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
            # 0. PRIORITY #1: DuckDuckGo (Free, no API key, working!)
            if len(all_businesses) < max_results:
                try:
                    ddg_searcher = DuckDuckGoBusinessSearcher()
                    ddg_businesses = await ddg_searcher.search_hamilton_manufacturing(
                        max_results=max_results - len(all_businesses)
                    )

                    # Convert DDG format to standard format
                    for biz in ddg_businesses:
                        business = {
                            'business_name': biz.get('name'),
                            'address': biz.get('street'),
                            'city': biz.get('city', 'Hamilton'),
                            'phone': biz.get('phone'),
                            'website': biz.get('website'),
                            'description': biz.get('description'),
                            'data_source': 'duckduckgo'
                        }
                        all_businesses.append(business)

                    self.logger.info("duckduckgo_businesses_added", count=len(ddg_businesses))
                except Exception as e:
                    self.logger.warning("duckduckgo_fetch_failed", error=str(e))

            # 1. OpenStreetMap (Free, public, but may have rate limits)
            if len(all_businesses) < max_results:
                try:
                    osm_searcher = OpenStreetMapSearcher()
                    osm_businesses = await osm_searcher.search_hamilton_area(
                        industry_types=industry_types,
                        max_results=max_results - len(all_businesses)
                    )

                    # Convert OSM format to standard format
                    for biz in osm_businesses:
                        business = {
                            'business_name': biz.get('name'),
                            'address': biz.get('street'),
                            'city': biz.get('city', 'Hamilton'),
                            'postal_code': biz.get('postal_code'),
                            'phone': biz.get('phone'),
                            'website': biz.get('website'),
                            'latitude': biz.get('latitude'),
                            'longitude': biz.get('longitude'),
                            'industry': industry_types[0] if industry_types else 'general',
                            'data_source': 'openstreetmap'
                        }
                        all_businesses.append(business)

                    self.logger.info("openstreetmap_businesses_added", count=len(osm_businesses))
                except Exception as e:
                    self.logger.warning("openstreetmap_fetch_failed", error=str(e))

            # 1. Yellow Pages Canada (Established B2B directory, FREE)
            if len(all_businesses) < max_results:
                try:
                    yp_businesses = await self._fetch_from_yellowpages(industry_types, max_results - len(all_businesses))
                    all_businesses.extend(yp_businesses)
                    self.logger.info("yellowpages_businesses_added", count=len(yp_businesses))
                except Exception as e:
                    self.logger.warning("yellowpages_fetch_failed", error=str(e))

            # 2. Hamilton Chamber of Commerce (Verified members, HIGH QUALITY)
            if len(all_businesses) < max_results:
                try:
                    chamber_businesses = await self._fetch_from_hamilton_chamber(industry_types, max_results - len(all_businesses))
                    all_businesses.extend(chamber_businesses)
                    self.logger.info("hamilton_chamber_businesses_added", count=len(chamber_businesses))
                except Exception as e:
                    self.logger.warning("hamilton_chamber_fetch_failed", error=str(e))

            # 3. Canadian Importers Database (Government data, official)
            if len(all_businesses) < max_results:
                try:
                    importers_businesses = await self._fetch_from_canadian_importers(industry_types, max_results - len(all_businesses))
                    all_businesses.extend(importers_businesses)
                    self.logger.info("canadian_importers_businesses_added", count=len(importers_businesses))
                except Exception as e:
                    self.logger.warning("canadian_importers_fetch_failed", error=str(e))

            # DEDUPLICATION: Remove duplicates using fingerprinting
            self.logger.info("deduplication_started", total_businesses=len(all_businesses))
            deduplicated_businesses = self._deduplicate_businesses(all_businesses)
            self.logger.info("deduplication_complete",
                           deduplicated=len(deduplicated_businesses),
                           duplicates_removed=len(all_businesses) - len(deduplicated_businesses))

            # CROSS-VALIDATION: Group businesses by name and validate multi-source data
            self.logger.info("cross_validation_started", total_businesses=len(deduplicated_businesses))

            validator = SourceCrossValidator()
            validated_businesses = await self._cross_validate_businesses(deduplicated_businesses, validator)

            self.logger.info("cross_validation_complete",
                           validated_businesses=len(validated_businesses),
                           original_count=len(deduplicated_businesses))

            # Enhance with additional data
            enhanced_businesses = []
            for business in validated_businesses[:max_results]:
                enhanced = await self._enhance_business_data(business)
                if enhanced:
                    enhanced_businesses.append(enhanced)
            
            self.logger.info("business_aggregation_completed", 
                           businesses_found=len(enhanced_businesses))
            
            return enhanced_businesses
            
        except Exception as e:
            self.logger.error("business_aggregation_failed", error=str(e))
            # Return fallback data if all sources fail
            return []  # No fallback - rely on 3 quality sources

    def _deduplicate_businesses(self, businesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate businesses using fingerprinting.

        Keeps the first occurrence of each unique business (by fingerprint).
        Merges data from duplicates into the kept record.

        Args:
            businesses: List of business records

        Returns:
            Deduplicated list with merged data
        """
        if not businesses:
            return []

        seen_fingerprints = {}
        deduplicated = []
        duplicate_count = 0

        for business in businesses:
            # Compute fingerprint
            fingerprint = compute_business_fingerprint(
                name=business.get('business_name', ''),
                street=business.get('address', ''),
                city=business.get('city', ''),
                postal=business.get('postal_code', ''),
                phone=business.get('phone', ''),
                website=business.get('website', '')
            )

            # Add fingerprint to business record
            business['fingerprint'] = fingerprint

            if fingerprint in seen_fingerprints:
                # Duplicate found - merge data into existing record
                duplicate_count += 1
                existing = seen_fingerprints[fingerprint]

                # Merge data (prefer non-null values)
                for key, value in business.items():
                    if value and not existing.get(key):
                        existing[key] = value

                # Track data sources
                existing_sources = existing.get('data_sources', '')
                new_source = business.get('data_source', '')
                if new_source and new_source not in existing_sources:
                    existing['data_sources'] = f"{existing_sources},{new_source}" if existing_sources else new_source

                self.logger.debug("duplicate_business_merged",
                                business_name=business.get('business_name'),
                                fingerprint=fingerprint,
                                sources=existing['data_sources'])
            else:
                # New business - add to results
                seen_fingerprints[fingerprint] = business
                deduplicated.append(business)

        self.logger.info("deduplication_summary",
                        original_count=len(businesses),
                        deduplicated_count=len(deduplicated),
                        duplicates_removed=duplicate_count,
                        deduplication_rate=f"{(duplicate_count / len(businesses) * 100):.1f}%")

        return deduplicated

    async def _fetch_from_hamilton_chamber(self,
                                          industry_types: List[str],
                                          max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch businesses from Hamilton Chamber of Commerce member directory.
        Verified, paying members with high quality data.
        """
        businesses = []

        try:
            chamber_searcher = HamiltonChamberSearcher()

            # Search by industry if specified
            for industry in industry_types:
                results = await chamber_searcher.search_members(
                    industry_type=industry,
                    max_results=max_results // len(industry_types)
                )

                # Convert to standard format
                for biz in results:
                    business = {
                        'business_name': biz.get('name'),
                        'address': biz.get('address'),
                        'city': biz.get('city', 'Hamilton'),
                        'postal_code': biz.get('postal_code'),
                        'phone': biz.get('phone'),
                        'website': biz.get('website'),
                        'industry': industry,
                        'category': biz.get('category'),
                        'description': biz.get('description'),
                        'data_source': 'hamilton_chamber'
                    }
                    businesses.append(business)

                # Rate limiting
                await asyncio.sleep(3)

                if len(businesses) >= max_results:
                    break

            self.logger.info("hamilton_chamber_fetch_complete", count=len(businesses))

        except Exception as e:
            self.logger.error("hamilton_chamber_fetch_failed", error=str(e))

        return businesses[:max_results]

    async def _fetch_from_canadian_importers(self,
                                            industry_types: List[str],
                                            max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch businesses from Canadian Importers Database.
        Government data - official and free.
        """
        businesses = []

        try:
            importers_searcher = CanadianImportersSearcher()

            # Map industry types to product keywords
            product_keywords = {
                'manufacturing': ['machinery', 'equipment', 'metal', 'industrial'],
                'printing': ['printing equipment', 'paper', 'ink'],
                'wholesale': ['raw materials', 'supplies', 'bulk goods'],
                'equipment_rental': ['equipment', 'tools', 'machinery'],
                'professional_services': ['office equipment', 'supplies']
            }

            # Collect all relevant keywords
            all_keywords = []
            for industry in industry_types:
                all_keywords.extend(product_keywords.get(industry, []))

            # Remove duplicates
            all_keywords = list(set(all_keywords))

            results = await importers_searcher.search_importers(
                city='Hamilton',
                province='Ontario',
                product_keywords=all_keywords,
                max_results=max_results
            )

            # Convert to standard format
            for biz in results:
                # Determine industry from products imported
                products = biz.get('products_imported', '').lower()
                industry = 'manufacturing'  # Default
                if 'printing' in products:
                    industry = 'printing'
                elif 'wholesale' in products or 'distribution' in products:
                    industry = 'wholesale'

                business = {
                    'business_name': biz.get('name'),
                    'address': biz.get('address'),
                    'city': biz.get('city', 'Hamilton'),
                    'province': biz.get('province', 'Ontario'),
                    'postal_code': biz.get('postal_code'),
                    'phone': biz.get('phone'),
                    'website': biz.get('website'),
                    'industry': industry,
                    'products_imported': biz.get('products_imported'),
                    'data_source': 'canadian_importers'
                }
                businesses.append(business)

            self.logger.info("canadian_importers_fetch_complete", count=len(businesses))

        except Exception as e:
            self.logger.error("canadian_importers_fetch_failed", error=str(e))

        return businesses[:max_results]

    async def _cross_validate_businesses(
        self,
        businesses: List[Dict[str, Any]],
        validator: SourceCrossValidator
    ) -> List[Dict[str, Any]]:
        """
        Cross-validate businesses from multiple sources.

        Groups businesses by normalized name and validates consistency.
        Merges consensus data from multiple sources.

        Args:
            businesses: List of all businesses from all sources
            validator: SourceCrossValidator instance

        Returns:
            List of validated businesses with consensus data
        """
        if not businesses:
            return []

        # Helper function to normalize business names for grouping
        def normalize_business_name(name: str) -> str:
            """Normalize business name for grouping."""
            if not name:
                return ""
            normalized = name.lower().strip()
            # Remove common suffixes
            for suffix in ['ltd', 'limited', 'inc', 'incorporated', 'corp', 'corporation', 'llc', 'co']:
                normalized = normalized.replace(f' {suffix}', '').replace(f'.{suffix}', '')
            # Remove punctuation
            normalized = normalized.replace('.', '').replace(',', '').replace('&', 'and')
            # Remove extra spaces
            normalized = ' '.join(normalized.split())
            return normalized

        # Group businesses by normalized name
        business_groups = {}
        for biz in businesses:
            name = biz.get('business_name', '')
            if not name:
                continue

            normalized_name = normalize_business_name(name)
            if normalized_name not in business_groups:
                business_groups[normalized_name] = []
            business_groups[normalized_name].append(biz)

        # Validate each group
        validated_businesses = []
        multi_source_count = 0
        single_source_count = 0
        excluded_count = 0

        for normalized_name, group in business_groups.items():
            if len(group) > 1:
                # Multiple sources - cross-validate
                multi_source_count += 1

                try:
                    is_valid, issues, consensus_data = await validator.validate_multi_source_business(
                        group,
                        group[0].get('business_name', '')
                    )

                    if is_valid:
                        # Merge consensus data into first business record
                        merged = group[0].copy()

                        # Update with consensus values (prefer consensus over single source)
                        if consensus_data.get('address'):
                            merged['address'] = consensus_data['address']
                        if consensus_data.get('phone'):
                            merged['phone'] = consensus_data['phone']
                        if consensus_data.get('website'):
                            merged['website'] = consensus_data['website']
                        if consensus_data.get('industry'):
                            merged['industry'] = consensus_data['industry']

                        # Add validation metadata
                        merged['validation_confidence'] = consensus_data.get('validation_confidence', 0.0)
                        merged['validation_issues'] = issues if issues else []
                        merged['source_count'] = len(group)
                        merged['data_sources'] = ','.join([b.get('data_source', 'unknown') for b in group])

                        validated_businesses.append(merged)

                        self.logger.info("multi_source_business_validated",
                                       business_name=group[0].get('business_name'),
                                       source_count=len(group),
                                       confidence=consensus_data.get('validation_confidence', 0.0),
                                       issues_count=len(issues))
                    else:
                        # Failed validation - exclude
                        excluded_count += 1
                        self.logger.warning("multi_source_business_excluded",
                                          business_name=group[0].get('business_name'),
                                          source_count=len(group),
                                          issues=issues)

                except Exception as e:
                    self.logger.error("cross_validation_error",
                                    business_name=group[0].get('business_name', ''),
                                    error=str(e))
                    # On validation error, keep first source
                    validated_businesses.append(group[0])
            else:
                # Single source - accept as-is with metadata
                single_source_count += 1
                single = group[0].copy()
                single['validation_confidence'] = 0.6  # Lower confidence for single source
                single['validation_issues'] = []
                single['source_count'] = 1
                single['data_sources'] = single.get('data_source', 'unknown')
                validated_businesses.append(single)

        self.logger.info("cross_validation_summary",
                        total_groups=len(business_groups),
                        multi_source=multi_source_count,
                        single_source=single_source_count,
                        excluded=excluded_count,
                        validated=len(validated_businesses))

        return validated_businesses

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

    async def _fetch_from_yellowpages(self,
                                     industry_types: List[str],
                                     max_results: int) -> List[Dict[str, Any]]:
        """
        Fetch businesses from Yellow Pages Canada.
        Best B2B coverage of manufacturing/industrial businesses.
        """
        businesses = []

        try:
            yp_searcher = YellowPagesSearcher()

            # Map industry types to Yellow Pages search terms
            search_terms = {
                'manufacturing': ['manufacturing', 'machine shop', 'metal fabrication'],
                'printing': ['printing services', 'commercial printing'],
                'wholesale': ['wholesale distributor', 'industrial supplier'],
                'equipment_rental': ['equipment rental', 'industrial equipment'],
                'professional_services': ['business services']
            }

            # Search for relevant industries
            for industry in industry_types:
                terms = search_terms.get(industry, [industry])
                for term in terms:
                    results = await yp_searcher.search_businesses(term, "Hamilton, ON", max_results // len(terms))

                    # Convert to standard format
                    for biz in results:
                        business = {
                            'business_name': biz.get('name'),
                            'address': biz.get('street'),
                            'city': biz.get('city', 'Hamilton'),
                            'postal_code': biz.get('postal_code'),
                            'phone': biz.get('phone'),
                            'website': biz.get('website'),
                            'industry': industry,
                            'data_source': 'yellowpages'
                        }
                        businesses.append(business)

                    # Rate limiting
                    await asyncio.sleep(2)

                    if len(businesses) >= max_results:
                        break

                if len(businesses) >= max_results:
                    break

            self.logger.info("yellowpages_fetch_complete", count=len(businesses))

        except Exception as e:
            self.logger.error("yellowpages_fetch_failed", error=str(e))

        return businesses[:max_results]

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