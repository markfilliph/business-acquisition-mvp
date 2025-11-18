#!/usr/bin/env python3
"""
Add postal codes to the 100 leads using geocoding.

This script enriches the existing leads by looking up postal codes
based on the street address using a geocoding service.
"""
import sys
import csv
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import config


async def geocode_address(session: aiohttp.ClientSession, address: str, city: str, province: str) -> Optional[str]:
    """
    Geocode an address to get postal code using Google Geocoding API.

    Args:
        session: HTTP session
        address: Street address
        city: City name
        province: Province code

    Returns:
        Postal code or None if not found
    """
    if not address or address == "Unknown":
        return None

    # Format full address for geocoding
    full_address = f"{address}, {city}, {province}, Canada"

    try:
        # Google Geocoding API
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': full_address,
            'key': config.GOOGLE_PLACES_API_KEY,
            'components': f'country:CA|administrative_area:{province}'  # Restrict to Canada/Ontario
        }

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()

                if data.get('status') == 'OK' and data.get('results'):
                    result = data['results'][0]

                    # Extract postal code from address_components
                    for component in result.get('address_components', []):
                        if 'postal_code' in component.get('types', []):
                            postal_code = component.get('long_name')
                            return postal_code

    except Exception as e:
        print(f"   ⚠️  Geocoding error for {address}: {e}")

    return None


async def enrich_leads_with_postal_codes():
    """Enrich the 100 leads with postal codes."""

    input_path = Path('data/outputs/100_LEADS_STANDARDIZED_FORMAT.csv')
    output_path = Path('data/outputs/100_LEADS_WITH_POSTAL_CODES.csv')

    print("\n📮 ADDING POSTAL CODES TO 100 LEADS")
    print("=" * 60)
    print(f"📥 Input:  {input_path}")
    print(f"📤 Output: {output_path}")
    print()

    if not input_path.exists():
        print(f"❌ ERROR: Input file not found: {input_path}")
        return False

    if not config.GOOGLE_PLACES_API_KEY:
        print("❌ ERROR: GOOGLE_PLACES_API_KEY not configured")
        print("   Add your API key to .env file")
        return False

    # Read existing leads
    leads = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)

    print(f"✅ Loaded {len(leads)} leads")
    print(f"🔍 Looking up postal codes using Google Geocoding API...")
    print()

    # Enrich with postal codes
    enriched_count = 0
    failed_count = 0
    already_had = 0

    async with aiohttp.ClientSession() as session:
        for idx, lead in enumerate(leads, 1):
            # Check if already has postal code
            if lead['Postal Code'] and lead['Postal Code'] != 'Unknown':
                already_had += 1
                continue

            address = lead['Address']
            city = lead['City']
            province = lead['Province']

            # Geocode to get postal code
            postal_code = await geocode_address(session, address, city, province)

            if postal_code:
                lead['Postal Code'] = postal_code
                enriched_count += 1
                print(f"✅ {idx:3d}/{len(leads)} {lead['Business Name'][:40]:40s} → {postal_code}")
            else:
                failed_count += 1
                print(f"⚠️  {idx:3d}/{len(leads)} {lead['Business Name'][:40]:40s} → Not found")

            # Rate limiting (Google has generous limits, but be respectful)
            if idx % 10 == 0:
                await asyncio.sleep(0.5)

    # Write enriched leads
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)

    print()
    print("=" * 60)
    print("✅ ENRICHMENT COMPLETED")
    print(f"📊 Already had postal codes: {already_had}")
    print(f"📮 Postal codes added:      {enriched_count}")
    print(f"⚠️  Not found:              {failed_count}")
    print(f"💾 Output saved to:         {output_path}")
    print()

    if enriched_count > 0:
        print(f"🎉 SUCCESS! Added {enriched_count} postal codes to your leads.")
    else:
        print("⚠️  No postal codes were added. Check addresses and API key.")

    return True


if __name__ == "__main__":
    if not asyncio.run(enrich_leads_with_postal_codes()):
        sys.exit(1)
