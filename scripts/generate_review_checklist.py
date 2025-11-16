"""
Generate manual review checklist from current pipeline.
Applies new filters and generates systematic 5-minute review tasks.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from src.core.models import BusinessLead, ContactInfo, LocationInfo, RevenueEstimate
from src.filters.size_filters import filter_by_size
from src.filters.business_type_filters import BusinessTypeFilter
from src.enrichment.warning_generator import generate_warnings


def load_leads_from_csv(csv_path: str) -> list:
    """Load leads from CSV and convert to BusinessLead objects."""
    df = pd.read_csv(csv_path)

    leads = []
    for _, row in df.iterrows():
        # Create ContactInfo
        website = row.get('website')
        if pd.isna(website) or website == 'N/A':
            website = None

        contact = ContactInfo(
            phone=row.get('phone') if pd.notna(row.get('phone')) else None,
            email=None,  # Not in CSV
            website=website
        )

        # Create LocationInfo
        location = LocationInfo(
            address=row.get('street') if pd.notna(row.get('street')) else None,
            city=row.get('city') if pd.notna(row.get('city')) else None,
            province=row.get('province') if pd.notna(row.get('province')) else None,
            postal_code=None  # Not in CSV
        )

        # Create RevenueEstimate (use midpoint of range for better accuracy)
        revenue_min = row.get('revenue_min', 0)
        revenue_max = row.get('revenue_max', 0)

        if pd.notna(revenue_min) and pd.notna(revenue_max):
            revenue_min = int(float(revenue_min))
            revenue_max = int(float(revenue_max))
            # Use midpoint as the estimate
            revenue_estimate_amount = (revenue_min + revenue_max) // 2
        elif pd.notna(revenue_max):
            revenue_estimate_amount = int(float(revenue_max))
        else:
            revenue_estimate_amount = None

        revenue = RevenueEstimate(
            estimated_amount=revenue_estimate_amount,
            confidence_score=row.get('confidence', 0.0) if pd.notna(row.get('confidence')) else 0.0
        )

        # Parse employee count
        employee_range = row.get('employee_range', '')
        if pd.notna(employee_range) and '-' in str(employee_range):
            # Take upper bound of range (e.g., "7-16" -> 16)
            try:
                employee_count = int(str(employee_range).split('-')[1])
            except:
                employee_count = None
        else:
            employee_count = None

        # Create BusinessLead
        industry = row.get('industry', 'general_business')
        if pd.isna(industry):
            industry = 'general_business'

        lead = BusinessLead(
            business_name=row['business_name'],
            contact=contact,
            location=location,
            revenue_estimate=revenue,
            employee_count=employee_count,
            industry=industry,
            review_count=int(row.get('review_count')) if pd.notna(row.get('review_count')) else None,
            years_in_business=None  # Not in CSV
        )

        leads.append(lead)

    return leads


def apply_filters_and_classify(leads: list) -> dict:
    """
    Apply all filters and classify leads.

    Returns:
        {
            'excluded_size': [...],
            'excluded_retail': [...],
            'excluded_location': [...],
            'clean': [...],
            'clean_with_warnings': [...]
        }
    """
    type_filter = BusinessTypeFilter()

    results = {
        'excluded_size': [],
        'excluded_retail': [],
        'excluded_location': [],
        'clean': [],
        'clean_with_warnings': []
    }

    for lead in leads:
        # Filter 1: Size
        is_oversized, reason = filter_by_size(lead)
        if is_oversized:
            results['excluded_size'].append((lead, reason))
            continue

        # Filter 2: Retail
        is_retail, reason = type_filter.is_retail_business(
            lead.business_name,
            lead.industry,
            lead.contact.website
        )
        if is_retail:
            results['excluded_retail'].append((lead, reason))
            continue

        # Filter 3: Location label
        is_location, reason = type_filter.is_location_label(
            lead.business_name,
            lead.contact.website,
            lead.review_count
        )
        if is_location:
            results['excluded_location'].append((lead, reason))
            continue

        # Passed all filters - check for warnings
        warnings = generate_warnings(lead)
        for warning in warnings:
            lead.add_warning("MANUAL_REVIEW", warning)

        if warnings:
            results['clean_with_warnings'].append(lead)
        else:
            results['clean'].append(lead)

    return results


def print_summary(results: dict):
    """Print summary of filtering results."""
    total = sum([
        len(results['excluded_size']),
        len(results['excluded_retail']),
        len(results['excluded_location']),
        len(results['clean']),
        len(results['clean_with_warnings'])
    ])

    print("\n" + "=" * 70)
    print("FILTER RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n❌ EXCLUDED - Size (revenue/employees): {len(results['excluded_size'])}")
    for lead, reason in results['excluded_size']:
        print(f"  - {lead.business_name}: {reason}")

    print(f"\n❌ EXCLUDED - Retail Business: {len(results['excluded_retail'])}")
    for lead, reason in results['excluded_retail']:
        print(f"  - {lead.business_name}: {reason}")

    print(f"\n❌ EXCLUDED - Location Label: {len(results['excluded_location'])}")
    for lead, reason in results['excluded_location']:
        print(f"  - {lead.business_name}: {reason}")

    print(f"\n✅ CLEAN (no warnings): {len(results['clean'])}")
    for lead in results['clean']:
        print(f"  - {lead.business_name}")

    print(f"\n⚠️  CLEAN with warnings: {len(results['clean_with_warnings'])}")
    for lead in results['clean_with_warnings']:
        print(f"  - {lead.business_name} ({len(lead.warnings)} warnings)")

    print(f"\n📊 OVERALL:")
    print(f"  Total leads: {total}")
    print(f"  Excluded: {len(results['excluded_size']) + len(results['excluded_retail']) + len(results['excluded_location'])} ({(len(results['excluded_size']) + len(results['excluded_retail']) + len(results['excluded_location'])) / total * 100:.0f}%)")
    print(f"  Clean: {len(results['clean']) + len(results['clean_with_warnings'])} ({(len(results['clean']) + len(results['clean_with_warnings'])) / total * 100:.0f}%)")
    print(f"  High priority (no warnings): {len(results['clean'])} ({len(results['clean']) / total * 100:.0f}%)")
    print()


def generate_checklist_file(results: dict, output_path: str):
    """Generate manual review checklist file."""
    # Combine clean leads (prioritize those without warnings)
    all_clean_leads = results['clean'] + results['clean_with_warnings']

    if not all_clean_leads:
        print("⚠️  No clean leads to review!")
        return

    # Sort: no warnings first
    all_clean_leads.sort(key=lambda x: len(x.warnings))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("MANUAL REVIEW CHECKLIST - HAMILTON BUSINESS LEADS\n")
        f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Total Leads: {len(all_clean_leads)}\n")
        f.write(f"Estimated Time: {len(all_clean_leads) * 5} minutes ({len(all_clean_leads) * 5 / 60:.1f} hours)\n")
        f.write("=" * 70 + "\n\n")

        for i, lead in enumerate(all_clean_leads, 1):
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"LEAD {i} of {len(all_clean_leads)}\n")
            f.write("=" * 70 + "\n")

            # Write checklist
            website = lead.contact.website or "NO WEBSITE - check directory listings"
            priority = "HIGH" if not lead.warnings else "MEDIUM"

            f.write(f"\n=== MANUAL REVIEW: {lead.business_name} ===\n")
            f.write(f"Priority: {priority}\n")
            f.write(f"Estimated Time: 5 minutes\n\n")

            f.write(f"BUSINESS INFO:\n")
            f.write(f"  Name: {lead.business_name}\n")
            f.write(f"  Address: {lead.location.address}, {lead.location.city}\n")
            f.write(f"  Phone: {lead.contact.phone or 'N/A'}\n")
            f.write(f"  Website: {website}\n")
            f.write(f"  Industry: {lead.industry}\n")
            if lead.employee_count:
                f.write(f"  Employees: {lead.employee_count}\n")
            if lead.revenue_estimate.estimated_amount:
                f.write(f"  Revenue Estimate: ${lead.revenue_estimate.estimated_amount/1_000_000:.2f}M\n")
            if lead.review_count:
                f.write(f"  Google Reviews: {lead.review_count}\n")
            f.write("\n")

            f.write("STEP 1: Verify Still Operating (1 min)\n")
            f.write(f'  [ ] Google: "{lead.business_name} closed"\n')
            f.write("  [ ] Check Google Maps: Recent reviews (last 3 months)?\n")
            f.write(f"  [ ] Website accessible: {website}\n")
            f.write("\n")
            f.write("  Red Flags: \"Permanently closed\", \"Out of business\", auction notices\n\n")

            f.write("STEP 2: Check Compliance & Risk (1 min)\n")
            f.write(f'  [ ] Google: "{lead.business_name} Hamilton violations"\n')
            f.write(f'  [ ] Google: "{lead.business_name} Hamilton health"\n')
            f.write(f'  [ ] Google News: "{lead.business_name}" (filter: past year)\n')
            f.write("\n")
            f.write("  Red Flags: Health closures, lawsuits, distress sales, negative press\n\n")

            f.write("STEP 3: Verify Business Type (1 min)\n")
            f.write("  [ ] Website: Primarily B2B or consumer retail?\n")
            f.write("  [ ] Customer base: Industrial/commercial or retail consumers?\n")
            f.write("  [ ] If food business: Restaurant/retail or manufacturing?\n")
            f.write("\n")
            f.write("  Red Flags: Retail storefront, consumer e-commerce, franchise\n\n")

            f.write("STEP 4: Validate Size (1 min)\n")
            f.write("  [ ] LinkedIn company page: How many employees listed?\n")
            f.write("  [ ] Website \"About\" page: Company size mentioned?\n")
            f.write("  [ ] Multiple locations mentioned anywhere?\n")
            f.write("\n")
            f.write("  Red Flags: 50+ employees on LinkedIn, \"offices in X cities\", \"global\"\n\n")

            f.write("STEP 5: Quick Due Diligence (1 min)\n")
            f.write("  [ ] BBB profile or rating\n")
            f.write("  [ ] Any public financial disclosures?\n")
            f.write(f'  [ ] Google: "{lead.business_name} for sale" (already on market?)\n')
            f.write("\n")
            f.write("  Red Flags: F rating, bankruptcy filings, actively listed for sale\n\n")

            f.write("---\n")
            f.write("DECISION:\n")
            f.write("  [ ] PROCEED - Clean lead, ready for outreach\n")
            f.write("  [ ] FLAG - Minor concerns, proceed with caution\n")
            f.write("  [ ] EXCLUDE - Deal-breaker issue found\n\n")

            f.write("Notes:\n")
            f.write("_" * 70 + "\n")
            f.write("_" * 70 + "\n\n")

            # Add warnings if any
            if lead.warnings:
                f.write("⚠️ SYSTEM WARNINGS:\n")
                for warning in lead.warnings:
                    f.write(f"  - {warning}\n")
                f.write("\n")

            # Search queries
            f.write("QUICK SEARCH QUERIES:\n")
            f.write(f'  - "{lead.business_name}" Hamilton manufacturing\n')
            f.write(f'  - "{lead.business_name}" reviews\n')
            f.write(f'  - "{lead.business_name}" employees linkedin\n')
            f.write(f'  - site:linkedin.com/company "{lead.business_name}"\n')
            f.write("\n")

    print(f"\n✅ Manual review checklist generated: {output_path}")
    print(f"📋 {len(all_clean_leads)} leads to review")
    print(f"⏱️  Estimated time: {len(all_clean_leads) * 5} minutes ({len(all_clean_leads) * 5 / 60:.1f} hours)\n")


def main():
    """Main execution."""
    # Load current leads
    csv_path = "data/FINAL_VALIDATED_LEADS_20251103_165454.csv"
    print(f"\n📂 Loading leads from: {csv_path}")

    leads = load_leads_from_csv(csv_path)
    print(f"✅ Loaded {len(leads)} leads")

    # Apply filters
    print("\n🔍 Applying filters...")
    results = apply_filters_and_classify(leads)

    # Print summary
    print_summary(results)

    # Generate checklist
    output_path = "data/outputs/MANUAL_REVIEW_CHECKLIST.txt"
    print(f"\n📝 Generating checklist: {output_path}")
    generate_checklist_file(results, output_path)

    print("\n✅ DONE!\n")
    print("Next steps:")
    print("1. Open the checklist file")
    print("2. Spend 5 minutes per lead reviewing systematically")
    print("3. Mark PROCEED / FLAG / EXCLUDE for each")
    print("4. Focus on high-priority leads first (no warnings)\n")


if __name__ == "__main__":
    main()
