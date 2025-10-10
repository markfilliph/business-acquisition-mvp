#!/usr/bin/env python3
"""
Type Mappings Builder - Collects real place types from APIs to build comprehensive mappings.
PRIORITY: P0 - Critical for deployment (prevents retail/gas/auto leakage).

Usage:
    python3 scripts/build_type_mappings.py --sample-size 100 --output type_analysis.json
"""

import argparse
import asyncio
import json
import sys
import os
from typing import Dict, Set, List
from collections import Counter
import structlog

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.sources.places import PlacesService
from src.core.config import settings
from src.sources.google_maps import GoogleMapsSearcher

logger = structlog.get_logger(__name__)


class TypeMappingCollector:
    """Collects and analyzes place types from real API calls."""

    def __init__(self):
        self.places_service = PlacesService(
            google_api_key=settings.google_places_api_key,
            yelp_api_key=settings.yelp_api_key
        )
        self.google_searcher = GoogleMapsSearcher(api_key=settings.google_places_api_key)

        # Track all seen types
        self.google_types_seen: Counter = Counter()
        self.yelp_types_seen: Counter = Counter()
        self.osm_types_seen: Counter = Counter()

        # Track unmapped types
        self.unmapped_google: Set[str] = set()
        self.unmapped_yelp: Set[str] = set()

    async def collect_from_google_maps(self, limit: int = 100) -> List[Dict]:
        """
        Fetch sample businesses from Google Maps to get real-world diversity.

        Args:
            limit: Number of businesses to sample

        Returns:
            List of business dictionaries with name/address
        """
        logger.info("collecting_google_maps_sample", limit=limit)

        # Query multiple categories to get diverse sample
        search_queries = [
            "manufacturing companies Hamilton Ontario",
            "industrial suppliers Hamilton Ontario",
            "machine shops Hamilton Ontario",
            "print shops Hamilton Ontario",
            "metal fabrication Hamilton Ontario",
        ]

        businesses = []
        per_query = limit // len(search_queries)

        for query in search_queries:
            try:
                results = await self.google_searcher.search(query, max_results=per_query)
                for place in results:
                    business = {
                        'name': place.get('name', ''),
                        'address': place.get('formatted_address', ''),
                        'place_id': place.get('place_id', ''),
                    }
                    businesses.append(business)

                    if len(businesses) >= limit:
                        break

            except Exception as e:
                logger.error("google_maps_query_failed", query=query, error=str(e))
                continue

            if len(businesses) >= limit:
                break

        logger.info("google_maps_sample_collected", count=len(businesses))
        return businesses[:limit]

    async def enrich_with_place_types(self, business: Dict) -> Dict:
        """
        Query all place type sources for a business.

        Args:
            business: Dict with name and address

        Returns:
            Enhanced business dict with raw types from each source
        """
        name = business['name']
        address = business['address']

        logger.debug("enriching_business", name=name)

        # Get raw types from each source
        google_types = await self.places_service.get_google_place_types(name, address)
        yelp_types = await self.places_service.get_yelp_categories(name, address)
        osm_types = await self.places_service.get_osm_tags(name, address)

        # Track all seen types
        for gt in google_types:
            self.google_types_seen[gt] += 1
        for yt in yelp_types:
            self.yelp_types_seen[yt] += 1
        for ot in osm_types:
            self.osm_types_seen[ot] += 1

        # Check for unmapped types
        from src.sources.places import GOOGLE_TO_CANONICAL, YELP_TO_CANONICAL, OSM_TO_CANONICAL

        for gt in google_types:
            if gt not in GOOGLE_TO_CANONICAL:
                self.unmapped_google.add(gt)

        for yt in yelp_types:
            if yt not in YELP_TO_CANONICAL:
                self.unmapped_yelp.add(yt)

        business['raw_google_types'] = google_types
        business['raw_yelp_types'] = yelp_types
        business['raw_osm_types'] = osm_types

        return business

    async def collect_sample(self, sample_size: int = 100) -> List[Dict]:
        """
        Main collection pipeline.

        Args:
            sample_size: Number of businesses to sample

        Returns:
            List of businesses with all place type data
        """
        logger.info("starting_collection", sample_size=sample_size)

        # Step 1: Get sample businesses from Google Maps
        businesses = await self.collect_from_google_maps(limit=sample_size)

        # Step 2: Enrich each with place types
        enriched_businesses = []
        for i, business in enumerate(businesses, 1):
            try:
                logger.info("processing_business", progress=f"{i}/{len(businesses)}", name=business['name'])
                enriched = await self.enrich_with_place_types(business)
                enriched_businesses.append(enriched)

                # Rate limiting - small delay between requests
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error("business_enrichment_failed", name=business['name'], error=str(e))
                continue

        logger.info("collection_complete", total=len(enriched_businesses))
        return enriched_businesses

    def analyze_results(self) -> Dict:
        """
        Analyze collected types and generate mapping recommendations.

        Returns:
            Analysis report with unmapped types and frequency counts
        """
        logger.info("analyzing_results")

        analysis = {
            'summary': {
                'total_google_types': len(self.google_types_seen),
                'total_yelp_types': len(self.yelp_types_seen),
                'total_osm_types': len(self.osm_types_seen),
                'unmapped_google_count': len(self.unmapped_google),
                'unmapped_yelp_count': len(self.unmapped_yelp),
            },
            'unmapped_google': sorted(list(self.unmapped_google)),
            'unmapped_yelp': sorted(list(self.unmapped_yelp)),
            'google_type_frequencies': dict(self.google_types_seen.most_common(50)),
            'yelp_type_frequencies': dict(self.yelp_types_seen.most_common(50)),
            'recommendations': self._generate_mapping_recommendations()
        }

        return analysis

    def _generate_mapping_recommendations(self) -> List[Dict]:
        """Generate recommended mappings for unmapped types."""
        recommendations = []

        # Suggest mappings for common unmapped types
        for google_type in sorted(self.unmapped_google, key=lambda x: self.google_types_seen[x], reverse=True)[:20]:
            freq = self.google_types_seen[google_type]

            # Heuristic suggestions based on keywords
            suggestion = self._suggest_canonical_type(google_type)

            recommendations.append({
                'source': 'google',
                'raw_type': google_type,
                'frequency': freq,
                'suggested_canonical': suggestion,
                'action': 'review_manually'
            })

        return recommendations

    def _suggest_canonical_type(self, raw_type: str) -> str:
        """Heuristic to suggest canonical type based on keywords."""
        raw_lower = raw_type.lower()

        # Retail/consumer exclusions
        if any(kw in raw_lower for kw in ['store', 'shop', 'retail', 'supermarket', 'pharmacy']):
            return 'retail_general'
        if any(kw in raw_lower for kw in ['gas', 'fuel', 'petrol']):
            return 'gas_station'
        if any(kw in raw_lower for kw in ['car_dealer', 'auto_dealer', 'dealership']):
            return 'car_dealer'
        if any(kw in raw_lower for kw in ['restaurant', 'food', 'cafe', 'bar', 'diner']):
            return 'restaurant'
        if any(kw in raw_lower for kw in ['salon', 'beauty', 'hair', 'nail', 'spa']):
            return 'salon'

        # Manufacturing/industrial inclusions
        if any(kw in raw_lower for kw in ['manufactur', 'factory', 'plant', 'industrial']):
            return 'manufacturing'
        if any(kw in raw_lower for kw in ['print', 'printing']):
            return 'printing'
        if any(kw in raw_lower for kw in ['warehouse', 'storage', 'distribution']):
            return 'warehousing'
        if any(kw in raw_lower for kw in ['machine', 'equipment', 'tool']):
            return 'industrial_equipment'
        if any(kw in raw_lower for kw in ['metal', 'fabrication', 'welding']):
            return 'metal_fabrication'

        # Default: use raw type as canonical
        return raw_type.lower().replace('-', '_')


