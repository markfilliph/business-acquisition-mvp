#!/usr/bin/env python3
"""
Generate 100 Business Leads - 20 per Industry
Balanced distribution across 5 target industries with comprehensive filtering.

Target: 20 clean leads per industry × 5 industries = 100 total leads

Industries:
- Manufacturing
- Wholesale
- Professional Services
- Printing
- Equipment Rental
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


async def generate_leads_by_industry(target_per_industry: int = 20):
    """
    Generate leads with balanced distribution across industries.

    Args:
        target_per_industry: Number of clean leads per industry (default 20)
    """
    print(f"\n{'='*70}")
    print(f"🎯 GENERATING {target_per_industry} LEADS PER INDUSTRY")
    print(f"{'='*70}")
    print(f"Target: {target_per_industry} leads × 5 industries = {target_per_industry * 5} total")
    print(f"Source: Google Places API (New)")
    print(f"Location: Hamilton, ON (15km radius)")
    print(f"Filters: Size + Business Type + Warning System")
    print(f"{'='*70}\n")

    # Industries to target
    industries = ['manufacturing', 'wholesale', 'professional_services', 'printing', 'equipment_rental']

    # Initialize
    type_filter = BusinessTypeFilter()
    places_source = GooglePlacesSource()

    # Track results by industry
    results_by_industry = {
        industry: {
            'clean': [],
            'excluded': [],
            'discovered': 0
        } for industry in industries
    }

    total_stats = {
        'discovered': 0,
        'excluded_size': 0,
        'excluded_retail': 0,
        'excluded_location': 0,
        'clean_no_warnings': 0,
        'clean_with_warnings': 0
    }

    # Process each industry
    for industry_idx, industry in enumerate(industries, 1):
        print(f"\n{'='*70}")
        print(f"🔍 Industry {industry_idx}/5: {industry.upper()}")
        print(f"{'='*70}")
        print(f"Target: {target_per_industry} clean leads")

        clean_count = 0
        fetch_rounds = 0
        max_fetch_rounds = 10  # Safety limit

        while clean_count < target_per_industry and fetch_rounds < max_fetch_rounds:
            fetch_rounds += 1

            # Fetch businesses for this industry
            # Start with 30 per round, increase if needed
            fetch_count = 30 if fetch_rounds == 1 else 50

            print(f"\n   Round {fetch_rounds}: Fetching {fetch_count} {industry} businesses...")

            businesses = await places_source.fetch_businesses(
                location="Hamilton, ON",
                industry=industry,
                max_results=fetch_count
            )

            results_by_industry[industry]['discovered'] += len(businesses)
            total_stats['discovered'] += len(businesses)

            print(f"   ✅ Discovered {len(businesses)} businesses")

            # Filter each business
            for biz in businesses:
                # Convert to dict format
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
                    # Conservative estimates (will be rough without enrichment)
                    'revenue_estimate': 1_000_000,
                    'employee_count': 15,
                }

                # Filter 1: Size
                is_oversized, size_reason = filter_by_size(lead_dict)
                if is_oversized:
                    total_stats['excluded_size'] += 1
                    results_by_industry[industry]['excluded'].append({
                        **lead_dict,
                        'exclusion_reason': size_reason
                    })
                    continue

                # Filter 2: Retail
                is_retail, retail_reason = type_filter.is_retail_business(
                    business_name=lead_dict['business_name'],
                    industry=lead_dict.get('industry'),
                    website=lead_dict.get('website')
                )
                if is_retail:
                    total_stats['excluded_retail'] += 1
                    results_by_industry[industry]['excluded'].append({
                        **lead_dict,
                        'exclusion_reason': f"RETAIL: {retail_reason}"
                    })
                    continue

                # Filter 3: Location Label
                is_location, location_reason = type_filter.is_location_label(
                    business_name=lead_dict['business_name'],
                    website=lead_dict.get('website'),
                    review_count=lead_dict.get('review_count', 0)
                )
                if is_location:
                    total_stats['excluded_location'] += 1
                    results_by_industry[industry]['excluded'].append({
                        **lead_dict,
                        'exclusion_reason': f"LOCATION: {location_reason}"
                    })
                    continue

                # Filter 4: Apply Warnings
                try:
                    business_lead = BusinessLead(
                        business_name=lead_dict['business_name'],
                        contact=ContactInfo(
                            phone=lead_dict.get('phone'),
                            website=lead_dict.get('website')
                        ),
                        location=LocationInfo(
                            street_address=lead_dict.get('street_address', ''),
                            city=lead_dict.get('city', 'Hamilton'),
                            province=lead_dict.get('province', 'ON'),
                            postal_code=lead_dict.get('postal_code', '')
                        ),
                        revenue_estimate=RevenueEstimate(
                            estimated_amount=lead_dict.get('revenue_estimate', 1_000_000)
                        ),
                        employee_count=lead_dict.get('employee_count', 15),
                        review_count=lead_dict.get('review_count', 0)
                    )

                    warnings = generate_warnings(business_lead)
                    lead_dict['warnings'] = warnings
                    lead_dict['priority'] = 'HIGH' if not warnings else 'MEDIUM'

                    if warnings:
                        total_stats['clean_with_warnings'] += 1
                    else:
                        total_stats['clean_no_warnings'] += 1

                except Exception as e:
                    # If warning generation fails, still keep the lead but mark as needing review
                    lead_dict['warnings'] = [f"WARNING_GENERATION_FAILED: {str(e)}"]
                    lead_dict['priority'] = 'MEDIUM'
                    total_stats['clean_with_warnings'] += 1

                # Add to clean leads
                results_by_industry[industry]['clean'].append(lead_dict)
                clean_count += 1

                # Stop if we've reached the target for this industry
                if clean_count >= target_per_industry:
                    break

            print(f"   📊 Clean leads so far: {clean_count}/{target_per_industry}")

            # Rate limiting between rounds
            if clean_count < target_per_industry:
                await asyncio.sleep(2)

        # Summary for this industry
        print(f"\n   ✅ {industry.upper()} COMPLETE:")
        print(f"      - Discovered: {results_by_industry[industry]['discovered']}")
        print(f"      - Clean leads: {len(results_by_industry[industry]['clean'])}")
        print(f"      - Excluded: {len(results_by_industry[industry]['excluded'])}")

    # Export Results
    print(f"\n{'='*70}")
    print(f"📄 EXPORTING RESULTS")
    print(f"{'='*70}\n")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(__file__).parent.parent / 'data' / 'outputs'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export all clean leads to one file
    all_clean_leads = []
    for industry in industries:
        all_clean_leads.extend(results_by_industry[industry]['clean'][:target_per_industry])

    output_file = output_dir / f'NEW_100_LEADS_BY_INDUSTRY_{timestamp}.csv'

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'Business Name', 'Street Address', 'City', 'Province', 'Postal Code',
            'Phone', 'Website', 'Industry', 'Data Source', 'Place Types',
            'Review Count', 'Rating', 'Warnings', 'Priority'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lead in all_clean_leads:
            warnings = lead.get('warnings', [])

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
                'Priority': lead.get('priority', 'MEDIUM')
            })

    print(f"✅ Exported {len(all_clean_leads)} leads to {output_file}\n")

    # Export exclusions
    all_excluded = []
    for industry in industries:
        all_excluded.extend(results_by_industry[industry]['excluded'])

    exclusions_file = output_dir / f'EXCLUDED_100_LEADS_{timestamp}.csv'

    with open(exclusions_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Business Name', 'Website', 'Industry', 'Exclusion Reason']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lead in all_excluded:
            writer.writerow({
                'Business Name': lead['business_name'],
                'Website': lead.get('website', ''),
                'Industry': lead.get('industry', ''),
                'Exclusion Reason': lead.get('exclusion_reason', '')
            })

    print(f"✅ Exported {len(all_excluded)} exclusions to {exclusions_file}\n")

    # Print final statistics
    print(f"\n{'='*70}")
    print(f"📊 FINAL STATISTICS")
    print(f"{'='*70}")
    print(f"\nTotal Discovered:      {total_stats['discovered']}")
    print(f"  ├─ Clean (no warn):  {total_stats['clean_no_warnings']}")
    print(f"  ├─ Clean (warnings): {total_stats['clean_with_warnings']}")
    print(f"  ├─ Excluded (size):  {total_stats['excluded_size']}")
    print(f"  ├─ Excluded (retail): {total_stats['excluded_retail']}")
    print(f"  └─ Excluded (location): {total_stats['excluded_location']}")

    print(f"\n{'='*70}")
    print(f"BY INDUSTRY BREAKDOWN")
    print(f"{'='*70}")
    for industry in industries:
        stats = results_by_industry[industry]
        clean = len(stats['clean'])
        excluded = len(stats['excluded'])
        discovered = stats['discovered']
        pass_rate = (clean / discovered * 100) if discovered > 0 else 0

        print(f"\n{industry.upper()}")
        print(f"  Discovered: {discovered}")
        print(f"  Clean:      {clean}")
        print(f"  Excluded:   {excluded}")
        print(f"  Pass Rate:  {pass_rate:.1f}%")

    print(f"\n{'='*70}")
    print(f"FINAL OUTPUT")
    print(f"{'='*70}")
    print(f"Total Clean Leads:     {len(all_clean_leads)}")
    print(f"  ├─ HIGH priority:    {sum(1 for l in all_clean_leads if l.get('priority') == 'HIGH')}")
    print(f"  └─ MEDIUM priority:  {sum(1 for l in all_clean_leads if l.get('priority') == 'MEDIUM')}")
    print(f"\nOverall Pass Rate:     {(len(all_clean_leads) / total_stats['discovered'] * 100):.1f}%")
    print(f"{'='*70}\n")

    print(f"✅ Done! Check files:")
    print(f"   - {output_file}")
    print(f"   - {exclusions_file}\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate 100 business leads (20 per industry)'
    )
    parser.add_argument(
        '--per-industry',
        type=int,
        default=20,
        help='Number of leads per industry (default: 20)'
    )

    args = parser.parse_args()

    await generate_leads_by_industry(target_per_industry=args.per_industry)


if __name__ == '__main__':
    asyncio.run(main())
