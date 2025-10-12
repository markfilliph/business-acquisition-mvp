#!/usr/bin/env python3
"""
Evidence-Based Lead Generator - Production Implementation
Uses new validation system with fingerprinting, evidence tracking, and strict gates.

Based on IMPLEMENTATION_PLAN_UPDATES.md Phase 1.
Replaces quick_generator.py with production-grade validation.
"""
import sys
import asyncio
import aiosqlite
from datetime import datetime
from typing import List, Dict, Optional
import structlog

from src.integrations.business_data_aggregator import BusinessDataAggregator
from src.core.normalization import compute_fingerprint, normalize_name, normalize_address, normalize_phone
from src.core.evidence import Observation, create_observation
from src.services.new_validation_service import ValidationService
from src.sources.places import PlacesService
from src.core.config import config

logger = structlog.get_logger(__name__)


class EvidenceBasedLeadGenerator:
    """
    New lead generation pipeline with evidence tracking.

    Flow:
    1. Discovery → Persist raw (status=DISCOVERED)
    2. Geocode → Update coordinates (status=GEOCODED)
    3. Enrich → Create observations (status=ENRICHED)
    4. Validate → Run gates (status=QUALIFIED/EXCLUDED/REVIEW_REQUIRED)
    5. Export → Only if is_exportable=True
    """

    def __init__(self, db_path: str = 'data/leads_v2.db'):
        self.db_path = db_path
        self.validator = ValidationService()
        self.places_service = PlacesService(
            google_api_key=getattr(config, 'google_api_key', None),
            yelp_api_key=getattr(config, 'yelp_api_key', None)
        )
        self.stats = {
            'discovered': 0,
            'geocoded': 0,
            'enriched': 0,
            'qualified': 0,
            'excluded': 0,
            'review_required': 0,
            'duplicates_blocked': 0,
            'category_blocked': 0,
            'geo_blocked': 0,
            'corroboration_blocked': 0
        }

    async def get_db(self):
        """Get database connection."""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        return db

    async def discover_and_persist(self, business_data: Dict) -> Optional[int]:
        """
        Step 1: Discover business and persist immediately.

        Returns: business_id if new, None if duplicate
        """
        # Compute fingerprint
        fingerprint = compute_fingerprint(business_data)

        db = await self.get_db()
        try:
            # Check for duplicate
            cursor = await db.execute(
                "SELECT id, original_name FROM businesses WHERE fingerprint = ?",
                (fingerprint,)
            )
            existing = await cursor.fetchone()

            if existing:
                self.stats['duplicates_blocked'] += 1
                logger.info("duplicate_blocked",
                          fingerprint=fingerprint,
                          existing_name=existing['original_name'],
                          new_name=business_data.get('name'))
                return None

            # Insert new business
            cursor = await db.execute(
                """INSERT INTO businesses
                (fingerprint, normalized_name, original_name, street, city, postal_code, phone, website, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED')""",
                (
                    fingerprint,
                    normalize_name(business_data.get('name', '')),
                    business_data.get('name'),
                    business_data.get('street'),
                    business_data.get('city', 'Hamilton'),
                    business_data.get('postal_code'),
                    normalize_phone(business_data.get('phone', '')),
                    business_data.get('website'),
                )
            )

            await db.commit()
            business_id = cursor.lastrowid

            self.stats['discovered'] += 1
            logger.info("business_discovered",
                      business_id=business_id,
                      name=business_data.get('name'),
                      fingerprint=fingerprint)

            return business_id

        finally:
            await db.close()

    async def geocode_business(self, business_id: int, address: str) -> bool:
        """
        Step 2: Geocode business to get coordinates.

        For now, uses existing lat/lng from OSM data.
        TODO: Implement proper geocoding service.
        """
        # Placeholder - would call geocoding service here
        # For now, just mark as geocoded if we have coordinates
        db = await self.get_db()
        try:
            await db.execute(
                "UPDATE businesses SET status = 'GEOCODED' WHERE id = ?",
                (business_id,)
            )
            await db.commit()
            self.stats['geocoded'] += 1
            return True
        finally:
            await db.close()

    async def enrich_business(self, business_id: int, business_data: Dict) -> bool:
        """
        Step 3: Enrich business by creating observations.

        Creates observations for:
        - Phone (from OSM/YellowPages)
        - Address (from OSM)
        - Website (from OSM)
        - Place types (from Places API)
        """
        db = await self.get_db()
        try:
            # Update status
            await db.execute(
                "UPDATE businesses SET status = 'ENRICHED' WHERE id = ?",
                (business_id,)
            )

            # Create observations from source data
            now = datetime.utcnow()

            # OSM observations
            if business_data.get('phone'):
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='openstreetmap.org',
                    field='phone',
                    value=business_data['phone'],
                    confidence=0.9,
                    observed_at=now
                ))

            if business_data.get('street'):
                full_address = f"{business_data.get('street', '')}, {business_data.get('city', '')}"
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='openstreetmap.org',
                    field='address',
                    value=full_address,
                    confidence=1.0,
                    observed_at=now
                ))

            if business_data.get('website'):
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='openstreetmap.org',
                    field='website',
                    value=business_data['website'],
                    confidence=0.8,
                    observed_at=now
                ))

            # Get place types from Places API
            name = business_data.get('name', '')
            city = business_data.get('city', 'Hamilton')
            place_types = await self.places_service.get_merged_types(name, city)

            if place_types:
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='places_api',
                    field='place_types',
                    value=','.join(place_types),
                    confidence=0.95,
                    observed_at=now
                ))

            await db.commit()
            self.stats['enriched'] += 1

            logger.info("business_enriched",
                      business_id=business_id,
                      observations_created=4,
                      place_types_count=len(place_types))

            return True

        except Exception as e:
            logger.error("enrichment_failed", business_id=business_id, error=str(e))
            return False
        finally:
            await db.close()

    async def validate_business(self, business_id: int, place_types: List[str]) -> str:
        """
        Step 4: Run validation gates.

        Returns: 'QUALIFIED', 'EXCLUDED', or 'REVIEW_REQUIRED'
        """
        db = await self.get_db()
        try:
            status, reasons = await self.validator.validate_business(db, business_id, place_types)

            # Update business status
            await db.execute(
                "UPDATE businesses SET status = ? WHERE id = ?",
                (status, business_id)
            )
            await db.commit()

            # Update stats
            if status == 'QUALIFIED':
                self.stats['qualified'] += 1
            elif status == 'EXCLUDED':
                self.stats['excluded'] += 1
                # Track exclusion reason
                if reasons:
                    if 'category' in reasons[0].lower():
                        self.stats['category_blocked'] += 1
                    elif 'radius' in reasons[0].lower() or 'geo' in reasons[0].lower():
                        self.stats['geo_blocked'] += 1
                    elif 'corroborat' in reasons[0].lower() or 'conflict' in reasons[0].lower():
                        self.stats['corroboration_blocked'] += 1
            elif status == 'REVIEW_REQUIRED':
                self.stats['review_required'] += 1

            logger.info("business_validated",
                      business_id=business_id,
                      status=status,
                      reasons=reasons)

            return status

        finally:
            await db.close()

    async def generate_leads(self, count: int = 20, show: bool = False):
        """
        Main pipeline: discover → persist → enrich → validate.

        Args:
            count: Target number of QUALIFIED leads
            show: Print detailed progress
        """
        print(f"🎯 Evidence-Based Lead Generation (Production System)")
        print(f"{'='*70}")
        print(f"Target: {count} qualified leads")
        print(f"Database: {self.db_path}")
        print(f"Validation: Category + Geo + Corroboration + Website + Revenue")
        print(f"{'='*70}\n")

        aggregator = BusinessDataAggregator()

        async with aggregator:
            # Fetch more businesses to account for filtering
            fetch_count = count * 15  # 15x multiplier based on expected 93% rejection rate

            print(f"🔍 Step 1/4: Discovering {fetch_count} businesses from OpenStreetMap...")
            # Use target industries from config
            target_industries = ['manufacturing', 'wholesale', 'professional_services', 'printing', 'equipment_rental']
            businesses = await aggregator.fetch_hamilton_businesses(
                industry_types=target_industries,
                max_results=fetch_count
            )

            print(f"📊 Discovered {len(businesses)} raw businesses\n")

            for idx, biz in enumerate(businesses, 1):
                business_id = None  # Initialize to avoid UnboundLocalError
                try:
                    # Step 1: Discover & Persist
                    business_data = {
                        'name': biz.get('business_name', ''),
                        'street': biz.get('address', ''),
                        'city': biz.get('city', 'Hamilton'),
                        'postal_code': biz.get('postal_code'),
                        'phone': biz.get('phone'),
                        'website': biz.get('website'),
                        'latitude': biz.get('latitude'),
                        'longitude': biz.get('longitude')
                    }

                    business_id = await self.discover_and_persist(business_data)

                    if business_id is None:
                        # Duplicate
                        if show:
                            print(f"[{idx}/{len(businesses)}] ⚠️  DUPLICATE: {business_data['name']}")
                        continue

                    if show:
                        print(f"[{idx}/{len(businesses)}] ✅ DISCOVERED: {business_data['name']} (ID: {business_id})")

                    # Step 2: Geocode
                    if business_data.get('latitude') and business_data.get('longitude'):
                        db = await self.get_db()
                        await db.execute(
                            "UPDATE businesses SET latitude = ?, longitude = ?, status = 'GEOCODED' WHERE id = ?",
                            (business_data['latitude'], business_data['longitude'], business_id)
                        )
                        await db.commit()
                        await db.close()
                        self.stats['geocoded'] += 1

                    # Step 3: Enrich
                    await self.enrich_business(business_id, business_data)

                    # Step 4: Validate
                    # Get place types from observations
                    db = await self.get_db()
                    cursor = await db.execute(
                        "SELECT value FROM observations WHERE business_id = ? AND field = 'place_types'",
                        (business_id,)
                    )
                    row = await cursor.fetchone()
                    await db.close()

                    place_types = row['value'].split(',') if row and row['value'] else []

                    status = await self.validate_business(business_id, place_types)

                    if show:
                        status_icon = {
                            'QUALIFIED': '✅',
                            'EXCLUDED': '❌',
                            'REVIEW_REQUIRED': '⚠️'
                        }.get(status, '?')
                        print(f"    {status_icon} {status}: {business_data['name']}")

                    # Check if we've reached target
                    if self.stats['qualified'] >= count:
                        print(f"\n🎉 Target reached! {self.stats['qualified']} qualified leads")
                        break

                except Exception as e:
                    logger.error("pipeline_error", business_id=business_id, error=str(e))
                    if show:
                        print(f"    ❌ ERROR: {str(e)}")
                    continue

        # Print final stats
        self.print_stats()

    def print_stats(self):
        """Print pipeline statistics."""
        print(f"\n{'='*70}")
        print(f"📊 Pipeline Statistics")
        print(f"{'='*70}")
        print(f"Discovered:        {self.stats['discovered']}")
        print(f"Geocoded:          {self.stats['geocoded']}")
        print(f"Enriched:          {self.stats['enriched']}")
        print(f"Qualified:         {self.stats['qualified']} ✅")
        print(f"Excluded:          {self.stats['excluded']}")
        print(f"  - Category:      {self.stats['category_blocked']}")
        print(f"  - Geography:     {self.stats['geo_blocked']}")
        print(f"  - Corroboration: {self.stats['corroboration_blocked']}")
        print(f"Review Required:   {self.stats['review_required']}")
        print(f"Duplicates:        {self.stats['duplicates_blocked']}")
        print(f"{'='*70}")

        if self.stats['discovered'] > 0:
            qual_rate = (self.stats['qualified'] / self.stats['discovered']) * 100
            print(f"\nQualification Rate: {qual_rate:.1f}%")
            print(f"Target: <10% (retail leakage prevention working if <10%)")


async def main():
    """Main entry point matching quick_generator.py interface."""
    import argparse

    parser = argparse.ArgumentParser(description='Evidence-Based Lead Generator')
    parser.add_argument('count', type=int, nargs='?', default=20, help='Number of qualified leads to generate')
    parser.add_argument('--show', action='store_true', help='Show detailed progress')

    args = parser.parse_args()

    generator = EvidenceBasedLeadGenerator()
    await generator.generate_leads(count=args.count, show=args.show)


if __name__ == '__main__':
    asyncio.run(main())
