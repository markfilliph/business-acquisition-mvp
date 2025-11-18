"""
Apply Exclusion Filters and Re-Validate

1. Load enriched Google Places data
2. Apply exclusion filters
3. Export filtered candidates for LinkedIn verification
"""
import asyncio
import csv
from src.filters.exclusion_filters import ExclusionFilters


async def filter_and_prepare_for_verification():
    """Apply filters to enriched data and prepare for manual verification."""

    filters = ExclusionFilters()

    # Load enriched data
    input_csv = 'data/google_places_FULLY_ENRICHED.csv'

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        businesses = list(reader)

    print(f"\n{'='*80}")
    print("APPLYING EXCLUSION FILTERS")
    print(f"{'='*80}\n")
    print(f"Total businesses to check: {len(businesses)}\n")

    passed = []
    excluded = []

    for biz in businesses:
        name = biz.get('Business Name', '')
        industry = biz.get('Industry', '')

        should_exclude, reason = filters.should_exclude(name, industry)

        if should_exclude:
            biz['Exclusion Reason'] = reason
            excluded.append(biz)
            print(f"❌ EXCLUDED: {name}")
            print(f"   Reason: {reason}\n")
        else:
            passed.append(biz)
            print(f"✅ PASSED: {name}")

    print(f"\n{'='*80}")
    print("FILTER RESULTS")
    print(f"{'='*80}")
    print(f"✅ Passed filters: {len(passed)}")
    print(f"❌ Excluded: {len(excluded)}")
    print()

    # Further filter by years in business
    candidates_for_verification = []

    for biz in passed:
        years = biz.get('Years in Business', '')

        # Skip if no years data
        if not years or years.startswith('UNKNOWN'):
            continue

        try:
            years_float = float(years)

            # Accept 10+ years for manual verification
            if years_float >= 10:
                candidates_for_verification.append(biz)
        except:
            continue

    print(f"Businesses with 10+ years in business: {len(candidates_for_verification)}")
    print()

    # Export for LinkedIn verification
    output_csv = 'data/CANDIDATES_FOR_LINKEDIN_VERIFICATION.csv'

    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        if candidates_for_verification:
            fieldnames = list(candidates_for_verification[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(candidates_for_verification)

    print(f"✅ Exported {len(candidates_for_verification)} candidates to: {output_csv}")
    print()
    print("="*80)
    print("NEXT STEP: Manual LinkedIn Verification")
    print("="*80)
    print("\nRun the following command to start manual verification:")
    print("  python src/enrichment/linkedin_verification.py")
    print()
    print("This will:")
    print("  1. Open each company's LinkedIn page")
    print("  2. Ask you to verify actual employee count")
    print("  3. Mark franchises/corporations for exclusion")
    print("  4. Generate final verified leads list")
    print()

    # Show top candidates
    print("="*80)
    print("TOP CANDIDATES FOR VERIFICATION (sorted by years in business)")
    print("="*80)
    print()

    sorted_candidates = sorted(
        candidates_for_verification,
        key=lambda x: float(x.get('Years in Business', 0)),
        reverse=True
    )

    for i, biz in enumerate(sorted_candidates[:30], 1):
        name = biz.get('Business Name', '')
        years = biz.get('Years in Business', '')
        emp_range = biz.get('Employee Range', '')
        website = biz.get('Website', '')

        print(f"{i}. {name}")
        print(f"   Years: {years} | Employees: {emp_range}")
        print(f"   Website: {website}")
        print()

    return len(candidates_for_verification)


if __name__ == '__main__':
    asyncio.run(filter_and_prepare_for_verification())
