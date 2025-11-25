#!/usr/bin/env python3
"""
Enrich existing Burlington leads with owner info and master processing
"""
import asyncio
import csv
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.enrichment.owner_lookup import lookup_owners_for_leads_combined
from src.pipeline.master_lead_processor import process_leads_file


async def main():
    print("\n" + "="*70)
    print("ENRICHING BURLINGTON LEADS")
    print("="*70)

    # Input file
    input_file = "data/outputs/BURLINGTON_RELAXED_53_LEADS_20251123_225658.csv"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n📁 Input: {input_file}")

    # Read existing leads
    leads = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append({
                'business_name': row['Business Name'],
                'website': row['Website'],
                'street_address': row['Street Address'],
                'city': row['City'],
                'province': row['Province'],
                'postal_code': row['Postal Code'],
                'phone': row['Phone'],
                'industry': row['Industry'],
                'revenue_estimate': row['Estimated Revenue (CAD)'],
                'revenue_range': row['Estimated Revenue Range'],
                'employee_range': row['Estimated Employees (Range)'],
                'sde_estimate': row['SDE Estimate'],
                'confidence_score': row['Confidence Score'],
                'data_source': row['Data Source'],
                'place_types': row['Place Types'],
                'review_count': row['Review Count'],
                'rating': row['Rating'],
                'warnings': row['Warnings'],
                'priority': row['Priority']
            })

    print(f"✅ Loaded {len(leads)} leads\n")

    # Step 1: Owner lookup (Website + WHOIS + LinkedIn)
    print("👤 STEP 1: OWNER LOOKUP (Website + WHOIS + LinkedIn)")
    print("="*70)
    enriched_leads = await lookup_owners_for_leads_combined(leads, use_linkedin=True)

    # Step 2: Export with owner info
    output_with_owners = f"data/outputs/BURLINGTON_53_WITH_OWNERS_{timestamp}.csv"

    with open(output_with_owners, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'Business Name', 'Street Address', 'City', 'Province', 'Postal Code',
            'Phone', 'Website', 'Industry',
            'Owner/Contact Name', 'Owner Confidence', 'Owner Source',
            'LinkedIn Name', 'LinkedIn URL', 'LinkedIn Title',
            'Estimated Revenue (CAD)', 'Estimated Revenue Range',
            'Estimated Employees (Range)', 'SDE Estimate', 'Confidence Score',
            'Data Source', 'Place Types', 'Review Count', 'Rating',
            'Warnings', 'Priority'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for lead in enriched_leads:
            writer.writerow({
                'Business Name': lead['business_name'],
                'Street Address': lead['street_address'],
                'City': lead['city'],
                'Province': lead['province'],
                'Postal Code': lead['postal_code'],
                'Phone': lead['phone'],
                'Website': lead['website'],
                'Industry': lead['industry'],
                'Owner/Contact Name': lead.get('owner_name', ''),
                'Owner Confidence': lead.get('owner_confidence', 'none'),
                'Owner Source': lead.get('owner_source', ''),
                'LinkedIn Name': lead.get('linkedin_name', ''),
                'LinkedIn URL': lead.get('linkedin_url', ''),
                'LinkedIn Title': lead.get('linkedin_title', ''),
                'Estimated Revenue (CAD)': lead['revenue_estimate'],
                'Estimated Revenue Range': lead['revenue_range'],
                'Estimated Employees (Range)': lead['employee_range'],
                'SDE Estimate': lead['sde_estimate'],
                'Confidence Score': lead['confidence_score'],
                'Data Source': lead['data_source'],
                'Place Types': lead['place_types'],
                'Review Count': lead['review_count'],
                'Rating': lead['rating'],
                'Warnings': lead['warnings'],
                'Priority': lead['priority']
            })

    print(f"\n✅ Exported {len(enriched_leads)} leads WITH OWNER INFO")
    print(f"📁 File: {output_with_owners}\n")

    # Step 3: Run master lead processor
    print("🔵 STEP 2: MASTER LEAD PROCESSOR")
    print("="*70)
    print("Standardizing leads according to acquisition thesis...\n")

    standardized_file = process_leads_file(output_with_owners)

    print(f"\n✅ Master processing complete!")
    print(f"📁 FINAL OUTPUT: {standardized_file}\n")

    # Print summary
    owners_found = sum(1 for lead in enriched_leads if lead.get('owner_name'))
    print("="*70)
    print("🎯 ENRICHMENT COMPLETE")
    print("="*70)
    print(f"Total leads:           {len(enriched_leads)}")
    print(f"Owners found:          {owners_found} ({owners_found/len(enriched_leads)*100:.1f}%)")
    print(f"\nFiles created:")
    print(f"  1. {output_with_owners}")
    print(f"  2. {standardized_file}")
    print("="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
