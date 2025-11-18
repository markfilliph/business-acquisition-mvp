#!/usr/bin/env python3
"""
Add postal codes to 100 leads - FAST version with progress display.
"""
import csv
import requests
import time
from pathlib import Path

def geocode_address(address: str, city: str) -> str:
    """Geocode address using Nominatim API."""
    if not address or address == "Unknown":
        return "Unknown"

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': f"{address}, {city}, Ontario, Canada",
        'format': 'json',
        'addressdetails': 1,
        'limit': 1,
        'countrycodes': 'ca'
    }
    headers = {'User-Agent': 'HamiltonBusinessLeads/1.0'}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                postcode = data[0].get('address', {}).get('postcode')
                if postcode:
                    # Format Canadian postal code (A1A 1A1)
                    postcode = postcode.upper().replace(' ', '')
                    if len(postcode) == 6:
                        return f"{postcode[:3]} {postcode[3:]}"
                    return postcode
    except:
        pass

    return "Unknown"

# Read leads
input_path = Path('data/outputs/100_LEADS_STANDARDIZED_FORMAT.csv')
output_path = Path('data/outputs/100_LEADS_WITH_POSTAL_CODES.csv')

print("\n📮 ADDING POSTAL CODES TO 100 LEADS")
print("=" * 70)
print(f"Using FREE OpenStreetMap Nominatim (1 request/second)")
print()

with open(input_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    leads = list(reader)

print(f"✅ Loaded {len(leads)} leads\n")

added = 0
for idx, lead in enumerate(leads, 1):
    if lead['Postal Code'] != 'Unknown':
        continue

    postal_code = geocode_address(lead['Address'], lead['City'])
    lead['Postal Code'] = postal_code

    if postal_code != 'Unknown':
        added += 1
        status = "✅"
    else:
        status = "⚠️ "

    print(f"{status} [{idx:3d}/100] {lead['Business Name'][:40]:40s} → {postal_code}")

    # Respect Nominatim's usage policy: 1 request/second
    time.sleep(1)

# Write output
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=leads[0].keys())
    writer.writeheader()
    writer.writerows(leads)

print()
print("=" * 70)
print(f"✅ COMPLETED!")
print(f"📮 Postal codes added: {added}/100")
print(f"💾 Saved to: {output_path}")
print()
