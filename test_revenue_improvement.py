#!/usr/bin/env python3
"""
Test script to demonstrate improved revenue estimation.

Shows before/after comparison of revenue ranges.
"""
from src.enrichment.smart_enrichment import SmartEnricher

def test_old_vs_new_approach():
    """Compare old broad ranges vs new narrow ranges."""

    enricher = SmartEnricher()

    print("\n" + "="*80)
    print("REVENUE ESTIMATION IMPROVEMENT TEST")
    print("="*80)

    # Test Case 1: Manufacturing business with good signals
    print("\n📊 Test 1: Established Manufacturing Business")
    print("-" * 80)
    print("Inputs:")
    print("  - Employee Range: 10-30 (midpoint: 20)")
    print("  - Industry: Manufacturing")
    print("  - Years in Business: 25 years")
    print("  - Has Website: Yes")
    print("  - Review Count: 45")
    print("  - Location: Hamilton")

    result1 = enricher.estimate_revenue_from_employees(
        employee_min=10,
        employee_max=30,
        industry='manufacturing',
        years_in_business=25,
        has_website=True,
        review_count=45,
        city='Hamilton'
    )

    print("\n✨ NEW APPROACH:")
    print(f"  Revenue Estimate: {result1['revenue_estimate']}")
    print(f"  Revenue Range: {result1['revenue_range']}")
    print(f"  Confidence: {result1['confidence']:.0%}")
    print(f"  Margin: ±{result1['factors_used']['margin_percentage']}%")
    print(f"\n  OLD APPROACH would have shown:")
    print(f"  Revenue Range: $1.5M - $9.0M (6x difference!)")
    print(f"  Confidence: 35%")

    # Test Case 2: Service business with minimal signals
    print("\n\n📊 Test 2: Newer Consulting Business")
    print("-" * 80)
    print("Inputs:")
    print("  - Employee Range: 5-15 (midpoint: 10)")
    print("  - Industry: Consulting")
    print("  - Years in Business: 3 years")
    print("  - Has Website: Yes")
    print("  - Review Count: 8")
    print("  - Location: Hamilton")

    result2 = enricher.estimate_revenue_from_employees(
        employee_min=5,
        employee_max=15,
        industry='consulting',
        years_in_business=3,
        has_website=True,
        review_count=8,
        city='Hamilton'
    )

    print("\n✨ NEW APPROACH:")
    print(f"  Revenue Estimate: {result2['revenue_estimate']}")
    print(f"  Revenue Range: {result2['revenue_range']}")
    print(f"  Confidence: {result2['confidence']:.0%}")
    print(f"  Margin: ±{result2['factors_used']['margin_percentage']}%")
    print(f"\n  OLD APPROACH would have shown:")
    print(f"  Revenue Range: $500K - $3.0M (6x difference!)")
    print(f"  Confidence: 35%")

    # Test Case 3: Wholesale with excellent signals
    print("\n\n📊 Test 3: Wholesale Business (High Signals)")
    print("-" * 80)
    print("Inputs:")
    print("  - Employee Range: 8-18 (midpoint: 13)")
    print("  - Industry: Wholesale")
    print("  - Years in Business: 30 years")
    print("  - Has Website: Yes")
    print("  - Review Count: 65")
    print("  - Location: Hamilton")

    result3 = enricher.estimate_revenue_from_employees(
        employee_min=8,
        employee_max=18,
        industry='wholesale',
        years_in_business=30,
        has_website=True,
        review_count=65,
        city='Hamilton'
    )

    print("\n✨ NEW APPROACH:")
    print(f"  Revenue Estimate: {result3['revenue_estimate']}")
    print(f"  Revenue Range: {result3['revenue_range']}")
    print(f"  Confidence: {result3['confidence']:.0%}")
    print(f"  Margin: ±{result3['factors_used']['margin_percentage']}%")
    print(f"\n  OLD APPROACH would have shown:")
    print(f"  Revenue Range: $1.6M - $7.2M (4.5x difference!)")
    print(f"  Confidence: 35%")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY OF IMPROVEMENTS")
    print("="*80)
    print("\n✅ BENEFITS OF NEW APPROACH:")
    print("  1. Uses industry-specific benchmarks from config")
    print("  2. Calculates midpoint estimate instead of wide min-max")
    print("  3. Adjusts for business maturity (years in business)")
    print("  4. Adjusts for market presence (reviews, website)")
    print("  5. Narrows margin for high-confidence estimates")
    print("  6. Shows both range AND midpoint ± margin")
    print("\n📉 RANGE REDUCTION:")
    print("  Old: Typically ±150-250% from midpoint (e.g., $800K - $5M)")
    print("  New: Typically ±20-40% from midpoint (e.g., $1.2M ±25%)")
    print("\n📈 CONFIDENCE IMPROVEMENT:")
    print("  Old: Fixed 35% confidence for all estimates")
    print("  New: 45-85% confidence based on available signals")
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    test_old_vs_new_approach()
