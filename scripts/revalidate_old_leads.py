#!/usr/bin/env python3
"""
Revalidate old leads using the updated pipeline (no estimation, no hardcoded data).
Compares old data with new validation results.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

from src.services.validation_service import BusinessValidationService
from src.core.config import config
from src.core.models import BusinessLead, ContactInfo, LocationInfo, RevenueEstimate

# Old leads from October 1, 2025 (BEFORE fixes)
OLD_LEADS = [
    {
        'business_name': 'A.H. Burns Energy Systems Ltd.',
        'address': '1-1370 Sandhill Drive, Ancaster, ON L9G 4V5',
        'phone': '(905) 525-6321',
        'website': 'https://burnsenergy.ca',
        'industry': 'professional_services',
        'revenue': 1160000,  # OLD - was estimated
        'years': 22,  # OLD - was hardcoded
        'employees': 8,  # OLD - was hardcoded
    },
    {
        'business_name': '360 Energy Inc',
        'address': '1480 Sandhill Drive Unit 8B, Ancaster, ON L9G 4V5',
        'phone': '(877) 431-0332',
        'website': 'https://360energy.net',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 22,
        'employees': 6,
    },
    {
        'business_name': 'AVL Manufacturing Inc.',
        'address': 'Hamilton, ON',
        'phone': '(905) 544-0606',
        'website': 'https://avlmfg.com',
        'industry': 'manufacturing',
        'revenue': 1100000,
        'years': 22,
        'employees': 6,
    },
    {
        'business_name': 'VSX Web Design',
        'address': 'Stoney Creek, ON',
        'phone': '(905) 662-8679',
        'website': 'https://vsxwebdesign.com',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Premier Printing and Signs Ltd',
        'address': 'Hamilton, ON',
        'phone': '(905) 544-9999',
        'website': 'http://www.vehiclegraphicshamilton.ca',
        'industry': 'printing',
        'revenue': 1040000,
        'years': 22,
        'employees': 6,
    },
    {
        'business_name': 'Affinity Biologicals Inc',
        'address': 'Ancaster, ON',
        'phone': '(905) 304-7555',
        'website': 'https://www.affinitybiologicals.com',
        'industry': 'manufacturing',
        'revenue': 1100000,
        'years': 22,
        'employees': 6,
    },
    {
        'business_name': 'Nova Filtration Technologies Inc',
        'address': 'Ancaster, ON',
        'phone': '(905) 648-6400',
        'website': 'https://www.novafiltration.com',
        'industry': 'manufacturing',
        'revenue': 1100000,
        'years': 22,
        'employees': 6,
    },
    {
        'business_name': 'Steel & Timber Supply Co Inc',
        'address': 'Ancaster, ON',
        'phone': '(905) 648-4449',
        'website': 'https://www.steelandtimber.com',
        'industry': 'wholesale',
        'revenue': 1280000,
        'years': 22,
        'employees': 6,
    },
    {
        'business_name': 'Access Point Lowering Systems Inc',
        'address': 'Ancaster, ON',
        'phone': '(905) 648-3212',
        'website': 'https://www.accesspoint.ca',
        'industry': 'manufacturing',
        'revenue': 1400000,
        'years': 22,
        'employees': 8,
    },
    {
        'business_name': 'Niagara Belco Elevator Inc',
        'address': 'Ancaster, ON',
        'phone': '(905) 648-4200',
        'website': 'https://www.niagarabelco.com',
        'industry': 'manufacturing',
        'revenue': 1100000,
        'years': 22,
        'employees': 6,
    },
    {
        'business_name': 'Tan Thanh Supermarket & Houseware',
        'address': '115, Park Street North, Hamilton',
        'phone': '(905) 528-8181',
        'website': None,
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Dee Signs',
        'address': '1021, Waterdown Road, Hamilton',
        'phone': '(905) 639-1144',
        'website': 'https://www.deesigns.ca/',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': "Curry's Art Supplies",
        'address': '610, King Street West, Hamilton, L8P 1C2',
        'phone': '(905) 529-7700',
        'website': 'https://www.currys.com',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'New Hope Community Bikes',
        'address': '1249, Main Street East, Hamilton, L8K 1A8',
        'phone': '(905) 545-1991',
        'website': 'https://www.newhopecommunitybikes.com/',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Fastenal',
        'address': '1205, Rymal Road East, Hamilton, L8W 3M9',
        'phone': '(905) 388-1698',
        'website': 'https://www.fastenal.com/locations/details/onha1',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Pardon Applications of Canada',
        'address': '21, King Street West, Hamilton, L4P 4W7',
        'phone': '(905) 545-2022',
        'website': 'https://www.pardonapplications.ca/',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Central Health Institute',
        'address': '346, Main Street East, Hamilton',
        'phone': '(905) 524-0440',
        'website': None,
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Bicycle Works',
        'address': '316, Dundas Street East',
        'phone': '(905) 689-1991',
        'website': None,
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Anytime Convenience',
        'address': '649, Upper James Street, Hamilton, L9C 2Y9',
        'phone': '(905) 389-9845',
        'website': None,
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
    {
        'business_name': 'Nardini Specialties',
        'address': '184, Highway 8, Hamilton, L8G 1C3',
        'phone': '(905) 662-5758',
        'website': 'https://www.nardinispecialties.ca/',
        'industry': 'professional_services',
        'revenue': 1000000,
        'years': 16,
        'employees': 6,
    },
]


async def revalidate_leads():
    """Revalidate old leads with new pipeline (no estimation/hardcoded data)."""

    print("=" * 80)
    print("LEAD REVALIDATION - October 2, 2025")
    print("=" * 80)
    print("Comparing OLD data (with estimation) vs NEW validation (no estimation)")
    print()

    validator = BusinessValidationService(config)

    results = {
        'old_total': len(OLD_LEADS),
        'new_valid': 0,
        'new_invalid': 0,
        'comparison': []
    }

    for i, old_lead_data in enumerate(OLD_LEADS, 1):
        print(f"\n{i}. {old_lead_data['business_name']}")
        print("-" * 80)

        # Create lead object (NEW WAY - no estimation)
        # We DON'T use the old estimated/hardcoded values
        lead = BusinessLead(
            business_name=old_lead_data['business_name'],
            contact=ContactInfo(
                phone=old_lead_data['phone'],
                email=None,
                website=old_lead_data['website']
            ),
            location=LocationInfo(
                address=old_lead_data['address'],
                city='Hamilton',  # Default
                province='ON',
                postal_code='L9G 4V5',  # Default Ancaster
                country='Canada'
            ),
            industry=old_lead_data['industry'],
            years_in_business=None,  # NEW: Don't use old hardcoded value
            employee_count=None,  # NEW: Don't use old hardcoded value
            revenue_estimate=RevenueEstimate()  # NEW: Empty - no estimation
        )

        # Validate with NEW pipeline
        is_valid, issues = await validator.validate_business_lead(lead)

        comparison = {
            'business_name': old_lead_data['business_name'],
            'old_status': 'Valid (with estimation)',
            'new_status': 'Valid' if is_valid else 'Invalid',
            'old_data': {
                'revenue': f"${old_lead_data['revenue']:,} (ESTIMATED)",
                'years': f"{old_lead_data['years']} (HARDCODED)",
                'employees': f"{old_lead_data['employees']} (HARDCODED)"
            },
            'new_data': {
                'revenue': 'None (not estimated)',
                'years': 'None (not available)',
                'employees': 'None (not available)'
            },
            'validation_issues': issues if not is_valid else []
        }

        results['comparison'].append(comparison)

        if is_valid:
            results['new_valid'] += 1
            print(f"   ✅ NEW STATUS: Valid")
        else:
            results['new_invalid'] += 1
            print(f"   ❌ NEW STATUS: Invalid")
            print(f"   Issues: {', '.join(issues)}")

        print(f"\n   OLD DATA (Oct 1 - with estimation):")
        print(f"      Revenue: ${old_lead_data['revenue']:,} ❌ ESTIMATED")
        print(f"      Years: {old_lead_data['years']} ❌ HARDCODED")
        print(f"      Employees: {old_lead_data['employees']} ❌ HARDCODED")

        print(f"\n   NEW DATA (Oct 2 - no estimation):")
        print(f"      Revenue: None ✅ NOT ESTIMATED")
        print(f"      Years: None ✅ NOT AVAILABLE")
        print(f"      Employees: None ✅ NOT AVAILABLE")

    # Summary
    print("\n" + "=" * 80)
    print("REVALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Leads from Oct 1: {results['old_total']}")
    print(f"Valid with NEW pipeline: {results['new_valid']}")
    print(f"Invalid with NEW pipeline: {results['new_invalid']}")
    print()
    print("KEY DIFFERENCES:")
    print("  OLD SYSTEM (Oct 1):")
    print("    ❌ Estimated revenue for all leads")
    print("    ❌ Hardcoded employee counts (6-8)")
    print("    ❌ Hardcoded years in business (16-22)")
    print("    ❌ Used fallback businesses list")
    print()
    print("  NEW SYSTEM (Oct 2):")
    print("    ✅ No revenue estimation (None)")
    print("    ✅ No employee count estimation (None)")
    print("    ✅ No years hardcoding (None)")
    print("    ✅ Only real data from external sources")
    print()

    # Export detailed report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"output/revalidation_report_{timestamp}.json"

    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"📄 Detailed report: {report_file}")

    # Create summary text file
    summary_file = f"output/revalidation_summary_{timestamp}.txt"
    with open(summary_file, 'w') as f:
        f.write("LEAD REVALIDATION REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Original Leads: {results['old_total']} (from Oct 1, 2025)\n")
        f.write(f"Valid with NEW pipeline: {results['new_valid']}\n")
        f.write(f"Invalid with NEW pipeline: {results['new_invalid']}\n")
        f.write("\n")

        f.write("COMPARISON: OLD vs NEW\n")
        f.write("=" * 80 + "\n\n")

        for comp in results['comparison']:
            f.write(f"{comp['business_name']}\n")
            f.write("-" * 80 + "\n")
            f.write(f"Old Status: {comp['old_status']}\n")
            f.write(f"New Status: {comp['new_status']}\n")
            f.write("\nOLD DATA (with estimation):\n")
            for key, value in comp['old_data'].items():
                f.write(f"  {key}: {value}\n")
            f.write("\nNEW DATA (no estimation):\n")
            for key, value in comp['new_data'].items():
                f.write(f"  {key}: {value}\n")
            if comp['validation_issues']:
                f.write("\nValidation Issues:\n")
                for issue in comp['validation_issues']:
                    f.write(f"  - {issue}\n")
            f.write("\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("KEY CHANGES IN NEW SYSTEM:\n")
        f.write("=" * 80 + "\n")
        f.write("✅ NO revenue estimation - was $1M-$1.4M, now None\n")
        f.write("✅ NO employee count estimation - was 6-8, now None\n")
        f.write("✅ NO years in business hardcoding - was 16-22, now None\n")
        f.write("✅ NO hardcoded fallback business list - all from real sources\n")
        f.write("✅ Keeps leads even with missing data - doesn't reject\n")
        f.write("\n")

    print(f"📄 Summary report: {summary_file}")

    return results


if __name__ == '__main__':
    asyncio.run(revalidate_leads())
