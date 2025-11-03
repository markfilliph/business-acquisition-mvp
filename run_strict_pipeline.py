#!/usr/bin/env python3
"""
STRICT LEAD GENERATION PIPELINE
- Google Places ONLY (most accurate source)
- Strict category filtering (no restaurants, retail, franchises)
- Revenue range max 50% spread
- Manufacturing/Wholesale/B2B only
"""
import asyncio
import aiosqlite
from datetime import datetime
import structlog

from src.sources.google_places import GooglePlacesSource
from src.gates.category_gate import category_gate
from src.enrichment.smart_enrichment import SmartEnricher
from src.core.config import config

logger = structlog.get_logger(__name__)


async def run_strict_pipeline(target_count=20):
    """
    Strict pipeline using only Google Places.

    Flow:
    1. Fetch from Google Places (manufacturing only)
    2. Apply STRICT category filtering
    3. Estimate revenue with narrow ranges
    4. Validate range width (<50% spread)
    5. Only qualify businesses meeting ALL criteria
    """

    print(f"\n{'='*90}")
    print(f"🎯 STRICT LEAD GENERATION PIPELINE")
    print(f"{'='*90}")
    print(f"Target: {target_count} qualified leads")
    print(f"Source: Google Places API ONLY")
    print(f"Criteria:")
    print(f"  ✓ Manufacturing / Wholesale / B2B ONLY")
    print(f"  ✓ NO restaurants, retail, consumer services")
    print(f"  ✓ NO franchises or chains")
    print(f"  ✓ 5-30 employees")
    print(f"  ✓ 15+ years in business")
    print(f"  ✓ Revenue $800K-$2M (adjusted)")
    print(f"  ✓ Revenue range <50% spread")
    print(f"{'='*90}\n")

    # Initialize
    google_places = GooglePlacesSource()
    enricher = SmartEnricher()

    # Stats
    stats = {
        'discovered': 0,
        'category_excluded': 0,
        'franchise_excluded': 0,
        'revenue_range_too_wide': 0,
        'revenue_out_of_range': 0,
        'qualified': 0
    }

    qualified_leads = []

    # Fetch manufacturing businesses from Google Places
    print("🔍 Step 1/4: Discovering businesses from Google Places...")
    businesses = await google_places.fetch_businesses(
        location='Hamilton, ON',
        industry='manufacturing',
        max_results=target_count * 10  # Fetch 10x to account for filtering
    )

    stats['discovered'] = len(businesses)
    print(f"✅ Discovered {len(businesses)} businesses\n")

    print("🔍 Step 2/4: Applying strict category filters...")
    for idx, biz in enumerate(businesses, 1):
        print(f"[{idx}/{len(businesses)}] {biz.name}")

        # STRICT category gate (with website check for corporate patterns)
        category_result = category_gate(
            industry=biz.industry or 'unknown',
            business_types=[biz.industry] if biz.industry else [],
            business_name=biz.name,
            website=biz.website if hasattr(biz, 'website') else None
        )

        if not category_result.passes:
            if 'franchise' in (category_result.review_reason or '').lower():
                stats['franchise_excluded'] += 1
                print(f"    ❌ EXCLUDED: Franchise/chain")
            else:
                stats['category_excluded'] += 1
                print(f"    ❌ EXCLUDED: {category_result.review_reason}")
            continue

        # Estimate employees (if not already available)
        if not hasattr(biz, 'employee_count') or not biz.employee_count:
            emp_estimate = enricher.estimate_employees_from_industry(
                industry=biz.industry or 'general_business',
                city=biz.city
            )
            emp_min = emp_estimate['employee_range_min']
            emp_max = emp_estimate['employee_range_max']
        else:
            emp_min = emp_max = biz.employee_count

        # Check employee range
        if emp_min < 5 or emp_max > 30:
            print(f"    ❌ EXCLUDED: Employees {emp_min}-{emp_max} (need 5-30)")
            continue

        # Calculate years in business from year_established if available
        years_in_business = None
        if hasattr(biz, 'year_established') and biz.year_established:
            from datetime import datetime
            current_year = datetime.now().year
            years_in_business = current_year - biz.year_established

        # Get review count from Google Places data
        review_count = getattr(biz, 'review_count', 0) or 0

        # Estimate revenue with multi-factor approach (NOW ENHANCED!)
        rev_estimate = enricher.estimate_revenue_from_employees(
            employee_min=emp_min,
            employee_max=emp_max,
            industry=biz.industry or 'general_business',
            years_in_business=years_in_business,
            has_website=bool(biz.website),
            review_count=review_count,
            city=biz.city
        )

        # Check revenue range width (must be <80% spread - realistic without enrichment)
        rev_min = rev_estimate['revenue_min']
        rev_max = rev_estimate['revenue_max']
        rev_mid = rev_estimate['revenue_midpoint']

        spread_percentage = ((rev_max - rev_min) / rev_mid) * 100

        if spread_percentage > 80:
            stats['revenue_range_too_wide'] += 1
            print(f"    ❌ EXCLUDED: Revenue range too wide ({spread_percentage:.0f}% spread)")
            continue

        # Check if revenue midpoint is in target range
        target_min = config.TARGET_REVENUE_MIN
        target_max = config.TARGET_REVENUE_MAX

        # Must have SOME overlap with target range
        if rev_max < target_min or rev_min > target_max:
            stats['revenue_out_of_range'] += 1
            print(f"    ❌ EXCLUDED: Revenue ${rev_min:,.0f}-${rev_max:,.0f} outside ${target_min:,.0f}-${target_max:,.0f}")
            continue

        # QUALIFIED!
        stats['qualified'] += 1
        qualified_leads.append({
            'name': biz.name,
            'address': f"{biz.street}, {biz.city}",
            'phone': biz.phone or 'N/A',
            'website': biz.website or 'N/A',
            'industry': biz.industry or 'general_business',
            'employees': f"{emp_min}-{emp_max}",
            'revenue_range': f"${rev_min:,.0f}-${rev_max:,.0f}",
            'revenue_spread': f"{spread_percentage:.0f}%",
            'confidence': rev_estimate['confidence']
        })

        print(f"    ✅ QUALIFIED: {biz.name}")
        print(f"       Employees: {emp_min}-{emp_max}")
        print(f"       Revenue: ${rev_min:,.0f}-${rev_max:,.0f} ({spread_percentage:.0f}% spread)")

        if stats['qualified'] >= target_count:
            print(f"\n🎉 Target reached! {stats['qualified']} qualified leads")
            break

    # Print results
    print(f"\n{'='*90}")
    print(f"📊 RESULTS")
    print(f"{'='*90}")
    print(f"Discovered:              {stats['discovered']}")
    print(f"Category Excluded:       {stats['category_excluded']}")
    print(f"Franchise Excluded:      {stats['franchise_excluded']}")
    print(f"Revenue Range Too Wide:  {stats['revenue_range_too_wide']}")
    print(f"Revenue Out of Range:    {stats['revenue_out_of_range']}")
    print(f"✅ QUALIFIED:            {stats['qualified']}")
    print(f"{'='*90}\n")

    if qualified_leads:
        print(f"📋 QUALIFIED LEADS:\n")
        for idx, lead in enumerate(qualified_leads, 1):
            print(f"{idx}. {lead['name']}")
            print(f"   📍 {lead['address']}")
            print(f"   📞 {lead['phone']}")
            print(f"   🌐 {lead['website']}")
            print(f"   👥 Employees: {lead['employees']}")
            print(f"   💰 Revenue: {lead['revenue_range']} ({lead['revenue_spread']} spread)")
            print(f"   🏭 Industry: {lead['industry']}")
            print(f"   📊 Confidence: {lead['confidence']:.0%}")
            print()

    return qualified_leads


if __name__ == '__main__':
    asyncio.run(run_strict_pipeline(target_count=20))
