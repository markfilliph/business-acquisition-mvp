#!/usr/bin/env python3
"""
Reorganize the clean leads file with requested field order.

Field Order:
1. business_name
2. phone
3. website
4. address (full address)
5. postal_code
6. revenue
7. sde
8. employee_count
9. ... all other fields
"""
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

input_file = Path("data/outputs/HOT_LEADS_CLEAN_64_LEADS_20251119_085159.csv")

if not input_file.exists():
    print(f"❌ File not found: {input_file}")
    exit(1)

print("\n" + "="*80)
print("REORGANIZING CLEAN LEADS FILE")
print("="*80)
print(f"Input: {input_file.name}\n")

# Read all leads
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    all_leads = list(reader)

print(f"Total leads in input: {len(all_leads)}")

# Reorganize each lead
reorganized_leads = []

for lead in all_leads:
    # Calculate full address
    address_parts = []
    if lead.get('street_address'):
        address_parts.append(lead['street_address'])
    if lead.get('city'):
        address_parts.append(lead['city'])
    if lead.get('province'):
        address_parts.append(lead['province'])

    full_address = ', '.join(address_parts)

    # Get employee count (calculate from range)
    employee_range = lead.get('employee_range', '')
    if employee_range and '-' in employee_range:
        low, high = employee_range.split('-')
        try:
            employee_count = (int(low) + int(high)) // 2
        except:
            employee_count = 10
    else:
        employee_count = 10

    # Create reorganized lead
    reorganized = {
        # Priority fields (as requested)
        'business_name': lead.get('business_name', ''),
        'phone': lead.get('phone', ''),
        'website': lead.get('website', ''),
        'address': full_address,
        'postal_code': lead.get('postal_code', ''),
        'revenue': lead.get('estimated_revenue', ''),
        'sde': lead.get('sde_estimate', ''),
        'employee_count': employee_count,

        # All other fields (in alphabetical order)
        'city': lead.get('city', ''),
        'confidence_score': lead.get('confidence_score', ''),
        'data_source': lead.get('data_source', ''),
        'employee_range': employee_range,
        'industry': lead.get('industry', ''),
        'place_types': lead.get('place_types', ''),
        'priority': lead.get('priority', ''),
        'province': lead.get('province', ''),
        'query_type': lead.get('query_type', ''),
        'query_used': lead.get('query_used', ''),
        'rating': lead.get('rating', ''),
        'revenue_range': lead.get('revenue_range', ''),
        'review_count': lead.get('review_count', ''),
        'street_address': lead.get('street_address', ''),
        'validation_layers_passed': lead.get('validation_layers_passed', ''),
    }

    reorganized_leads.append(reorganized)

# Count by industry
by_industry = defaultdict(int)
for lead in reorganized_leads:
    by_industry[lead['industry']] += 1

print("\nLeads by industry:")
for industry, count in sorted(by_industry.items()):
    print(f"  {industry:25}: {count:2} leads")
print(f"  {'TOTAL':25}: {len(reorganized_leads):2} leads")

# Write reorganized file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = Path(f"data/outputs/HOT_LEADS_REORGANIZED_{len(reorganized_leads)}_LEADS_{timestamp}.csv")

# Ensure field order
fieldnames = [
    'business_name', 'phone', 'website', 'address', 'postal_code',
    'revenue', 'sde', 'employee_count', 'city', 'confidence_score',
    'data_source', 'employee_range', 'industry', 'place_types',
    'priority', 'province', 'query_type', 'query_used', 'rating',
    'revenue_range', 'review_count', 'street_address', 'validation_layers_passed'
]

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(reorganized_leads)

print(f"\n✅ Output file: {output_file.name}")
print(f"   Total leads: {len(reorganized_leads)}")
print(f"   Industries: {len(by_industry)}")
print()
print("Field order:")
print("  1. business_name")
print("  2. phone")
print("  3. website")
print("  4. address (full)")
print("  5. postal_code")
print("  6. revenue")
print("  7. sde")
print("  8. employee_count")
print("  9. ... all other fields")
print()
print("="*80 + "\n")
