#!/usr/bin/env python3
"""
Export Qualified Leads Report with Full Details
"""
import asyncio
import aiosqlite
from datetime import datetime


async def export_report():
    """Generate detailed qualified leads report."""

    db_path = 'data/leads_v2.db'

    print(f"\n{'='*100}")
    print(f"📋 QUALIFIED LEADS - DETAILED REPORT")
    print(f"{'='*100}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*100}\n")

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    try:
        # Get qualified businesses
        cursor = await db.execute("""
            SELECT
                id,
                original_name,
                street,
                city,
                phone,
                website
            FROM businesses
            WHERE status = 'QUALIFIED'
            ORDER BY id DESC
            LIMIT 20
        """)

        businesses = await cursor.fetchall()

        if not businesses:
            print("❌ No qualified leads found.\n")
            return

        print(f"✅ Found {len(businesses)} Qualified Leads\n")

        for idx, biz in enumerate(businesses, 1):
            # Get observations for this business
            obs_cursor = await db.execute("""
                SELECT field, value, confidence
                FROM observations
                WHERE business_id = ?
            """, (biz['id'],))

            observations = await obs_cursor.fetchall()
            obs_dict = {}
            for obs in observations:
                if obs['field'] not in obs_dict or obs['confidence'] > obs_dict[obs['field']][1]:
                    obs_dict[obs['field']] = (obs['value'], obs['confidence'])

            # Print business details
            print(f"{idx}. {biz['original_name']}")
            print(f"   {'─'*96}")
            print(f"   📍 Address:          {biz['street']}, {biz['city']}")
            print(f"   🌐 Website:          {biz['website'] or 'N/A'}")
            print(f"   📞 Phone:            {biz['phone'] or 'N/A'}")

            # Employees
            employees = obs_dict.get('employee_count', ('N/A', 0))[0]
            print(f"   👥 Employees:        {employees}")

            # Revenue
            rev_min = obs_dict.get('revenue_estimate_min', ('N/A', 0))[0]
            rev_max = obs_dict.get('revenue_estimate_max', ('N/A', 0))[0]
            if rev_min != 'N/A' and rev_max != 'N/A':
                try:
                    print(f"   💰 Revenue:          ${float(rev_min):,.0f} - ${float(rev_max):,.0f}")
                except:
                    print(f"   💰 Revenue:          {rev_min} - {rev_max}")
            else:
                print(f"   💰 Revenue:          Not available")

            # Years in business
            years = obs_dict.get('years_in_business', ('N/A', 0))[0]
            founded = obs_dict.get('year_founded', ('N/A', 0))[0]
            if founded and founded != 'N/A':
                print(f"   📅 Years in Bus:     {years} (founded {founded})")
            else:
                print(f"   📅 Years in Bus:     {years}")

            print()

        print(f"{'='*100}\n")

    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(export_report())
