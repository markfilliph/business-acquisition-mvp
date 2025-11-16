#!/usr/bin/env python3
"""
Generate 40 New Business Leads - Post-Filter Implementation
Uses Google Places API to discover businesses and applies new filter system.

Features:
- Fetches businesses from Google Places API
- Applies size filters ($1.5M revenue cap, 25 employee cap)
- Applies business type filters (retail, location labels)
- Generates warning flags for manual review
- Exports to CSV with filter results
"""
import sys
import asyncio
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sources.google_places import GooglePlacesSource
from src.filters.size_filters import filter_by_size
from src.filters.business_type_filters import BusinessTypeFilter
from src.enrichment.warning_generator import generate_warnings
from src.core.config import config
from src.core.models import BusinessLead, ContactInfo, LocationInfo, RevenueEstimate


async def generate_new_leads(target_count: int = 40):
    """
    Generate new business leads using Google Places API.

    Args:
        target_count: Target number of leads after filtering (default 40)
    """
    print(f"\n{'='*70}")
    print(f"🎯 GENERATING {target_count} NEW BUSINESS LEADS")
    print(f"{'='*70}")
    print(f"Source: Google Places API (New)")
    print(f"Location: Hamilton, ON (15km radius)")
    print(f"Filters: Size + Business Type + Warning System")
    print(f"{'='*70}\n")

    # Initialize
    type_filter = BusinessTypeFilter()
    stats = {
        'discovered': 0,
        'excluded_size': 0,
        'excluded_retail': 0,
        'excluded_location': 0,
        'clean': 0,
        'clean_with_warnings': 0
    }

    # Store results
    all_leads = []
    excluded_leads = []

    # Fetch from Google Places
    print("🔍 Step 1/3: Discovering businesses from Google Places API...")

    places_source = GooglePlacesSource()

    # Fetch 3x target to account for filtering (assuming ~33% pass rate)
    fetch_count = target_count * 3

    # Target manufacturing, wholesale, professional services
    industries = ['manufacturing', 'wholesale', 'professional_services', 'printing', 'equipment_rental']

    for industry in industries:
        if len(all_leads) >= fetch_count:
            break

        print(f"   - Fetching {industry} businesses...")
        businesses = await places_source.fetch_businesses(
            location="Hamilton, ON",
            industry=industry,
            max_results=fetch_count // len(industries)
        )

        stats['discovered'] += len(businesses)

        # Convert to dict format for filtering
        for biz in businesses:
            lead_dict = {
                'business_name': biz.name,
                'street_address': biz.street or '',
                'city': biz.city or 'Hamilton',
                'province': biz.province or 'ON',
                'postal_code': biz.postal_code or '',
                'phone': biz.phone or '',
                'website': biz.website or '',
                'industry': industry,
                'data_source': f'Google Places API - {industry}',
                'place_types': ','.join(biz.raw_data.get('place_types', [])) if biz.raw_data else '',
                'review_count': biz.review_count or 0,
                'rating': biz.rating or 0.0,
                # Estimate revenue based on industry avg (will be rough)
                'revenue_estimate': 1_000_000,  # Placeholder
                'employee_count': 15,  # Placeholder - Google doesn't provide this
            }
            all_leads.append(lead_dict)

        # Rate limiting between searches
        await asyncio.sleep(1)

    print(f"✅ Discovered {stats['discovered']} total businesses\n")

    # Step 2: Apply Filters
    print(f"🔍 Step 2/3: Applying filters...")

    clean_leads = []

    for lead in all_leads:
        # Filter 1: Size
        is_oversized, size_reason = filter_by_size(lead)
        if is_oversized:
            stats['excluded_size'] += 1
            excluded_leads.append({**lead, 'exclusion_reason': size_reason})
            continue

        # Filter 2: Retail
        is_retail, retail_reason = type_filter.is_retail_business(
            business_name=lead['business_name'],
            industry=lead.get('industry'),
            website=lead.get('website')
        )
        if is_retail:
            stats['excluded_retail'] += 1
            excluded_leads.append({**lead, 'exclusion_reason': f"RETAIL: {retail_reason}"})
            continue

        # Filter 3: Location Label
        is_location, location_reason = type_filter.is_location_label(
            business_name=lead['business_name'],
            website=lead.get('website'),
            review_count=lead.get('review_count', 0)
        )
        if is_location:
            stats['excluded_location'] += 1
            excluded_leads.append({**lead, 'exclusion_reason': f"LOCATION: {location_reason}"})
            continue

        # Filter 4: Apply Warnings (non-fatal)
        # Create BusinessLead object for warning generator
        try:
            business_lead = BusinessLead(
                business_name=lead['business_name'],
                contact=ContactInfo(
                    phone=lead.get('phone'),
                    website=lead.get('website')
                ),
                location=LocationInfo(
                    street_address=lead.get('street_address', ''),
                    city=lead.get('city', 'Hamilton'),
                    province=lead.get('province', 'ON'),
                    postal_code=lead.get('postal_code', '')
                ),
                revenue_estimate=RevenueEstimate(
                    estimated_amount=lead.get('revenue_estimate', 1_000_000)
                ),
                employee_count=lead.get('employee_count', 15),
                review_count=lead.get('review_count', 0)
            )

            warnings = generate_warnings(business_lead)
            lead['warnings'] = warnings

            if warnings:
                stats['clean_with_warnings'] += 1
            else:
                stats['clean'] += 1

            clean_leads.append(lead)

        except Exception as e:
            print(f"   ⚠️  Warning generation failed for {lead['business_name']}: {str(e)}")
            lead['warnings'] = []
            stats['clean'] += 1
            clean_leads.append(lead)

    print(f"✅ Filtering complete\n")

    # Step 3: Export Results
    print(f"📄 Step 3/3: Exporting results...")

    # Take target_count from clean leads
    final_leads = clean_leads[:target_count]

    # Export to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(__file__).parent.parent / 'data' / 'outputs'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f'NEW_LEADS_{target_count}_{timestamp}.csv'

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'Business Name', 'Street Address', 'City', 'Province', 'Postal Code',
            'Phone', 'Website', 'Industry', 'Data Source', 'Place Types',
            'Review Count', 'Rating', 'Warnings', 'Priority'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lead in final_leads:
            warnings = lead.get('warnings', [])
            priority = 'HIGH' if not warnings else 'MEDIUM'

            writer.writerow({
                'Business Name': lead['business_name'],
                'Street Address': lead.get('street_address', ''),
                'City': lead.get('city', 'Hamilton'),
                'Province': lead.get('province', 'ON'),
                'Postal Code': lead.get('postal_code', ''),
                'Phone': lead.get('phone', ''),
                'Website': lead.get('website', ''),
                'Industry': lead.get('industry', ''),
                'Data Source': lead.get('data_source', 'Google Places API'),
                'Place Types': lead.get('place_types', ''),
                'Review Count': lead.get('review_count', 0),
                'Rating': lead.get('rating', 0.0),
                'Warnings': ' | '.join(warnings) if warnings else 'None',
                'Priority': priority
            })

    print(f"✅ Exported {len(final_leads)} leads to {output_file}\n")

    # Also export exclusions for reference
    exclusions_file = output_dir / f'EXCLUDED_LEADS_{timestamp}.csv'

    with open(exclusions_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Business Name', 'Website', 'Industry', 'Exclusion Reason']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lead in excluded_leads:
            writer.writerow({
                'Business Name': lead['business_name'],
                'Website': lead.get('website', ''),
                'Industry': lead.get('industry', ''),
                'Exclusion Reason': lead.get('exclusion_reason', '')
            })

    print(f"✅ Exported {len(excluded_leads)} exclusions to {exclusions_file}\n")

    # Print final statistics
    print(f"\n{'='*70}")
    print(f"📊 FINAL STATISTICS")
    print(f"{'='*70}")
    print(f"Total Discovered:      {stats['discovered']}")
    print(f"  ├─ Clean (no warn):  {stats['clean']}")
    print(f"  ├─ Clean (warnings): {stats['clean_with_warnings']}")
    print(f"  ├─ Excluded (size):  {stats['excluded_size']}")
    print(f"  ├─ Excluded (retail): {stats['excluded_retail']}")
    print(f"  └─ Excluded (location): {stats['excluded_location']}")
    print(f"\nFinal Output:          {len(final_leads)} leads")
    print(f"  ├─ HIGH priority:    {sum(1 for l in final_leads if not l.get('warnings'))}")
    print(f"  └─ MEDIUM priority:  {sum(1 for l in final_leads if l.get('warnings'))}")
    print(f"\nPass Rate:             {(len(clean_leads) / stats['discovered'] * 100):.1f}%")
    print(f"{'='*70}\n")

    print(f"✅ Done! Check files:")
    print(f"   - {output_file}")
    print(f"   - {exclusions_file}\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate 40 new business leads with filters')
    parser.add_argument('count', type=int, nargs='?', default=40,
                      help='Number of leads to generate (default: 40)')

    args = parser.parse_args()

    await generate_new_leads(target_count=args.count)


if __name__ == '__main__':
    asyncio.run(main())
