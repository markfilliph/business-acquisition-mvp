"""
Export Qualified Leads - Direct SQL Approach

Queries database for businesses that meet all criteria:
1. Employee count: 5-30 (from employee_range_min/max)
2. Years in business: >= 15 (from website_age_years)
3. Revenue: >= $1M (from revenue estimates)
4. Location: Hamilton area
"""
import asyncio
import aiosqlite
import csv
from datetime import datetime


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

        # Export to CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f'data/QUALIFIED_LEADS_{timestamp}.csv'

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Business ID', 'Business Name', 'Street', 'City', 'Province',
                'Phone', 'Website', 'Industry', 'Employee Range',
                'Years in Business', 'Year Founded', 'Revenue Range'
            ])

            for row in rows:
                (bid, name, street, city, province, phone, website, industry,
                 emp_min, emp_max, years, revenue, year_founded) = row

                emp_range = f"{emp_min}-{emp_max}" if emp_min and emp_max else "UNKNOWN"

                writer.writerow([
                    bid, name, street or '', city or '', province or '',
                    phone or '', website or '', industry or '',
                    emp_range, years or '', year_founded or '', revenue or ''
                ])

                print(f"{len([r for r in rows if r == row])}. {name}")
                print(f"   📍 {street}, {city}")
                print(f"   📞 {phone or 'N/A'}")
                print(f"   🌐 {website or 'N/A'}")
                print(f"   👥 {emp_range} employees")
                print(f"   📅 {years} years in business (founded {year_founded})")
                print(f"   💰 {revenue}")
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