async def main():
    parser = argparse.ArgumentParser(description='Build place type mappings from real API data')
    parser.add_argument('--sample-size', type=int, default=100, help='Number of businesses to sample')
    parser.add_argument('--output', type=str, default='type_analysis.json', help='Output file for analysis')
    parser.add_argument('--businesses-output', type=str, default='', help='Optional: save enriched businesses to file')

    args = parser.parse_args()

    collector = TypeMappingCollector()

    # Collect sample data
    enriched_businesses = await collector.collect_sample(sample_size=args.sample_size)

    # Analyze results
    analysis = collector.analyze_results()

    # Save analysis
    with open(args.output, 'w') as f:
        json.dump(analysis, f, indent=2)

    print(f"\n✅ Analysis saved to: {args.output}")
    print(f"\nSummary:")
    print(f"  Google types seen: {analysis['summary']['total_google_types']}")
    print(f"  Yelp types seen: {analysis['summary']['total_yelp_types']}")
    print(f"  Unmapped Google: {analysis['summary']['unmapped_google_count']}")
    print(f"  Unmapped Yelp: {analysis['summary']['unmapped_yelp_count']}")

    # Optionally save enriched businesses
    if args.businesses_output:
        with open(args.businesses_output, 'w') as f:
            json.dump(enriched_businesses, f, indent=2)
        print(f"\n✅ Enriched businesses saved to: {args.businesses_output}")

    print(f"\n⚠️  Next step: Review {args.output} and add mappings to src/sources/places.py")
    print(f"    Focus on unmapped types with high frequency.")


if __name__ == '__main__':
    asyncio.run(main())
