#!/usr/bin/env python3
"""
Export Qualified Leads from Database
Works with the existing v3 pipeline and database structure

Usage:
    python scripts/export_qualified_leads.py --target 30
    python scripts/export_qualified_leads.py --target 30 --output data/my_leads.csv
"""

import os
import sys
import argparse
import asyncio
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.exports.csv_exporter import CSVExporter
import aiosqlite


async def export_qualified_leads(db_path: str, target_count: int, output_file: str = None):
    """
    Export qualified leads from the database

    Args:
        db_path: Path to leads database
        target_count: Number of qualified leads needed
        output_file: Optional output CSV path
    """

    print(f"\n{'='*70}")
    print(f"📊 EXPORTING QUALIFIED LEADS")
    print(f"{'='*70}")
    print(f"🎯 Target:      {target_count} qualified leads")
    print(f"💾 Database:    {db_path}")
    print(f"{'='*70}\n")

    # Connect to database
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    try:
        # Count qualified leads
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM businesses WHERE status = 'QUALIFIED'"
        )
        row = await cursor.fetchone()
        qualified_count = row['count']

        print(f"✅ Found {qualified_count} qualified leads in database")

        if qualified_count < target_count:
            shortfall = target_count - qualified_count
            print(f"\n⚠️  WARNING: Only {qualified_count}/{target_count} qualified leads available")
            print(f"   Missing: {shortfall} leads")
            print(f"\n💡 Suggestions:")
            print(f"   • Run: ./generate_v3 {target_count} (to discover more leads)")
            print(f"   • Relax validation criteria")
            print(f"   • Check REVIEW_REQUIRED leads (may be manually qualifiable)")

            # Show review_required count
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM businesses WHERE status = 'REVIEW_REQUIRED'"
            )
            row = await cursor.fetchone()
            review_count = row['count']

            if review_count > 0:
                print(f"\n📋 {review_count} leads in REVIEW_REQUIRED status")
                print(f"   Consider manually reviewing these leads")

        # Generate timestamped filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'data/qualified_leads_{timestamp}.csv'

        # Export using existing CSV exporter
        print(f"\n📤 Exporting to: {output_file}")
        exporter = CSVExporter(db_path)
        stats = await exporter.export(output_file)

        print(f"\n✅ Export Complete:")
        print(f"   File: {output_file}")
        print(f"   Total businesses: {stats['total']}")
        print(f"   Qualified: {stats['qualified']}")
        print(f"   Excluded: {stats['excluded']}")
        print(f"   Review Required: {stats['review_required']}")

        # Show sample of qualified leads
        cursor = await db.execute(
            """SELECT original_name, phone, website, employee_count
               FROM businesses
               WHERE status = 'QUALIFIED'
               LIMIT 10"""
        )

        qualified_sample = await cursor.fetchall()

        if qualified_sample:
            print(f"\n📋 Sample of Qualified Leads:")
            print(f"{'='*70}")
            for idx, lead in enumerate(qualified_sample, 1):
                emp = lead['employee_count'] if lead['employee_count'] else '?'
                print(f"{idx:2d}. {lead['original_name']:<40} ({emp} employees)")

            if qualified_count > 10:
                print(f"... and {qualified_count - 10} more")

        print(f"\n{'='*70}")
        print(f"✅ SUCCESS! {stats['qualified']} qualified leads exported")
        print(f"📂 File: {output_file}")
        print(f"{'='*70}\n")

        return output_file

    finally:
        await db.close()


def main():
    """Command-line interface"""

    parser = argparse.ArgumentParser(
        description='Export qualified leads from v3 database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all qualified leads
  python scripts/export_qualified_leads.py --target 30

  # Export to specific file
  python scripts/export_qualified_leads.py --target 30 --output data/my_leads.csv

  # Use different database
  python scripts/export_qualified_leads.py --db data/custom.db --target 40
        """
    )

    parser.add_argument(
        '--target',
        type=int,
        default=30,
        help='Number of qualified leads needed (default: 30)'
    )

    parser.add_argument(
        '--db',
        type=str,
        default='data/leads_v3.db',
        help='Database path (default: data/leads_v3.db)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output CSV file (default: data/qualified_leads_TIMESTAMP.csv)'
    )

    args = parser.parse_args()

    # Check if database exists
    if not os.path.exists(args.db):
        print(f"❌ Error: Database not found: {args.db}")
        print(f"\n💡 Run lead generation first:")
        print(f"   ./generate_v3 {args.target}")
        sys.exit(1)

    # Run export
    output_file = asyncio.run(export_qualified_leads(
        db_path=args.db,
        target_count=args.target,
        output_file=args.output
    ))

    if output_file:
        print(f"🚀 Next steps:")
        print(f"   1. Review: {output_file}")
        print(f"   2. Import to CRM or begin outreach")
        print(f"   3. Track responses\n")


if __name__ == "__main__":
    main()
