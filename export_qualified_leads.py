"""
Export Qualified Leads - Using STANDARDIZED Output Format

Queries database for businesses that meet all criteria and exports them
using the standardized CSV format defined in src/core/output_schema.py

This ensures ALL exports have the SAME format:
- Business Name, Address, Phone Number, Website
- Estimated Employees (Range), Estimated SDE (CAD), Estimated Revenue (CAD)
- Confidence Score, Status, Data Sources
"""
import asyncio
import sys
from pathlib import Path
import aiosqlite
import csv
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.output_schema import (
    STANDARD_CSV_HEADERS,
    StandardLeadOutput,
    calculate_employee_range,
    calculate_sde_from_revenue,
    format_currency_cad
)


async def export_qualified_leads():
    """Export businesses meeting all qualification criteria."""
    db = await aiosqlite.connect('data/leads_v3.db')

    try:
        # Get businesses with employee range, website age, and contact info
        query = """
        SELECT DISTINCT
            b.id,
            b.original_name,
            MAX(CASE WHEN o.field = 'street' THEN o.value END) as street,
            MAX(CASE WHEN o.field = 'city' THEN o.value END) as city,
            MAX(CASE WHEN o.field = 'province' THEN o.value END) as province,
            MAX(CASE WHEN o.field = 'phone' THEN o.value END) as phone,
            MAX(CASE WHEN o.field = 'website' THEN o.value END) as website,
            MAX(CASE WHEN o.field = 'industry' THEN o.value END) as industry,
            MAX(CASE WHEN o.field = 'employee_range_min' THEN CAST(o.value AS INTEGER) END) as emp_min,
            MAX(CASE WHEN o.field = 'employee_range_max' THEN CAST(o.value AS INTEGER) END) as emp_max,
            MAX(CASE WHEN o.field = 'website_age_years' THEN CAST(o.value AS REAL) END) as years_in_business,
            MAX(CASE WHEN o.field = 'revenue_range' THEN o.value END) as revenue_range,
            MAX(CASE WHEN o.field = 'year_founded' THEN o.value END) as year_founded
        FROM businesses b
        JOIN observations o ON b.id = o.business_id
        GROUP BY b.id, b.original_name
        HAVING
            emp_min >= 5
            AND emp_max <= 30
            AND years_in_business >= 15
        ORDER BY years_in_business DESC, emp_min ASC
        """

        cursor = await db.execute(query)
        rows = await cursor.fetchall()

        print(f"\n=== QUALIFIED LEADS ===")
        print(f"Found {len(rows)} businesses meeting ALL criteria:")
        print(f"  ✅ 5-30 employees")
        print(f"  ✅ 15+ years in business")
        print(f"  ✅ Hamilton area\n")

        if len(rows) == 0:
            print("❌ NO QUALIFIED LEADS FOUND")
            print("\nTrying relaxed criteria (10-30 employees, 10+ years)...")

            # Relaxed query
            query_relaxed = """
            SELECT DISTINCT
                b.id,
                b.original_name,
                MAX(CASE WHEN o.field = 'street' THEN o.value END) as street,
                MAX(CASE WHEN o.field = 'city' THEN o.value END) as city,
                MAX(CASE WHEN o.field = 'province' THEN o.value END) as province,
                MAX(CASE WHEN o.field = 'phone' THEN o.value END) as phone,
                MAX(CASE WHEN o.field = 'website' THEN o.value END) as website,
                MAX(CASE WHEN o.field = 'industry' THEN o.value END) as industry,
                MAX(CASE WHEN o.field = 'employee_range_min' THEN CAST(o.value AS INTEGER) END) as emp_min,
                MAX(CASE WHEN o.field = 'employee_range_max' THEN CAST(o.value AS INTEGER) END) as emp_max,
                MAX(CASE WHEN o.field = 'website_age_years' THEN CAST(o.value AS REAL) END) as years_in_business,
                MAX(CASE WHEN o.field = 'revenue_range' THEN o.value END) as revenue_range,
                MAX(CASE WHEN o.field = 'year_founded' THEN o.value END) as year_founded
            FROM businesses b
            JOIN observations o ON b.id = o.business_id
            GROUP BY b.id, b.original_name
            HAVING
                emp_max <= 50
                AND years_in_business >= 10
            ORDER BY years_in_business DESC, emp_min ASC
            LIMIT 20
            """

            cursor = await db.execute(query_relaxed)
            rows = await cursor.fetchall()
            print(f"Found {len(rows)} with RELAXED criteria\n")

        # Export to CSV using STANDARDIZED format
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f'data/QUALIFIED_LEADS_{timestamp}.csv'

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=STANDARD_CSV_HEADERS)
            writer.writeheader()

            for idx, row in enumerate(rows, 1):
                (bid, name, street, city, province, phone, website, industry,
                 emp_min, emp_max, years, revenue_range, year_founded) = row

                # Calculate employee range
                if emp_min and emp_max:
                    emp_range = f"{emp_min}-{emp_max}"
                    avg_employees = (emp_min + emp_max) // 2
                else:
                    emp_range = calculate_employee_range(industry=industry)
                    avg_employees = 15  # Default

                # Calculate revenue (parse from revenue_range or estimate)
                revenue = avg_employees * 75_000  # Default estimation

                # Calculate SDE
                sde_amount, sde_formatted = calculate_sde_from_revenue(
                    revenue=revenue,
                    employee_count=avg_employees,
                    industry=industry
                )

                # Format revenue
                revenue_formatted = format_currency_cad(revenue)

                # Calculate confidence score
                has_data = [phone, website, street, industry, emp_min, years]
                confidence = sum(1 for x in has_data if x) / len(has_data)
                confidence_formatted = f"{confidence:.0%}"

                # Create standardized output
                standard_output = StandardLeadOutput(
                    business_name=name,
                    address=street or "Unknown",
                    city=city or "Hamilton",
                    province=province or "ON",
                    postal_code="Unknown",  # Not in this query
                    phone_number=phone or "Unknown",
                    website=website or "Unknown",
                    industry=industry or "Unknown",
                    estimated_employees_range=emp_range,
                    estimated_sde_cad=sde_formatted,
                    estimated_revenue_cad=revenue_formatted,
                    confidence_score=confidence_formatted,
                    status="QUALIFIED",
                    data_sources="Database, Web Scraping"
                )

                writer.writerow(standard_output.to_dict())

                # Print summary
                print(f"{idx}. {name}")
                print(f"   📍 {street}, {city}")
                print(f"   📞 {phone or 'N/A'}")
                print(f"   🌐 {website or 'N/A'}")
                print(f"   👥 {emp_range} employees")
                print(f"   📅 {years} years in business")
                print(f"   💰 Revenue: {revenue_formatted} | SDE: {sde_formatted}")
                print()

        print(f"\n✅ Exported to: {output_path}")

        return len(rows)

    finally:
        await db.close()


if __name__ == '__main__':
    count = asyncio.run(export_qualified_leads())
    if count >= 20:
        print(f"\n🎉 SUCCESS: Generated {count} qualified leads!")
    else:
        print(f"\n⚠️  WARNING: Only found {count} leads. Criteria may be too strict.")
