#!/usr/bin/env python3
"""
Deduplicate and clean the consolidated leads file.

Removes:
1. Duplicate businesses (same phone/website) across industries
2. Businesses that fail the FIXED balanced filters
"""
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import sys

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.analysis.pre_qualification_filters_balanced import pre_qualify_lead_balanced


def deduplicate_and_clean():
    """Deduplicate and filter consolidated leads."""

    input_file = Path("data/outputs/HOT_LEADS_CONSOLIDATED_20_LEADS_20251119_083809.csv")

    if not input_file.exists():
        print(f"❌ File not found: {input_file}")
        return

    print("\n" + "="*80)
    print("DEDUPLICATING AND CLEANING CONSOLIDATED LEADS")
    print("="*80)
    print(f"Input: {input_file.name}\n")

    # Read all leads
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_leads = list(reader)

    print(f"Total leads in input: {len(all_leads)}")
    print()

    # Step 1: Deduplicate by phone number (most reliable)
    print("STEP 1: Deduplicating by phone number...")
    phone_map = {}
    duplicates_found = 0

    for lead in all_leads:
        phone = lead.get('phone', '').strip()

        if not phone:
            # No phone - use website as fallback
            phone = lead.get('website', '').strip()

        if phone in phone_map:
            # Duplicate found
            duplicates_found += 1
            existing = phone_map[phone]

            # Keep the one with more data or first one encountered
            print(f"  ⚠️  Duplicate: {lead['business_name']} ({lead['industry']}) = " +
                  f"{existing['business_name']} ({existing['industry']})")

            # Keep the first industry encountered (manufacturing > wholesale > others)
            industry_priority = {'manufacturing': 1, 'wholesale': 2, 'equipment_rental': 3,
                               'professional_services': 4, 'printing': 5}

            existing_priority = industry_priority.get(existing['industry'], 99)
            lead_priority = industry_priority.get(lead['industry'], 99)

            if lead_priority < existing_priority:
                # Replace with higher priority industry
                phone_map[phone] = lead
                print(f"      Keeping: {lead['industry']} (higher priority)")
            else:
                print(f"      Keeping: {existing['industry']} (first encountered)")
        else:
            phone_map[phone] = lead

    unique_leads = list(phone_map.values())
    print(f"  ✅ Removed {duplicates_found} duplicates")
    print(f"  ✅ Unique leads: {len(unique_leads)}")
    print()

    # Step 2: Filter with FIXED balanced filters
    print("STEP 2: Filtering with FIXED balanced filters...")
    clean_leads = []
    rejected_leads = []

    for lead in unique_leads:
        business_name = lead.get('business_name', '')
        industry = lead.get('industry', 'manufacturing')

        # Parse place_types from CSV string format
        place_types_str = lead.get('place_types', '')
        if place_types_str:
            place_types = [t.strip().strip('"') for t in place_types_str.strip('"').split(',')]
        else:
            place_types = []

        # Create place_data for filter
        place_data = {
            'name': business_name,
            'website': lead.get('website', ''),
            'user_ratings_total': int(lead.get('review_count', 0)) if lead.get('review_count') else 0,
            'types': place_types,
            'rating': float(lead.get('rating', 0)) if lead.get('rating') else 0.0,
        }

        # Test with FIXED balanced filters
        passes, reason, metadata = pre_qualify_lead_balanced(place_data, industry=industry)

        if passes:
            clean_leads.append(lead)
        else:
            rejected_leads.append({
                'business_name': business_name,
                'industry': industry,
                'reason': reason,
                'review_count': lead.get('review_count'),
                'website': lead.get('website')
            })
            print(f"  ❌ Rejected: {business_name:45} - {reason}")

    print(f"  ✅ Clean leads: {len(clean_leads)}")
    print(f"  ❌ Rejected: {len(rejected_leads)}")
    print()

    # Step 3: Write cleaned file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = input_file.parent / f"HOT_LEADS_CLEAN_{len(clean_leads)}_LEADS_{timestamp}.csv"

    if clean_leads:
        fieldnames = clean_leads[0].keys()

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(clean_leads)

        print("="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Original leads: {len(all_leads)}")
        print(f"Duplicates removed: {duplicates_found}")
        print(f"Failed filters: {len(rejected_leads)}")
        print(f"Clean leads: {len(clean_leads)}")
        print()
        print(f"Effectiveness: {len(clean_leads)/len(all_leads)*100:.1f}%")
        print()
        print(f"✅ Output file: {output_file.name}")
        print("="*80 + "\n")

        # Show rejection breakdown
        print("REJECTION BREAKDOWN:")
        rejection_counts = defaultdict(int)
        for rej in rejected_leads:
            reason = rej['reason'].split(':')[0]  # Get category
            rejection_counts[reason] += 1

        for reason, count in sorted(rejection_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count}")
        print()

    else:
        print("❌ No clean leads remaining!")


if __name__ == '__main__':
    deduplicate_and_clean()
