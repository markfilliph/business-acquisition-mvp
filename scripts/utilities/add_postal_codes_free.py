#!/usr/bin/env python3
"""
Add postal codes to the 100 leads using FREE OpenStreetMap Nominatim geocoding.

No API key required!
"""
import sys
import csv
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional
import time


async def geocode_address_nominatim(session: aiohttp.ClientSession, address: str, city: str) -> Optional[str]:
    """
    Geocode an address using OpenStreetMap Nominatim (FREE, no API key needed).

    Args:
        session: HTTP session
        address: Street address
        city: City name

    Returns:
        Postal code or None if not found
    """
    if not address or address == "Unknown":
        return None

    # Format query for Nominatim
    query = f"{address}, {city}, Ontario, Canada"

    try:
        # Nominatim API (free, no key required)
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': query,
            'format': 'json',
            'addressdetails': 1,
            'limit': 1,
            'countrycodes': 'ca'
        }

        # Required User-Agent header for Nominatim
        headers = {
            'User-Agent': 'HamiltonBusinessLeadsEnricher/1.0'
        }

        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()

                if data and len(data) > 0:
                    result = data[0]
                    address_details = result.get('address', {})

                    # Nominatim returns postal code in address field
                    postal_code = address_details.get('postcode')

                    if postal_code:
                        # Format Canadian postal code properly (A1A 1A1)
                        postal_code = postal_code.upper().replace(' ', '')
                        if len(postal_code) == 6:
                            postal_code = f"{postal_code[:3]} {postal_code[3:]}"
                        return postal_code

    except Exception as e:
        pass  # Silently fail for individual lookups

    return None


async def enrich_leads_with_postal_codes():
    """Enrich the 100 leads with postal codes using free geocoding."""

    input_path = Path('data/outputs/100_LEADS_STANDARDIZED_FORMAT.csv')
    output_path = Path('data/outputs/100_LEADS_WITH_POSTAL_CODES.csv')

    print("\n📮 ADDING POSTAL CODES TO 100 LEADS")
    print("=" * 60)
    print(f"📥 Input:  {input_path}")
    print(f"📤 Output: {output_path}")
    print(f"🌍 Using: OpenStreetMap Nominatim (FREE - no API key)")
    print()

    if not input_path.exists():
        print(f"❌ ERROR: Input file not found: {input_path}")
        return False

    # Read existing leads
    leads = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)

    print(f"✅ Loaded {len(leads)} leads")
    print(f"🔍 Looking up postal codes...")
    print(f"⏱️  Please wait ~2 minutes (rate limited to respect OSM servers)")
    print()

    # Enrich with postal codes
    enriched_count = 0
    failed_count = 0

    async with aiohttp.ClientSession() as session:
        for idx, lead in enumerate(leads, 1):
            # Check if already has postal code
            if lead['Postal Code'] and lead['Postal Code'] != 'Unknown':
                continue

            address = lead['Address']
            city = lead['City']

            # Geocode to get postal code
            postal_code = await geocode_address_nominatim(session, address, city)

            if postal_code:
                lead['Postal Code'] = postal_code
                enriched_count += 1
                print(f"✅ {idx:3d}/{len(leads)} {lead['Business Name'][:35]:35s} → {postal_code}")
            else:
                failed_count += 1
                # Keep as Unknown for failed lookups
                lead['Postal Code'] = 'Unknown'
                print(f"⚠️  {idx:3d}/{len(leads)} {lead['Business Name'][:35]:35s} → Not found")

            # IMPORTANT: Nominatim requires 1 second delay between requests
            # This is their usage policy - respect it!
            await asyncio.sleep(1.0)

    # Write enriched leads
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)

    print()
    print("=" * 60)
    print("✅ ENRICHMENT COMPLETED")
    print(f"📮 Postal codes added:      {enriched_count}/{len(leads)}")
    print(f"⚠️  Not found:              {failed_count}/{len(leads)}")
    print(f"💾 Output saved to:         {output_path}")
    print()

    # Show sample
    print("📋 Sample Results (first 5 with postal codes):")
    print("-" * 60)
    count = 0
    for lead in leads:
        if lead['Postal Code'] != 'Unknown':
            print(f"{lead['Business Name'][:40]:40s} {lead['Postal Code']}")
            count += 1
            if count >= 5:
                break

    print()
    if enriched_count > 0:
        print(f"🎉 SUCCESS! Added {enriched_count} postal codes to your leads.")
        print(f"📄 New file: {output_path}")
    else:
        print("⚠️  No postal codes were added. Addresses may be incomplete.")

    return True


if __name__ == "__main__":
    print("\n⚠️  NOTE: This uses OpenStreetMap's free Nominatim service")
    print("   Rate limit: 1 request/second (required by OSM)")
    print("   Total time: ~100 seconds (~2 minutes)")
    print()

    try:
        if not asyncio.run(enrich_leads_with_postal_codes()):
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Partial results may be saved.")
        sys.exit(1)
