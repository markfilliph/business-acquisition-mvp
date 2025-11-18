#!/usr/bin/env python3
"""
Test REAL data enrichment - scraping actual employee counts and company data
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.enrichment.website_scraper_enrichment import WebsiteScraperEnricher
from src.enrichment.linkedin_enrichment import LinkedInEnricher


async def test_real_enrichment():
    """Test scraping real data from websites and LinkedIn."""

    # Test cases - real businesses from our leads
    test_companies = [
        {
            'name': 'Murray Wholesale',
            'website': 'http://www.murraywholesale.shop/',
            'industry': 'wholesale'
        },
        {
            'name': 'LUCX WHOLESALE',
            'website': 'http://www.lucxwholesale.com/',
            'industry': 'wholesale'
        },
        {
            'name': 'Karma Candy Inc',
            'website': 'http://www.karmacandy.ca/',
            'industry': 'manufacturing'
        }
    ]

    website_scraper = WebsiteScraperEnricher()
    linkedin_scraper = LinkedInEnricher()

    print("="*80)
    print("🔍 TESTING REAL DATA ENRICHMENT")
    print("="*80)
    print("\nSources:")
    print("  1. Website Scraper - Extract employee count from company websites")
    print("  2. LinkedIn Scraper - Get real employee data from LinkedIn")
    print("="*80 + "\n")

    for company in test_companies:
        print(f"\n{'='*80}")
        print(f"📊 {company['name']}")
        print(f"{'='*80}")
        print(f"Website: {company['website']}")
        print(f"Industry: {company['industry']}\n")

        # Try website scraping
        print("🌐 Attempting website scraping...")
        website_data = await website_scraper.scrape_website(
            website=company['website']
        )

        if website_data and website_data.get('employee_count'):
            print(f"   ✅ Found employee count: {website_data['employee_count']}")
            print(f"   Source: Website scrape (Confidence: {website_data.get('confidence', 0)*100:.0f}%)")
        elif website_data and website_data.get('employee_range'):
            print(f"   ✅ Found employee range: {website_data['employee_range']}")
            print(f"   Source: Website scrape (Confidence: {website_data.get('confidence', 0)*100:.0f}%)")
        else:
            print(f"   ❌ No employee data found on website")

        if website_data and website_data.get('year_founded'):
            years_in_business = 2025 - website_data['year_founded']
            print(f"   ✅ Founded: {website_data['year_founded']} ({years_in_business} years in business)")

        # Try LinkedIn scraping
        print("\n🔗 Attempting LinkedIn scraping...")
        linkedin_url = await linkedin_scraper.find_linkedin_url(
            company_name=company['name'],
            website=company['website']
        )

        if linkedin_url:
            print(f"   ✅ Found LinkedIn: {linkedin_url}")
            linkedin_data = await linkedin_scraper.scrape_company_page(linkedin_url)

            if linkedin_data and linkedin_data.get('employee_count'):
                print(f"   ✅ LinkedIn employee count: {linkedin_data['employee_count']}")
            elif linkedin_data and linkedin_data.get('employee_range'):
                print(f"   ✅ LinkedIn employee range: {linkedin_data['employee_range']}")
        else:
            print(f"   ❌ LinkedIn page not found")

        print()
        await asyncio.sleep(2)  # Rate limiting

    print("\n" + "="*80)
    print("📋 SUMMARY")
    print("="*80)
    print("\nReal data sources provide:")
    print("  ✅ Actual employee counts (not estimates)")
    print("  ✅ Real company ages (from websites/domain registration)")
    print("  ✅ Verified company data (from LinkedIn)")
    print("\nLimitations:")
    print("  ⚠️  Not all companies have employee counts on their websites")
    print("  ⚠️  LinkedIn scraping can be blocked/rate-limited")
    print("  ⚠️  Revenue data is NOT publicly available for private companies")
    print("\nRecommendation:")
    print("  → Use website/LinkedIn scraping where available")
    print("  → Fall back to SmartEnricher estimates for missing data")
    print("  → Revenue can ONLY be estimated (no public source for small businesses)")
    print("="*80 + "\n")


if __name__ == '__main__':
    asyncio.run(test_real_enrichment())
