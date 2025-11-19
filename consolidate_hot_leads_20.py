#!/usr/bin/env python3
"""
Consolidate all HOT_LEADS_20_* files into a single file with industry field.
Uses the most recent file for each industry.
"""
import csv
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add to path
sys.path.insert(0, str(Path(__file__).parent))
from src.core.standard_fields import get_standard_fieldnames, format_lead_for_output

# Find all HOT_LEADS_20_* files
data_dir = Path("data/outputs")
hot_leads_files = list(data_dir.glob("HOT_LEADS_20_*_OPTIMIZED_*.csv"))

print(f"\n{'='*80}")
print("CONSOLIDATING HOT LEADS")
print(f"{'='*80}\n")

# Group by industry and get the most recent file for each
industry_files = defaultdict(list)
for file in hot_leads_files:
    # Extract industry from filename: HOT_LEADS_20_{industry}_OPTIMIZED_{timestamp}.csv
    parts = file.stem.split('_')

    # Find industry (between "20" and "OPTIMIZED")
    try:
        idx_20 = parts.index('20')
        idx_opt = parts.index('OPTIMIZED')
        industry = '_'.join(parts[idx_20+1:idx_opt])

        # Extract timestamp
        timestamp_str = '_'.join(parts[idx_opt+1:])

        industry_files[industry].append((timestamp_str, file))
    except (ValueError, IndexError):
        print(f"⚠️  Skipping malformed filename: {file.name}")
        continue

# Get most recent file for each industry
selected_files = {}
for industry, files in industry_files.items():
    # Sort by timestamp (most recent first)
    files.sort(reverse=True)
    selected_files[industry] = files[0][1]
    print(f"✅ {industry:25} -> {files[0][1].name}")

print()

# Read and consolidate
all_leads = []
stats = defaultdict(int)

for industry, file_path in selected_files.items():
    print(f"📖 Reading {industry}...")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            if not rows:
                print(f"   ⚠️  Empty file, skipping")
                continue

            # Add industry field to each row
            for row in rows:
                row['industry'] = industry
                all_leads.append(row)

            stats[industry] = len(rows)
            print(f"   ✅ Added {len(rows)} leads")

    except Exception as e:
        print(f"   ❌ Error reading file: {e}")

print()
print(f"{'='*80}")
print(f"SUMMARY")
print(f"{'='*80}")
for industry, count in sorted(stats.items()):
    print(f"  {industry:25}: {count:3} leads")
print(f"  {'TOTAL':25}: {len(all_leads):3} leads")
print(f"{'='*80}\n")

# Write consolidated file
if all_leads:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = data_dir / f"HOT_LEADS_CONSOLIDATED_20_LEADS_{timestamp}.csv"

    # Get all fieldnames (union of all fields)
    fieldnames = set()
    for lead in all_leads:
        fieldnames.update(lead.keys())

    # Ensure 'industry' is in the fieldnames and move it to second position (after business_name)
    fieldnames = list(fieldnames)
    if 'industry' in fieldnames:
        fieldnames.remove('industry')
    if 'business_name' in fieldnames:
        fieldnames.remove('business_name')
        fieldnames = ['business_name', 'industry'] + sorted(fieldnames)
    else:
        fieldnames = ['industry'] + sorted(fieldnames)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_leads)

    print(f"✅ Consolidated file created: {output_file.name}")
    print(f"   Total leads: {len(all_leads)}")
    print(f"   Industries: {len(stats)}")
    print()
else:
    print("❌ No leads found to consolidate")

print(f"{'='*80}\n")
