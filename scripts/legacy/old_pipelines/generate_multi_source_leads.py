#!/usr/bin/env python3
"""
Generate 20+ leads from MULTIPLE real business data sources.
Uses: YellowPages, Google Places, Yelp, Better Business Bureau, Industry directories.
NO OSM - only professional business directories.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
import re
import aiohttp
from bs4 import BeautifulSoup

from src.integrations.yellowpages_client import YellowPagesClient
from src.services.validation_service import BusinessValidationService
from src.core.config import config
from src.core.models import BusinessLead, ContactInfo, LocationInfo, RevenueEstimate


def merge_business_data(sources_data: list) -> dict:
    """
    Merge data from multiple sources for the same business.
    Cross-references to fill in missing data.
    """
    merged = {
        'business_name': None,
        'phone': None,
        'website': None,
        'address': None,
        'city': None,
        'employee_count': None,
        'years_in_business': None,
        'sources': []
    }

    for data in sources_data:
        merged['sources'].append(data.get('source', 'Unknown'))

        # Take first available value for each field
        for field in ['business_name', 'phone', 'website', 'address', 'city', 'employee_count', 'years_in_business']:
            if data.get(field) and not merged[field]:
                merged[field] = data.get(field)

    merged['sources'] = list(set(merged['sources']))
    return merged


class MultiSourceLeadGenerator:
    """Generate leads from multiple professional business directories."""

    def __init__(self):
        self.logger = None
        self.session = None
        self.validator = BusinessValidationService(config)

    async def scrape_hamilton_chamber(self, max_results: int = 50) -> list:
        """
        Scrape Hamilton Chamber of Commerce member directory.
        https://www.hamiltonchamber.ca/member-directory/
        """
        print("📂 Scraping Hamilton Chamber of Commerce...")
        businesses = []

        try:
            url = "https://business.hamiltonchamber.ca/list"
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find business listings
                    listings = soup.find_all('div', class_='card-body') or soup.find_all('div', class_='mn-listing')

                    for listing in listings[:max_results]:
                        try:
                            # Extract business name
                            name_elem = listing.find('h2') or listing.find('h3') or listing.find('a', class_='mn-title')
                            if name_elem:
                                business_name = name_elem.get_text(strip=True)

                                # Extract contact info
                                phone = None
                                phone_elem = listing.find('a', href=re.compile(r'tel:'))
                                if phone_elem:
                                    phone = phone_elem.get_text(strip=True)

                                website = None
                                web_elem = listing.find('a', href=re.compile(r'http'))
                                if web_elem:
                                    website = web_elem.get('href')

                                # Extract address
                                address = None
                                addr_elem = listing.find('address') or listing.find('div', class_='address')
                                if addr_elem:
                                    address = addr_elem.get_text(strip=True)

                                businesses.append({
                                    'business_name': business_name,
                                    'phone': phone,
                                    'website': website,
                                    'address': address or 'Hamilton, ON',
                                    'city': 'Hamilton',
                                    'source': 'Hamilton Chamber of Commerce'
                                })
                        except Exception as e:
                            continue

                    print(f"   ✅ Found {len(businesses)} businesses from Chamber")
                else:
                    print(f"   ⚠️  Chamber website returned status {response.status}")
        except Exception as e:
            print(f"   ❌ Chamber scrape error: {str(e)[:100]}")

        return businesses

    async def scrape_better_business_bureau(self, max_results: int = 50) -> list:
        """
        Scrape BBB listings for Hamilton area.
        https://www.bbb.org/ca/on/hamilton
        """
        print("📂 Scraping Better Business Bureau...")
        businesses = []

        try:
            # BBB search for Hamilton businesses
            url = "https://www.bbb.org/search?find_country=CAN&find_loc=Hamilton%2C+ON&find_text=&page=1"

            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find business listings
                    listings = soup.find_all('div', class_='result') or soup.find_all('div', class_='search-result')

                    for listing in listings[:max_results]:
                        try:
                            # Extract business name
                            name_elem = listing.find('h3') or listing.find('a', class_='business-name')
                            if name_elem:
                                business_name = name_elem.get_text(strip=True)

                                # Extract phone
                                phone = None
                                phone_elem = listing.find('span', class_='phone')
                                if phone_elem:
                                    phone = phone_elem.get_text(strip=True)

                                # Extract address
                                address = None
                                addr_elem = listing.find('span', class_='address')
                                if addr_elem:
                                    address = addr_elem.get_text(strip=True)

                                # Extract website (usually requires clicking through)
                                website = None

                                businesses.append({
                                    'business_name': business_name,
                                    'phone': phone,
                                    'website': website,
                                    'address': address or 'Hamilton, ON',
                                    'city': 'Hamilton',
                                    'source': 'Better Business Bureau'
                                })
                        except Exception as e:
                            continue

                    print(f"   ✅ Found {len(businesses)} businesses from BBB")
                else:
                    print(f"   ⚠️  BBB website returned status {response.status}")
        except Exception as e:
            print(f"   ❌ BBB scrape error: {str(e)[:100]}")

        return businesses

    async def scrape_canada411(self, industry: str = "manufacturing", max_results: int = 50) -> list:
        """
        Scrape Canada411 business directory.
        https://www.canada411.ca/
        """
        print(f"📂 Scraping Canada411 for {industry}...")
        businesses = []

        try:
            # Canada411 search
            search_term = quote(industry)
            location = quote("Hamilton, ON")
            url = f"https://www.canada411.ca/search/?stype=si&what={search_term}&where={location}"

            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find business listings
                    listings = soup.find_all('div', class_='c411Listing')

                    for listing in listings[:max_results]:
                        try:
                            # Extract business name
                            name_elem = listing.find('h3', class_='c411ListedName') or listing.find('a', class_='business-name')
                            if name_elem:
                                business_name = name_elem.get_text(strip=True)

                                # Extract phone
                                phone = None
                                phone_elem = listing.find('a', class_='c411Phone')
                                if phone_elem:
                                    phone = phone_elem.get_text(strip=True)

                                # Extract address
                                address = None
                                addr_elem = listing.find('span', class_='c411Address')
                                if addr_elem:
                                    address = addr_elem.get_text(strip=True)

                                # Extract website
                                website = None
                                web_elem = listing.find('a', class_='c411Website')
                                if web_elem:
                                    website = web_elem.get('href')

                                businesses.append({
                                    'business_name': business_name,
                                    'phone': phone,
                                    'website': website,
                                    'address': address or 'Hamilton, ON',
                                    'city': 'Hamilton',
                                    'source': 'Canada411'
                                })
                        except Exception as e:
                            continue

                    print(f"   ✅ Found {len(businesses)} businesses from Canada411")
                else:
                    print(f"   ⚠️  Canada411 returned status {response.status}")
        except Exception as e:
            print(f"   ❌ Canada411 scrape error: {str(e)[:100]}")

        return businesses

    async def search_yelp_api(self, industry: str = "manufacturing", max_results: int = 50) -> list:
        """
        Search Yelp for Hamilton businesses.
        Note: Would need Yelp API key for full access.
        """
        print(f"📂 Scraping Yelp for {industry}...")
        businesses = []

        try:
            # Yelp search (without API, scraping is limited)
            search_term = quote(industry)
            url = f"https://www.yelp.ca/search?find_desc={search_term}&find_loc=Hamilton%2C+ON"

            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Yelp has anti-scraping measures, so results may be limited
                    listings = soup.find_all('div', {'data-testid': 'serp-ia-card'})

                    for listing in listings[:max_results]:
                        try:
                            # Extract business name
                            name_elem = listing.find('h3') or listing.find('a', class_='business-name')
                            if name_elem:
                                business_name = name_elem.get_text(strip=True)

                                # Phone and other details require clicking through
                                businesses.append({
                                    'business_name': business_name,
                                    'phone': None,
                                    'website': None,
                                    'address': 'Hamilton, ON',
                                    'city': 'Hamilton',
                                    'source': 'Yelp'
                                })
                        except Exception as e:
                            continue

                    print(f"   ✅ Found {len(businesses)} businesses from Yelp")
                else:
                    print(f"   ⚠️  Yelp returned status {response.status}")
        except Exception as e:
            print(f"   ❌ Yelp scrape error: {str(e)[:100]}")

        return businesses

    async def generate_leads(self, target_count: int = 20):
        """Generate leads from multiple sources."""

        print("=" * 80)
        print(f"MULTI-SOURCE LEAD GENERATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print(f"Target: {target_count} qualified leads")
        print(f"Sources: YellowPages, Hamilton Chamber, BBB, Canada411, Yelp")
        print()

        # Create session
        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        async with aiohttp.ClientSession(timeout=timeout, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }) as session:
            self.session = session

            all_businesses = []

            # Source 1: YellowPages (BEST SOURCE - has phone, website, address)
            print("\n" + "=" * 80)
            print("SOURCE 1: YELLOWPAGES.CA")
            print("=" * 80)
            async with YellowPagesClient(session) as yp_client:
                for industry in ['manufacturing', 'professional_services', 'wholesale']:
                    yp_results = await yp_client.search_hamilton_businesses(
                        industry_category=industry,
                        max_results=30
                    )
                    for biz in yp_results:
                        biz['source'] = 'YellowPages'
                        all_businesses.append(biz)
                    print(f"   YellowPages {industry}: {len(yp_results)} businesses")
                    await asyncio.sleep(2)  # Rate limiting

            # Source 2: Hamilton Chamber of Commerce
            print("\n" + "=" * 80)
            print("SOURCE 2: HAMILTON CHAMBER OF COMMERCE")
            print("=" * 80)
            chamber_businesses = await self.scrape_hamilton_chamber(max_results=50)
            all_businesses.extend(chamber_businesses)

            # Source 3: Better Business Bureau
            print("\n" + "=" * 80)
            print("SOURCE 3: BETTER BUSINESS BUREAU")
            print("=" * 80)
            bbb_businesses = await self.scrape_better_business_bureau(max_results=50)
            all_businesses.extend(bbb_businesses)

            # Source 4: Canada411
            print("\n" + "=" * 80)
            print("SOURCE 4: CANADA411")
            print("=" * 80)
            for industry in ['manufacturing', 'professional services']:
                canada411_results = await self.scrape_canada411(industry=industry, max_results=20)
                all_businesses.extend(canada411_results)
                await asyncio.sleep(2)

            # Source 5: Yelp
            print("\n" + "=" * 80)
            print("SOURCE 5: YELP")
            print("=" * 80)
            yelp_results = await self.search_yelp_api(industry='business services', max_results=20)
            all_businesses.extend(yelp_results)

            print("\n" + "=" * 80)
            print(f"📊 TOTAL FETCHED: {len(all_businesses)} businesses from all sources")
            print("=" * 80)

            # Group by business name to merge data from multiple sources
            print("\n🔗 CROSS-REFERENCING DATA FROM MULTIPLE SOURCES...")
            business_groups = {}
            for biz in all_businesses:
                name_key = biz.get('business_name', '').lower().strip()
                name_key = re.sub(r'\s+(ltd|limited|inc|corp|co)\.?$', '', name_key)  # Normalize
                if name_key:
                    if name_key not in business_groups:
                        business_groups[name_key] = []
                    business_groups[name_key].append(biz)

            # Merge data from multiple sources for each business
            merged_businesses = []
            for name_key, sources in business_groups.items():
                if len(sources) > 1:
                    print(f"   📊 {sources[0].get('business_name')}: Found in {len(sources)} sources - merging data")
                merged = merge_business_data(sources)
                if merged['business_name']:
                    merged_businesses.append(merged)

            print(f"📊 BUSINESSES AFTER CROSS-REFERENCING: {len(merged_businesses)}")
            print(f"   (Merged data from {len(all_businesses)} total records)")
            print()

            unique_businesses = merged_businesses

            # Validate and qualify
            print("🔍 VALIDATING AND QUALIFYING LEADS...")
            print()

            qualified_leads = []

            for i, biz in enumerate(unique_businesses, 1):
                if len(qualified_leads) >= target_count:
                    break

                business_name = biz.get('business_name')
                if not business_name:
                    continue

                print(f"[{i}/{len(unique_businesses)}] {business_name}")

                # Create lead
                try:
                    lead = BusinessLead(
                        business_name=business_name,
                        contact=ContactInfo(
                            phone=biz.get('phone'),
                            email=biz.get('email'),
                            website=biz.get('website')
                        ),
                        location=LocationInfo(
                            address=biz.get('address', 'Hamilton, ON'),
                            city=biz.get('city', 'Hamilton'),
                            province='ON',
                            postal_code='L8P 1A1',  # Default Hamilton
                            country='Canada'
                        ),
                        industry=biz.get('industry', 'professional_services'),
                        years_in_business=biz.get('years_in_business'),
                        employee_count=biz.get('employee_count'),
                        revenue_estimate=RevenueEstimate()
                    )

                    # Validate
                    is_valid, issues = await self.validator.validate_business_lead(lead)

                    if is_valid:
                        sources_used = biz.get('sources', [biz.get('source', 'Unknown')])
                        qualified_leads.append({
                            'lead': lead,
                            'sources': sources_used,
                            'data_completeness': {
                                'has_phone': bool(lead.contact.phone),
                                'has_website': bool(lead.contact.website),
                                'has_employee_count': bool(lead.employee_count),
                                'has_years': bool(lead.years_in_business),
                            }
                        })
                        sources_str = ', '.join(sources_used) if isinstance(sources_used, list) else sources_used
                        print(f"   ✅ QUALIFIED ({len(qualified_leads)}/{target_count}) - Sources: {sources_str}")
                    else:
                        print(f"   ❌ Rejected: {issues[0] if issues else 'validation failed'}")

                except Exception as e:
                    print(f"   ⚠️  Error: {str(e)[:50]}")
                    continue

                print()

            # Export results
            return await self.export_results(qualified_leads)

    async def export_results(self, qualified_leads):
        """Export results to JSON and text files."""

        print("=" * 80)
        print(f"✅ GENERATION COMPLETE: {len(qualified_leads)} qualified leads")
        print("=" * 80)
        print()

        # Data completeness
        total_with_phone = sum(1 for e in qualified_leads if e['data_completeness']['has_phone'])
        total_with_website = sum(1 for e in qualified_leads if e['data_completeness']['has_website'])
        total_with_employees = sum(1 for e in qualified_leads if e['data_completeness']['has_employee_count'])
        total_with_years = sum(1 for e in qualified_leads if e['data_completeness']['has_years'])

        print("📊 DATA COMPLETENESS:")
        print(f"   Phone: {total_with_phone}/{len(qualified_leads)} ({total_with_phone/len(qualified_leads)*100:.1f}%)")
        print(f"   Website: {total_with_website}/{len(qualified_leads)} ({total_with_website/len(qualified_leads)*100:.1f}%)")
        print(f"   Employee Count: {total_with_employees}/{len(qualified_leads)} ({total_with_employees/len(qualified_leads)*100:.1f}%)")
        print(f"   Years: {total_with_years}/{len(qualified_leads)} ({total_with_years/len(qualified_leads)*100:.1f}%)")
        print()

        # Source breakdown
        source_usage = {}
        multi_source_count = 0
        for item in qualified_leads:
            sources_list = item.get('sources', [item.get('source', 'Unknown')])
            if isinstance(sources_list, str):
                sources_list = [sources_list]

            if len(sources_list) > 1:
                multi_source_count += 1

            for source in sources_list:
                source_usage[source] = source_usage.get(source, 0) + 1

        print("📊 SOURCES:")
        for source, count in sorted(source_usage.items(), key=lambda x: x[1], reverse=True):
            print(f"   {source}: {count} leads")
        print(f"   Multi-source (cross-referenced): {multi_source_count} leads")
        print()

        # Export JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = f"output/multi_source_leads_{timestamp}.json"

        export_data = {
            'generated_at': timestamp,
            'total_leads': len(qualified_leads),
            'source_usage': source_usage,
            'multi_source_count': multi_source_count,
            'leads': []
        }

        for item in qualified_leads:
            lead = item['lead']
            sources_list = item.get('sources', [])
            if isinstance(sources_list, str):
                sources_list = [sources_list]

            export_data['leads'].append({
                'business_name': lead.business_name,
                'address': lead.location.address,
                'city': lead.location.city,
                'phone': lead.contact.phone,
                'website': lead.contact.website,
                'industry': lead.industry,
                'years_in_business': lead.years_in_business,
                'employee_count': lead.employee_count,
                'sources': sources_list,
                'cross_referenced': len(sources_list) > 1,
                'data_completeness': item['data_completeness']
            })

        with open(json_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"💾 JSON export: {json_file}")

        # Text summary
        summary_file = f"output/multi_source_summary_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write("MULTI-SOURCE LEAD GENERATION - SUMMARY\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Leads: {len(qualified_leads)}\n")
            f.write("\n")

            f.write("SOURCES\n")
            f.write("-" * 80 + "\n")
            for source, count in sorted(source_usage.items(), key=lambda x: x[1], reverse=True):
                f.write(f"{source}: {count} leads\n")
            f.write(f"Multi-source (cross-referenced): {multi_source_count} leads\n")
            f.write("\n")

            f.write("DATA COMPLETENESS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Phone: {total_with_phone}/{len(qualified_leads)} ({total_with_phone/len(qualified_leads)*100:.1f}%)\n")
            f.write(f"Website: {total_with_website}/{len(qualified_leads)} ({total_with_website/len(qualified_leads)*100:.1f}%)\n")
            f.write(f"Employee Count: {total_with_employees}/{len(qualified_leads)} ({total_with_employees/len(qualified_leads)*100:.1f}%)\n")
            f.write(f"Years: {total_with_years}/{len(qualified_leads)} ({total_with_years/len(qualified_leads)*100:.1f}%)\n")
            f.write("\n")

            f.write("DETAILED LEADS\n")
            f.write("-" * 80 + "\n\n")

            for i, item in enumerate(qualified_leads, 1):
                lead = item['lead']
                sources_list = item.get('sources', [])
                if isinstance(sources_list, str):
                    sources_list = [sources_list]

                f.write(f"{i}. {lead.business_name}\n")
                f.write(f"   Sources: {', '.join(sources_list)}")
                if len(sources_list) > 1:
                    f.write(" ✅ CROSS-REFERENCED\n")
                else:
                    f.write("\n")
                f.write(f"   Address: {lead.location.address}\n")
                if lead.contact.phone:
                    f.write(f"   Phone: {lead.contact.phone} ✅\n")
                if lead.contact.website:
                    f.write(f"   Website: {lead.contact.website} ✅\n")
                if lead.years_in_business:
                    f.write(f"   Years: {lead.years_in_business} ✅\n")
                if lead.employee_count:
                    f.write(f"   Employees: {lead.employee_count} ✅\n")
                f.write("\n")

        print(f"📄 Summary: {summary_file}")

        return qualified_leads


async def main():
    generator = MultiSourceLeadGenerator()
    await generator.generate_leads(target_count=20)


if __name__ == '__main__':
    asyncio.run(main())
