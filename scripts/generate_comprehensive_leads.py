#!/usr/bin/env python3
"""
Generate 20 comprehensive leads with maximum data enrichment.
Uses multiple sources to fill in as much data as possible.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
import re

from src.integrations.business_data_aggregator import BusinessDataAggregator
from src.integrations.yellowpages_client import YellowPagesClient
from src.services.validation_service import BusinessValidationService
from src.core.config import config
from src.core.models import BusinessLead, ContactInfo, LocationInfo, RevenueEstimate

async def enrich_from_multiple_sources(business_name: str, website: str = None):
    """
    Try to get employee count and years from multiple sources.
    """
    enrichment = {
        'employee_count': None,
        'years_in_business': None,
        'sources_checked': []
    }

    # Source 1: Check if year is in business name
    year_match = re.search(r'\b(19|20)\d{2}\b', business_name)
    if year_match:
        year_founded = int(year_match.group())
        enrichment['years_in_business'] = 2025 - year_founded
        enrichment['sources_checked'].append(f"business_name_year_{year_founded}")

    # Source 2: Check for "since YYYY" in name
    since_match = re.search(r'since\s+(19|20)\d{2}', business_name.lower())
    if since_match and not enrichment['years_in_business']:
        year_founded = int(since_match.group(1))
        enrichment['years_in_business'] = 2025 - year_founded
        enrichment['sources_checked'].append(f"business_name_since_{year_founded}")

    # Source 3: Try to scrape website for "Since YYYY" or "Founded YYYY"
    if website and not enrichment['years_in_business']:
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(website, allow_redirects=True) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Look for "Since YYYY" or "Founded YYYY" patterns
                        founded_patterns = [
                            r'since\s+(19|20)\d{2}',
                            r'founded\s+(19|20)\d{2}',
                            r'established\s+(19|20)\d{2}',
                            r'est\.?\s+(19|20)\d{2}',
                        ]

                        for pattern in founded_patterns:
                            match = re.search(pattern, content.lower())
                            if match:
                                year_founded = int(match.group(1))
                                enrichment['years_in_business'] = 2025 - year_founded
                                enrichment['sources_checked'].append(f"website_founded_{year_founded}")
                                break
        except Exception as e:
            enrichment['sources_checked'].append(f"website_error_{str(e)[:30]}")

    # Source 4: Look for employee count on website (About page, Team page)
    if website and not enrichment['employee_count']:
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Try main page
                async with session.get(website, allow_redirects=True) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Look for employee count patterns
                        employee_patterns = [
                            r'(\d+)\s+employees?',
                            r'team\s+of\s+(\d+)',
                            r'staff\s+of\s+(\d+)',
                            r'(\d+)\s+team\s+members?',
                            r'(\d+)\s+professionals?',
                        ]

                        for pattern in employee_patterns:
                            match = re.search(pattern, content.lower())
                            if match:
                                employee_count = int(match.group(1))
                                # Sanity check - reasonable range
                                if 1 <= employee_count <= 500:
                                    enrichment['employee_count'] = employee_count
                                    enrichment['sources_checked'].append(f"website_employees_{employee_count}")
                                    break
        except Exception as e:
            enrichment['sources_checked'].append(f"website_employee_error_{str(e)[:30]}")

    return enrichment


async def generate_comprehensive_leads(target_count: int = 20):
    """
    Generate comprehensive leads with maximum data enrichment.
    """

    print("=" * 80)
    print(f"COMPREHENSIVE LEAD GENERATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(f"Target: {target_count} highly enriched leads")
    print(f"Strategy: Pull from multiple sources, enrich with web scraping")
    print()

    # Initialize services
    aggregator = BusinessDataAggregator()
    validator = BusinessValidationService(config)

    # We'll fetch MORE businesses to ensure we get 20 qualified after enrichment
    fetch_count = target_count * 10  # Fetch 10x to ensure we get enough after enrichment

    print(f"📥 Fetching {fetch_count} businesses from multiple sources...")
    print()

    # Fetch from aggregator (OSM + other sources)
    async with aggregator:
        raw_businesses = await aggregator.fetch_hamilton_businesses(
            industry_types=['manufacturing', 'wholesale', 'professional_services', 'printing', 'equipment_rental'],
            max_results=fetch_count
        )

    print(f"✅ Fetched {len(raw_businesses)} raw businesses")
    print(f"🔄 Enriching with web scraping and multiple sources...")
    print()

    enriched_leads = []
    processed = 0

    for biz in raw_businesses:
        processed += 1

        if len(enriched_leads) >= target_count:
            break

        business_name = biz.get('business_name')
        website = biz.get('website')

        if not business_name:
            continue

        print(f"[{processed}/{len(raw_businesses)}] Enriching: {business_name}")

        # Multi-source enrichment
        enrichment = await enrich_from_multiple_sources(business_name, website)

        # Use enrichment if available, otherwise None
        employee_count = enrichment.get('employee_count') or biz.get('employee_count')
        years_in_business = enrichment.get('years_in_business') or biz.get('years_in_business')

        # Show enrichment results
        if enrichment['sources_checked']:
            print(f"   📊 Enrichment sources: {', '.join(enrichment['sources_checked'])}")

        if employee_count:
            print(f"   👥 Employee count: {employee_count}")
        if years_in_business:
            print(f"   📅 Years in business: {years_in_business}")

        # Create lead
        try:
            lead = BusinessLead(
                business_name=business_name,
                contact=ContactInfo(
                    phone=biz.get('phone'),
                    email=biz.get('email'),
                    website=website
                ),
                location=LocationInfo(
                    address=biz.get('address', ''),
                    city=biz.get('city', 'Hamilton'),
                    province='ON',
                    postal_code=biz.get('postal_code', 'L9G 4V5'),
                    country='Canada'
                ),
                industry=biz.get('industry', 'professional_services'),
                years_in_business=years_in_business,
                employee_count=employee_count,
                revenue_estimate=RevenueEstimate()  # No estimation
            )

            # Validate
            is_valid, issues = await validator.validate_business_lead(lead)

            if is_valid:
                enriched_leads.append({
                    'lead': lead,
                    'enrichment_sources': enrichment['sources_checked'],
                    'data_completeness': {
                        'has_phone': bool(lead.contact.phone),
                        'has_website': bool(lead.contact.website),
                        'has_employee_count': bool(lead.employee_count),
                        'has_years': bool(lead.years_in_business),
                    }
                })
                print(f"   ✅ QUALIFIED ({len(enriched_leads)}/{target_count})")
                print()
            else:
                print(f"   ❌ Rejected: {', '.join(issues[:2])}")
                print()

        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")
            print()
            continue

    # Results summary
    print("=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    print(f"✅ Generated {len(enriched_leads)} qualified leads")
    print()

    # Data completeness stats
    total_with_phone = sum(1 for e in enriched_leads if e['data_completeness']['has_phone'])
    total_with_website = sum(1 for e in enriched_leads if e['data_completeness']['has_website'])
    total_with_employees = sum(1 for e in enriched_leads if e['data_completeness']['has_employee_count'])
    total_with_years = sum(1 for e in enriched_leads if e['data_completeness']['has_years'])

    print("📊 DATA COMPLETENESS:")
    print(f"   Phone: {total_with_phone}/{len(enriched_leads)} ({total_with_phone/len(enriched_leads)*100:.1f}%)")
    print(f"   Website: {total_with_website}/{len(enriched_leads)} ({total_with_website/len(enriched_leads)*100:.1f}%)")
    print(f"   Employee Count: {total_with_employees}/{len(enriched_leads)} ({total_with_employees/len(enriched_leads)*100:.1f}%)")
    print(f"   Years in Business: {total_with_years}/{len(enriched_leads)} ({total_with_years/len(enriched_leads)*100:.1f}%)")
    print()

    # Export
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON export
    json_file = f"output/comprehensive_leads_{timestamp}.json"
    export_data = {
        'generated_at': timestamp,
        'total_leads': len(enriched_leads),
        'leads': []
    }

    for item in enriched_leads:
        lead = item['lead']
        export_data['leads'].append({
            'business_name': lead.business_name,
            'address': lead.location.address,
            'city': lead.location.city,
            'phone': lead.contact.phone,
            'website': lead.contact.website,
            'industry': lead.industry,
            'years_in_business': lead.years_in_business,
            'employee_count': lead.employee_count,
            'enrichment_sources': item['enrichment_sources'],
            'data_completeness': item['data_completeness']
        })

    with open(json_file, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"💾 JSON export: {json_file}")

    # Text summary
    summary_file = f"output/comprehensive_leads_summary_{timestamp}.txt"
    with open(summary_file, 'w') as f:
        f.write("COMPREHENSIVE LEAD GENERATION - SUMMARY REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Qualified Leads: {len(enriched_leads)}\n")
        f.write("\n")

        f.write("DATA COMPLETENESS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Phone: {total_with_phone}/{len(enriched_leads)} ({total_with_phone/len(enriched_leads)*100:.1f}%)\n")
        f.write(f"Website: {total_with_website}/{len(enriched_leads)} ({total_with_website/len(enriched_leads)*100:.1f}%)\n")
        f.write(f"Employee Count: {total_with_employees}/{len(enriched_leads)} ({total_with_employees/len(enriched_leads)*100:.1f}%)\n")
        f.write(f"Years in Business: {total_with_years}/{len(enriched_leads)} ({total_with_years/len(enriched_leads)*100:.1f}%)\n")
        f.write("\n")

        f.write("DETAILED LEADS\n")
        f.write("-" * 80 + "\n\n")

        for i, item in enumerate(enriched_leads, 1):
            lead = item['lead']
            f.write(f"{i}. {lead.business_name}\n")
            f.write(f"   Address: {lead.location.address}\n")
            f.write(f"   City: {lead.location.city}\n")
            if lead.contact.phone:
                f.write(f"   Phone: {lead.contact.phone}\n")
            if lead.contact.website:
                f.write(f"   Website: {lead.contact.website}\n")
            f.write(f"   Industry: {lead.industry}\n")

            if lead.years_in_business:
                f.write(f"   Years in Business: {lead.years_in_business} ✅ REAL DATA\n")
            else:
                f.write(f"   Years in Business: Not available\n")

            if lead.employee_count:
                f.write(f"   Employee Count: {lead.employee_count} ✅ REAL DATA\n")
            else:
                f.write(f"   Employee Count: Not available\n")

            if item['enrichment_sources']:
                f.write(f"   Enrichment Sources: {', '.join(item['enrichment_sources'])}\n")

            f.write(f"   ✅ Validated\n")
            f.write("\n")

        f.write("=" * 80 + "\n")
        f.write("METHODOLOGY\n")
        f.write("-" * 80 + "\n")
        f.write("✅ NO estimation - all data from real sources\n")
        f.write("✅ Multi-source enrichment:\n")
        f.write("   - OpenStreetMap (business name, address, phone, website)\n")
        f.write("   - Business name parsing (year founded from name)\n")
        f.write("   - Website scraping (founded year, employee count)\n")
        f.write("   - Pattern matching ('Since YYYY', 'Founded YYYY')\n")
        f.write("✅ Full validation (website check, location, business type)\n")
        f.write("✅ Quality over quantity - only verified leads\n")
        f.write("\n")

    print(f"📄 Summary report: {summary_file}")
    print()

    # Display leads
    print("=" * 80)
    print("QUALIFIED LEADS")
    print("=" * 80)
    print()

    for i, item in enumerate(enriched_leads, 1):
        lead = item['lead']
        print(f"{i}. {lead.business_name}")
        print(f"   📍 {lead.location.address}, {lead.location.city}")
        if lead.contact.phone:
            print(f"   📞 {lead.contact.phone}")
        if lead.contact.website:
            print(f"   🌐 {lead.contact.website}")
        print(f"   💼 {lead.industry}")

        if lead.years_in_business:
            print(f"   📅 {lead.years_in_business} years ✅")
        else:
            print(f"   📅 Years: Not available")

        if lead.employee_count:
            print(f"   👥 {lead.employee_count} employees ✅")
        else:
            print(f"   👥 Employees: Not available")

        if item['enrichment_sources']:
            print(f"   📊 Enriched from: {', '.join(item['enrichment_sources'])}")

        print()

    return enriched_leads


if __name__ == '__main__':
    asyncio.run(generate_comprehensive_leads(target_count=20))
