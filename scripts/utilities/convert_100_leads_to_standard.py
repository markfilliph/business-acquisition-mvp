#!/usr/bin/env python3
"""
Convert the 100 leads from Nov 16, 2025 to standardized output format.

Reads: data/outputs/NEW_100_LEADS_BY_INDUSTRY_20251116_201005.csv
Writes: data/outputs/100_LEADS_STANDARDIZED_FORMAT.csv
"""
import sys
import csv
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.output_schema import (
    STANDARD_CSV_HEADERS,
    StandardLeadOutput,
    calculate_employee_range,
    calculate_sde_from_revenue,
    format_currency_cad
)


def estimate_employees_from_reviews(review_count, industry):
    """Estimate employee count based on review count and industry."""
    if not review_count or review_count == 0:
        # No reviews - likely very small
        return 5

    # Review count correlation with size
    if review_count < 10:
        return 5  # Very small
    elif review_count < 30:
        return 12  # Small
    elif review_count < 100:
        return 20  # Medium-small
    elif review_count < 300:
        return 30  # Medium
    else:
        return 40  # Larger (but we're targeting SMBs)


def convert_leads_to_standard_format():
    """Convert existing 100 leads to standardized format."""

    input_path = Path('data/outputs/NEW_100_LEADS_BY_INDUSTRY_20251116_201005.csv')
    output_path = Path('data/outputs/100_LEADS_STANDARDIZED_FORMAT.csv')

    print("🔄 CONVERTING 100 LEADS TO STANDARDIZED FORMAT")
    print("=" * 60)
    print(f"📥 Input:  {input_path}")
    print(f"📤 Output: {output_path}")
    print()

    if not input_path.exists():
        print(f"❌ ERROR: Input file not found: {input_path}")
        return False

    # Read existing leads
    leads = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)

    print(f"✅ Loaded {len(leads)} leads")
    print()

    # Convert to standardized format
    converted_count = 0
    industry_counts = {}

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=STANDARD_CSV_HEADERS)
        writer.writeheader()

        for idx, lead in enumerate(leads, 1):
            # Extract fields
            business_name = lead['Business Name']
            address = lead['Street Address']
            city = lead['City']
            province = lead['Province'] or 'ON'
            postal_code = lead['Postal Code'] or 'Unknown'
            phone = lead['Phone']
            website = lead['Website']
            industry = lead['Industry']
            data_source = lead['Data Source']
            review_count = int(lead['Review Count']) if lead['Review Count'] else 0
            warnings = lead['Warnings']
            priority = lead['Priority']

            # Count by industry
            industry_counts[industry] = industry_counts.get(industry, 0) + 1

            # Estimate employee count from review count
            estimated_employees = estimate_employees_from_reviews(review_count, industry)

            # Calculate employee range
            employee_range = calculate_employee_range(
                employee_count=estimated_employees,
                industry=industry
            )

            # Calculate revenue (default $75K per employee)
            revenue = estimated_employees * 75_000

            # Calculate SDE
            sde_amount, sde_formatted = calculate_sde_from_revenue(
                revenue=revenue,
                employee_count=estimated_employees,
                industry=industry
            )

            # Format revenue
            revenue_formatted = format_currency_cad(revenue)

            # Calculate confidence score based on data completeness
            has_data = [
                phone,
                website,
                address,
                postal_code if postal_code != 'Unknown' else None,
                True,  # Have industry
                True if review_count > 0 else None  # Have reviews
            ]
            confidence = sum(1 for x in has_data if x) / len(has_data)

            # Adjust confidence based on warnings
            if warnings and warnings != 'None':
                confidence *= 0.85  # Reduce confidence if has warnings

            confidence_formatted = f"{confidence:.0%}"

            # Determine status
            if priority == 'HIGH' and (not warnings or warnings == 'None'):
                status = 'QUALIFIED'
            elif priority == 'MEDIUM':
                status = 'REVIEW_REQUIRED'
            else:
                status = 'DISCOVERED'

            # Create standardized output
            standard_output = StandardLeadOutput(
                business_name=business_name,
                address=address or 'Unknown',
                city=city or 'Hamilton',
                province=province,
                postal_code=postal_code,
                phone_number=phone or 'Unknown',
                website=website or 'Unknown',
                industry=industry,
                estimated_employees_range=employee_range,
                estimated_sde_cad=sde_formatted,
                estimated_revenue_cad=revenue_formatted,
                confidence_score=confidence_formatted,
                status=status,
                data_sources=data_source
            )

            writer.writerow(standard_output.to_dict())
            converted_count += 1

            # Print progress every 20 leads
            if idx % 20 == 0:
                print(f"✅ Converted {idx}/{len(leads)} leads...")

    print()
    print("=" * 60)
    print("✅ CONVERSION COMPLETED")
    print(f"📊 Total leads converted: {converted_count}")
    print()
    print("📈 Industry Distribution:")
    for industry, count in sorted(industry_counts.items()):
        print(f"   {industry:25s}: {count:2d} leads")
    print()
    print(f"💾 Output saved to: {output_path}")
    print()
    print("📋 New Format Includes:")
    print("   ✅ Business Name, Address, Phone, Website")
    print("   ✅ Estimated Employees (Range)")
    print("   ✅ Estimated SDE in CAD")
    print("   ✅ Estimated Revenue in CAD")
    print("   ✅ Confidence Score")
    print("   ✅ Status (QUALIFIED/REVIEW_REQUIRED)")
    print()

    # Show sample of first 3 leads
    print("📋 Sample Leads (first 3):")
    print("-" * 60)

    with open(output_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            if i > 3:
                break
            print(f"\n{i}. {row['Business Name']}")
            print(f"   Address: {row['Address']}, {row['City']}")
            print(f"   Phone: {row['Phone Number']}")
            print(f"   Website: {row['Website']}")
            print(f"   Industry: {row['Industry']}")
            print(f"   Employees: {row['Estimated Employees (Range)']}")
            print(f"   Revenue: {row['Estimated Revenue (CAD)']} | SDE: {row['Estimated SDE (CAD)']}")
            print(f"   Confidence: {row['Confidence Score']} | Status: {row['Status']}")

    return True


if __name__ == "__main__":
    success = convert_leads_to_standard_format()

    if success:
        print("\n" + "=" * 60)
        print("🎉 SUCCESS! Your 100 leads now have the standardized format.")
        print("=" * 60)
        print("\nThe output file includes ALL required fields:")
        print("• Business Name, Address, Phone, Website")
        print("• Estimated Employees (Range)")
        print("• Estimated SDE (CAD) - Seller's Discretionary Earnings")
        print("• Estimated Revenue (CAD)")
        print("• Confidence Score")
        print()
    else:
        print("\n❌ Conversion failed")
        sys.exit(1)
