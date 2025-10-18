#!/usr/bin/env python3
"""
Smart Business Discovery Pipeline (v3)

Next-generation lead discovery system with:
✅ Multi-source aggregation (seed list, CME, Innovation Canada, etc.)
✅ Priority-based source ordering
✅ Contact enrichment (email/phone discovery)
✅ Integration with existing validation gates
✅ Source performance tracking
✅ Automatic fallback logic

Replaces: evidence_based_generator.py (v2) which only used OSM
"""
import sys
import asyncio
import aiosqlite
from datetime import datetime
from typing import List, Dict, Optional
import structlog

from src.sources.multi_source_aggregator import MultiSourceAggregator
from src.enrichment.contact_enrichment import ContactEnricher
from src.enrichment.smart_enrichment import SmartEnricher
from src.core.normalization import compute_fingerprint, normalize_name, normalize_phone
from src.core.evidence import Observation, create_observation
from src.services.new_validation_service import ValidationService
from src.core.config import config
from src.exports import CSVExporter, ReportGenerator

logger = structlog.get_logger(__name__)


class SmartDiscoveryPipeline:
    """
    Smart business discovery pipeline with multi-source aggregation.

    Flow:
    1. Discovery (Multi-Source) → Fetch from best sources first
    2. Deduplication → Block duplicates by fingerprint
    3. Contact Enrichment → Find emails/phones from websites
    4. Persistence → Save to database with observations
    5. Geocoding → Update coordinates
    6. Validation → Run through 5 strict gates
    7. Export → Only QUALIFIED leads
    """

    def __init__(self, db_path: str = 'data/leads_v3.db'):
        self.db_path = db_path
        self.aggregator = MultiSourceAggregator()
        self.enricher = ContactEnricher()
        self.smart_enricher = SmartEnricher()  # NEW: Multi-factor revenue estimation
        self.validator = ValidationService()

        self.stats = {
            'discovered': 0,
            'duplicates_blocked': 0,
            'enriched': 0,
            'geocoded': 0,
            'qualified': 0,
            'excluded': 0,
            'review_required': 0,
            'source_breakdown': {}
        }

    def _industry_to_place_types(self, industry: str) -> List[str]:
        """
        Convert industry description to place_types for category gate.

        This allows seed list businesses to pass validation without Google Places API.
        Maps diverse B2B industries to appropriate place_types.
        """
        if not industry:
            return []

        industry_lower = industry.lower()
        place_types = []

        # Manufacturing keywords
        if any(kw in industry_lower for kw in ['manufacturing', 'fabrication', 'machining', 'production']):
            place_types.append('manufacturing')

        if any(kw in industry_lower for kw in ['steel', 'metal', 'aluminum']):
            place_types.append('manufacturing')

        if 'printing' in industry_lower:
            place_types.append('printing')

        if any(kw in industry_lower for kw in ['wholesale', 'distribution', 'distributor']):
            place_types.append('wholesale_distribution')

        if any(kw in industry_lower for kw in ['equipment', 'machinery', 'industrial']):
            place_types.append('manufacturing')

        if any(kw in industry_lower for kw in ['food', 'processing', 'grain', 'meat']):
            place_types.append('food_manufacturing')

        if any(kw in industry_lower for kw in ['chemical', 'plastics', 'injection molding']):
            place_types.append('chemical_manufacturing')

        if any(kw in industry_lower for kw in ['electrical', 'electronics', 'power']):
            place_types.append('manufacturing')

        if 'tool' in industry_lower and 'die' in industry_lower:
            place_types.append('manufacturing')

        if 'precision' in industry_lower:
            place_types.append('manufacturing')

        # Consulting keywords
        if 'consulting' in industry_lower or 'consultant' in industry_lower:
            if any(kw in industry_lower for kw in ['engineering', 'environmental', 'geotechnical']):
                place_types.append('engineering_consulting')
            elif any(kw in industry_lower for kw in ['business', 'management', 'advisory']):
                place_types.append('business_consulting')
            elif 'it' in industry_lower or 'technology' in industry_lower:
                place_types.append('it_consulting')

        # IT & Technology Services
        if any(kw in industry_lower for kw in ['it solutions', 'it services', 'managed services', 'technology services']):
            place_types.append('it_consulting')

        if 'cybersecurity' in industry_lower:
            place_types.append('it_consulting')

        # Marketing & Advertising
        if any(kw in industry_lower for kw in ['marketing', 'advertising', 'agency']):
            place_types.append('marketing_agency')

        # Logistics & Warehousing
        if any(kw in industry_lower for kw in ['logistics', 'warehousing', '3pl', 'distribution']):
            place_types.append('logistics')

        if 'customs' in industry_lower or 'brokerage' in industry_lower:
            place_types.append('logistics')

        # Commercial Services
        if any(kw in industry_lower for kw in ['commercial cleaning', 'janitorial', 'facility']):
            place_types.append('commercial_cleaning')

        if 'security' in industry_lower and 'commercial' in industry_lower:
            place_types.append('security_services')

        # Accounting & Business Services
        if any(kw in industry_lower for kw in ['accounting', 'audit', 'tax']):
            place_types.append('business_consulting')

        # Packaging
        if 'packaging' in industry_lower:
            place_types.append('packaging_services')

        # If no match found, try broader categorization
        if not place_types:
            if 'service' in industry_lower:
                place_types.append('commercial_services')

        # Remove duplicates
        return list(set(place_types))

    async def get_db(self):
        """Get database connection."""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        return db

    async def discover_and_persist(self, business_data) -> Optional[int]:
        """
        Discover business and persist with source tracking.

        Args:
            business_data: BusinessData object from source

        Returns: business_id if new, None if duplicate
        """
        # Compute fingerprint
        fingerprint = compute_fingerprint({
            'name': business_data.name,
            'street': business_data.street or '',
            'city': business_data.city or ''
        })

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
                logger.debug(
                    "duplicate_blocked",
                    fingerprint=fingerprint,
                    existing_name=existing['original_name'],
                    new_name=business_data.name
                )
                return None

            # Insert new business
            cursor = await db.execute(
                """INSERT INTO businesses
                (fingerprint, normalized_name, original_name, street, city, postal_code,
                 phone, website, latitude, longitude, employee_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DISCOVERED')""",
                (
                    fingerprint,
                    normalize_name(business_data.name),
                    business_data.name,
                    business_data.street,
                    business_data.city or 'Hamilton',
                    business_data.postal_code,
                    normalize_phone(business_data.phone or ''),
                    business_data.website,
                    business_data.latitude,
                    business_data.longitude,
                    business_data.employee_count
                )
            )

            await db.commit()
            business_id = cursor.lastrowid

            # Track source
            source = business_data.source
            self.stats['source_breakdown'][source] = self.stats['source_breakdown'].get(source, 0) + 1
            self.stats['discovered'] += 1

            # Create observation for source
            await create_observation(db, Observation(
                business_id=business_id,
                source_url=business_data.source_url,
                field='source',
                value=source,
                confidence=business_data.confidence,
                observed_at=datetime.utcnow()
            ))

            logger.info(
                "business_discovered",
                business_id=business_id,
                name=business_data.name,
                source=source,
                confidence=business_data.confidence
            )

            return business_id

        finally:
            await db.close()

    async def enrich_business(self, business_id: int, business_data) -> bool:
        """
        Enrich business with contact information.

        Uses:
        - Existing data from source
        - Website scraping for emails/phones
        - Contact page discovery
        """
        db = await self.get_db()
        try:
            # Enrich contacts if website available
            if business_data.website:
                enrichment = await self.enricher.enrich_business(
                    business_name=business_data.name,
                    website=business_data.website,
                    existing_phone=business_data.phone,
                    existing_email=business_data.email
                )

                # Create observations for enriched data
                now = datetime.utcnow()

                for email in enrichment['emails']:
                    await create_observation(db, Observation(
                        business_id=business_id,
                        source_url=enrichment['contact_page_url'] or business_data.website,
                        field='email',
                        value=email,
                        confidence=enrichment['confidence'],
                        observed_at=now
                    ))

                for phone in enrichment['phones']:
                    await create_observation(db, Observation(
                        business_id=business_id,
                        source_url=enrichment['contact_page_url'] or business_data.website,
                        field='phone',
                        value=phone,
                        confidence=enrichment['confidence'],
                        observed_at=now
                    ))

            # Create observations from original source data
            now = datetime.utcnow()

            if business_data.street:
                full_address = f"{business_data.street}, {business_data.city or 'Hamilton'}"
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url=business_data.source_url,
                    field='address',
                    value=full_address,
                    confidence=business_data.confidence,
                    observed_at=now
                ))

            if business_data.phone:
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url=business_data.source_url,
                    field='phone',
                    value=business_data.phone,
                    confidence=business_data.confidence,
                    observed_at=now
                ))

            if business_data.postal_code:
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url=business_data.source_url,
                    field='postal_code',
                    value=business_data.postal_code,
                    confidence=business_data.confidence,
                    observed_at=now
                ))

            if business_data.industry:
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url=business_data.source_url,
                    field='industry',
                    value=business_data.industry,
                    confidence=business_data.confidence,
                    observed_at=now
                ))

                # Create synthetic place_types from industry for seed list businesses
                # This allows them to pass category gate without Google Places API
                place_types = self._industry_to_place_types(business_data.industry)
                if place_types:
                    await create_observation(db, Observation(
                        business_id=business_id,
                        source_url=business_data.source_url,
                        field='place_types',
                        value=','.join(place_types),
                        confidence=business_data.confidence,
                        observed_at=now
                    ))

            # NEW: Smart Employee & Revenue Estimation
            # Use SmartEnricher for multi-factor revenue estimation (narrower ranges!)
            if business_data.industry:
                # Step 1: Estimate employee range from industry
                employee_estimate = self.smart_enricher.estimate_employees_from_industry(
                    industry=business_data.industry,
                    city=business_data.city or 'Hamilton'
                )

                # Store employee range observations
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='smart_enrichment',
                    field='employee_range_min',
                    value=str(employee_estimate['employee_range_min']),
                    confidence=employee_estimate['confidence'],
                    observed_at=now
                ))

                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='smart_enrichment',
                    field='employee_range_max',
                    value=str(employee_estimate['employee_range_max']),
                    confidence=employee_estimate['confidence'],
                    observed_at=now
                ))

                # Step 2: Estimate revenue using multi-factor approach
                # Extract signals for revenue estimation
                years_in_business = getattr(business_data, 'years_in_business', None)
                has_website = bool(business_data.website)
                review_count = getattr(business_data, 'review_count', 0)

                revenue_estimate = self.smart_enricher.estimate_revenue_from_employees(
                    employee_min=employee_estimate['employee_range_min'],
                    employee_max=employee_estimate['employee_range_max'],
                    industry=business_data.industry,
                    years_in_business=years_in_business,
                    has_website=has_website,
                    review_count=review_count,
                    city=business_data.city or 'Hamilton'
                )

                # Store revenue observations (with new narrow ranges!)
                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='smart_enrichment',
                    field='revenue_midpoint',
                    value=str(revenue_estimate['revenue_midpoint']),
                    confidence=revenue_estimate['confidence'],
                    observed_at=now
                ))

                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='smart_enrichment',
                    field='revenue_min',
                    value=str(revenue_estimate['revenue_min']),
                    confidence=revenue_estimate['confidence'],
                    observed_at=now
                ))

                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='smart_enrichment',
                    field='revenue_max',
                    value=str(revenue_estimate['revenue_max']),
                    confidence=revenue_estimate['confidence'],
                    observed_at=now
                ))

                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='smart_enrichment',
                    field='revenue_range',
                    value=revenue_estimate['revenue_range'],
                    confidence=revenue_estimate['confidence'],
                    observed_at=now
                ))

                await create_observation(db, Observation(
                    business_id=business_id,
                    source_url='smart_enrichment',
                    field='revenue_estimate',
                    value=revenue_estimate['revenue_estimate'],  # e.g., "$1.2M ±25%"
                    confidence=revenue_estimate['confidence'],
                    observed_at=now
                ))

                logger.info(
                    "smart_revenue_estimation",
                    business_id=business_id,
                    revenue_estimate=revenue_estimate['revenue_estimate'],
                    confidence=f"{revenue_estimate['confidence']:.0%}",
                    margin=f"±{revenue_estimate['factors_used']['margin_percentage']}%"
                )

            # Update status
            await db.execute(
                "UPDATE businesses SET status = 'ENRICHED' WHERE id = ?",
                (business_id,)
            )
            await db.commit()

            self.stats['enriched'] += 1

            logger.info(
                "business_enriched",
                business_id=business_id,
                name=business_data.name
            )

            return True

        except Exception as e:
            logger.error("enrichment_failed", business_id=business_id, error=str(e))
            return False
        finally:
            await db.close()

    async def validate_business(self, business_id: int) -> str:
        """
        Run business through validation gates.

        Returns: 'QUALIFIED', 'EXCLUDED', or 'REVIEW_REQUIRED'
        """
        db = await self.get_db()
        try:
            # Get place types from observations (for category gate)
            cursor = await db.execute(
                "SELECT value FROM observations WHERE business_id = ? AND field = 'place_types'",
                (business_id,)
            )
            row = await cursor.fetchone()
            place_types = row['value'].split(',') if row and row['value'] else []

            # Run validation
            status, reasons = await self.validator.validate_business(db, business_id, place_types)

            # Update status
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
            elif status == 'REVIEW_REQUIRED':
                self.stats['review_required'] += 1

            logger.info(
                "business_validated",
                business_id=business_id,
                status=status,
                reasons=reasons
            )

            return status

        finally:
            await db.close()

    async def generate_leads(self, count: int = 50, industry: str = None, show: bool = False):
        """
        Main pipeline: Multi-source discovery with smart fallback.

        Args:
            count: Target number of QUALIFIED leads
            industry: Industry filter (optional)
            show: Print detailed progress
        """
        print(f"🚀 Smart Business Discovery Pipeline (v3)")
        print(f"{'='*80}")
        print(f"Target: {count} qualified leads")
        print(f"Database: {self.db_path}")
        print(f"Discovery: Multi-source (seed list, CME, IC, etc.)")
        print(f"Enrichment: Contact discovery (email/phone)")
        print(f"Validation: 5 strict gates")
        print(f"{'='*80}\n")

        # Step 1: Multi-source discovery
        fetch_count = count * 15  # 15x multiplier for filtering
        print(f"🔍 Step 1/5: Multi-Source Discovery (target: {fetch_count} raw businesses)")
        print(f"   Sources: Seed list → CME → Innovation Canada → YellowPages → OSM")
        print("-" * 80)

        businesses = await self.aggregator.fetch_from_all_sources(
            target_count=fetch_count,
            location="Hamilton, ON",
            industry=industry
        )

        print(f"\n✅ Discovered {len(businesses)} businesses from {len(set(b.source for b in businesses))} sources\n")

        # Step 2-5: Process each business
        for idx, biz in enumerate(businesses, 1):
            try:
                if show:
                    print(f"[{idx}/{len(businesses)}] Processing: {biz.name} (from {biz.source})")

                # Step 2: Persist (with deduplication)
                business_id = await self.discover_and_persist(biz)

                if business_id is None:
                    if show:
                        print(f"   ⚠️  DUPLICATE - skipped")
                    continue

                # Step 3: Geocode (if coordinates available)
                if biz.latitude and biz.longitude:
                    db = await self.get_db()
                    await db.execute(
                        "UPDATE businesses SET latitude = ?, longitude = ?, status = 'GEOCODED' WHERE id = ?",
                        (biz.latitude, biz.longitude, business_id)
                    )
                    await db.commit()
                    await db.close()
                    self.stats['geocoded'] += 1

                # Step 4: Enrich (contact discovery)
                await self.enrich_business(business_id, biz)

                # Step 5: Validate
                status = await self.validate_business(business_id)

                if show:
                    status_icon = {'QUALIFIED': '✅', 'EXCLUDED': '❌', 'REVIEW_REQUIRED': '⚠️'}.get(status, '?')
                    print(f"   {status_icon} {status}")

                # Check if target reached
                if self.stats['qualified'] >= count:
                    print(f"\n🎉 Target reached! {self.stats['qualified']} qualified leads")
                    break

            except Exception as e:
                logger.error("pipeline_error", business_id=business_id if 'business_id' in locals() else None, error=str(e))
                if show:
                    print(f"   ❌ ERROR: {str(e)}")
                continue

        # Final report
        self.print_stats()
        self.aggregator.print_source_performance()

        # Auto-export: Generate timestamped CSV and report
        await self.auto_export()

    async def auto_export(self):
        """
        Automatically generate timestamped CSV and report files.
        Called after each lead generation run.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        print(f"\n{'='*80}")
        print(f"📄 AUTO-EXPORT: Generating timestamped files")
        print(f"{'='*80}")

        # Export CSV
        csv_path = f"data/leads_{timestamp}.csv"
        csv_exporter = CSVExporter(self.db_path)
        csv_stats = await csv_exporter.export(csv_path)

        print(f"\n✅ CSV Export Complete:")
        print(f"   File: {csv_path}")
        print(f"   Total: {csv_stats['total']} businesses")
        print(f"   Qualified: {csv_stats['qualified']}")
        print(f"   Excluded: {csv_stats['excluded']}")
        print(f"   Review Required: {csv_stats['review_required']}")

        # Generate Report
        report_path = f"data/validation_report_{timestamp}.txt"
        report_gen = ReportGenerator(self.db_path)
        report_stats = await report_gen.generate(report_path)

        print(f"\n✅ Validation Report Complete:")
        print(f"   File: {report_path}")
        print(f"   Lines: {report_stats['lines']}")
        print(f"   Total: {report_stats['total']} businesses")

        print(f"\n{'='*80}")
        print(f"📦 EXPORTS SAVED:")
        print(f"   • {csv_path}")
        print(f"   • {report_path}")
        print(f"{'='*80}\n")

        logger.info(
            "auto_export_complete",
            csv_path=csv_path,
            report_path=report_path,
            total=csv_stats['total']
        )

    def print_stats(self):
        """Print pipeline statistics."""
        print(f"\n{'='*80}")
        print(f"📊 PIPELINE STATISTICS")
        print(f"{'='*80}")
        print(f"Discovered:        {self.stats['discovered']}")
        print(f"Geocoded:          {self.stats['geocoded']}")
        print(f"Enriched:          {self.stats['enriched']}")
        print(f"Qualified:         {self.stats['qualified']} ✅")
        print(f"Excluded:          {self.stats['excluded']}")
        print(f"Review Required:   {self.stats['review_required']}")
        print(f"Duplicates:        {self.stats['duplicates_blocked']}")
        print(f"\n📦 SOURCE BREAKDOWN:")
        for source, count in sorted(self.stats['source_breakdown'].items(), key=lambda x: x[1], reverse=True):
            print(f"   {source:<25} {count:>5} businesses")
        print(f"{'='*80}")

        if self.stats['discovered'] > 0:
            qual_rate = (self.stats['qualified'] / self.stats['discovered']) * 100
            print(f"\nQualification Rate: {qual_rate:.1f}%")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Smart Business Discovery Pipeline v3')
    parser.add_argument('count', type=int, nargs='?', default=50, help='Number of qualified leads')
    parser.add_argument('--industry', type=str, help='Industry filter (e.g., manufacturing)')
    parser.add_argument('--show', action='store_true', help='Show detailed progress')

    args = parser.parse_args()

    pipeline = SmartDiscoveryPipeline()
    await pipeline.generate_leads(count=args.count, industry=args.industry, show=args.show)


if __name__ == '__main__':
    asyncio.run(main())
