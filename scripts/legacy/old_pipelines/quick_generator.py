#!/usr/bin/env python3
"""
Quick Lead Generator - Fast, No LLM Enrichment
Generates qualified leads in under 1 minute using only validation.
"""
import sys
import asyncio
import re
import json
from datetime import datetime

from src.integrations.business_data_aggregator import BusinessDataAggregator
from src.services.validation_service import BusinessValidationService
from src.core.config import config
from src.core.models import BusinessLead, ContactInfo, LocationInfo, RevenueEstimate

async def search_business_website(business_name: str, city: str = "Hamilton") -> str:
    """Search for business website if missing from OSM data."""
    # Website search functionality removed - was using deleted web_search module
    # TODO: Implement alternative website discovery method if needed
    return ''

async def generate_leads(count=20, show=False):
    """Generate leads without LLM enrichment for speed"""

    print(f"🎯 Quick Lead Generation (No LLM - Fast Mode)")
    print(f"{'='*70}")
    print(f"Target: {count} qualified leads")
    print(f"Criteria: ${config.business_criteria.target_revenue_min:,}-${config.business_criteria.target_revenue_max:,}, {config.business_criteria.min_years_in_business}+ years, ≤30 employees")
    print(f"{'='*70}\n")

    # Retail chains and non-profits to exclude
    excluded_chains = {
        # Major retail chains
        'fortinos', 'food basics', 'freshco', 'circle k', 'bell', 'goemans',
        'nations fresh foods', 'pet valu', 'first choice', 'pickwick',
        'once upon a child', 'the brick', 'main cycle', 'freewheel cycle',
        'take the leap', 'fastenal',  # Fastenal is retail chain
        # Retail keywords
        'supermarket', 'convenience', 'art supplies', 'community bikes',
        # Non-profit indicators
        'community', 'institute', 'foundation', 'society', 'association',
        'non-profit', 'not-for-profit', 'charity', 'centre', 'center'
    }

    aggregator = BusinessDataAggregator()
    validator = BusinessValidationService(config)

    valid_leads = []
    stats = {
        'total': 0,
        'skilled_trade': 0,
        'too_large': 0,
        'missing_data': 0,
        'validation_failed': 0,
        'website_searched': 0,
        'website_found': 0,
        'retail_nonprofit': 0,
        'content_validation_failed': 0,
        'other': 0
    }

    async with aggregator:
        # Fetch aggressively - get many businesses to ensure we hit target
        # Start with 10x multiplier to get enough candidates
        fetch_count = count * 10
        print(f"🔍 Fetching {fetch_count} businesses from OpenStreetMap...")
        print(f"   (Will enrich with Yellow Pages, web scraping, and validation after)")

        businesses = await aggregator.fetch_hamilton_businesses(
            industry_types=config.business_criteria.target_industries,
            max_results=fetch_count
        )

        stats['total'] = len(businesses)
        print(f"📊 Discovered {len(businesses)} raw businesses\n")

        for biz in businesses:
            try:
                # Skip retail chains and non-profits
                business_name_lower = biz.get('business_name', '').lower()
                if any(chain in business_name_lower for chain in excluded_chains):
                    stats['retail_nonprofit'] += 1
                    if show:
                        print(f"❌ RETAIL/NON-PROFIT: {biz.get('business_name')}")
                    continue

                # Get industry and employee count (NO estimation)
                # Keep whatever data we have - don't reject if missing
                industry = biz.get('industry', 'professional_services')
                employee_count = biz.get('employee_count')  # May be None
                years_in_business = biz.get('years_in_business')  # May be None

                # Log missing data for tracking but don't reject
                if not employee_count:
                    stats['missing_data'] += 1
                    if show:
                        print(f"ℹ️  Missing employee count: {biz.get('business_name')}")

                if not years_in_business:
                    stats['missing_data'] += 1
                    if show:
                        print(f"ℹ️  Missing years: {biz.get('business_name')}")

                # NO REVENUE ESTIMATION - Revenue cannot be verified

                # Get website - search if missing from OSM data
                website = biz.get('website', '')
                if not website:
                    stats['website_searched'] += 1
                    if show:
                        print(f"🔍 Searching website for {biz.get('business_name')}...")
                    website = await search_business_website(
                        biz.get('business_name'),
                        biz.get('city', 'Hamilton')
                    )
                    if website:
                        stats['website_found'] += 1
                        if show:
                            print(f"   ✅ Found: {website}")

                # Create lead object (NO revenue estimation - use empty RevenueEstimate)
                lead = BusinessLead(
                    business_name=biz.get('business_name'),
                    contact=ContactInfo(
                        phone=biz.get('phone', ''),
                        email=biz.get('email', ''),
                        website=website
                    ),
                    location=LocationInfo(
                        address=biz.get('address', ''),
                        city=biz.get('city', 'Hamilton'),
                        province='ON',
                        postal_code='L9G 4V5',  # Default Ancaster postal code
                        country='Canada'
                    ),
                    industry=industry,
                    years_in_business=years_in_business,
                    employee_count=employee_count,
                    revenue_estimate=RevenueEstimate()  # Empty - no estimation, cannot be verified
                )

                # Validate with standard validation
                is_valid, issues = await validator.validate_business_lead(lead)

                if is_valid:
                    # Website content validation removed - module was deleted
                    if show:
                        print(f"✅ {lead.business_name}")

                    valid_leads.append(lead)
                    if show:
                        print(f"   📍 {lead.location.city}, ON | 👥 {lead.employee_count} emp | 📅 {lead.years_in_business} yrs")
                        if lead.contact.website:
                            print(f"   🌐 {lead.contact.website}")
                        print()
                else:
                    # Categorize rejection
                    issue_text = issues[0] if issues else ''
                    if 'skilled trade' in issue_text.lower():
                        stats['skilled_trade'] += 1
                        if show:
                            print(f"❌ SKILLED TRADE: {lead.business_name}")
                    elif 'employee count' in issue_text.lower():
                        if 'required' in issue_text.lower():
                            stats['missing_data'] += 1
                        elif '30' in issue_text:
                            stats['too_large'] += 1
                        if show:
                            print(f"❌ SIZE: {lead.business_name}")
                    else:
                        stats['validation_failed'] += 1

                if len(valid_leads) >= count:
                    break

            except Exception as e:
                stats['other'] += 1
                if show:
                    print(f"⚠️  Error: {biz.get('business_name')}: {str(e)[:60]}")
                # Continue processing other businesses - don't crash on single error
                continue

    # Print results
    print(f"\n{'='*70}")
    print(f"✅ QUALIFIED LEADS: {len(valid_leads)}/{stats['total']}")
    print(f"\n📊 Rejection Breakdown:")
    print(f"   🏪 Retail/Non-Profit: {stats['retail_nonprofit']}")
    print(f"   🔨 Skilled Trades: {stats['skilled_trade']}")
    print(f"   📄 Content Validation Failed: {stats['content_validation_failed']}")
    print(f"   📏 Too Large: {stats['too_large']}")
    print(f"   📋 Missing Data: {stats['missing_data']}")
    print(f"   ⚠️  Validation Failed: {stats['validation_failed']}")
    print(f"   ❓ Other: {stats['other']}")
    if stats['website_searched'] > 0:
        print(f"\n🔍 Website Search:")
        print(f"   Searched: {stats['website_searched']}")
        print(f"   Found: {stats['website_found']} ({stats['website_found']*100//stats['website_searched'] if stats['website_searched'] > 0 else 0}%)")
    print(f"{'='*70}\n")

    if valid_leads:
        # Export to JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"output/quick_leads_{timestamp}.json"

        leads_data = []
        for lead in valid_leads:
            leads_data.append({
                'business_name': lead.business_name,
                'address': lead.location.address,
                'city': lead.location.city,
                'phone': lead.contact.phone,
                'email': lead.contact.email,
                'website': lead.contact.website,
                'industry': lead.industry,
                'years_in_business': lead.years_in_business,
                'employee_count': lead.employee_count,
                'estimated_revenue': None  # No revenue estimation - cannot be verified
            })

        with open(output_file, 'w') as f:
            json.dump({
                'generated_at': timestamp,
                'total_leads': len(valid_leads),
                'criteria': {
                    'revenue_min': config.business_criteria.target_revenue_min,
                    'revenue_max': config.business_criteria.target_revenue_max,
                    'min_years': config.business_criteria.min_years_in_business,
                    'max_employees': config.business_criteria.max_employee_count
                },
                'leads': leads_data
            }, f, indent=2)

        print(f"📄 Exported to: {output_file}\n")

        # Show first 20 leads
        print(f"📋 QUALIFIED LEADS:\n")
        for i, lead in enumerate(valid_leads[:count], 1):
            print(f"{i}. {lead.business_name}")
            print(f"   📍 {lead.location.address}, {lead.location.city}, ON")
            print(f"   📞 {lead.contact.phone}")
            if lead.contact.website:
                print(f"   🌐 {lead.contact.website}")
            print(f"   💼 {lead.industry.replace('_', ' ').title()} | 📅 {lead.years_in_business} yrs | 👥 {lead.employee_count} emp")
            print()

    return valid_leads

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Quick lead generator (no LLM)")
    parser.add_argument('count', type=int, nargs='?', default=20, help="Number of leads to generate")
    parser.add_argument('--show', action='store_true', help="Show detailed progress")
    args = parser.parse_args()

    try:
        asyncio.run(generate_leads(args.count, args.show))
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        print("Partial results may have been saved to output/")
        sys.exit(1)
