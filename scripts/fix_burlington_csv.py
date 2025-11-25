#!/usr/bin/env python3
"""
Fix the corrupted Burlington CSV by cleaning owner names
"""
import asyncio
import csv
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.enrichment.owner_lookup import lookup_owners_for_leads_combined


async def main():
    print("\n" + "="*70)
    print("FIXING BURLINGTON LEADS - PROPER CSV EXPORT")
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

    # Owner lookup
    print("👤 OWNER LOOKUP (Website + WHOIS + LinkedIn)")
    print("="*70)
    enriched_leads = await lookup_owners_for_leads_combined(leads, use_linkedin=False)

    # Clean owner names - remove newlines
    for lead in enriched_leads:
        if lead.get('owner_name'):
            # Remove all whitespace/newlines and clean
            owner = str(lead['owner_name']).replace('\n', ' ').replace('\r', ' ')
            owner = ' '.join(owner.split())  # Normalize whitespace
            lead['owner_name'] = owner if owner else ''

    # Export with proper CSV quoting
    output_file = f"data/outputs/BURLINGTON_53_WITH_OWNERS_{timestamp}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'Business Name', 'Street Address', 'City', 'Province', 'Postal Code',
            'Phone', 'Website', 'Industry',
            'Owner/Contact Name', 'Owner Confidence', 'Owner Source',
            'Estimated Revenue (CAD)', 'Estimated Revenue Range',
            'Estimated Employees (Range)', 'SDE Estimate', 'Confidence Score',
            'Data Source', 'Place Types', 'Review Count', 'Rating',
            'Warnings', 'Priority'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
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

    print(f"\n✅ Exported {len(enriched_leads)} leads")
    print(f"📁 File: {output_file}\n")

    # Verify the file
    with open(output_file, 'r', encoding='utf-8') as f:
        line_count = sum(1 for line in f)
        print(f"✅ Verification: {line_count} lines (should be 54 = header + 53 leads)")

    # Print summary
    owners_found = sum(1 for lead in enriched_leads if lead.get('owner_name'))
    print("\n" + "="*70)
    print("🎯 COMPLETE")
    print("="*70)
    print(f"Total leads:           {len(enriched_leads)}")
    print(f"Owners found:          {owners_found} ({owners_found/len(enriched_leads)*100:.1f}%)")
    print(f"Output file:           {output_file}")
    print("="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
