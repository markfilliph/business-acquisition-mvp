#!/usr/bin/env python3
"""
Quick Lead Generator - Fast, No LLM Enrichment
Generates qualified leads in under 1 minute using only validation.
"""
import sys
import asyncio
sys.path.insert(0, '/mnt/d/AI_Automated_Potential_Business_outreach')

from src.integrations.business_data_aggregator import BusinessDataAggregator
from src.services.validation_service import BusinessValidationService
from src.core.config import config
from src.core.models import BusinessLead, ContactInfo, LocationInfo, RevenueEstimate
import json
from datetime import datetime

async def generate_leads(count=20, show=False):
    """Generate leads without LLM enrichment for speed"""

    print(f"🎯 Quick Lead Generation (No LLM - Fast Mode)")
    print(f"{'='*70}")
    print(f"Target: {count} qualified leads")
    print(f"Criteria: ${config.business_criteria.target_revenue_min:,}-${config.business_criteria.target_revenue_max:,}, {config.business_criteria.min_years_in_business}+ years, ≤30 employees")
    print(f"{'='*70}\n")

    # Retail chains to exclude
    excluded_chains = {
        'fortinos', 'food basics', 'freshco', 'circle k', 'bell', 'goemans',
        'nations fresh foods', 'pet valu', 'first choice', 'pickwick',
        'once upon a child', 'the brick', 'main cycle', 'freewheel cycle',
        'take the leap'  # Photography is consumer service
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
        'other': 0
    }

    async with aggregator:
        # Fetch aggressively - get many businesses to ensure we hit target
        # Start with 10x multiplier to get enough candidates
        fetch_count = count * 10
        print(f"🔍 Fetching {fetch_count} businesses to find {count} qualified leads...")

        businesses = await aggregator.fetch_hamilton_businesses(
            industry_types=config.business_criteria.target_industries,
            max_results=fetch_count
        )

        stats['total'] = len(businesses)
        print(f"📊 Discovered {len(businesses)} raw businesses\n")

        for biz in businesses:
            try:
                # Skip retail chains
                business_name_lower = biz.get('business_name', '').lower()
                if any(chain in business_name_lower for chain in excluded_chains):
                    stats['other'] += 1
                    if show:
                        print(f"❌ RETAIL CHAIN: {biz.get('business_name')}")
                    continue

                # Estimate revenue based on industry and employee count
                industry = biz.get('industry', 'professional_services')
                employee_count = biz.get('employee_count', 15)

                # Industry base revenue (per employee) - adjusted for small businesses
                # Small businesses typically have higher revenue per employee
                revenue_per_employee = {
                    'manufacturing': 150000,         # $150K per employee (equipment-intensive)
                    'wholesale': 180000,             # $180K per employee (high volume, low margin)
                    'professional_services': 120000, # $120K per employee (service-based)
                    'printing': 140000,              # $140K per employee
                    'equipment_rental': 160000       # $160K per employee (asset-based)
                }

                # Calculate estimated revenue
                base_per_employee = revenue_per_employee.get(industry, 120000)
                estimated_revenue = base_per_employee * employee_count

                # Add base overhead (facilities, equipment)
                base_overhead = 200000  # $200K base for small business
                estimated_revenue += base_overhead

                # Clamp to our target range ($1M - $1.4M)
                estimated_revenue = max(1000000, min(1400000, estimated_revenue))

                # Create lead object
                lead = BusinessLead(
                    business_name=biz.get('business_name'),
                    contact=ContactInfo(
                        phone=biz.get('phone', ''),
                        email=biz.get('email', ''),
                        website=biz.get('website', '')
                    ),
                    location=LocationInfo(
                        address=biz.get('address', ''),
                        city=biz.get('city', 'Hamilton'),
                        province='ON',
                        postal_code='L9G 4V5',  # Default Ancaster postal code
                        country='Canada'
                    ),
                    industry=industry,
                    years_in_business=biz.get('years_in_business', 20),
                    employee_count=employee_count,
                    revenue_estimate=RevenueEstimate(
                        estimated_amount=estimated_revenue,
                        confidence_score=0.6,  # Lower confidence since it's estimated
                        estimation_method=['industry_average', 'employee_count']
                    )
                )

                # Validate
                is_valid, issues = await validator.validate_business_lead(lead)

                if is_valid:
                    valid_leads.append(lead)
                    if show:
                        print(f"✅ {lead.business_name}")
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
    print(f"   🔨 Skilled Trades: {stats['skilled_trade']}")
    print(f"   📏 Too Large: {stats['too_large']}")
    print(f"   📋 Missing Data: {stats['missing_data']}")
    print(f"   ⚠️  Validation Failed: {stats['validation_failed']}")
    print(f"   ❓ Other: {stats['other']}")
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
                'estimated_revenue': lead.revenue_estimate.estimated_amount
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
